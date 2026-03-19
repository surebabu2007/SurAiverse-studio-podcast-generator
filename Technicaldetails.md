# SurAIverse TTS Studio — Technical Details

## 1. Architecture Overview

### Data Flow (Web UI)

```
Browser
  └─► gradio_app.py (tab handler function)
        └─► generate_*_speech() / generate_podcast_audio()
              └─► TTSEngine
                    └─► ModelManager
                          └─► chatterbox library (ChatterboxTurboTTS / ChatterboxMultilingualTTS / ChatterboxTTS)
                                └─► audio tensor
                    └─► AudioProcessor.concatenate_audio()
              └─► temp WAV file
  └─► audio rendered in browser
```

### Component Roles

| Component | File | Role |
|---|---|---|
| `TTSEngine` | `core/tts_engine.py` | Unified public API for all TTS generation. Routes by model type, handles chunking. |
| `ModelManager` | `core/model_manager.py` | Lazy-loads models one at a time; handles device detection and HuggingFace auth. |
| `GeminiClient` | `core/gemini_client.py` | LLM client for Google Gemini API. Generates podcast content, translates, enhances tags. |
| `LMStudioClient` | `core/lmstudio_client.py` | LLM client for LM Studio (OpenAI-compatible). Same interface as GeminiClient. |
| `PodcastGenerator` | `core/podcast_generator.py` | Orchestrates LLM → script → TTS pipeline. Handles solo/duo/panel formats. |
| `NewsAggregator` | `core/news_aggregator.py` | Uses active LLM client to suggest trending topics by category. |
| `AudioMixer` | `core/audio_mixer.py` | Mixes TTS speech with uploaded background music. |
| `AudioProcessor` | `core/audio_utils.py` | Concatenates audio segments with optional silence gaps. |
| `text_utils` | `core/text_utils.py` | Single source of truth for tag constants, strip/inject/clean/enhance utilities. |
| `gradio_app` | `app/gradio_app.py` | Single-file Gradio frontend (~2200 lines). All tab UIs and generation callbacks. |
| `api_server` | `app/api_server.py` | FastAPI REST server. Thin wrapper over TTSEngine. |
| `cli` | `app/cli.py` | CLI entry point for scripted generation. |

---

## 2. Component Deep Dives

### ModelManager (`core/model_manager.py`)
- Detects device priority: `DEVICE` env var → MPS → CUDA → CPU.
- Calls `huggingface_hub.login()` at startup using `HUGGINGFACE_TOKEN`.
- Maintains `_models: Dict[ModelType, Any]` — only one model loaded at a time.
- `get_model()` unloads the current model before loading a new one (`_unload_current_model`).
- All model load/unload events emit `logging.info` (not `print`).
- `get_paralinguistic_tags()` and `get_supported_languages()` are static methods — no model load required.

### TTSEngine (`core/tts_engine.py`)
- `generate_turbo()` / `generate_multilingual()`: chunk long text at 400 chars via `_split_text_into_chunks()`. Splits on `.!?।॥` sentence boundaries.
- `generate_multilingual()`: pre-normalises Devanagari danda (`।` → `.`, `॥` → `.`) before calling the library.
- `generate_multi_speaker_podcast()`: iterates segments, assigns voice paths per speaker, concatenates with configurable pause gaps. Failed segments are logged and skipped; generation continues.
- `_autocast_context()`: uses `torch.amp.autocast("cuda", float16)` on CUDA; `nullcontext` elsewhere.

### GeminiClient (`core/gemini_client.py`)
- Probes a prioritised list of model names at startup (`gemini-3-flash-preview` → ... → `gemini-1.5-flash`) until one responds.
- All utility functions (`_estimate_word_count`, `_clean_content_for_tts`, `_enhance_paralinguistic_tags`, `_inject_natural_paralinguistic_tags`) delegate to `core/text_utils.py`.
- `generate_podcast_content()` pipeline: build prompt → call API (up to 3 retries with exponential backoff) → clean → enhance → inject tags → **auto-enhance with LLM** → adjust length.
- `enhance_text_with_tags()`: sends content to Gemini with strict rules for contextually appropriate tag placement.
- `translate_script()`: strips tags before sending to LLM; validates `Speaker N:` format is preserved in the result.

### LMStudioClient (`core/lmstudio_client.py`)
- `_discover_model()` called at startup; `_refresh_model()` called before every request (handles live model changes in LM Studio UI).
- Same interface and pipeline as `GeminiClient` — both implement `generate_podcast_content()`, `enhance_text_with_tags()`, `translate_script()`, `parse_multi_speaker_content()`.
- `_SimpleResponse` class at module level wraps plain text into a Gemini-compatible `.text` attribute (used by `_ModelWrapper.generate_content()` for `NewsAggregator` compatibility).

### PodcastGenerator (`core/podcast_generator.py`)
- `get_llm_client()` selects between `GeminiClient` and `LMStudioClient` based on `LLM_PROVIDER` env var.
- Two-step flow exposed to `gradio_app.py`:
  1. `generate_podcast_content()` → English script.
  2. `translate_script()` → translated script (if non-English selected).
- `generate_multi_speaker_podcast()` delegates audio generation to `TTSEngine`.

### gradio_app (`app/gradio_app.py`)
- Module-level singletons: `engine`, `podcast_generator`, `news_aggregator`, `gemini_client` — all lazy-initialised via `get_*()` helpers.
- `generate_script()` is a **generator function** (uses `yield`). All early-exit paths must `yield` then `return`.
- `generate_podcast_audio()` reads `output_language`; dispatches to Multilingual model for non-English, Turbo for English.
- Intro/outro branding text is auto-translated before TTS when non-English is selected.
- Quick Tag JS inserted via `gr.Blocks(js=QUICK_TAG_JS)` — see Known Issues §5.
- `strip_paralinguistic_tags` imported from `core/text_utils` (not defined locally).

### text_utils (`core/text_utils.py`)
- `PARALINGUISTIC_TAGS`: list of 9 supported tags — single source of truth for all modules.
- `AVERAGE_WPM = 150`: shared constant for word count estimation.
- `_TAG_STRIP_RE`: compiled regex used by `strip_paralinguistic_tags()`.
- `strip_paralinguistic_tags(text)`: removes all tags; used before multilingual TTS and translation.
- `estimate_word_count(duration_minutes)`: returns `int(duration * 150 * 0.9)`.
- `clean_content_for_tts(content)`: strips markdown, URLs, HTML, stage directions; preserves `Speaker N:` labels and paralinguistic tags.
- `enhance_paralinguistic_tags(content)`: moves isolated tags (on their own line) back inline.
- `inject_natural_paralinguistic_tags(content, min_tags)`: 13 contextual patterns covering humor, surprise, reflection, emotion, frustration, transitions, and conspiratorial tone.

### AudioProcessor (`core/audio_utils.py`)
- `concatenate_audio(segments, pause_duration)`: accepts list of `(tensor, sample_rate)` tuples, resamples as needed, inserts silence between segments, returns `(concatenated_tensor, sample_rate)`.

---

## 3. Environment Variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `HUGGINGFACE_TOKEN` | Yes | — | Model downloads from `ResembleAI/chatterbox` |
| `GOOGLE_GEMINI_API_KEY` | For Gemini | — | Podcast script generation, enhance, translation |
| `LLM_PROVIDER` | No | `gemini` | `gemini` or `lmstudio` |
| `LM_STUDIO_URL` | For LM Studio | `http://localhost:8000` | Local LLM server base URL |
| `DEVICE` | No | auto | Force device: `cuda`, `mps`, or `cpu` |
| `HF_HOME` | No | `~/.cache/huggingface` | HuggingFace model cache location |
| `GRADIO_SERVER_PORT` | No | `7860` | Web UI port |
| `API_SERVER_PORT` | No | `8000` | REST API port |
| `CORS_ALLOWED_ORIGINS` | No | `*` | Comma-separated list of allowed CORS origins for API server |
| `MAX_CONCURRENT_TTS` | No | `2` | Max simultaneous TTS requests allowed by the API server semaphore |

---

## 4. Model Reference

| Model | Class | Tab(s) | Languages | Notes |
|---|---|---|---|---|
| Turbo (350M) | `ChatterboxTurboTTS` | Turbo TTS, Podcast (English) | English only | Supports paralinguistic tags; chunks at 400 chars |
| Multilingual (500M) | `ChatterboxMultilingualTTS` | Multilingual, Podcast (non-English) | 23 languages | Voice cloning via `audio_prompt_path` or built-in `conds.pt`; chunks at 400 chars |
| Original (500M) | `ChatterboxTTS` | Original | English only | Exposes `exaggeration` and `cfg_weight` params |

All models download from `ResembleAI/chatterbox` on HuggingFace on first use. All output at 24 kHz.

---

## 5. Known Issues & Applied Fixes

### Fix 1 — Multilingual / Hindi chunking (2026-03-17)
**Problem:** Multilingual model has `max_new_tokens=1000`. Long text hit the cap and was truncated.
**Fix:** Added chunking to `generate_multilingual()` — same 400-char chunk limit and `_split_text_into_chunks()` as Turbo.
**File:** `core/tts_engine.py`
**Rationale:** Turbo already had this pattern; multilingual needed the same treatment.

### Fix 2 — Devanagari danda regex (2026-03-17)
**Problem:** `_split_text_into_chunks` used `(?<=[.!?])\s+` — did not split on Hindi sentence endings.
**Fix:** Regex updated to `(?<=[.!?।॥])\s+`.
**File:** `core/tts_engine.py`
**Rationale:** Hindi text uses `।` (danda) and `॥` (double danda) as sentence terminators.

### Fix 3 — Devanagari danda pre-normalisation (2026-03-17)
**Problem:** The chatterbox library's `punc_norm` doesn't include `।` in its `sentence_enders`, causing a spurious trailing `.` to be appended to Hindi text.
**Fix:** Replace `।` → `.` and `॥` → `.` before calling `model.generate()`.
**File:** `core/tts_engine.py:generate_multilingual()`
**Rationale:** The library adds `.` if the last character is not a recognised sentence ender; pre-normalising prevents double punctuation.

### Fix 4 — Quick Tags cursor insert (2026-03-17)
**Problem:** Gradio 4.x sanitizes `gr.HTML` with DOMPurify (strips `<script>` and inline handlers). Python callbacks can't access `selectionStart`/`selectionEnd`. `mousedown` on a button steals focus and resets cursor to 0 before `onclick` fires.
**Fix:** `QUICK_TAG_JS` string injected via `gr.Blocks(js=...)` (trusted, not sanitised). Defines `window.insertTagAtCursor(tag)` and `attachTracker()` which saves cursor position on `mouseup`/`keyup`/`click`/`select`/`blur`. Tag buttons use `.click(fn=None, js="() => window.insertTagAtCursor('...')")`.
**File:** `app/gradio_app.py`
**Rationale:** Only trusted JS (not `gr.HTML`) can manipulate the DOM without sanitisation. Saving position on `blur` ensures it survives the focus steal.

### Fix 5 — CORS wildcard + credentials violation (2026-03-19)
**Problem:** `allow_origins=["*"]` with `allow_credentials=True` violates the CORS spec — browsers reject this combination.
**Fix:** `allow_credentials=False`. Origins configurable via `CORS_ALLOWED_ORIGINS` env var.
**File:** `app/api_server.py`
**Rationale:** The CORS spec explicitly forbids credentialed requests with a wildcard origin.

### Fix 6 — API input validation (2026-03-19)
**Problem:** No upper bound on `text` field in `GenerateRequest` — arbitrarily large inputs could exhaust memory.
**Fix:** Added `max_length=5000` to the `text` Field.
**File:** `app/api_server.py`
**Rationale:** FastAPI/Pydantic enforces this at the request boundary; returns HTTP 422 before reaching the TTS engine.

### Fix 7 — Temp file leak in voice cloning endpoint (2026-03-19)
**Problem:** If `engine.generate()` raised an exception after writing the voice file, `os.unlink(voice_path)` was never reached, leaving orphaned files in the temp directory.
**Fix:** Wrapped write + generate in `try/finally`; `os.unlink` moved into the `finally` block.
**File:** `app/api_server.py`
**Rationale:** `finally` guarantees cleanup regardless of exception path.

### Fix 8 — Duplicate constants and utilities (2026-03-19)
**Problem:** `PARALINGUISTIC_TAGS`, `AVERAGE_WPM`, `_clean_content_for_tts`, `_enhance_paralinguistic_tags`, `_inject_natural_paralinguistic_tags`, and `strip_paralinguistic_tags` were defined independently in `gemini_client.py`, `lmstudio_client.py`, and `gradio_app.py`.
**Fix:** Created `core/text_utils.py` as single source of truth. All three files now import from it.
**Rationale:** Eliminates divergence risk — a bug fix or improvement in one copy was not automatically applied to the others.

### Fix 10 — Thread safety for concurrent model loading (2026-03-19)
**Problem:** Two concurrent API requests calling `get_turbo()` simultaneously would both enter `get_model()`, see no loaded model, and attempt a parallel model load — causing a race condition on `_current_model` and potential VRAM corruption.
**Fix:** Added `threading.Lock` (`self._lock`) in `ModelManager`. `get_model()` acquires the lock; double-checks the cache inside the lock (in case another thread already loaded while waiting).
**File:** `core/model_manager.py`

### Fix 11 — Model warmup after loading (2026-03-19)
**Problem:** First inference after model load was 2–3× slower due to CUDA kernel compilation (JIT) and graph tracing.
**Fix:** `_warmup_model()` runs a short dummy `model.generate(text="Hi")` immediately after load. CUDA kernels compile during warmup; actual user requests get compiled paths.
**File:** `core/model_manager.py`

### Fix 12 — MPS (Apple Silicon) bfloat16 autocast (2026-03-19)
**Problem:** `_autocast_context()` returned `nullcontext()` for MPS, leaving mixed-precision speedup unused on Apple Silicon.
**Fix:** Tries `torch.amp.autocast("mps", dtype=torch.bfloat16)` first; falls back to `nullcontext()` if the PyTorch version doesn't support it.
**File:** `core/tts_engine.py`

### Fix 13 — O(N²) audio concatenation (2026-03-19)
**Problem:** `concatenate_audio()` iteratively called `torch.cat([result, pause, seg])` — each call allocates a new tensor of size `0..i`, producing N−1 unnecessary copies. For a 20-segment podcast this was severely wasteful.
**Fix:** Build a flat `parts` list first, then call `torch.cat(parts, dim=1)` once at the end. Also added resampler caching (`_resampler_cache`) to avoid re-creating `torchaudio.transforms.Resample` objects for the same rate pair.
**File:** `core/audio_utils.py`

### Fix 14 — API server output temp file leak (2026-03-19)
**Problem:** `/api/generate` and `/api/generate-with-voice` wrote output WAV files but never deleted them — `FileResponse` streams the file but doesn't clean up. Thousands of requests would fill `/tmp`.
**Fix:** Both endpoints accept `BackgroundTasks` and call `background_tasks.add_task(_delete_file, output_path)`. FastAPI runs the deletion after the response is fully sent.
**File:** `app/api_server.py`

### Fix 15 — API concurrency guard (2026-03-19)
**Problem:** A burst of concurrent `/api/generate` requests would attempt simultaneous model loads, exhausting VRAM and causing OOM.
**Fix:** `asyncio.Semaphore(MAX_CONCURRENT_TTS)` limits concurrent TTS requests. Default is 2; configurable via `MAX_CONCURRENT_TTS` env var.
**File:** `app/api_server.py`

### Fix 16 — Pre-compiled regex + generation timing (2026-03-19)
**Problem:** `_split_text_into_chunks` compiled its regex on every call via `re.split(r'...', text)`. No timing instrumentation made it impossible to identify slow requests.
**Fix:** `_SENTENCE_SPLIT_RE` compiled as a module-level constant. `time.perf_counter()` timing added around all generation methods; results logged at `DEBUG` level.
**File:** `core/tts_engine.py`

### Fix 17 — GeminiClient HTTP session reuse (2026-03-19)
**Problem:** `_extract_url_content()` called `requests.get()` directly, creating a new TCP connection per URL fetch (no connection pooling).
**Fix:** Added `self._session = requests.Session()` in `__init__`; `_extract_url_content()` now calls `self._session.get()`. Matches the pattern already used by `LMStudioClient`.
**File:** `core/gemini_client.py`

### Fix 9 — print() in core modules (2026-03-19)
**Problem:** `core/model_manager.py` (9 calls) and `core/tts_engine.py` (5 calls) used `print()`, bypassing the Python logging framework. No way to suppress or redirect these messages.
**Fix:** Replaced all with `logging.getLogger(__name__)` calls at appropriate levels (`info`, `warning`, `debug`).
**Files:** `core/model_manager.py`, `core/tts_engine.py`
**Rationale:** Startup banners in `gradio_app.py` and `api_server.py` are kept as `print()` — they are intentional console output.

---

## 6. Prompt Engineering Notes

### `_build_prompt()` structure (both `GeminiClient` and `LMStudioClient`)

Both clients use an identical `_build_prompt()` that branches on `speaker_count`:

**Solo (speaker_count == 1):**
- Role: professional podcast scriptwriter, broadcast-ready solo script.
- Style: NPR / TED Radio Hour / Lex Fridman.
- Paralinguistic tag rules: 3–5 total, quality over quantity, inline only.
- Structure: hook → development → memorable close.
- Optional `DEPTH` block added when `deep_research=True`.
- Optional `SOURCE` block added when input is a URL.

**Multi-speaker (speaker_count 2–4):**
- Role: professional podcast scriptwriter, broadcast-ready conversation.
- Speaker personalities: host (curious), guest (knowledgeable), contrarian (Speaker 3), storyteller (Speaker 4).
- Micro-conversation guidance (added 2026-03-19): micro-reactions, varied sentence length, emotional pacing, speakers completing/challenging each other's thoughts.
- Format: strict `Speaker N: dialogue` per line.
- Paralinguistic tag rules: 4–6 total across all speakers.
- Optional `DEPTH` block: contrasting expert views, counterintuitive insights, speakers visibly shifting position.

### Tag placement rules
- Tags placed inline within sentences — never on their own line.
- `[chuckle]` after genuinely funny/ironic remarks.
- `[laugh]` very sparingly — only truly hilarious moments.
- `[sigh]` before reflective or bittersweet statements.
- `[gasp]` before genuinely surprising revelations.
- `[clear throat]` at major topic shifts only (max 1–2 total).
- Conservative injection: `inject_natural_paralinguistic_tags()` only fires when existing tag count < `min_tags`.

### Auto-enhance pipeline (added 2026-03-19)
After rule-based injection, `generate_podcast_content()` calls `enhance_text_with_tags()` to let the LLM make a final pass with deeper contextual understanding. This runs silently — failure falls back to the rule-injected content.

### Naturalness improvements (2026-03-19)
Added to multi-speaker prompts:
- Micro-reactions: "Yeah, exactly.", "Wait, really?", "That's wild."
- Sentence length variation: short punchy → longer explanatory.
- Emotional pacing arc: conversational open → tension build → insight/humor release.
- Challenge/completion patterns: "But isn't that exactly the problem?"

Deep research instructions updated to emphasise:
- Real-world consequences.
- Counterintuitive insights.
- Analogies for complex ideas.
- Moments of revelation (solo) / visible position shifts (multi-speaker).

---

## 7. Performance Characteristics

| Operation | CPU | CUDA (GPU) | MPS (Apple Silicon) |
|---|---|---|---|
| Turbo model load | ~30–60s | ~10–20s | ~15–30s |
| Multilingual model load | ~45–90s | ~15–30s | ~20–45s |
| Short text generation (<100 chars) | ~5–15s | ~1–3s | ~2–5s |
| Long text generation (~400 chars) | ~15–45s | ~3–8s | ~5–15s |
| Multi-speaker podcast (5 min, 2 speakers) | ~10–20min | ~2–5min | ~4–10min |
| Model switch (unload + load) | +30–90s | +10–30s | +15–45s |

*Timings are approximate. Actual performance depends on hardware, model cache state, and text complexity.*

---

## 8. Future Recommendations

1. **Extract shared `_build_prompt()` to `text_utils`** — both clients currently maintain identical prompt-building logic. A single `build_podcast_prompt(topic, speaker_count, duration_minutes, deep_research, is_url, paralinguistic_tags)` function would eliminate further divergence risk.

2. **Rate limiting on the REST API** — the `/api/generate` and `/api/generate-with-voice` endpoints have no rate limiting. Under concurrent load, multiple model loads could exhaust GPU memory. Consider `slowapi` or a request queue.

3. **Output temp file cleanup** — `generate_speech()` in `api_server.py` writes to `tempfile.mktemp(suffix=".wav")` for the output but never deletes it (the voice input file is cleaned up, but the output is not). For long-running servers this accumulates files. Consider a `BackgroundTask` cleanup or a periodic sweep.

4. **Streaming TTS** — for long documents, users currently wait for the entire audio to be generated before playback begins. Streaming the WAV chunks as they are produced would reduce perceived latency significantly.

5. **Logging configuration** — core modules now use `logging.getLogger(__name__)` but no handler is configured by default. Add `logging.basicConfig(level=logging.INFO)` in the app entry points (`gradio_app.py`, `api_server.py`, `cli.py`) so these messages are visible without requiring users to configure logging themselves.

6. **`HUGGINGFACE_TOKEN` validation at startup** — currently a missing token only surfaces as a warning, followed by a cryptic HuggingFace auth error when the first model is loaded. Validating the token format (or making a lightweight API call) at startup would give users a clearer, earlier error message.

7. **Voice reference folder watching** — the voice reference dropdown is only refreshed on manual "Refresh Voice List" click. A filesystem watcher (`watchdog`) could update the dropdown automatically when files are added/removed.

8. **Multi-speaker voice assignment UI** — currently the voice assignment for each speaker is done via a fixed mapping in the Podcast tab. A dynamic per-speaker voice selector (generated based on actual speaker count in the script) would be more intuitive.
