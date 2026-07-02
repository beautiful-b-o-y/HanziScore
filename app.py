import os
import json
import math
import uuid
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SAMPLES_DIR = DATA_DIR / "samples"
ANALYSES_DIR = DATA_DIR / "analyses"
AI_CACHE_PATH = DATA_DIR / "ai_cache.json"
PAUSE_THRESHOLD_MS = 700
RECORD_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z-[a-f0-9]{8}$")


def ensure_data_paths() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    SAMPLES_DIR.mkdir(exist_ok=True)
    ANALYSES_DIR.mkdir(exist_ok=True)
    if not AI_CACHE_PATH.exists():
        AI_CACHE_PATH.write_text("{}\n", encoding="utf-8")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_record_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return f"{timestamp}-{suffix}"


def write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def is_valid_record_id(record_id: str) -> bool:
    return bool(RECORD_ID_PATTERN.fullmatch(record_id))


def summarize_analysis(analysis: dict) -> dict:
    metrics = analysis.get("metrics") if isinstance(analysis.get("metrics"), dict) else {}
    return {
        "id": analysis.get("id", ""),
        "createdAt": analysis.get("createdAt", ""),
        "targetCharacter": analysis.get("targetCharacter", ""),
        "strokeCount": metrics.get("strokeCount", 0),
        "pointCount": metrics.get("pointCount", 0),
        "durationMs": metrics.get("durationMs", 0),
    }


def list_saved_records() -> list[dict]:
    records = []
    for path in ANALYSES_DIR.glob("*.json"):
        try:
            analysis = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue

        record_id = str(analysis.get("id") or path.stem)
        if not is_valid_record_id(record_id):
            continue

        summary = summarize_analysis(analysis)
        summary["id"] = record_id
        records.append(summary)

    return sorted(records, key=lambda record: record["id"], reverse=True)


def validate_capture_payload(payload: object) -> tuple[dict | None, tuple[dict, int] | None]:
    if not isinstance(payload, dict):
        return None, ({"error": "Expected a JSON object."}, 400)

    strokes = payload.get("strokes")
    if not isinstance(strokes, list):
        return None, ({"error": "Expected strokes to be a list."}, 400)
    if not strokes:
        return None, ({"error": "At least one stroke is required."}, 400)

    normalized_strokes = []
    for stroke_index, stroke in enumerate(strokes, start=1):
        if not isinstance(stroke, dict):
            return None, ({"error": "Each stroke must be an object."}, 400)

        points = stroke.get("points")
        if not isinstance(points, list):
            return None, ({"error": "Each stroke must include a points list."}, 400)
        if not points:
            return None, ({"error": "Each stroke must include at least one point."}, 400)

        normalized_points = []
        for point in points:
            if not isinstance(point, dict):
                return None, ({"error": "Each point must be an object."}, 400)

            missing_keys = {"x", "y", "t", "pressure"} - set(point)
            if missing_keys:
                return (
                    None,
                    (
                        {
                            "error": "Each point must include x, y, t, and pressure.",
                            "missing": sorted(missing_keys),
                        },
                        400,
                    ),
                )

            try:
                normalized_point = {
                    "x": float(point["x"]),
                    "y": float(point["y"]),
                    "t": float(point["t"]),
                    "pressure": float(point["pressure"]),
                }
            except (TypeError, ValueError):
                return None, ({"error": "Point values must be numeric."}, 400)

            if not all(math.isfinite(value) for value in normalized_point.values()):
                return None, ({"error": "Point values must be finite numbers."}, 400)

            normalized_points.append(normalized_point)

        normalized_strokes.append(
            {
                "id": str(stroke.get("id") or f"stroke-{stroke_index}"),
                "pointerType": str(stroke.get("pointerType") or "unknown"),
                "points": normalized_points,
            }
        )

    normalized = dict(payload)
    normalized["targetCharacter"] = str(payload.get("targetCharacter") or "")
    normalized["strokes"] = normalized_strokes
    return normalized, None


def calculate_metrics(strokes: list[dict]) -> dict:
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
            "pauseThresholdMs": PAUSE_THRESHOLD_MS,
            "pauseCount": 0,
            "pauses": [],
        }

    start_t = min(point["t"] for point in all_points)
    end_t = max(point["t"] for point in all_points)
    duration_ms = max(0, end_t - start_t)

    path_length = 0.0
    for stroke in strokes:
        points = stroke["points"]
        for index in range(1, len(points)):
            previous = points[index - 1]
            current = points[index]
            path_length += math.hypot(current["x"] - previous["x"], current["y"] - previous["y"])

    pauses = []
    sorted_points = sorted(all_points, key=lambda point: point["t"])
    for index in range(1, len(sorted_points)):
        previous = sorted_points[index - 1]
        current = sorted_points[index]
        gap = current["t"] - previous["t"]
        if gap >= PAUSE_THRESHOLD_MS:
            pauses.append(
                {
                    "startT": round(previous["t"], 2),
                    "endT": round(current["t"], 2),
                    "durationMs": round(gap, 2),
                    "fromStrokeId": previous["strokeId"],
                    "toStrokeId": current["strokeId"],
                }
            )

    duration_seconds = duration_ms / 1000
    average_speed = path_length / duration_seconds if duration_seconds > 0 else 0

    return {
        "strokeCount": len(strokes),
        "pointCount": point_count,
        "durationMs": round(duration_ms, 2),
        "durationSeconds": round(duration_seconds, 3),
        "pathLengthPx": round(path_length, 2),
        "averageSpeedPxPerSecond": round(average_speed, 2),
        "pauseThresholdMs": PAUSE_THRESHOLD_MS,
        "pauseCount": len(pauses),
        "pauses": pauses,
    }


def create_app() -> Flask:
    ensure_data_paths()
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify(
            {
                "app": "HanziScore",
                "phase": 4,
                "status": "ok",
                "storage": "json-files",
            }
        )

    @app.get("/api/records")
    def records():
        return jsonify({"records": list_saved_records()})

    @app.get("/api/records/<record_id>")
    def record_detail(record_id: str):
        if not is_valid_record_id(record_id):
            return jsonify({"error": "Invalid record id."}), 400

        sample_path = SAMPLES_DIR / f"{record_id}.json"
        analysis_path = ANALYSES_DIR / f"{record_id}.json"
        if not sample_path.exists() or not analysis_path.exists():
            return jsonify({"error": "Record not found."}), 404

        try:
            sample = read_json(sample_path)
            analysis = read_json(analysis_path)
        except (OSError, json.JSONDecodeError):
            return jsonify({"error": "Record could not be read."}), 500

        return jsonify(
            {
                "id": record_id,
                "sample": sample,
                "analysis": analysis,
            }
        )

    @app.post("/api/captures")
    def receive_capture():
        payload, error = validate_capture_payload(request.get_json(silent=True))
        if error:
            body, status_code = error
            return jsonify(body), status_code

        record_id = make_record_id()
        received_at = now_utc_iso()
        metrics = calculate_metrics(payload["strokes"])
        sample_path = SAMPLES_DIR / f"{record_id}.json"
        analysis_path = ANALYSES_DIR / f"{record_id}.json"

        sample = {
            "id": record_id,
            "receivedAt": received_at,
            "payload": payload,
        }
        analysis = {
            "id": record_id,
            "sampleFile": f"data/samples/{record_id}.json",
            "createdAt": received_at,
            "targetCharacter": payload.get("targetCharacter", ""),
            "metrics": metrics,
        }

        write_json(sample_path, sample)
        write_json(analysis_path, analysis)

        return jsonify(
            {
                "phase": 3,
                "status": "stored",
                "stored": True,
                "recordId": record_id,
                "sampleFile": f"data/samples/{record_id}.json",
                "analysisFile": f"data/analyses/{record_id}.json",
                "targetCharacter": payload.get("targetCharacter", ""),
                "metrics": metrics,
            }
        )

    return app


if __name__ == "__main__":
    debug_enabled = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    create_app().run(host="127.0.0.1", port=5000, debug=debug_enabled)
