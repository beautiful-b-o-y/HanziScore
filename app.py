import os
import json
import math
import uuid
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import analysis as writing_analysis


def read_float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def read_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SAMPLES_DIR = DATA_DIR / "samples"
ANALYSES_DIR = DATA_DIR / "analyses"
AI_CACHE_PATH = DATA_DIR / "ai_cache.json"
PAUSE_THRESHOLD_MS = writing_analysis.PAUSE_THRESHOLD_MS
RECORD_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z-[a-f0-9]{8}$")
ZHIPU_MODEL = os.environ.get("ZHIPU_MODEL", "glm-5.2")
ZHIPU_CHAT_COMPLETIONS_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHIPU_TIMEOUT_SECONDS = read_float_env("ZHIPU_TIMEOUT_SECONDS", 60)
ZHIPU_MAX_RETRIES = max(0, read_int_env("ZHIPU_MAX_RETRIES", 2))
EXPLANATION_KEYS = (
    "summary",
    "evidence",
    "rhythm_interpretation",
    "rhythm",
    "pauses",
    "candidate_labels",
    "uncertainty",
    "observation_questions",
    "caution",
)
EXPLANATION_SOURCE_LABELS = {
    "cache": "本地 cache",
    "zhipu": "智谱",
    "local_rules": "本地规则",
}
EXPLANATION_PROTOCOL_VERSION = 2


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


def read_ai_cache() -> dict:
    try:
        cache = read_json(AI_CACHE_PATH)
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "records": {}}

    if "records" not in cache:
        cache = {"version": 1, "records": cache if isinstance(cache, dict) else {}}

    if not isinstance(cache.get("records"), dict):
        cache["records"] = {}

    return cache


def write_ai_cache(cache: dict) -> None:
    write_json(AI_CACHE_PATH, cache)


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


def get_record_files(record_id: str) -> tuple[dict | None, dict | None, tuple[dict, int] | None]:
    if not is_valid_record_id(record_id):
        return None, None, ({"error": "Invalid record id."}, 400)

    sample_path = SAMPLES_DIR / f"{record_id}.json"
    analysis_path = ANALYSES_DIR / f"{record_id}.json"
    if not sample_path.exists() or not analysis_path.exists():
        return None, None, ({"error": "Record not found."}, 404)

    try:
        sample = read_json(sample_path)
        analysis = read_json(analysis_path)
    except (OSError, json.JSONDecodeError):
        return None, None, ({"error": "Record could not be read."}, 500)

    return sample, analysis, None


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
    return writing_analysis.calculate_metrics(strokes, PAUSE_THRESHOLD_MS)


def compact_metrics_for_prompt(analysis: dict) -> dict:
    metrics = analysis.get("metrics") if isinstance(analysis.get("metrics"), dict) else {}
    event_summary = analysis.get("event_summary") if isinstance(analysis.get("event_summary"), dict) else {}
    data_events = event_summary.get("data_events") if isinstance(event_summary.get("data_events"), list) else []
    return {
        "strokeCount": metrics.get("strokeCount", 0),
        "pointCount": metrics.get("pointCount", 0),
        "durationMs": metrics.get("durationMs", 0),
        "durationSeconds": metrics.get("durationSeconds", 0),
        "pathLengthPx": metrics.get("pathLengthPx", 0),
        "averageSpeedPxPerSecond": metrics.get("averageSpeedPxPerSecond", 0),
        "pauseThresholdMs": metrics.get("pauseThresholdMs", PAUSE_THRESHOLD_MS),
        "pauseCount": metrics.get("pauseCount", 0),
        "pauses": metrics.get("pauses", [])[:8],
        "dataEvents": data_events[:24],
    }


def build_explanation_prompt(analysis: dict) -> str:
    metrics_json = json.dumps(compact_metrics_for_prompt(analysis), ensure_ascii=False, indent=2)
    return (
        "请根据 HanziScore（字谱）的书写统计特征生成 JSON 解读。\n"
        "只解释运动、时间、速度、停顿和节奏数据；不要识别汉字；不要判断笔顺；"
        "不要评价书法水平；不要打分。\n"
        "请谨慎表述可能的节奏或状态，例如使用“从时间和运动数据看起来”。\n"
        "必须只返回 JSON，不要返回 Markdown。\n"
        "JSON 顶层必须只包含这四个字符串字段：summary、rhythm、pauses、caution。\n\n"
        f"本地统计特征如下，未包含原始轨迹点：\n{metrics_json}"
    )


def parse_json_text(text: str) -> dict | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def format_explanation_json(explanation: dict) -> str:
    sections = [explanation.get(key, "") for key in EXPLANATION_KEYS]
    if not any(str(section).strip() for section in sections):
        sections = collect_explanation_text(explanation)
    return "\n\n".join(str(section).strip() for section in sections if str(section).strip())


def collect_explanation_text(value: object) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, list):
        sections = []
        for item in value:
            sections.extend(collect_explanation_text(item))
        return sections
    if isinstance(value, dict):
        sections = []
        for item in value.values():
            sections.extend(collect_explanation_text(item))
        return sections
    return []


def build_explanation_prompt(analysis: dict) -> str:
    evidence_json = json.dumps(compact_metrics_for_prompt(analysis), ensure_ascii=False, indent=2)
    return (
        "你是 HanziScore（字谱）的书写过程分析助手。必须只返回 JSON，不要返回 Markdown。\n"
        "请使用中文解释。只能引用下面提供的数值指标和 dataEvents 作为证据，不要使用原始轨迹。\n"
        "不要识别汉字，不要判断笔顺，不要评价书法水平，不要打分，不要推断部件，"
        "也不要把候选解释说成专家标签。\n"
        "如需描述节奏或状态，必须谨慎表述为基于时间和运动数据的解释。\n"
        "JSON 顶层只能包含四个字符串字段：summary、rhythm、pauses、caution。\n\n"
        f"本地证据如下，不包含原始轨迹数组：\n{evidence_json}"
    )


def generate_zhipu_explanation(analysis: dict) -> tuple[str | None, dict | None, str | None]:
    api_key = os.environ.get("ZHIPU_API_KEY", "").strip()
    if not api_key:
        return None, None, "ZHIPU_API_KEY is not available to the Flask process."

    model = os.environ.get("ZHIPU_MODEL", ZHIPU_MODEL)
    request_body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是 HanziScore 的书写过程分析助手，只能输出 JSON。",
            },
            {
                "role": "user",
                "content": build_explanation_prompt(analysis),
            },
        ],
        "temperature": 0.4,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    encoded_body = json.dumps(request_body, ensure_ascii=False).encode("utf-8")

    last_request_error = None
    try:
        for attempt in range(ZHIPU_MAX_RETRIES + 1):
            zhipu_request = urllib.request.Request(
                ZHIPU_CHAT_COMPLETIONS_URL,
                data=encoded_body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "Connection": "close",
                    "User-Agent": "HanziScore/0.1",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(zhipu_request, timeout=ZHIPU_TIMEOUT_SECONDS) as response:
                    response_data = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError:
                raise
            except (OSError, urllib.error.URLError) as error:
                last_request_error = error
                if attempt >= ZHIPU_MAX_RETRIES:
                    raise
                time.sleep(min(1.5 * (attempt + 1), 5))
    except urllib.error.HTTPError as error:
        try:
            error_body = error.read().decode("utf-8")
        except OSError:
            error_body = ""
        return None, None, f"Zhipu HTTP {error.code}: {error_body[:300]}"
    except (OSError, urllib.error.URLError) as error:
        request_error = last_request_error or error
        attempts = ZHIPU_MAX_RETRIES + 1
        return None, None, f"Zhipu request failed after {attempts} attempt(s): {request_error}"
    except json.JSONDecodeError as error:
        return None, None, f"Zhipu response was not valid JSON: {error}"

    choices = response_data.get("choices", [])
    first_choice = choices[0] if choices else {}
    message = first_choice.get("message") if isinstance(first_choice, dict) else {}
    text = message.get("content", "") if isinstance(message, dict) else ""
    if not isinstance(text, str):
        text = ""
    explanation_json = parse_json_text(text)
    if not explanation_json:
        return None, None, "Zhipu returned no valid JSON explanation."

    explanation_text = format_explanation_json(explanation_json)
    if not explanation_text:
        return None, None, "Zhipu JSON explanation was empty."

    return explanation_text, explanation_json, None


def generate_local_explanation(analysis: dict) -> tuple[str, dict]:
    metrics = analysis.get("metrics") if isinstance(analysis.get("metrics"), dict) else {}
    stroke_count = metrics.get("strokeCount", 0)
    point_count = metrics.get("pointCount", 0)
    duration_ms = metrics.get("durationMs", 0)
    path_length = metrics.get("pathLengthPx", 0)
    average_speed = metrics.get("averageSpeedPxPerSecond", 0)
    pause_count = metrics.get("pauseCount", 0)
    pause_threshold = metrics.get("pauseThresholdMs", PAUSE_THRESHOLD_MS)

    if average_speed >= 260:
        rhythm_note = "整体移动速度偏快，书写过程看起来更接近连续推进。"
    elif average_speed <= 90 and duration_ms:
        rhythm_note = "整体移动速度偏慢，书写过程看起来更偏审慎和分段。"
    else:
        rhythm_note = "整体移动速度处在较平稳的范围，书写过程看起来节奏较均衡。"

    if pause_count:
        pause_note = (
            f"系统检测到 {pause_count} 次不短于 {pause_threshold} ms 的停顿，"
            "这些停顿可理解为笔画转换、位置调整或短暂观察的时间片段。"
        )
    else:
        pause_note = (
            f"系统未检测到不短于 {pause_threshold} ms 的明显停顿，"
            "这表示本次记录中的轨迹衔接较连续。"
        )

    explanation_json = {
        "summary": (
            f"本次记录包含 {stroke_count} 个笔画、{point_count} 个采样点，"
            f"总时长约 {duration_ms} ms，轨迹长度约 {path_length} px，"
            f"平均速度约 {average_speed} px/s。"
        ),
        "rhythm": rhythm_note,
        "pauses": pause_note,
        "caution": "以上说明只基于书写统计特征，不能用于判断字符是否正确、笔顺是否规范或书法质量高低。",
    }
    return format_explanation_json(explanation_json), explanation_json


def summarize_event_types(analysis: dict) -> str:
    event_summary = analysis.get("event_summary") if isinstance(analysis.get("event_summary"), dict) else {}
    data_events = event_summary.get("data_events") if isinstance(event_summary.get("data_events"), list) else []
    if not data_events:
        return "当前阈值下没有笔画级 data event 被触发。"

    parts = []
    for event in data_events[:8]:
        parts.append(
            "第 {strokeIndex} 笔：{type}（数值 {value} {unit}，阈值 {threshold}）".format(
                strokeIndex=event.get("strokeIndex", "?"),
                type=event.get("type", "event"),
                value=event.get("value", "?"),
                unit=event.get("unit", ""),
                threshold=event.get("threshold", "?"),
            )
        )
    return "; ".join(parts)


def generate_local_explanation(analysis: dict) -> tuple[str, dict]:
    metrics = analysis.get("metrics") if isinstance(analysis.get("metrics"), dict) else {}
    stroke_count = metrics.get("strokeCount", 0)
    point_count = metrics.get("pointCount", 0)
    duration_ms = metrics.get("durationMs", 0)
    path_length = metrics.get("pathLengthPx", 0)
    average_speed = metrics.get("averageSpeedPxPerSecond", 0)
    pause_count = metrics.get("pauseCount", 0)
    pause_threshold = metrics.get("pauseThresholdMs", PAUSE_THRESHOLD_MS)
    event_text = summarize_event_types(analysis)

    if average_speed >= 260:
        rhythm_note = "从整体平均速度看，本次书写移动速度相对偏快。"
    elif average_speed <= 90 and duration_ms:
        rhythm_note = "从整体平均速度看，本次书写移动速度相对偏慢。"
    else:
        rhythm_note = "从整体平均速度看，本次书写移动速度处在较平稳的范围。"

    explanation_json = {
        "summary": (
            f"本次记录包含 {stroke_count} 个笔画、{point_count} 个采样点，"
            f"总时长为 {duration_ms} ms，轨迹长度为 {path_length} px，"
            f"平均速度为 {average_speed} px/s。"
        ),
        "rhythm": f"{rhythm_note} 笔画级证据：{event_text}",
        "pauses": (
            f"停顿检测器发现 {pause_count} 次不短于 {pause_threshold} ms 的停顿。"
        ),
        "caution": (
            "以上内容只是对时间、速度、停顿和 data event 的本地解释；"
            "不是汉字识别、笔顺判断、书法评分、部件识别或专家书法术语标注。"
        ),
    }
    return format_explanation_json(explanation_json), explanation_json


EVENT_LABEL_TITLES = {
    "low_speed_stroke": "候选：慢速推进",
    "high_speed_stroke": "候选：快速推进",
    "long_duration_stroke": "候选：延长处理笔段",
    "long_pause_before": "候选：停顿后调整",
    "long_pause_after": "候选：笔后节奏分界",
    "speed_variation": "候选：速度波动段",
    "fast_start": "候选：快速起笔",
    "slow_end": "候选：末端放慢",
    "sharp_turn": "候选：明显转折段",
}


def get_stroke_event_records(analysis: dict) -> list[dict]:
    strokes = analysis.get("strokes") if isinstance(analysis.get("strokes"), list) else []
    records = []
    for stroke in strokes:
        if not isinstance(stroke, dict):
            continue
        geometry = stroke.get("geometry") if isinstance(stroke.get("geometry"), dict) else {}
        dynamics = stroke.get("dynamics") if isinstance(stroke.get("dynamics"), dict) else {}
        turning_points = geometry.get("turning_points") if isinstance(geometry.get("turning_points"), list) else []
        labels = stroke.get("labels") if isinstance(stroke.get("labels"), list) else []
        records.append(
            {
                "strokeIndex": stroke.get("index", len(records) + 1),
                "strokeId": stroke.get("id", ""),
                "durationMs": dynamics.get("duration_ms", 0),
                "pathLengthPx": geometry.get("path_length", 0),
                "meanSpeedPxPerSecond": dynamics.get("mean_speed", 0),
                "maxSpeedPxPerSecond": dynamics.get("max_speed", 0),
                "speedVariance": dynamics.get("speed_variance", 0),
                "pauseBeforeMs": dynamics.get("pause_before_ms", 0),
                "pauseAfterMs": dynamics.get("pause_after_ms", 0),
                "turningPointCount": len(turning_points),
                "dataEvents": labels[:8],
            }
        )
    return records


def compact_metrics_for_prompt(analysis: dict) -> dict:
    metrics = analysis.get("metrics") if isinstance(analysis.get("metrics"), dict) else {}
    event_summary = analysis.get("event_summary") if isinstance(analysis.get("event_summary"), dict) else {}
    data_events = event_summary.get("data_events") if isinstance(event_summary.get("data_events"), list) else []
    return {
        "strokeCount": metrics.get("strokeCount", 0),
        "pointCount": metrics.get("pointCount", 0),
        "durationMs": metrics.get("durationMs", 0),
        "durationSeconds": metrics.get("durationSeconds", 0),
        "pathLengthPx": metrics.get("pathLengthPx", 0),
        "averageSpeedPxPerSecond": metrics.get("averageSpeedPxPerSecond", 0),
        "pauseThresholdMs": metrics.get("pauseThresholdMs", PAUSE_THRESHOLD_MS),
        "pauseCount": metrics.get("pauseCount", 0),
        "pauses": metrics.get("pauses", [])[:8],
        "strokeEvidence": get_stroke_event_records(analysis),
        "dataEvents": data_events[:24],
    }


def build_explanation_prompt(analysis: dict) -> str:
    evidence_json = json.dumps(compact_metrics_for_prompt(analysis), ensure_ascii=False, indent=2)
    return (
        "你是 HanziScore（字谱）的书写过程研究助手。必须只返回 JSON，不要返回 Markdown。\n"
        "请使用中文解释。你的任务不是评价书写，而是把可计算特征组织成可阅读、可比较、可沉淀的研究材料。\n"
        "只能引用下方提供的数值指标、strokeEvidence 和 dataEvents 作为证据，不要使用原始轨迹。\n"
        "不要识别汉字，不要判断笔顺，不要评价书法水平，不要打分，不要推断部件，"
        "不要推断书写者人格、能力或真实情绪状态，也不要把候选解释说成专家标签。\n"
        "当证据不足时必须说明不确定性。\n"
        "JSON 顶层必须包含这些字段：summary、evidence、rhythm_interpretation、"
        "candidate_labels、uncertainty、observation_questions、caution。\n"
        "candidate_labels 必须是数组，每项包含 label、evidence、uncertainty；label 必须以“候选：”开头。\n"
        "observation_questions 必须是数组，用于提出后续可观察、可比较的问题。\n\n"
        f"本地证据如下，不包含原始轨迹数组：\n{evidence_json}"
    )


def format_candidate_label(item: object) -> str:
    if isinstance(item, dict):
        label = str(item.get("label", "候选：未命名模式")).strip()
        evidence = str(item.get("evidence", "")).strip()
        uncertainty = str(item.get("uncertainty", "")).strip()
        parts = [label]
        if evidence:
            parts.append(f"证据：{evidence}")
        if uncertainty:
            parts.append(f"不确定性：{uncertainty}")
        return "；".join(parts)
    return str(item).strip()


def format_explanation_json(explanation: dict) -> str:
    if not isinstance(explanation, dict):
        return ""

    sections = []
    summary = str(explanation.get("summary", "")).strip()
    if summary:
        sections.append(f"概要\n{summary}")

    evidence = explanation.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    if isinstance(evidence, list) and evidence:
        lines = [str(item).strip() for item in evidence if str(item).strip()]
        if lines:
            sections.append("证据摘要\n" + "\n".join(f"- {line}" for line in lines))

    rhythm = str(
        explanation.get("rhythm_interpretation")
        or explanation.get("rhythm")
        or ""
    ).strip()
    if rhythm:
        sections.append(f"节奏解释\n{rhythm}")

    candidate_labels = explanation.get("candidate_labels", [])
    if isinstance(candidate_labels, str):
        candidate_labels = [candidate_labels]
    if isinstance(candidate_labels, list) and candidate_labels:
        lines = [format_candidate_label(item) for item in candidate_labels]
        lines = [line for line in lines if line]
        if lines:
            sections.append("候选标注\n" + "\n".join(f"- {line}" for line in lines))

    uncertainty = str(explanation.get("uncertainty", "")).strip()
    if uncertainty:
        sections.append(f"不确定性\n{uncertainty}")

    pauses = str(explanation.get("pauses", "")).strip()
    if pauses:
        sections.append(f"停顿说明\n{pauses}")

    questions = explanation.get("observation_questions", [])
    if isinstance(questions, str):
        questions = [questions]
    if isinstance(questions, list) and questions:
        lines = [str(item).strip() for item in questions if str(item).strip()]
        if lines:
            sections.append("后续观察问题\n" + "\n".join(f"- {line}" for line in lines))

    caution = str(explanation.get("caution", "")).strip()
    if caution:
        sections.append(f"边界说明\n{caution}")

    if sections:
        return "\n\n".join(sections)

    return "\n\n".join(collect_explanation_text(explanation))


def event_to_candidate_label(event: dict) -> dict:
    event_type = str(event.get("type", "data_event"))
    stroke_index = event.get("strokeIndex", "?")
    value = event.get("value", "?")
    unit = event.get("unit", "")
    threshold = event.get("threshold", "?")
    label = EVENT_LABEL_TITLES.get(event_type, f"候选：{event_type}")
    return {
        "label": label,
        "evidence": (
            f"第 {stroke_index} 笔触发 {event_type}，数值为 {value} {unit}，"
            f"阈值为 {threshold}。"
        ),
        "uncertainty": "该标签只是开放编码候选项，不能作为专家结论或书写质量判断。",
    }


def pick_extreme(records: list[dict], key: str, reverse: bool = True) -> dict | None:
    numeric_records = [record for record in records if isinstance(record.get(key), (int, float))]
    if not numeric_records:
        return None
    return sorted(numeric_records, key=lambda record: record.get(key, 0), reverse=reverse)[0]


def build_local_explanation_json(analysis: dict) -> dict:
    metrics = analysis.get("metrics") if isinstance(analysis.get("metrics"), dict) else {}
    evidence = compact_metrics_for_prompt(analysis)
    records = evidence["strokeEvidence"]
    data_events = evidence["dataEvents"]
    stroke_count = metrics.get("strokeCount", 0)
    point_count = metrics.get("pointCount", 0)
    duration_ms = metrics.get("durationMs", 0)
    path_length = metrics.get("pathLengthPx", 0)
    average_speed = metrics.get("averageSpeedPxPerSecond", 0)
    pause_count = metrics.get("pauseCount", 0)
    pause_threshold = metrics.get("pauseThresholdMs", PAUSE_THRESHOLD_MS)

    evidence_lines = [
        f"本次记录包含 {stroke_count} 个笔画、{point_count} 个采样点，总时长 {duration_ms} ms。",
        f"总轨迹长度为 {path_length} px，整体平均速度为 {average_speed} px/s。",
        f"系统检测到 {pause_count} 次不短于 {pause_threshold} ms 的停顿。",
    ]

    longest = pick_extreme(records, "durationMs")
    slowest = pick_extreme(records, "meanSpeedPxPerSecond", reverse=False)
    fastest = pick_extreme(records, "maxSpeedPxPerSecond")
    most_turns = pick_extreme(records, "turningPointCount")
    if longest:
        evidence_lines.append(f"第 {longest['strokeIndex']} 笔持续时间最长，为 {longest['durationMs']} ms。")
    if slowest:
        evidence_lines.append(
            f"第 {slowest['strokeIndex']} 笔平均速度最低，为 {slowest['meanSpeedPxPerSecond']} px/s。"
        )
    if fastest:
        evidence_lines.append(
            f"第 {fastest['strokeIndex']} 笔最大速度最高，为 {fastest['maxSpeedPxPerSecond']} px/s。"
        )
    if most_turns and most_turns.get("turningPointCount", 0):
        evidence_lines.append(
            f"第 {most_turns['strokeIndex']} 笔转折点最多，共 {most_turns['turningPointCount']} 个。"
        )

    if longest and slowest and longest["strokeIndex"] == slowest["strokeIndex"]:
        rhythm = (
            f"从时间和速度数据看，第 {longest['strokeIndex']} 笔同时表现为持续时间较长、"
            "平均速度较低，可以作为本次样本中节奏变化较明显的位置来观察。"
        )
    elif data_events:
        rhythm = (
            "从 dataEvents 看，本次样本存在若干局部节奏信号；这些信号适合用于比较不同样本中"
            "快慢、停顿和转折是否反复出现在相近位置。"
        )
    else:
        rhythm = (
            "当前阈值下未出现明显 data event，整体节奏解释应保持保守，主要依据总时长、"
            "平均速度和停顿数量进行描述。"
        )

    candidate_labels = [event_to_candidate_label(event) for event in data_events[:8]]
    if not candidate_labels:
        candidate_labels = [
            {
                "label": "候选：未见显著阈值事件",
                "evidence": "当前记录没有触发已配置的 dataEvents 阈值。",
                "uncertainty": "这不代表书写没有变化，只说明现有阈值下没有形成候选事件。",
            }
        ]

    observation_questions = [
        "最长停顿或最长持续笔画是否会在同一用户的多次书写中稳定出现？",
        "明显转折处是否经常伴随速度下降或速度方差升高？",
        "不同输入设备是否会改变平均速度、最大速度或 dataEvents 的触发频率？",
    ]
    if any(event.get("type") == "slow_end" for event in data_events):
        observation_questions.append("slow_end 是否经常出现在相同类型的笔画末端？")
    if any(event.get("type") in {"long_pause_before", "long_pause_after"} for event in data_events):
        observation_questions.append("长停顿在多次样本中是否对应相似的书写位置或换笔位置？")

    return {
        "summary": (
            "本次解释把本地计算出的速度、时长、停顿、转折和 dataEvents 组织为研究观察材料，"
            "不增加新的事实判断。"
        ),
        "evidence": evidence_lines,
        "rhythm_interpretation": rhythm,
        "candidate_labels": candidate_labels,
        "uncertainty": (
            "这些解释只能说明记录中的时间和运动结构；不能判断真实原因，也不能推断书写者状态、"
            "能力或书写质量。"
        ),
        "observation_questions": observation_questions[:5],
        "caution": (
            "以上内容不是汉字识别、笔顺判断、书法评分、部件识别或专家书法术语标注。"
        ),
    }


def generate_local_explanation(analysis: dict) -> tuple[str, dict]:
    explanation_json = build_local_explanation_json(analysis)
    return format_explanation_json(explanation_json), explanation_json


def make_explanation_response(
    record_id: str,
    source: str,
    text: str,
    generated_at: str,
    ai_json: dict | None = None,
    cached_source: str | None = None,
    fallback_reason: str | None = None,
) -> dict:
    response = {
        "recordId": record_id,
        "source": source,
        "sourceLabel": EXPLANATION_SOURCE_LABELS[source],
        "text": text,
        "generatedAt": generated_at,
        "json": ai_json or {},
    }
    if cached_source:
        response["cachedSource"] = cached_source
        response["cachedSourceLabel"] = EXPLANATION_SOURCE_LABELS.get(cached_source, cached_source)
    if fallback_reason:
        response["fallbackReason"] = fallback_reason
    return response


def explain_record(record_id: str, analysis: dict) -> dict:
    cache = read_ai_cache()
    cached = cache["records"].get(record_id)
    has_zhipu_key = bool(os.environ.get("ZHIPU_API_KEY", "").strip())
    cached_source = cached.get("source") if isinstance(cached, dict) else None
    cached_has_json = isinstance(cached, dict) and isinstance(cached.get("json"), dict)
    cached_protocol = cached.get("protocolVersion") if isinstance(cached, dict) else None
    cache_protocol_matches = cached_protocol == EXPLANATION_PROTOCOL_VERSION
    can_return_cache = cache_protocol_matches and (
        cached_source == "zhipu" or (not has_zhipu_key and cached_has_json)
    )

    if isinstance(cached, dict) and isinstance(cached.get("text"), str) and can_return_cache:
        return make_explanation_response(
            record_id=record_id,
            source="cache",
            text=cached["text"],
            generated_at=cached.get("generatedAt", ""),
            ai_json=cached.get("json") if isinstance(cached.get("json"), dict) else None,
            cached_source=cached_source,
            fallback_reason=cached.get("fallbackReason"),
        )

    generated_at = now_utc_iso()
    zhipu_text, zhipu_json, fallback_reason = generate_zhipu_explanation(analysis)
    if zhipu_text:
        source = "zhipu"
        text = zhipu_text
        ai_json = zhipu_json or {}
    else:
        source = "local_rules"
        text, ai_json = generate_local_explanation(analysis)

    cache["records"][record_id] = {
        "recordId": record_id,
        "source": source,
        "sourceLabel": EXPLANATION_SOURCE_LABELS[source],
        "text": text,
        "json": ai_json,
        "generatedAt": generated_at,
        "model": os.environ.get("ZHIPU_MODEL", ZHIPU_MODEL) if source == "zhipu" else "",
        "fallbackReason": fallback_reason or "",
        "metrics": compact_metrics_for_prompt(analysis),
        "protocolVersion": EXPLANATION_PROTOCOL_VERSION,
    }
    write_ai_cache(cache)

    return make_explanation_response(
        record_id,
        source,
        text,
        generated_at,
        ai_json=ai_json,
        fallback_reason=fallback_reason,
    )

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
                "phase": 6,
                "status": "ok",
                "storage": "json-files",
            }
        )

    @app.get("/api/records")
    def records():
        return jsonify({"records": list_saved_records()})

    @app.get("/api/records/<record_id>")
    def record_detail(record_id: str):
        sample, analysis, error = get_record_files(record_id)
        if error:
            body, status_code = error
            return jsonify(body), status_code

        return jsonify(
            {
                "id": record_id,
                "sample": sample,
                "analysis": analysis,
            }
        )

    @app.get("/api/records/<record_id>/explanation")
    def record_explanation(record_id: str):
        _sample, analysis, error = get_record_files(record_id)
        if error:
            body, status_code = error
            return jsonify(body), status_code

        return jsonify(explain_record(record_id, analysis))

    @app.post("/api/captures")
    def receive_capture():
        payload, error = validate_capture_payload(request.get_json(silent=True))
        if error:
            body, status_code = error
            return jsonify(body), status_code

        record_id = make_record_id()
        received_at = now_utc_iso()
        analysis_data = writing_analysis.build_analysis(payload["strokes"], PAUSE_THRESHOLD_MS)
        metrics = analysis_data["metrics"]
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
            "strokes": analysis_data["strokes"],
            "event_summary": analysis_data["event_summary"],
        }

        write_json(sample_path, sample)
        write_json(analysis_path, analysis)

        return jsonify(
            {
                "phase": 6,
                "status": "stored",
                "stored": True,
                "recordId": record_id,
                "sampleFile": f"data/samples/{record_id}.json",
                "analysisFile": f"data/analyses/{record_id}.json",
                "targetCharacter": payload.get("targetCharacter", ""),
                "metrics": metrics,
                "eventSummary": analysis_data["event_summary"],
            }
        )

    return app


if __name__ == "__main__":
    debug_enabled = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    port = int(os.environ.get("PORT", "5000"))
    create_app().run(host="127.0.0.1", port=port, debug=debug_enabled)
