import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SAMPLES_DIR = DATA_DIR / "samples"
ANALYSES_DIR = DATA_DIR / "analyses"
AI_CACHE_PATH = DATA_DIR / "ai_cache.json"


def ensure_data_paths() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    SAMPLES_DIR.mkdir(exist_ok=True)
    ANALYSES_DIR.mkdir(exist_ok=True)
    if not AI_CACHE_PATH.exists():
        AI_CACHE_PATH.write_text("{}\n", encoding="utf-8")


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
                "phase": 2,
                "status": "ok",
                "storage": "json-files",
            }
        )

    @app.post("/api/captures")
    def receive_capture():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Expected a JSON object."}), 400

        strokes = payload.get("strokes")
        if not isinstance(strokes, list):
            return jsonify({"error": "Expected strokes to be a list."}), 400

        point_count = 0
        for stroke in strokes:
            if not isinstance(stroke, dict):
                return jsonify({"error": "Each stroke must be an object."}), 400

            points = stroke.get("points")
            if not isinstance(points, list):
                return jsonify({"error": "Each stroke must include a points list."}), 400

            for point in points:
                if not isinstance(point, dict):
                    return jsonify({"error": "Each point must be an object."}), 400

                missing_keys = {"x", "y", "t", "pressure"} - set(point)
                if missing_keys:
                    return (
                        jsonify(
                            {
                                "error": "Each point must include x, y, t, and pressure.",
                                "missing": sorted(missing_keys),
                            }
                        ),
                        400,
                    )

            point_count += len(points)

        return jsonify(
            {
                "phase": 2,
                "status": "received",
                "stored": False,
                "targetCharacter": payload.get("targetCharacter", ""),
                "strokeCount": len(strokes),
                "pointCount": point_count,
            }
        )

    return app


if __name__ == "__main__":
    debug_enabled = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    create_app().run(host="127.0.0.1", port=5000, debug=debug_enabled)
