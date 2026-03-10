# Scripts: T2V pipeline and API client

This folder contains the **Text-to-Video (T2V) pipeline** and the **API client** for the video generation service. You can either run the pipeline directly on the server or run the API server and call it with the client.

---

## Running on the server

These instructions assume you are on the machine where TeachingMonster is installed (e.g. a Linux server with GPU), using the `monster` conda environment.

### 1. Environment and working directory

```bash
cd /path/to/teaching-monster-hub/TeachingMonster
conda activate monster
```

Ensure dependencies are installed and the Gemini API key is set:

```bash
pip install -r requirements.txt
# config/.env must contain: GEMINI_API_KEY=your_key
```

### 2. Option A: Run the pipeline directly

Use `T2V_pipeline.py` to generate a video without starting the API server. Good for one-off runs or debugging.

**Syntax:**

```bash
python scripts/T2V_pipeline.py \
  -r "REQUIREMENT_PROMPT" \
  -p "PERSONA_PROMPT" \
  [-c config/default.yaml] \
  [-o final_video.mp4] \
  [-d ./output]
```

**Arguments:**

| Argument | Short | Default | Description |
|----------|--------|---------|-------------|
| `--requirement-prompt` | `-r` | (required) | Main topic/requirement (e.g. what to teach). |
| `--persona-prompt` | `-p` | (required) | Audience/persona (e.g. education level, motivation). |
| `--config` | `-c` | `config/default.yaml` | Path to YAML config. |
| `--output-video-name` | `-o` | `final_video.mp4` | Output video filename. |
| `--final-video-dir` | `-d` | from config | Directory for the final video. |

**Example:**

```bash
python scripts/T2V_pipeline.py \
  -r "Topic: Chemistry of Life - Structure of water and hydrogen bonding" \
  -p "Education Level: University | Learning Motivation: Research papers | Timeline Urgency: Urgent" \
  -c config/default.yaml \
  -o my_video.mp4 \
  -d ./output
```

Outputs:

- **Video:** `{final-video-dir}/{output-video-name}` (e.g. `./output/my_video.mp4`)
- **Intermediates** in `./tmp_pipeline/` (or `tmp_dir` in config): slides, TTS, cursor data
- **Debug JSON** in `tmp/`: `outlines.json`, `slides_struct.json`, `scripts.json`, `word_timings.json`

---

### 3. Option B: Run the API server and use the client

Run the FastAPI server on the machine that will do the generation, then call it from the same server or from another machine with `api_client.py`.

**Start the server (on the server):**

```bash
cd /path/to/teaching-monster-hub/TeachingMonster
conda activate monster
python -m uvicorn src.server:app --host 0.0.0.0 --port 8000
```

Or:

```bash
python src/server.py
# Listens on http://0.0.0.0:8000 by default; override with PORT=5000 python src/server.py
```

**Call the API with the client:**

From the same server (or another machine with the repo):

```bash
cd /path/to/teaching-monster-hub/TeachingMonster
conda activate monster

python scripts/api_client.py \
  --request-id "bio01" \
  --topic "Topic: Chemistry of Life - Structure of water and hydrogen bonding" \
  --student-persona "Education Level: University | Learning Motivation: Research papers | Timeline Urgency: Urgent" \
  --base-url "http://localhost:8000"
```

From another host, point `--base-url` at the server (e.g. `http://SERVER_IP:8000`).

Optional: download the generated files:

```bash
python scripts/api_client.py \
  --request-id "bio01" \
  --topic "Your topic here" \
  --student-persona "Your persona here" \
  --base-url "http://localhost:5000" \
  --download-video \
  --download-subtitle \
  --output-dir ./downloads
```

**Note:** The server’s request body may use `course_requirement` instead of `topic`; the client’s `--topic` maps to that. If you call the API directly (e.g. with `curl`), use the field names defined in `src/server.py` (e.g. `VideoGenerateRequest`).

---

## Configuration

- **Config file:** `config/default.yaml` (override with `-c` for the pipeline or `CONFIG_PATH` for the server).
- **API key:** `config/.env` with `GEMINI_API_KEY=...`.
- **Output dirs:** In config, `output.tmp_dir` and `output.final_video_dir`; or use `-d` for the pipeline.

---

## Pipeline overview

`T2V_pipeline.py` runs:

1. **Outline** – From requirement + persona.
2. **Slides** – Structure and assets (PPT or 3B1B style).
3. **TTS** – Narration audio and word timings.
4. **Cursor** – Cursor trajectories.
5. **Render** – Final MP4 with slide images, cursor, and audio.

The API server uses this same pipeline; each request gets its own output directory under `output.final_video_dir` (e.g. `./output/{request_id}/`).
