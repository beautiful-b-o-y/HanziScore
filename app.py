import os
from pathlib import Path

from flask import Flask, jsonify, render_template


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
                "phase": 1,
                "status": "ok",
                "storage": "json-files",
            }
        )

    return app


if __name__ == "__main__":
    debug_enabled = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    create_app().run(host="127.0.0.1", port=5000, debug=debug_enabled)
