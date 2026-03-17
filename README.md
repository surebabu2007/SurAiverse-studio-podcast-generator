# SurAIverse TTS Studio

**AI-Powered TTS & Podcast Studio** by **Suresh Pydikondala**

Built on [Resemble AI's Chatterbox TTS](https://github.com/resemble-ai/chatterbox) with enhanced features for professional podcast generation, LLM-powered emotional tag injection, and GPU-optimized inference.

YouTube: [SurAIverse](https://www.youtube.com/@suraiverse)

---

## Features

- **AI Podcast Generator** - Generate podcasts from topics, URLs, or your own scripts
  - Solo, Duo, or Panel speaker modes (1-3 speakers)
  - Trending topic discovery with one-click generation
  - Background music mixing with volume control
  - Script upload support (.txt, .md, .docx)

- **Enhance (LLM-Powered)** - Automatically inject paralinguistic tags into text using Gemini AI
  - Analyzes emotional tone and context
  - Inserts `[laugh]`, `[sigh]`, `[gasp]`, etc. at natural positions
  - Available in both Turbo TTS and Podcast tabs

- **Three TTS Models:**
  - **Turbo (350M)** - Fast generation with paralinguistic tags
  - **Multilingual (500M)** - 23+ languages with voice cloning
  - **Original (500M)** - CFG weight and exaggeration tuning

- **GPU Optimized:**
  - CUDA float16 autocast for faster NVIDIA inference
  - cuDNN benchmark auto-tuning
  - `torch.inference_mode()` for all generation
  - Apple Silicon MPS acceleration

- **Voice Cloning:**
  - Drop audio files into `voice reference/` folder for automatic detection
  - Upload or record new voices directly in the UI
  - Supports: WAV, MP3, FLAC, OGG, M4A, AAC, WMA, AIFF, OPUS

- **Multiple Interfaces:**
  - Web UI (Gradio) with professional dark theme
  - CLI tool for quick generation
  - REST API (FastAPI) for integration

---

## Quick Start

### 1. Setup

**Windows (NVIDIA GPU):**
```batch
setup.bat
```

**Mac (Apple Silicon):**
```bash
chmod +x setup.sh && ./setup.sh
```

### 2. Configure API Keys

**Option A: Settings Tab (Recommended)**
Launch the app and go to the **Settings** tab to enter your API keys through the UI.

**Option B: .env File**
```bash
cp env.template .env
# Edit .env with your keys
```

You need:
- **HuggingFace Token** - [Get one here](https://huggingface.co/settings/tokens) (required for model downloads)
- **Google Gemini API Key** - [Get one here](https://aistudio.google.com/apikey) (required for podcast generation & Enhance)

### 3. Launch

```bash
python app/gradio_app.py
```

Open http://localhost:7860 in your browser.

Options:
```bash
python app/gradio_app.py --no-share    # Local only
python app/gradio_app.py --port 8080   # Custom port
```

---

## Tabs

| Tab | Description |
|-----|-------------|
| **Podcast** | Generate podcasts from topics or custom scripts with multi-speaker support |
| **Turbo TTS** | Fast TTS with paralinguistic tags and Enhance button |
| **Multilingual** | 23+ languages with voice cloning |
| **Original** | Fine-tuned output with exaggeration & CFG controls |
| **Settings** | API key configuration and system info |

---

## Paralinguistic Tags (Turbo Model)

Add these tags in your text for expressive speech, or use the **Enhance** button to add them automatically:

| Tag | Effect |
|-----|--------|
| `[laugh]` | Laughter |
| `[chuckle]` | Light chuckle |
| `[sigh]` | Sighing |
| `[gasp]` | Gasping |
| `[cough]` | Coughing |
| `[groan]` | Groaning |
| `[sniff]` | Sniffing |
| `[shush]` | Shushing |
| `[clear throat]` | Throat clearing |

**Example:**
```
"Hi there! [laugh] That's so funny [chuckle] anyway, let me tell you..."
```

---

## Supported Languages

Arabic, Danish, German, Greek, English, Spanish, Finnish, French, Hebrew, Hindi, Italian, Japanese, Korean, Malay, Dutch, Norwegian, Polish, Portuguese, Russian, Swedish, Swahili, Turkish, Chinese

---

## CLI & API

**CLI:**
```bash
python app/cli.py generate "Hello, world!"
python app/cli.py generate "Bonjour!" -m multilingual -l fr
python app/cli.py tags        # Show available tags
python app/cli.py languages   # List languages
```

**REST API:**
```bash
python app/api_server.py
# API docs at http://localhost:8000/docs
```

---

## Project Structure

```
SurAIverse TTS Studio/
├── app/
│   ├── gradio_app.py         # Web UI (Gradio)
│   ├── api_server.py         # REST API (FastAPI)
│   └── cli.py                # CLI tool
├── core/
│   ├── tts_engine.py         # Unified TTS engine
│   ├── model_manager.py      # Model loading & GPU optimization
│   ├── gemini_client.py      # Gemini API (podcast + enhance)
│   ├── podcast_generator.py  # Podcast orchestration
│   ├── news_aggregator.py    # Trending news
│   ├── audio_utils.py        # Audio processing
│   └── audio_mixer.py        # Background music mixing
├── voice reference/          # Voice cloning audio files
├── outputs/                  # Generated audio
├── .env                      # API keys (not committed)
├── env.template              # Environment template
└── README.md
```

---

## Troubleshooting

**CUDA not detected:** Run `nvidia-smi` to verify drivers, then reinstall PyTorch:
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**MPS not available (Mac):** Ensure you're on Apple Silicon with macOS 12.3+.

**Out of memory:** The system loads one model at a time. Close other apps and restart if needed.

**Model download issues:** Verify your HuggingFace token, or pre-download: `python scripts/download_models.py --all`

---

## Credits

- Developed by **Suresh Pydikondala** ([SurAIverse](https://www.youtube.com/@suraiverse))
- Based on [Chatterbox TTS](https://github.com/resemble-ai/chatterbox) by [Resemble AI](https://resemble.ai/)
- Model hosting by [HuggingFace](https://huggingface.co/ResembleAI)

## License

This project uses Chatterbox TTS which is licensed under the MIT License.
