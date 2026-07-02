# HanziScore 字谱

HanziScore 是一个五天轻量 Demo，用来记录一个汉字怎样被写出来，而不是识别、纠错或评分。

## Current Status

Phase 3 is complete:

- Canvas renders a writing guide.
- Pointer Events capture strokes and points.
- Each point keeps `x`, `y`, `t`, and `pressure`.
- Clear and save controls are available.
- Save writes the capture JSON to `data/samples/`.
- Flask calculates stroke count, duration, path length, average speed, and pauses.
- Analysis JSON is written to `data/analyses/`.
- Replay and AI explanation are reserved for later phases.

## Run Locally

当前项目包含 Flask 骨架、首页模板、静态资源、JSON 数据目录、Canvas 书写采集和基础指标计算。

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

打开：

```text
http://127.0.0.1:5000
```

健康检查：

```text
http://127.0.0.1:5000/health
```

## Python

建议优先使用 Python 3.12 或 3.13。当前本机 `py` 启动器检测到 Python 3.14.6，如果依赖安装和运行都正常，也可以继续用于本地 Demo。

## OpenAI API Key

阶段 5 才会接入 OpenAI。届时后端会从系统环境变量读取 API key，不会把 key 写入项目文件。

PowerShell 临时配置：

```powershell
$env:OPENAI_API_KEY = "your_api_key_here"
```

PowerShell 持久配置：

```powershell
setx OPENAI_API_KEY "your_api_key_here"
```

配置后重新打开一个 PowerShell 窗口再运行项目。

## Scope

本项目保持轻量：

- Python + Flask
- 原生 HTML/CSS/JavaScript
- Canvas + Pointer Events
- JSON 文件存储
- AI 解释必须回退到缓存或本地规则

不会引入 React、Vue、TypeScript、构建工具、Docker、数据库、登录、云部署、模型训练、汉字识别、笔顺纠错或书法评分。
