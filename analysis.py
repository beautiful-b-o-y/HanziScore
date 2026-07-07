import math
from statistics import mean, pvariance


PAUSE_THRESHOLD_MS = 700
LONG_STROKE_DURATION_MS = 1400
LONG_PAUSE_MS = PAUSE_THRESHOLD_MS
LOW_SPEED_PX_PER_SECOND = 70
HIGH_SPEED_PX_PER_SECOND = 420
FAST_START_PX_PER_SECOND = 360
SLOW_END_PX_PER_SECOND = 80
SPEED_VARIANCE_THRESHOLD = 18000
SHARP_TURN_DEGREES = 65
TURN_SEGMENT_DEGREES = 35
RESAMPLED_POINT_COUNT = 32


def rounded(value: float, digits: int = 2) -> float:
    return round(value, digits) if math.isfinite(value) else 0


def distance(a: dict, b: dict) -> float:
    return math.hypot(b["x"] - a["x"], b["y"] - a["y"])


def point_at_fraction(a: dict, b: dict, fraction: float) -> dict:
    return {
        "x": a["x"] + (b["x"] - a["x"]) * fraction,
        "y": a["y"] + (b["y"] - a["y"]) * fraction,
        "t": a["t"] + (b["t"] - a["t"]) * fraction,
        "pressure": a["pressure"] + (b["pressure"] - a["pressure"]) * fraction,
    }


def calculate_path_length(points: list[dict]) -> float:
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def calculate_bbox(points: list[dict]) -> dict:
    if not points:
        return {"minX": 0, "minY": 0, "maxX": 0, "maxY": 0, "width": 0, "height": 0}

    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]
    min_x = min(xs)
    min_y = min(ys)
    max_x = max(xs)
    max_y = max(ys)
    return {
        "minX": rounded(min_x),
        "minY": rounded(min_y),
        "maxX": rounded(max_x),
        "maxY": rounded(max_y),
        "width": rounded(max_x - min_x),
        "height": rounded(max_y - min_y),
    }


def calculate_centroid(points: list[dict]) -> dict:
    if not points:
        return {"x": 0, "y": 0}
    return {
        "x": rounded(mean(point["x"] for point in points)),
        "y": rounded(mean(point["y"] for point in points)),
    }


def normalize_points(points: list[dict], bbox: dict) -> list[dict]:
    width = bbox["width"] or 1
    height = bbox["height"] or 1
    start_t = points[0]["t"] if points else 0
    end_t = points[-1]["t"] if points else start_t
    duration = max(1, end_t - start_t)

    return [
        {
            "x": rounded((point["x"] - bbox["minX"]) / width, 4),
            "y": rounded((point["y"] - bbox["minY"]) / height, 4),
            "t": rounded((point["t"] - start_t) / duration, 4),
            "pressure": rounded(point["pressure"], 3),
        }
        for point in points
    ]


def resample_points(points: list[dict], target_count: int = RESAMPLED_POINT_COUNT) -> list[dict]:
    if len(points) <= 1:
        return [format_point(point) for point in points]

    path_length = calculate_path_length(points)
    if path_length == 0:
        return [format_point(points[0]), format_point(points[-1])]

    count = min(target_count, max(2, len(points)))
    step = path_length / (count - 1)
    resampled = [points[0]]
    segment_index = 1
    walked = 0.0

    for target_index in range(1, count - 1):
        target_distance = step * target_index
        while segment_index < len(points):
            previous = points[segment_index - 1]
            current = points[segment_index]
            segment_length = distance(previous, current)
            if walked + segment_length >= target_distance:
                fraction = 0 if segment_length == 0 else (target_distance - walked) / segment_length
                resampled.append(point_at_fraction(previous, current, fraction))
                break
            walked += segment_length
            segment_index += 1

    resampled.append(points[-1])
    return [format_point(point) for point in resampled]


def format_point(point: dict) -> dict:
    return {
        "x": rounded(point["x"]),
        "y": rounded(point["y"]),
        "t": rounded(point["t"]),
        "pressure": rounded(point["pressure"], 3),
    }


def calculate_angle_profile(points: list[dict]) -> list[dict]:
    profile = []
    for index in range(1, len(points)):
        previous = points[index - 1]
        current = points[index]
        angle = math.degrees(math.atan2(current["y"] - previous["y"], current["x"] - previous["x"]))
        profile.append({"segmentIndex": index - 1, "angleDeg": rounded(angle)})
    return profile


def angle_delta(previous_angle: float, current_angle: float) -> float:
    delta = current_angle - previous_angle
    while delta > 180:
        delta -= 360
    while delta < -180:
        delta += 360
    return delta


def calculate_curvature_profile(angle_profile: list[dict], points: list[dict]) -> list[dict]:
    profile = []
    for index in range(1, len(angle_profile)):
        delta = angle_delta(angle_profile[index - 1]["angleDeg"], angle_profile[index]["angleDeg"])
        point = points[index] if index < len(points) else points[-1]
        profile.append(
            {
                "pointIndex": index,
                "t": rounded(point["t"]),
                "deltaAngleDeg": rounded(delta),
            }
        )
    return profile


def find_turning_points(curvature_profile: list[dict], points: list[dict]) -> list[dict]:
    turns = []
    for item in curvature_profile:
        if abs(item["deltaAngleDeg"]) >= TURN_SEGMENT_DEGREES:
            point = points[item["pointIndex"]]
            turns.append(
                {
                    "pointIndex": item["pointIndex"],
                    "x": rounded(point["x"]),
                    "y": rounded(point["y"]),
                    "t": rounded(point["t"]),
                    "deltaAngleDeg": item["deltaAngleDeg"],
                }
            )
    return turns


def calculate_speed_profile(points: list[dict]) -> list[dict]:
    profile = []
    for index in range(1, len(points)):
        previous = points[index - 1]
        current = points[index]
        delta_ms = max(0, current["t"] - previous["t"])
        length = distance(previous, current)
        speed = length / (delta_ms / 1000) if delta_ms > 0 else 0
        profile.append(
            {
                "segmentIndex": index - 1,
                "startT": rounded(previous["t"]),
                "endT": rounded(current["t"]),
                "durationMs": rounded(delta_ms),
                "lengthPx": rounded(length),
                "speedPxPerSecond": rounded(speed),
            }
        )
    return profile


def calculate_acceleration_profile(speed_profile: list[dict]) -> list[dict]:
    profile = []
    for index in range(1, len(speed_profile)):
        previous = speed_profile[index - 1]
        current = speed_profile[index]
        delta_ms = max(0, current["endT"] - previous["endT"])
        acceleration = (
            (current["speedPxPerSecond"] - previous["speedPxPerSecond"]) / (delta_ms / 1000)
            if delta_ms > 0
            else 0
        )
        profile.append(
            {
                "segmentIndex": current["segmentIndex"],
                "t": current["endT"],
                "accelerationPxPerSecond2": rounded(acceleration),
            }
        )
    return profile


def calculate_width_profile(points: list[dict], pointer_type: str, speed_profile: list[dict]) -> dict:
    if pointer_type == "mouse":
        speeds = [item["speedPxPerSecond"] for item in speed_profile]
        max_speed = max(speeds) if speeds else 0
        widths = []
        for item in speed_profile:
            speed_ratio = item["speedPxPerSecond"] / max_speed if max_speed > 0 else 0
            widths.append(
                {
                    "segmentIndex": item["segmentIndex"],
                    "widthPx": rounded(4.8 - speed_ratio * 2.2),
                }
            )
        return {
            "width_profile": widths,
            "width_profile_source": "simulated_from_speed",
            "note": "Mouse input has no reliable pressure width; this proxy is derived from speed.",
        }

    widths = [
        {
            "pointIndex": index,
            "widthPx": rounded(2.4 + max(0, min(1, point["pressure"])) * 3.2),
        }
        for index, point in enumerate(points)
    ]
    return {
        "width_profile": widths,
        "width_profile_source": "pointer_pressure",
        "note": "Width proxy is derived from Pointer Events pressure values.",
    }


def detect_segments(points: list[dict], curvature_profile: list[dict]) -> list[dict]:
    if not points:
        return []

    turn_indexes = {
        item["pointIndex"]
        for item in curvature_profile
        if abs(item["deltaAngleDeg"]) >= TURN_SEGMENT_DEGREES
    }
    segments = [{"type": "start", "pointIndex": 0, "t": rounded(points[0]["t"])}]
    for index in range(1, len(points)):
        segment_type = "turn" if index in turn_indexes else "move"
        segments.append(
            {
                "type": segment_type,
                "fromPointIndex": index - 1,
                "toPointIndex": index,
                "startT": rounded(points[index - 1]["t"]),
                "endT": rounded(points[index]["t"]),
            }
        )
    segments.append({"type": "end", "pointIndex": len(points) - 1, "t": rounded(points[-1]["t"])})
    return segments


def build_data_events(
    duration_ms: float,
    mean_speed: float,
    max_speed: float,
    speed_variance: float,
    pause_before_ms: float,
    pause_after_ms: float,
    speed_profile: list[dict],
    turning_points: list[dict],
) -> list[dict]:
    events = []

    def add(event_type: str, value: float, threshold: float, unit: str) -> None:
        events.append(
            {
                "type": event_type,
                "value": rounded(value),
                "threshold": rounded(threshold),
                "unit": unit,
            }
        )

    if mean_speed and mean_speed <= LOW_SPEED_PX_PER_SECOND:
        add("low_speed_stroke", mean_speed, LOW_SPEED_PX_PER_SECOND, "px/s")
    if max_speed >= HIGH_SPEED_PX_PER_SECOND:
        add("high_speed_stroke", max_speed, HIGH_SPEED_PX_PER_SECOND, "px/s")
    if duration_ms >= LONG_STROKE_DURATION_MS:
        add("long_duration_stroke", duration_ms, LONG_STROKE_DURATION_MS, "ms")
    if pause_before_ms >= LONG_PAUSE_MS:
        add("long_pause_before", pause_before_ms, LONG_PAUSE_MS, "ms")
    if pause_after_ms >= LONG_PAUSE_MS:
        add("long_pause_after", pause_after_ms, LONG_PAUSE_MS, "ms")
    if speed_variance >= SPEED_VARIANCE_THRESHOLD:
        add("speed_variation", speed_variance, SPEED_VARIANCE_THRESHOLD, "(px/s)^2")
    if speed_profile and speed_profile[0]["speedPxPerSecond"] >= FAST_START_PX_PER_SECOND:
        add("fast_start", speed_profile[0]["speedPxPerSecond"], FAST_START_PX_PER_SECOND, "px/s")
    if speed_profile and speed_profile[-1]["speedPxPerSecond"] <= SLOW_END_PX_PER_SECOND:
        add("slow_end", speed_profile[-1]["speedPxPerSecond"], SLOW_END_PX_PER_SECOND, "px/s")

    sharp_turns = [
        turn for turn in turning_points if abs(turn["deltaAngleDeg"]) >= SHARP_TURN_DEGREES
    ]
    if sharp_turns:
        add("sharp_turn", max(abs(turn["deltaAngleDeg"]) for turn in sharp_turns), SHARP_TURN_DEGREES, "deg")

    return events


def analyze_stroke(stroke: dict, index: int, strokes: list[dict]) -> dict:
    points = stroke["points"]
    previous_points = strokes[index - 1]["points"] if index > 0 else []
    next_points = strokes[index + 1]["points"] if index + 1 < len(strokes) else []
    start_point = points[0]
    end_point = points[-1]
    duration_ms = max(0, end_point["t"] - start_point["t"])
    path_length = calculate_path_length(points)
    bbox = calculate_bbox(points)
    angle_profile = calculate_angle_profile(points)
    curvature_profile = calculate_curvature_profile(angle_profile, points)
    turning_points = find_turning_points(curvature_profile, points)
    speed_profile = calculate_speed_profile(points)
    acceleration_profile = calculate_acceleration_profile(speed_profile)
    speeds = [item["speedPxPerSecond"] for item in speed_profile]
    mean_speed = mean(speeds) if speeds else 0
    max_speed = max(speeds) if speeds else 0
    speed_variance = pvariance(speeds) if len(speeds) > 1 else 0
    pause_before_ms = (
        max(0, start_point["t"] - previous_points[-1]["t"]) if previous_points else 0
    )
    pause_after_ms = max(0, next_points[0]["t"] - end_point["t"]) if next_points else 0
    data_events = build_data_events(
        duration_ms,
        mean_speed,
        max_speed,
        speed_variance,
        pause_before_ms,
        pause_after_ms,
        speed_profile,
        turning_points,
    )

    return {
        "id": stroke["id"],
        "index": index + 1,
        "pointerType": stroke.get("pointerType", "unknown"),
        "raw_points": [format_point(point) for point in points],
        "geometry": {
            "normalized_points": normalize_points(points, bbox),
            "resampled_points": resample_points(points),
            "bbox": bbox,
            "path_length": rounded(path_length),
            "centroid": calculate_centroid(points),
            "start_point": format_point(start_point),
            "end_point": format_point(end_point),
            "angle_profile": angle_profile,
            "curvature_profile": curvature_profile,
            "turning_points": turning_points,
        },
        "dynamics": {
            "speed_profile": speed_profile,
            "acceleration_profile": acceleration_profile,
            "mean_speed": rounded(mean_speed),
            "max_speed": rounded(max_speed),
            "speed_variance": rounded(speed_variance),
            "pause_before_ms": rounded(pause_before_ms),
            "pause_after_ms": rounded(pause_after_ms),
            "duration_ms": rounded(duration_ms),
        },
        "segments": detect_segments(points, curvature_profile),
        "visual_proxy": calculate_width_profile(points, stroke.get("pointerType", "unknown"), speed_profile),
        "labels": data_events,
    }


def calculate_metrics(strokes: list[dict], pause_threshold_ms: int = PAUSE_THRESHOLD_MS) -> dict:
    all_points = [
        {"strokeId": stroke["id"], **point}
        for stroke in strokes
        for point in stroke["points"]
    ]
    point_count = len(all_points)

    if not all_points:
        return {
            "strokeCount": 0,
            "pointCount": 0,
            "durationMs": 0,
            "durationSeconds": 0,
            "pathLengthPx": 0,
            "averageSpeedPxPerSecond": 0,
            "pauseThresholdMs": pause_threshold_ms,
            "pauseCount": 0,
            "pauses": [],
        }

    start_t = min(point["t"] for point in all_points)
    end_t = max(point["t"] for point in all_points)
    duration_ms = max(0, end_t - start_t)
    path_length = sum(calculate_path_length(stroke["points"]) for stroke in strokes)

    pauses = []
    sorted_points = sorted(all_points, key=lambda point: point["t"])
    for index in range(1, len(sorted_points)):
        previous = sorted_points[index - 1]
        current = sorted_points[index]
        gap = current["t"] - previous["t"]
        if gap >= pause_threshold_ms:
            pauses.append(
                {
                    "startT": rounded(previous["t"]),
                    "endT": rounded(current["t"]),
                    "durationMs": rounded(gap),
                    "fromStrokeId": previous["strokeId"],
                    "toStrokeId": current["strokeId"],
                }
            )

    duration_seconds = duration_ms / 1000
    average_speed = path_length / duration_seconds if duration_seconds > 0 else 0

    return {
        "strokeCount": len(strokes),
        "pointCount": point_count,
        "durationMs": rounded(duration_ms),
        "durationSeconds": rounded(duration_seconds, 3),
        "pathLengthPx": rounded(path_length),
        "averageSpeedPxPerSecond": rounded(average_speed),
        "pauseThresholdMs": pause_threshold_ms,
        "pauseCount": len(pauses),
        "pauses": pauses,
    }


def build_event_summary(stroke_events: list[dict]) -> dict:
    data_events = []
    for stroke in stroke_events:
        for event in stroke["labels"]:
            data_events.append({"strokeId": stroke["id"], "strokeIndex": stroke["index"], **event})
    return {
        "data_event_count": len(data_events),
        "data_events": data_events,
    }


def build_analysis(strokes: list[dict], pause_threshold_ms: int = PAUSE_THRESHOLD_MS) -> dict:
    stroke_events = [analyze_stroke(stroke, index, strokes) for index, stroke in enumerate(strokes)]
    return {
        "metrics": calculate_metrics(strokes, pause_threshold_ms),
        "strokes": stroke_events,
        "event_summary": build_event_summary(stroke_events),
    }
