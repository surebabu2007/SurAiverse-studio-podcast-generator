# CLAUDE.md

This file provides guidance to AI coding assistants working with this repository.

**Author:** Suresh Pydikondala | YouTube: https://www.youtube.com/@suraiverse

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
# Windows (NVIDIA GPU) — one-click installer
INSTALL.bat                         # launches installer.ps1 via PowerShell

# Mac (Apple Silicon)
chmod +x setup.sh && ./setup.sh

# Manual
cp env.template .env   # then edit .env with API keys
```

### One-click installer (Windows)
- **`INSTALL.bat`** — thin launcher; runs `installer.ps1` via `powershell -ExecutionPolicy Bypass`.
- **`installer.ps1`** — 7-step PowerShell installer: Python check → venv creation → pip upgrade → PyTorch/CUDA install (tries cu121 → cu118 → cu124 → CPU fallback) → project dependencies (filters out torch/torchaudio to avoid CUDA index conflicts) → project config (folders, `.env`, API key prompts, `Launch SurAIverse.bat`) → verification.
- **`Launch SurAIverse.bat`** — created by the installer; activates the venv and runs `app/gradio_app.py`.
- **Step 7 verification** checks: `from google import genai` (not `google.generativeai` — that's the old deprecated package), `gradio`, `torch`, `fastapi`, `requests`.
- **`env.template`** is the source of truth for all `.env` variables. When adding a new env var, add it here (commented out with description) so new installers pick it up.
- **`setup.sh`** (Mac) creates `outputs/`, `samples/`, and `voice reference/` — do not add source-code folders (`app/`, `core/`, `scripts/`) to that mkdir; they already exist in the repo.

There are no tests in this project.

---

## Architecture

### Request flow (web UI)
```
Browser → gradio_app.py (tab function) → generate_*_speech() → TTSEngine → ModelManager → chatterbox library → audio file → browser
```

### Core layers

**`core/model_manager.py`** — Owns all model lifecycle. Lazy-loads one model at a time; switching models unloads the previous one to conserve memory. Handles HuggingFace auth and GPU detection (CUDA → MPS → CPU). All three models output at 24 kHz. A `threading.Lock` prevents concurrent model loads under parallel API requests. After each load, `_warmup_model()` runs a dummy inference to pre-compile CUDA kernels, and `_log_gpu_memory()` logs VRAM usage. Do not load models directly — always go through `ModelManager`.

**`core/tts_engine.py`** — The only public API for generation. Has three generation methods (`generate_turbo`, `generate_multilingual`, `generate_original`) each wrapping the corresponding chatterbox model. Both turbo and multilingual chunk long text at 400 chars (via `_split_text_into_chunks`) and concatenate results. Text chunking splits on `.!?।॥` sentence boundaries. The unified `generate()` method dispatches by `model_type` string and is used internally by `generate_multi_speaker_podcast()`.

**`core/podcast_generator.py`** — Orchestrates the LLM → script → TTS pipeline. Calls `get_llm_client()` which returns either a `GeminiClient` or `LMStudioClient` based on `LLM_PROVIDER` env var. Supports Solo / Duo / Panel (1–4 speakers). Also exposes `translate_script()` which delegates to the active LLM client.

**`core/gemini_client.py`** and **`core/lmstudio_client.py`** — Both implement the same interface: `generate_podcast_content()`, `enhance_text_with_tags()`, `translate_script()`, `parse_multi_speaker_content()`. `GeminiClient` probes a prioritised list of model names at startup to find one that responds. `LMStudioClient` uses an OpenAI-compatible HTTP endpoint and calls `_discover_model()` at startup; `_refresh_model()` is called before each request in case the user changed it in the LM Studio UI.

**`core/news_aggregator.py`** — Uses the active LLM client to generate trending topic suggestions by category. Called from the Podcast tab's "Trending Topics" panel.

**`core/audio_mixer.py`** — Mixes TTS speech with an uploaded background music file. Used in the Podcast tab.

**`core/audio_utils.py`** — `AudioProcessor.concatenate_audio()` is the shared utility for joining audio segments with optional pause gaps (returns a `(tensor, sample_rate)` tuple). Used by `TTSEngine` for chunked generation and multi-speaker stitching, and by `gradio_app.py` for intro/outro assembly.

**`core/text_utils.py`** — Single source of truth for paralinguistic tag constants and shared text utilities: `PARALINGUISTIC_TAGS` (9 tags), `AVERAGE_WPM`, `strip_paralinguistic_tags()`, `clean_content_for_tts()`, `enhance_paralinguistic_tags()`, `inject_natural_paralinguistic_tags()` (13 contextual patterns), `estimate_word_count()`. Imported by `gemini_client.py`, `lmstudio_client.py`, and `gradio_app.py`.

**`app/gradio_app.py`** — Single-file Gradio app (~2200 lines). Key globals: `CUSTOM_CSS` (styling), `QUICK_TAG_JS` (JS injected via `gr.Blocks(js=...)`). Module-level singletons — `engine`, `podcast_generator`, `news_aggregator`, `gemini_client` — all lazy-initialised via `get_*()` helpers. Tab builder functions: `create_podcast_tab`, `create_turbo_tab`, `create_multilingual_tab`, `create_original_tab`. Module-level constants `PODCAST_LANGUAGE_CHOICES` and `_PODCAST_LANGS` drive the podcast language selector; `strip_paralinguistic_tags()` imported from `core.text_utils` removes tags before non-English TTS.

### Podcast tab two-step flow
1. **Step 1 — Generate Script** (`generate_script`, a **generator function**): calls the LLM to produce an English script, then optionally translates it via `generator.translate_script()` if a non-English language is selected. Yields intermediate status updates (e.g. "Translating…") for live UI feedback — all early-exit paths must `yield` then `return`, never a bare `return` with a value.
2. **Step 2 — Generate Audio** (`generate_podcast_audio`): reads `output_language`; if non-English, strips paralinguistic tags and dispatches to the Multilingual model (`tts_model_type="multilingual"`, `language_id=lang_id`); otherwise uses Turbo. Handles multi-speaker segment parsing, voice mapping, intro/outro branding, and background music mixing.

### LLM provider switching
Set `LLM_PROVIDER=gemini` or `LLM_PROVIDER=lmstudio` in `.env`. The podcast generator, news aggregator, enhance feature, and translation all honour this. Resetting the provider from the Settings tab nulls out `podcast_generator`, `news_aggregator`, and `gemini_client` so they re-initialise on next use.

### Voice cloning
Drop audio files into `voice reference/` — the UI scans that folder on load and on "Refresh Voice List". Supported formats: WAV, MP3, FLAC, OGG, M4A, AAC, WMA, AIFF, OPUS. Users can also upload/record directly in the UI. Voice path is passed as `audio_prompt_path` to the chatterbox model.

### Output files
Generated audio is written to temp files via `tempfile.mktemp(suffix=".wav")` and also converted to MP4 (AAC) via `pydub` for download. The `outputs/` directory is used by the CLI.

---

## Models

| Model | Class | Tab(s) | Languages | Notes |
|-------|-------|--------|-----------|-------|
| Turbo (350M) | `ChatterboxTurboTTS` | Turbo TTS, Podcast (English) | English only | Supports paralinguistic tags |
| Multilingual (500M) | `ChatterboxMultilingualTTS` | Multilingual, Podcast (non-English) | 23 languages | Voice cloning via `audio_prompt_path` or built-in `conds.pt` |
| Original (500M) | `ChatterboxTTS` | Original | English only | Exposes `exaggeration` and `cfg_weight` params |

Models download from `ResembleAI/chatterbox` on HuggingFace on first use. `HUGGINGFACE_TOKEN` is required.

---

## Environment Variables (`.env`)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `HUGGINGFACE_TOKEN` | Yes | — | Model downloads |
| `GOOGLE_GEMINI_API_KEY` | For Gemini | — | Podcast + Enhance + Translate |
| `LLM_PROVIDER` | No | `gemini` | `gemini` or `lmstudio` |
| `LM_STUDIO_URL` | For LM Studio | — | Local LLM server |
| `DEVICE` | No | auto | `cuda`, `mps`, or `cpu` |
| `HF_HOME` | No | `~/.cache/huggingface` | Model cache location |
| `GRADIO_SERVER_PORT` | No | `7860` | Web UI port |
| `API_SERVER_PORT` | No | `8000` | REST API port |
| `CORS_ALLOWED_ORIGINS` | No | `*` | Comma-separated allowed origins for API server CORS |
| `MAX_CONCURRENT_TTS` | No | `2` | Max simultaneous TTS requests in the API server |

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

### Podcast language selection (2026-03-19) — `app/gradio_app.py`, `core/`
- Script always generated in English first, then translated via the active LLM client — better quality than generating in the target language directly.
- `generate_script()` is a **generator function** (uses `yield`). All early-exit paths must `yield` then `return`, never a bare `return` with a value.
- Paralinguistic tags are stripped (`strip_paralinguistic_tags()`) before translation AND before multilingual TTS — the Multilingual model does not support them.
- English path is unchanged: Turbo model, no translation, tags fully supported.
- Intro/Outro branding text is **auto-translated** to the selected language before TTS — `get_podcast_generator().translate_script()` is called inside `generate_podcast_audio()` in `app/gradio_app.py` just before the branding voice resolution block. Translation failures are silently caught; English text is used as fallback (multilingual TTS still runs, just with English text).

### Auto-translate branding intro/outro (2026-03-19) — `app/gradio_app.py`
- `translated_intro` / `translated_outro` variables hold the (possibly translated) branding text.
- Translation only runs when `use_multilingual` is `True` (i.e. non-English is selected) and the corresponding checkbox (`add_intro` / `add_outro`) is enabled.
- The intro/outro TTS blocks use `translated_intro` / `translated_outro` instead of `intro_text.strip()` / `outro_text.strip()`.
- **Do not** revert to passing `intro_text`/`outro_text` directly to the multilingual TTS — the model speaks whatever language the *text* is in, regardless of `language_id`.

### Shared text utilities (2026-03-19) — `core/text_utils.py`
- `PARALINGUISTIC_TAGS`, `AVERAGE_WPM`, `strip_paralinguistic_tags()`, `clean_content_for_tts()`, `enhance_paralinguistic_tags()`, and `inject_natural_paralinguistic_tags()` all live in `core/text_utils.py` — the single source of truth.
- `gemini_client.py`, `lmstudio_client.py`, and `gradio_app.py` import from here. Do not redefine these locally in any of those files.
- `inject_natural_paralinguistic_tags()` has 13 contextual patterns (expanded from 5). Add new patterns here, not in the LLM client files.
- `CORS_ALLOWED_ORIGINS` env var added — comma-separated origins for the API server. Defaults to `*` but `allow_credentials` is now `False` (required by the CORS spec when using a wildcard origin).

### Auto-enhance pipeline (2026-03-19) — `core/gemini_client.py`, `core/lmstudio_client.py`
- `generate_podcast_content()` now calls `enhance_text_with_tags()` after rule-based tag injection — a second LLM pass for deeper contextual placement.
- Failure is silently caught; rule-injected content is used as fallback. Do not remove the `try/except` wrapper.
- Tags are still stripped before translation and before multilingual TTS — the auto-enhance output only improves English Turbo output.

### API server fixes (2026-03-19) — `app/api_server.py`
- `allow_credentials=False` — cannot combine `True` with `allow_origins=["*"]` (CORS spec violation).
- `text` field capped at `max_length=5000` in `GenerateRequest` — prevents OOM from arbitrarily large inputs.
- Voice temp file in `generate_speech_with_voice()` is cleaned up in a `try/finally` block — guarantees deletion even if generation raises an exception.
- **Output temp file cleanup** — both TTS endpoints now use `BackgroundTasks` to call `_delete_file(output_path)` after the response is sent. Prevents `/tmp` disk fill on long-running servers.
- **Concurrency cap** — `asyncio.Semaphore(MAX_CONCURRENT_TTS)` (default 2, env-configurable) wraps both TTS endpoints. Prevents OOM from burst concurrent requests attempting simultaneous model loads. Do not remove — without it, 10 parallel requests can exhaust VRAM.

### Production GPU / performance fixes (2026-03-19) — `core/`
- **Thread-safe model loading** (`model_manager.py`) — `threading.Lock` with double-checked locking in `get_model()`. Prevents race condition where two threads both see no loaded model and attempt a parallel load. Do not bypass the lock.
- **Model warmup** (`model_manager.py`) — `_warmup_model()` runs a dummy `generate("Hi")` immediately after load. CUDA kernels compile during warmup so the first real user request gets compiled paths. Warmup failures are silently logged at DEBUG and do not block the load.
- **GPU memory logging** (`model_manager.py`) — `_log_gpu_memory()` logs allocated/reserved GB after every model load. Uses `torch.cuda.memory_allocated()` on CUDA and `torch.mps.current_allocated_memory()` on MPS.
- **MPS bfloat16 autocast** (`tts_engine.py`) — `_autocast_context()` now tries `torch.amp.autocast("mps", dtype=torch.bfloat16)` on Apple Silicon before falling back to `nullcontext()`. ~20–30% inference speedup on M-series.
- **Generation timing** (`tts_engine.py`) — `time.perf_counter()` wraps all generation paths; results logged at `DEBUG`. Enable with `logging.basicConfig(level=logging.DEBUG)`.
- **Pre-compiled split regex** (`tts_engine.py`) — `_SENTENCE_SPLIT_RE` compiled as a module-level constant; `_split_text_into_chunks` uses it directly. Do not move it back inline.
- **O(N²) → O(N) audio concatenation** (`audio_utils.py`) — `concatenate_audio()` now builds a flat `parts[]` list and calls `torch.cat(parts, dim=1)` once. The old iterative `torch.cat([result, pause, seg])` created N−1 full-size copies. For a 20-segment podcast this is ~10× fewer allocations.
- **Resampler caching** (`audio_utils.py`) — `_resampler_cache: Dict[Tuple[int,int], Resample]` on `AudioProcessor` class. `_get_resampler(src_sr, tgt_sr)` returns a cached instance. Avoids re-creating the transform object for every segment in multi-segment generation.
- **GeminiClient HTTP session** (`gemini_client.py`) — `self._session = requests.Session()` created in `__init__`; `_extract_url_content()` uses it instead of bare `requests.get()`. Enables TCP connection pooling, matching the pattern already used by `LMStudioClient`.

### Logging (2026-03-19) — `core/model_manager.py`, `core/tts_engine.py`
- All `print()` calls in these two modules replaced with `logging.getLogger(__name__)`. Use `logger.info/warning/debug` for any new messages added here.
- Startup banner `print()` blocks in `gradio_app.py` and `api_server.py` are intentional console output — keep them as `print`.
- No logging handler is configured by default; add `logging.basicConfig(level=logging.INFO)` in entry points if you want these messages visible.

### Chatterbox warning notes — `core/tts_engine.py`
- The `token_repetition=True` / `forcing EOS` log lines from `alignment_stream_analyzer` are **normal** — the model correctly detects it has finished speaking and stops early (well within its 1000-token budget). Do not attempt to suppress these.
- The `Reference mel length is not equal to 2 * reference token length` warning is a known chatterbox quirk with certain reference audio files. It does not prevent generation.

### Installer fixes (2026-03-19) — `installer.ps1`, `env.template`, `setup.sh`
- **Wrong Gemini import in Step 7** (`installer.ps1`) — previously verified `import google.generativeai` (old deprecated package). The codebase uses `from google import genai` (new `google-genai` package). Fixed to `from google import genai` so the check actually validates what the app uses. Also added `requests` to the check list.
- **Missing env vars in `env.template`** — `CORS_ALLOWED_ORIGINS` and `MAX_CONCURRENT_TTS` were not in the template, so fresh installs had no visibility into these options. Both added as commented-out optional vars with descriptions. **Rule: whenever a new env var is added to the codebase, add it to `env.template` at the same time.**
- **Wrong mkdir in `setup.sh`** — previously `mkdir -p outputs samples app core scripts` which tried to create `app/`, `core/`, `scripts/` (source folders that already exist) and was missing `voice reference/` (required for voice cloning dropdown). Fixed to `mkdir -p outputs samples "voice reference"`.

### Other constraints
- **Voice reference or `conds.pt` must exist** — if neither is present for the Multilingual model, generation raises `AssertionError`. The model downloads `conds.pt` automatically via `from_pretrained`.
- **One model loaded at a time** — switching tabs unloads the current model. This is intentional for memory management, not a bug.
- **`requirements.txt`** is tuned for Mac/CPU. Use **`requirements-windows.txt`** on Windows with NVIDIA GPU (includes CUDA-enabled PyTorch).
