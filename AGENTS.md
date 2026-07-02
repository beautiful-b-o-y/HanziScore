# HanziScore Agent Notes

## Project Goal

HanziScore, also called 字谱, is a five-day lightweight Flask demo. It records how a Chinese character is written, rather than recognizing, correcting, or scoring the character.

End-to-end loop:

1. User writes on a Canvas.
2. Frontend records strokes and points as JSON.
3. Each point stores `x`, `y`, `t`, and `pressure`.
4. Flask calculates stroke count, duration, path length, speed, and pauses.
5. Frontend replays the writing.
6. AI, cache, or local rules explain the writing data.

## Hard Constraints

- Use Python + Flask.
- Use native HTML, CSS, and JavaScript.
- Use Canvas + Pointer Events.
- Store data as JSON files.
- Do not use a database.
- Do not use React, Vue, TypeScript, or frontend build tools.
- Do not use Docker.
- Do not add login, accounts, or cloud deployment.
- Do not train models.
- Do not implement Chinese character recognition.
- Do not implement stroke-order correction.
- Do not implement calligraphy scoring.
- AI explanation must fall back to cache or local rules.

## Product Semantics

- The app may record a target character title, such as `永` or `木`, but must not use it for recognition.
- Explanations should use professional language.
- Explanations may cautiously discuss possible writing rhythm or emotional state, but must phrase those as interpretations of timing and motion data rather than facts.
- Raw trajectory JSON may be saved locally.
- Pause threshold should be configurable from one clear constant or setting when implemented.

## User Environment Decisions

- Primary browser target: Chrome.
- Input support target: mouse, touchpad, and pressure stylus where Pointer Events expose pressure. If only one path is available, support mouse first.
- AI provider target: OpenAI.
- The OpenAI API key must be read from local environment variable `OPENAI_API_KEY`; never commit secrets.
- Python 3.12 or 3.13 is preferred for stability. Python 3.14.6 is currently available through the Windows `py` launcher and can be used if dependencies work.
- The user wants Git and plans to upload the project to GitHub.

## Current State

Phase 1 is complete.

Implemented:

- Minimal Flask app in `app.py`.
- Homepage template in `templates/index.html`.
- Static CSS and JavaScript under `static/`.
- JSON data directories under `data/`.
- `requirements.txt`, `.gitignore`, and `README.md`.
- `/health` endpoint returns app status.

Not implemented yet:

- Real Canvas writing capture.
- Stroke JSON save endpoint.
- Metrics calculation.
- Replay workflow.
- AI/cache/local-rule explanation.

## Phase Plan

### Phase 1: Project Skeleton

Acceptance:

- Local Flask server starts.
- Homepage opens.
- `/health` returns JSON.
- No database, frontend framework, build tool, Docker, login, or cloud deployment.

### Phase 2: Canvas Writing Capture

Acceptance:

- User can write with mouse in Chrome.
- Pointer Events record strokes.
- Each point stores `x`, `y`, `t`, and `pressure`.
- UI supports clear and save.
- Save sends JSON to Flask.

### Phase 3: JSON Storage And Metrics

Acceptance:

- Flask receives writing JSON and saves it to `data/samples/`.
- Flask calculates stroke count, total duration, path length, average speed, and pauses.
- Analysis JSON is saved to `data/analyses/`.
- The app still does not recognize, correct, or score characters.

### Phase 4: Frontend Replay

Acceptance:

- A saved writing sample can be loaded.
- Canvas replays strokes in time order.
- Playback includes play, pause, reset, and speed control.
- Metrics are visible in the UI.

### Phase 5: AI, Cache, And Local Explanation

Acceptance:

- Explanation first checks cache.
- If `OPENAI_API_KEY` is configured, OpenAI can generate an explanation.
- If OpenAI is unavailable, local rules generate a fallback explanation.
- Output explains writing process data, not character correctness or calligraphy quality.

## Development Rules

- Work one phase at a time.
- Do not start the next phase until the user confirms.
- Keep edits small and easy to review.
- Prefer standard library helpers and plain Flask patterns.
- Use `.venv` for local dependencies.
- Keep generated runtime data out of Git.
- Do not commit API keys, `.env` files, virtual environments, or saved writing JSON samples unless the user explicitly asks for sample fixtures.

## Verification Commands

Use PowerShell from the repository root.

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m py_compile app.py
.\.venv\Scripts\python -c "from app import create_app; app=create_app(); client=app.test_client(); print(client.get('/').status_code); print(client.get('/health').json)"
.\.venv\Scripts\python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Phase-End Report Format

At the end of each phase, report:

- Modified files.
- Commands run.
- Test results.
- Items the user needs to check personally.

