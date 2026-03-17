# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What This Project Is

**SurAIverse TTS Studio** — a Gradio web app (+ FastAPI REST server + CLI) for AI Text-to-Speech generation, podcast creation, and voice cloning. Built on [Resemble AI's Chatterbox TTS](https://github.com/resemble-ai/chatterbox). Developed by Suresh Pydikondala.

---

## Commands

### Launch the web UI
```bash
python app/gradio_app.py              # default: http://localhost:7860
python app/gradio_app.py --port 8080  # custom port
python app/gradio_app.py --no-share   # local only
python launch.py                      # alternate entry point
```

### Launch the REST API
```bash
python app/api_server.py
# Swagger docs at http://localhost:8000/docs
```

### CLI
```bash
python app/cli.py generate "Hello, world!"
python app/cli.py generate "Bonjour!" -m multilingual -l fr
python app/cli.py generate "Hi" -v "voice reference/myvoice.wav" -o out.wav
python app/cli.py tags        # list paralinguistic tags
python app/cli.py languages   # list supported languages
```

### Pre-download models
```bash
python scripts/download_models.py --all
```

### Environment setup
```bash
# Windows (NVIDIA GPU)
setup.bat

# Mac (Apple Silicon)
chmod +x setup.sh && ./setup.sh

# Manual
cp env.template .env   # then edit .env with API keys
```

There are no tests in this project.

---

## Architecture

### Request flow (web UI)
```
Browser → gradio_app.py (tab function) → generate_*_speech() → TTSEngine → ModelManager → chatterbox library → audio file → browser
```

### Core layers

**`core/model_manager.py`** — Owns all model lifecycle. Lazy-loads one model at a time; switching models unloads the previous one to conserve memory. Handles HuggingFace auth and GPU detection (CUDA → MPS → CPU). Do not load models directly — always go through `ModelManager`.

**`core/tts_engine.py`** — The only public API for generation. Has three generation methods (`generate_turbo`, `generate_multilingual`, `generate_original`) each wrapping the corresponding chatterbox model. Both turbo and multilingual chunk long text at 400 chars (via `_split_text_into_chunks`) and concatenate results. Text chunking splits on `.!?।॥` sentence boundaries.

**`core/podcast_generator.py`** — Orchestrates LLM → script → TTS pipeline. Calls `get_llm_client()` which returns either a `GeminiClient` or `LMStudioClient` based on `LLM_PROVIDER` env var. Uses the Turbo TTS model only (English). Supports Solo / Duo / Panel (1-3 speakers).

**`core/gemini_client.py`** — Wraps Google Generative AI SDK. Used for both podcast script generation and the "Enhance with Tags" feature that injects paralinguistic tags into plain text.

**`core/lmstudio_client.py`** — Local LLM alternative to Gemini. Pointed at a local LM Studio server URL.

**`app/gradio_app.py`** — Single-file Gradio app (~2100 lines). Key globals: `CUSTOM_CSS` (styling), `QUICK_TAG_JS` (JS injected via `gr.Blocks(js=...)`). Tab builder functions: `create_podcast_tab`, `create_turbo_tab`, `create_multilingual_tab`, `create_original_tab`. All generation calls go through module-level helper functions (`generate_turbo_speech`, `generate_multilingual_speech`, etc.) which call `get_engine()` (lazy singleton).

### LLM provider switching
Set `LLM_PROVIDER=gemini` or `LLM_PROVIDER=lmstudio` in `.env`. The podcast generator and enhance feature both honour this. LM Studio requires a running local server (`LM_STUDIO_URL`); Gemini requires `GOOGLE_GEMINI_API_KEY`.

### Voice cloning
Drop audio files into `voice reference/` — the UI scans that folder on load and on "Refresh Voice List". Supported formats: WAV, MP3, FLAC, OGG, M4A, AAC, WMA, AIFF, OPUS. Users can also upload/record directly in the UI. Voice path is passed as `audio_prompt_path` to the chatterbox model.

### Output files
Generated audio is written to temp files via `tempfile.mktemp(suffix=".wav")` and also converted to MP4 for download. The `outputs/` directory is used by the CLI.

---

## Models

| Model | Class | Tab(s) | Languages | Notes |
|-------|-------|--------|-----------|-------|
| Turbo (350M) | `ChatterboxTurboTTS` | Turbo TTS, Podcast | English only | Supports paralinguistic tags |
| Multilingual (500M) | `ChatterboxMultilingualTTS` | Multilingual | 23 languages | Voice cloning via `audio_prompt_path` or built-in `conds.pt` |
| Original (500M) | `ChatterboxTTS` | Original | English only | Exposes `exaggeration` and `cfg_weight` params |

Models download from `ResembleAI/chatterbox` on HuggingFace on first use. `HUGGINGFACE_TOKEN` is required.

---

## Environment Variables (`.env`)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `HUGGINGFACE_TOKEN` | Yes | — | Model downloads |
| `GOOGLE_GEMINI_API_KEY` | For Gemini | — | Podcast + Enhance |
| `LLM_PROVIDER` | No | `gemini` | `gemini` or `lmstudio` |
| `LM_STUDIO_URL` | For LM Studio | — | Local LLM server |
| `DEVICE` | No | auto | `cuda`, `mps`, or `cpu` |
| `HF_HOME` | No | `~/.cache/huggingface` | Model cache location |
| `GRADIO_SERVER_PORT` | No | `7860` | Web UI port |
| `API_SERVER_PORT` | No | `8000` | REST API port |

---

## Known Fixes & Non-Obvious Constraints

### Multilingual / Hindi (2026-03-17) — `core/tts_engine.py`
1. **Added chunking to `generate_multilingual`** — the underlying model has `max_new_tokens=1000`; long text hit the cap. Now chunks at 400 chars and concatenates, same as turbo. Affects all 23 languages.
2. **Fixed `_split_text_into_chunks` regex** — `(?<=[.!?])\s+` → `(?<=[.!?।॥])\s+` to split on Devanagari danda for Hindi.
3. **Pre-normalise Devanagari danda** — the chatterbox library's internal `punc_norm` doesn't include `।` in its `sentence_enders`, so Hindi text ending with `।` got a spurious extra `.`. Fixed by replacing `।` → `.` and `॥` → `.` before calling the library.

### Quick Tags cursor insert (2026-03-17) — `app/gradio_app.py`
**Why `gr.HTML` + `<script>` didn't work:** Gradio 4.x sanitizes `gr.HTML` with DOMPurify — strips `<script>` tags and all inline event handlers (`onclick`, `onmousedown`).

**Why Python callbacks can't do this:** `selectionStart`/`selectionEnd` only exist in the browser; Python receives only the text value.

**Why focus loss was a problem:** `mousedown` on any button steals focus from the textarea and resets `selectionStart` to 0 before `onclick` fires.

**Working solution:**
- `QUICK_TAG_JS` string is injected via `gr.Blocks(js=QUICK_TAG_JS)` — trusted code, not sanitized.
- It defines `window.insertTagAtCursor(tag)` and `attachTracker()` which listens to `mouseup`, `keyup`, `click`, `select`, `blur` on the textarea, saving position to `window._turboSelStart/_turboSelEnd`. `blur` is included so position survives the focus steal.
- Tag buttons are `gr.Button` with `.click(fn=None, inputs=[], outputs=[], js="() => window.insertTagAtCursor('...')")` — Gradio's native client-side click, no server round-trip.
- `turbo_text` has `elem_id="turbo_text_input"` so JS can find it via `#turbo_text_input textarea`.

**Do not** revert to Python callbacks or `gr.HTML` `<script>` tags for this feature.

### Other constraints
- **Podcast tab is English-only** — uses Turbo model, no language selector.
- **Voice reference or `conds.pt` must exist** — if neither is present for the Multilingual model, generation raises `AssertionError`. The model downloads `conds.pt` automatically via `from_pretrained`.
- **One model loaded at a time** — switching tabs unloads the current model. This is intentional for memory management, not a bug.
- **`requirements.txt`** is tuned for Mac/CPU. Use **`requirements-windows.txt`** on Windows with NVIDIA GPU (includes CUDA-enabled PyTorch).
