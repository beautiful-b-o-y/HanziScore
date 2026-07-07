# HanziScore 字谱

HanziScore is a lightweight Flask demo for recording how a Chinese character is written. It records strokes, timing, pressure, replay data, local metrics, and an optional AI explanation. It does not recognize characters, correct stroke order, or score calligraphy.

## Current Status

Phase 6 is complete:

- Canvas renders a writing guide.
- Pointer Events capture strokes and points.
- Each point keeps `x`, `y`, `t`, and `pressure`.
- Mouse writing includes a lightweight brush-size control for a more legible
  visual stroke.
- Save writes capture JSON to `data/samples/`.
- Flask calculates stroke count, duration, path length, average speed, and pauses.
- Analysis JSON is written to `data/analyses/`.
- Saved records can be loaded for Canvas replay.
- Replay supports play, pause, reset, and speed control.
- AI explanation uses cache, Zhipu API, or local rules.
- Analysis JSON now includes stroke event records with geometry, dynamics, simple
  segment labels, visual proxy data, and data event labels.

## Run Locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

Health check:

```text
http://127.0.0.1:5000/health
```

## Zhipu API Key

AI explanation reads the Zhipu API key from the local environment variable `ZHIPU_API_KEY`. Do not write keys into source code.

PowerShell temporary setup:

```powershell
$env:ZHIPU_API_KEY = "your_zhipu_api_key_here"
```

PowerShell persistent setup:

```powershell
setx ZHIPU_API_KEY "your_zhipu_api_key_here"
```

After `setx`, open a new PowerShell or restart VS Code before running the app.

The default model is:

```text
glm-5.2
```

You can override it for local testing:

```powershell
$env:ZHIPU_MODEL = "glm-5.2"
```

The API read timeout defaults to 60 seconds. You can raise it for slower models:

```powershell
$env:ZHIPU_TIMEOUT_SECONDS = "90"
```

Connection-level failures are retried twice by default. You can tune this locally:

```powershell
$env:ZHIPU_MAX_RETRIES = "3"
```

The Zhipu request only sends locally calculated writing statistics and stroke-level `dataEvents` evidence such as event type, value, threshold, unit, and stroke index. It does not upload raw trajectory point arrays.

If Zhipu is unavailable, the API key is missing, quota is reached, or the response is invalid, HanziScore automatically returns a local template explanation and shows the fallback reason in the UI.

## AI Explanation Protocol

AI explanations are used to organize local measurements into readable research
notes. They are not a substitute for a calligraphy teacher and are not aesthetic
scores.

The explanation protocol asks for:

- `summary`: a short overview of what the explanation is doing.
- `evidence`: concrete numeric facts and triggered `dataEvents`.
- `rhythm_interpretation`: a cautious interpretation of timing and motion
  relationships.
- `candidate_labels`: open-coding candidates such as rhythm shift, slow ending,
  or sharp turn, each with evidence and uncertainty.
- `uncertainty`: what the current evidence cannot prove.
- `observation_questions`: follow-up questions for comparing future samples.
- `caution`: explicit scope limits.

AI and local fallback explanations must cite local metrics or `dataEvents`, keep
uncertainty visible, and avoid character recognition, stroke-order judgment,
calligraphy scoring, component detection, personality inference, ability
inference, or claims about the writer's real emotional state.

User-facing explanations should not read like raw metric dumps. Numeric metrics
and thresholds are used as internal evidence, while the displayed explanation
should favor intuitive rhythm language such as slower movement, clearer pause,
sharper turn, faster start, or a possible rhythm boundary.

## Phase 6 Stroke Event Fields

Saved samples still keep the original raw capture payload under `data/samples/`.
Analysis files under `data/analyses/` add a `strokes` array. Each analyzed stroke
contains:

- `raw_points`: the original per-stroke point list preserved for local JSON review.
- `geometry`: `normalized_points`, `resampled_points`, `bbox`, `path_length`,
  `centroid`, `start_point`, `end_point`, `angle_profile`, `curvature_profile`,
  and `turning_points`.
- `dynamics`: `speed_profile`, `acceleration_profile`, `mean_speed`,
  `max_speed`, `speed_variance`, `pause_before_ms`, `pause_after_ms`, and
  `duration_ms`.
- `segments`: lightweight `start`, `move`, `turn`, and `end` segment markers.
- `visual_proxy`: a local drawing proxy. Mouse input is marked
  `simulated_from_speed`; it is not claimed to be real pressure.
- `labels`: threshold-based `data_events` such as `low_speed_stroke`,
  `high_speed_stroke`, `long_duration_stroke`, `long_pause_before`,
  `long_pause_after`, `speed_variation`, `fast_start`, `slow_end`, and
  `sharp_turn`.

The analysis also includes `event_summary.data_events`, a compact list used by
the frontend event table and by AI/local explanation evidence.

Mouse brush size is stored as `brushSize` on each stroke so replay can preserve
the visible stroke weight. This is a display setting, not a claim about real
stylus pressure.

These events describe movement data only. They are not character recognition,
stroke-order standards, calligraphy scores, component detection, expert
calligraphy terminology, or model-training labels.

## Scope

The project stays lightweight:

- Python + Flask
- Native HTML/CSS/JavaScript
- Canvas + Pointer Events
- JSON file storage
- AI explanation must fall back to cache or local rules

The project does not add React, Vue, TypeScript, build tools, Docker, a database, login, cloud deployment, model training, Chinese character recognition, stroke-order correction, or calligraphy scoring.
