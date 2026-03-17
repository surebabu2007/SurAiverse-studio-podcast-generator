"""
SurAIverse TTS Studio - Gradio Web Interface
AI-Powered TTS & Podcast Studio by Suresh Pydikondala
Based on Resemble AI's Chatterbox TTS
"""

import os
import re
import sys
import tempfile
import platform
from pathlib import Path
from typing import List, Tuple, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import gradio as gr
from dotenv import load_dotenv, set_key

from core.tts_engine import TTSEngine
from core.podcast_generator import PodcastGenerator
from core.news_aggregator import NewsAggregator
from core.audio_mixer import AudioMixer

# Load environment variables
load_dotenv()

# Voice reference folder path
VOICE_REFERENCE_FOLDER = Path(__file__).parent.parent / "voice reference"

# Supported audio formats for voice reference
SUPPORTED_AUDIO_FORMATS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".aiff", ".opus"}

# .env file path
ENV_FILE_PATH = Path(__file__).parent.parent / ".env"


def get_voice_reference_files() -> List[Tuple[str, str]]:
    """Scan the voice reference folder and return list of audio files."""
    if not VOICE_REFERENCE_FOLDER.exists():
        VOICE_REFERENCE_FOLDER.mkdir(parents=True, exist_ok=True)
        return []

    audio_files = []
    for file_path in VOICE_REFERENCE_FOLDER.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_AUDIO_FORMATS:
            display_name = file_path.stem
            audio_files.append((display_name, str(file_path)))

    audio_files.sort(key=lambda x: x[0].lower())
    return audio_files


def refresh_voice_references() -> gr.update:
    """Refresh the voice reference dropdown choices."""
    files = get_voice_reference_files()
    choices = [("None (No voice cloning)", "")] + files
    return gr.update(choices=choices, value="")



# Initialize TTS Engine (lazy loading)
engine = None
podcast_generator = None
news_aggregator = None
gemini_client = None  # Now used as generic LLM client for enhance feature


def get_engine():
    """Get or initialize the TTS engine."""
    global engine
    if engine is None:
        engine = TTSEngine()
    return engine


def get_podcast_generator():
    """Get or initialize the podcast generator."""
    global podcast_generator
    if podcast_generator is None:
        try:
            podcast_generator = PodcastGenerator()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize podcast generator: {str(e)}")
    return podcast_generator


def get_news_aggregator():
    """Get or initialize the news aggregator."""
    global news_aggregator
    if news_aggregator is None:
        try:
            news_aggregator = NewsAggregator()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize news aggregator: {str(e)}")
    return news_aggregator


def get_gemini_client():
    """Get or initialize the LLM client for enhance feature (Gemini or LM Studio)."""
    global gemini_client
    if gemini_client is None:
        from core.podcast_generator import get_llm_client
        gemini_client = get_llm_client()
    return gemini_client


def convert_wav_to_mp4(wav_path: str) -> str:
    """Convert a WAV file to MP4 (AAC audio) for download."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_wav(wav_path)
        mp4_path = wav_path.rsplit(".", 1)[0] + ".mp4"
        audio.export(mp4_path, format="mp4")
        return mp4_path
    except Exception as e:
        print(f"MP4 conversion failed: {e}, falling back to WAV download")
        return wav_path


def enhance_text(text: str) -> str:
    """Enhance text with paralinguistic tags using Gemini."""
    if not text or not text.strip():
        raise gr.Error("Please enter some text to enhance.")
    try:
        client = get_gemini_client()
        enhanced = client.enhance_text_with_tags(text.strip())
        return enhanced
    except Exception as e:
        raise gr.Error(f"Enhance failed: {str(e)}")


def read_uploaded_script(file_path: str) -> str:
    """Read content from an uploaded script file."""
    if not file_path:
        return ""
    try:
        path = Path(file_path)
        if path.suffix.lower() in {".txt", ".md"}:
            return path.read_text(encoding="utf-8")
        elif path.suffix.lower() == ".docx":
            try:
                import docx
                doc = docx.Document(str(path))
                return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except ImportError:
                raise gr.Error("Install python-docx to upload .docx files: pip install python-docx")
        else:
            return path.read_text(encoding="utf-8")
    except Exception as e:
        raise gr.Error(f"Failed to read file: {str(e)}")


# Custom CSS - SurAIverse Professional Dark Theme
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Playfair+Display:wght@400;500;600;700;800;900&family=Cormorant+Garamond:wght@300;400;500;600;700&family=Inter:wght@300;400;500&display=swap');

:root {
    --primary: #7c3aed;
    --primary-hover: #6d28d9;
    --primary-light: #8b5cf6;
    --accent: #f59e0b;
    --accent-hover: #d97706;
    --bg-dark: #0a0a0f;
    --bg-card: #141420;
    --bg-input: #1e1e2e;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --border: #2a2a3e;
    --success: #10b981;
    --warning: #f59e0b;
    --error: #ef4444;
}

* {
    font-family: 'Space Grotesk', sans-serif !important;
    box-sizing: border-box !important;
}

html, body {
    margin: 0 !important;
    padding: 0 !important;
    overflow-x: hidden;
    width: 100%;
}

body, .gradio-container {
    background: var(--bg-dark) !important;
    color: var(--text-primary) !important;
}

/* Edge-to-edge full-width layout */
.gradio-container {
    max-width: 100% !important;
    width: 100% !important;
    margin: 0 !important;
    padding: 0 1.25rem !important;
}

/* Override Gradio's internal layout wrappers */
.gradio-container > .main,
.gradio-container .contain,
.gradio-container .gap {
    max-width: 100% !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
}

/* ===== Keyframe Animations ===== */

@keyframes shimmer {
    0% { background-position: -200% center; }
    100% { background-position: 200% center; }
}

@keyframes topLineSweep {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

@keyframes fadeInUp {
    0% { opacity: 0; transform: translateY(18px); }
    100% { opacity: 1; transform: translateY(0); }
}

@keyframes subtlePulse {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 0.7; }
}

@keyframes orbFloat1 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    33% { transform: translate(30px, -20px) scale(1.05); }
    66% { transform: translate(-20px, 15px) scale(0.95); }
}

@keyframes orbFloat2 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    33% { transform: translate(-25px, 20px) scale(0.95); }
    66% { transform: translate(20px, -15px) scale(1.05); }
}

@keyframes letterSpacingBreath {
    0%, 100% { letter-spacing: 0.18em; }
    50% { letter-spacing: 0.22em; }
}

/* ===== Header Container ===== */

.header-container {
    text-align: center;
    padding: 3.5rem 2rem 2.5rem;
    background: linear-gradient(160deg, #0c0c18 0%, #141428 30%, #1a1a35 50%, #141428 70%, #0c0c18 100%);
    border-radius: 20px;
    margin-bottom: 1.5rem;
    border: 1px solid rgba(124, 58, 237, 0.15);
    position: relative;
    overflow: hidden;
    box-shadow:
        0 4px 40px rgba(124, 58, 237, 0.08),
        0 1px 3px rgba(0, 0, 0, 0.3),
        inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

/* Animated top accent line */
.header-container::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg,
        transparent 0%,
        var(--primary) 20%,
        var(--accent) 50%,
        var(--primary-light) 80%,
        transparent 100%);
    background-size: 200% 100%;
    animation: shimmer 6s ease-in-out infinite;
}

/* Subtle bottom accent line */
.header-container::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 10%;
    right: 10%;
    height: 1px;
    background: linear-gradient(90deg,
        transparent,
        rgba(124, 58, 237, 0.2) 30%,
        rgba(245, 158, 11, 0.15) 50%,
        rgba(124, 58, 237, 0.2) 70%,
        transparent);
}

/* Floating orb decorations */
.header-orb {
    position: absolute;
    border-radius: 50%;
    filter: blur(60px);
    pointer-events: none;
    opacity: 0;
    animation: subtlePulse 8s ease-in-out infinite;
}

.header-orb-1 {
    width: 200px;
    height: 200px;
    background: radial-gradient(circle, rgba(124, 58, 237, 0.12) 0%, transparent 70%);
    top: -40px;
    left: -30px;
    animation: subtlePulse 8s ease-in-out infinite, orbFloat1 20s ease-in-out infinite;
    opacity: 0.5;
}

.header-orb-2 {
    width: 180px;
    height: 180px;
    background: radial-gradient(circle, rgba(245, 158, 11, 0.08) 0%, transparent 70%);
    bottom: -50px;
    right: -20px;
    animation: subtlePulse 10s ease-in-out 2s infinite, orbFloat2 25s ease-in-out infinite;
    opacity: 0.4;
}

.header-orb-3 {
    width: 120px;
    height: 120px;
    background: radial-gradient(circle, rgba(139, 92, 246, 0.06) 0%, transparent 70%);
    top: 20%;
    right: 15%;
    animation: subtlePulse 12s ease-in-out 4s infinite, orbFloat1 30s ease-in-out reverse infinite;
    opacity: 0.3;
}

/* Fine grid pattern overlay */
.header-grid {
    position: absolute;
    inset: 0;
    background-image:
        linear-gradient(rgba(124, 58, 237, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(124, 58, 237, 0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    mask-image: radial-gradient(ellipse 60% 60% at 50% 50%, black 20%, transparent 70%);
    -webkit-mask-image: radial-gradient(ellipse 60% 60% at 50% 50%, black 20%, transparent 70%);
}

/* ===== Title Typography ===== */

.header-title {
    font-family: 'Playfair Display', Georgia, 'Times New Roman', serif !important;
    font-size: 4.2rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: 0.04em;
    line-height: 1.1;
    position: relative;
    z-index: 1;
    animation: fadeInUp 1s ease-out;
    background: linear-gradient(
        135deg,
        #c4b5fd 0%,
        #a78bfa 15%,
        #8b5cf6 30%,
        #f5d08a 50%,
        #f59e0b 65%,
        #d4a056 80%,
        #a78bfa 100%
    );
    background-size: 300% 100%;
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: fadeInUp 1s ease-out, shimmer 8s ease-in-out 1.5s infinite;
    text-shadow: none;
}

.header-title-studio {
    font-family: 'Playfair Display', Georgia, 'Times New Roman', serif !important;
    font-size: 4.2rem;
    font-weight: 400;
    font-style: italic;
    margin: 0;
    letter-spacing: 0.02em;
    line-height: 1.1;
    position: relative;
    z-index: 1;
    animation: fadeInUp 1s ease-out 0.15s both;
    background: linear-gradient(
        135deg,
        rgba(248, 250, 252, 0.95) 0%,
        rgba(203, 213, 225, 0.8) 50%,
        rgba(248, 250, 252, 0.9) 100%
    );
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}

/* Decorative line under title */
.header-divider {
    width: 80px;
    height: 1px;
    margin: 1rem auto 0.8rem;
    background: linear-gradient(90deg,
        transparent,
        var(--primary-light) 30%,
        var(--accent) 50%,
        var(--primary-light) 70%,
        transparent);
    position: relative;
    z-index: 1;
    animation: fadeInUp 1s ease-out 0.3s both;
}

.header-divider-dot {
    width: 6px;
    height: 6px;
    background: var(--accent);
    border-radius: 50%;
    margin: -3px auto 0;
    position: relative;
    z-index: 1;
    box-shadow: 0 0 10px rgba(245, 158, 11, 0.4);
}

/* ===== Subtitle ===== */

.header-subtitle {
    font-family: 'Inter', 'Space Grotesk', sans-serif !important;
    color: var(--text-secondary);
    font-size: 0.95rem;
    font-weight: 300;
    margin-top: 0.6rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    position: relative;
    z-index: 1;
    animation: fadeInUp 1s ease-out 0.45s both, letterSpacingBreath 10s ease-in-out 3s infinite;
}

/* ===== Author Line ===== */

.header-author {
    color: rgba(148, 163, 184, 0.6);
    font-family: 'Inter', 'Space Grotesk', sans-serif !important;
    font-size: 0.8rem;
    font-weight: 400;
    margin-top: 1rem;
    letter-spacing: 0.05em;
    position: relative;
    z-index: 1;
    animation: fadeInUp 1s ease-out 0.6s both;
}

.header-author strong {
    color: rgba(248, 250, 252, 0.75);
    font-weight: 500;
}

.header-author a {
    color: var(--accent) !important;
    text-decoration: none;
    transition: color 0.3s ease, letter-spacing 0.3s ease;
    font-weight: 500;
}

.header-author a:hover {
    color: #fbbf24 !important;
    letter-spacing: 0.03em;
}

.header-sep {
    display: inline-block;
    margin: 0 0.5rem;
    color: rgba(124, 58, 237, 0.3);
}

/* Tabs */
.tabs {
    background: var(--bg-card) !important;
    border-radius: 12px !important;
    border: 1px solid var(--border) !important;
    padding: 0.5rem !important;
}

.tab-nav {
    background: transparent !important;
    border: none !important;
}

.tab-nav button {
    background: transparent !important;
    color: var(--text-secondary) !important;
    border: none !important;
    padding: 0.75rem 1.5rem !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}

.tab-nav button.selected {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-hover) 100%) !important;
    color: white !important;
}

.tab-nav button:hover:not(.selected) {
    background: var(--bg-input) !important;
    color: var(--text-primary) !important;
}

/* Inputs */
textarea, input[type="text"] {
    background: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    padding: 1rem !important;
    font-size: 1rem !important;
    transition: border-color 0.2s ease !important;
}

textarea:focus, input[type="text"]:focus {
    border-color: var(--primary) !important;
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.2) !important;
}

/* Buttons */
button.primary {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-hover) 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.875rem 2rem !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3) !important;
}

button.primary:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(124, 58, 237, 0.4) !important;
}

/* Enhance button */
.enhance-btn {
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-hover) 100%) !important;
    color: #1a1a2e !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3) !important;
}

.enhance-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(245, 158, 11, 0.4) !important;
}

/* Tag buttons */
.tag-btn {
    background: var(--bg-input) !important;
    color: var(--accent) !important;
    border: 1px solid var(--accent) !important;
    border-radius: 20px !important;
    padding: 0.5rem 1rem !important;
    font-size: 0.875rem !important;
    font-family: 'JetBrains Mono', monospace !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
}

.tag-btn:hover {
    background: var(--accent) !important;
    color: var(--bg-dark) !important;
}

/* Sliders */
.slider input[type="range"] {
    accent-color: var(--primary) !important;
}

/* Audio player */
audio {
    width: 100% !important;
    border-radius: 10px !important;
}

/* Dropdowns */
.dropdown, select {
    background: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    padding: 0.75rem 1rem !important;
}

/* File upload */
.file-upload {
    background: var(--bg-input) !important;
    border: 2px dashed var(--border) !important;
    border-radius: 12px !important;
    padding: 2rem !important;
    text-align: center !important;
    transition: all 0.2s ease !important;
}

.file-upload:hover {
    border-color: var(--primary) !important;
    background: rgba(124, 58, 237, 0.05) !important;
}

/* Labels */
label {
    color: var(--text-primary) !important;
    font-weight: 500 !important;
    margin-bottom: 0.5rem !important;
}

/* Card styling */
.card {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 1.5rem !important;
}

/* Download button */
.download-btn a {
    color: var(--accent) !important;
    font-weight: 600 !important;
}

/* Settings info box */
.settings-info {
    background: rgba(124, 58, 237, 0.1) !important;
    border: 1px solid rgba(124, 58, 237, 0.3) !important;
    border-radius: 10px !important;
    padding: 1rem !important;
    color: var(--text-secondary) !important;
}

/* Mobile responsive */
@media screen and (max-width: 768px) {
    .gradio-container { padding: 0 0.5rem !important; }
    .header-container { padding: 2rem 1rem 1.5rem !important; margin-bottom: 1rem !important; }
    .header-title { font-size: 2.6rem !important; }
    .header-title-studio { font-size: 2.6rem !important; }
    .header-subtitle { font-size: 0.75rem !important; letter-spacing: 0.12em !important; }
    .header-orb { display: none; }
    .gr-row { flex-direction: column !important; }
    .gr-column { width: 100% !important; max-width: 100% !important; }
    button, .primary-btn { min-height: 48px !important; font-size: 1rem !important; }
    .tag-btn { padding: 0.75rem 0.875rem !important; font-size: 0.8rem !important; min-height: 44px !important; }
    textarea { font-size: 16px !important; min-height: 120px !important; }
    input[type="text"], select, .dropdown { font-size: 16px !important; min-height: 48px !important; }
    audio { width: 100% !important; min-height: 54px !important; }
    .tab-nav button { padding: 1rem !important; font-size: 0.9rem !important; }
}

@media screen and (max-width: 480px) {
    .header-title { font-size: 2rem !important; }
    .header-title-studio { font-size: 2rem !important; }
    .header-subtitle { font-size: 0.65rem !important; }
    .tag-btn { padding: 0.625rem 0.75rem !important; font-size: 0.75rem !important; }
    .tab-nav button { padding: 0.75rem 0.5rem !important; font-size: 0.8rem !important; }
}

@media (hover: none) and (pointer: coarse) {
    button:hover, .tag-btn:hover, .primary-btn:hover { transform: none !important; }
    button:active, .tag-btn:active { transform: scale(0.98) !important; opacity: 0.9 !important; }
}

@supports (padding: max(0px)) {
    .gradio-container {
        padding-left: max(1rem, env(safe-area-inset-left)) !important;
        padding-right: max(1rem, env(safe-area-inset-right)) !important;
        padding-bottom: max(1rem, env(safe-area-inset-bottom)) !important;
    }
}
"""

# JavaScript injected globally via gr.Blocks(js=...).
# gr.HTML sanitizes content with DOMPurify (strips <script> and inline event
# handlers), so JS must be injected here instead.
QUICK_TAG_JS = """
() => {
    // Saved cursor position — updated whenever the user interacts with the
    // textarea so it survives the focus loss that happens when a button is clicked.
    window._turboSelStart = 0;
    window._turboSelEnd   = 0;

    window.insertTagAtCursor = function(tag) {
        var el = document.querySelector('#turbo_text_input textarea');
        if (!el) return;

        var start = window._turboSelStart;
        var end   = window._turboSelEnd;

        // Clamp to actual text length (safety guard)
        var len = el.value.length;
        start = Math.min(start, len);
        end   = Math.min(end,   len);

        var before = el.value.substring(0, start);
        var after  = el.value.substring(end);

        var needSpaceBefore = before.length > 0 && before[before.length - 1] !== ' ';
        var needSpaceAfter  = after.length  > 0 && after[0] !== ' ';
        var insertText = (needSpaceBefore ? ' ' : '') + tag + (needSpaceAfter ? ' ' : '');
        var newValue   = before + insertText + after;

        // Use the native setter so Gradio/Svelte's reactivity picks up the change.
        var nativeSetter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value'
        ).set;
        nativeSetter.call(el, newValue);
        el.dispatchEvent(new Event('input', { bubbles: true }));

        // Advance saved position to just after the inserted tag.
        var newCursor = start + insertText.length;
        window._turboSelStart = newCursor;
        window._turboSelEnd   = newCursor;

        el.focus();
        el.setSelectionRange(newCursor, newCursor);
    };

    // Attach cursor-tracking listeners to the textarea.
    // Retries every 500 ms until the element is present in the DOM.
    function attachTracker() {
        var el = document.querySelector('#turbo_text_input textarea');
        if (!el) { setTimeout(attachTracker, 500); return; }

        function save() {
            window._turboSelStart = el.selectionStart;
            window._turboSelEnd   = el.selectionEnd;
        }
        ['mouseup', 'keyup', 'click', 'select', 'blur'].forEach(function(evt) {
            el.addEventListener(evt, save);
        });
    }
    attachTracker();
}
"""


def create_podcast_tab():
    """Create the Podcast generation tab with script upload support."""

    TRENDING_CATEGORIES = [
        # Row 1 - Tech & Science
        ("Technology", "technology"),
        ("AI", "ai"),
        ("Science", "science"),
        ("Space", "space"),
        ("Cybersecurity", "cybersecurity"),
        ("Crypto", "crypto"),
        # Row 2 - News & Business
        ("World News", "world"),
        ("Politics", "politics"),
        ("Business", "business"),
        ("Startups", "startups"),
        ("Automotive", "automotive"),
        # Row 3 - Entertainment & Culture
        ("Entertainment", "entertainment"),
        ("Movies", "movies"),
        ("Music", "music"),
        ("Gaming", "video_games"),
        ("Comedy", "comedy"),
        # Row 4 - Lifestyle & Health
        ("Health", "health"),
        ("Mental Health", "mental_health"),
        ("Food", "food"),
        ("Travel", "travel"),
        ("Lifestyle", "lifestyle"),
        # Row 5 - More Topics
        ("Sports", "sports"),
        ("Education", "education"),
        ("Environment", "environment"),
        ("True Crime", "true_crime"),
        ("History", "history"),
        ("Motivation", "motivation"),
        ("Relationships", "relationships"),
        ("Parenting", "parenting"),
    ]

    with gr.Column():
        gr.Markdown(
            """
            <div style="text-align: center; margin-bottom: 1rem;">
                <h2 style="margin: 0; font-size: 1.5rem;">AI Podcast Generator</h2>
                <p style="color: var(--text-secondary); margin-top: 0.5rem;">Generate from a topic, paste your own script, or upload a script file</p>
            </div>
            """
        )

        # Input mode selector
        input_mode = gr.Radio(
            label="Input Mode",
            choices=[("Generate from Topic", "topic"), ("Use My Script", "script")],
            value="topic",
            interactive=True,
        )

        # --- Topic Mode ---
        with gr.Group(visible=True) as topic_mode_group:
            podcast_topic = gr.Textbox(
                label="Topic",
                placeholder="Enter a topic, paste a URL, or click a trending topic below...",
                lines=2,
                max_lines=4,
            )

            with gr.Accordion("Trending Topics (click to fetch latest news)", open=True):
                trending_btns = []
                # Display in rows of 6
                for row_start in range(0, len(TRENDING_CATEGORIES), 6):
                    row_items = TRENDING_CATEGORIES[row_start:row_start + 6]
                    with gr.Row():
                        for label, category in row_items:
                            btn = gr.Button(label, size="sm", variant="secondary")
                            trending_btns.append((btn, category))

        # --- Script Mode ---
        with gr.Group(visible=False) as script_mode_group:
            podcast_script = gr.Textbox(
                label="Paste your script",
                placeholder="Paste your podcast script here...",
                lines=10,
                max_lines=30,
            )
            with gr.Row():
                script_upload = gr.File(
                    label="Or upload a script file (.txt, .md, .docx)",
                    file_types=[".txt", ".md", ".docx"],
                    type="filepath",
                )
                script_enhance_btn = gr.Button(
                    "Enhance with Tags",
                    size="sm",
                    elem_classes=["enhance-btn"],
                )

        # Load uploaded script into text area
        script_upload.change(
            fn=read_uploaded_script,
            inputs=[script_upload],
            outputs=[podcast_script],
        )

        # Sample scripts for multi-speaker formats
        SAMPLE_SCRIPTS = {
            1: "",
            2: """Speaker 1: Welcome to the show! Today we're diving into a fascinating topic. So, what do you think about this?

Speaker 2: Thanks for having me! I think it's really exciting. There's so much to unpack here.

Speaker 1: Absolutely. Let's start with the basics and work our way up.

Speaker 2: Sounds great. The first thing people should know is...""",
            3: """Speaker 1: Welcome everyone to today's panel discussion! We have two great guests joining us. Let's jump right in.

Speaker 2: Thanks for having us! I've been looking forward to this conversation.

Speaker 3: Same here. This is a topic I'm really passionate about.

Speaker 1: Let's start with the big question. What's your take on this?

Speaker 2: From my perspective, I think the key issue is...

Speaker 3: I'd add to that. There's another angle worth considering...

Speaker 1: Great points from both of you. Let's dig deeper into that.""",
            4: """Speaker 1: Welcome to our roundtable! We've got a full panel today with three incredible guests. Let's get started.

Speaker 2: Great to be here! I've been following this topic closely.

Speaker 3: Same here. I think there are some really important angles we need to cover.

Speaker 4: Absolutely. And I'd love to bring a different perspective to the table.

Speaker 1: Perfect. Let's start with the big picture. What's everyone's initial take?

Speaker 2: Well, from where I sit, the most critical factor is...

Speaker 3: I agree with some of that, but I think we're missing...

Speaker 4: That's a great point. I'd also add that...

Speaker 1: Fascinating. Let's unpack each of those viewpoints.""",
        }

        # Enhance script with tags
        script_enhance_btn.click(
            fn=enhance_text,
            inputs=[podcast_script],
            outputs=[podcast_script],
        )

        # Settings
        gr.Markdown("**Settings**")
        with gr.Row():
            speaker_count = gr.Radio(
                label="Speakers",
                choices=[("Solo", 1), ("Duo", 2), ("Panel (3)", 3), ("Panel (4)", 4)],
                value=1,
                interactive=True,
            )
            duration_minutes = gr.Radio(
                label="Duration",
                choices=[("1 min", 1), ("3 min", 3), ("5 min", 5), ("10 min", 10)],
                value=3,
                interactive=True,
            )

        # Show sample script when speaker count changes in script mode
        def on_speaker_count_change(count, mode, current_script):
            count = int(count)
            if mode != "script":
                return gr.update()
            # Only populate if script is empty or already contains a sample
            is_sample = (not current_script or not current_script.strip()
                         or current_script.strip().startswith("Speaker 1:"))
            if is_sample:
                return gr.update(value=SAMPLE_SCRIPTS.get(count, ""))
            return gr.update()

        speaker_count.change(
            fn=on_speaker_count_change,
            inputs=[speaker_count, input_mode, podcast_script],
            outputs=[podcast_script],
        )

        # Toggle input mode visibility and show sample script for multi-speaker
        def toggle_input_mode(mode, count, current_script):
            topic_visible = gr.update(visible=(mode == "topic"))
            script_visible = gr.update(visible=(mode == "script"))
            if mode == "script":
                count = int(count)
                is_empty = not current_script or not current_script.strip()
                if is_empty and count > 1:
                    return topic_visible, script_visible, gr.update(value=SAMPLE_SCRIPTS.get(count, ""))
            return topic_visible, script_visible, gr.update()

        input_mode.change(
            fn=toggle_input_mode,
            inputs=[input_mode, speaker_count, podcast_script],
            outputs=[topic_mode_group, script_mode_group, podcast_script],
        )

        with gr.Accordion("Advanced Options", open=False):
            with gr.Row():
                deep_research = gr.Checkbox(
                    label="Deep Research (more detailed content)",
                    value=False,
                )
            with gr.Row():
                background_music = gr.Audio(
                    label="Background Music (optional)",
                    type="filepath",
                    sources=["upload"],
                )
                music_volume = gr.Slider(
                    label="Music Volume",
                    minimum=0,
                    maximum=100,
                    value=25,
                    step=5,
                )

            gr.Markdown("**Voice Cloning** (select from saved voices or upload)")

            voice_files = get_voice_reference_files()
            voice_choices = [("None (No voice cloning)", "")] + voice_files

            podcast_voice_dropdowns = []
            podcast_voice_uploads = []
            podcast_voice_groups = []

            podcast_refresh_voices_btn = gr.Button("Refresh Voice List", size="sm")

            for i in range(4):
                with gr.Group(visible=(i == 0)) as voice_group:
                    gr.Markdown(f"**Speaker {i+1}**")
                    dropdown = gr.Dropdown(
                        label="Select saved voice",
                        choices=voice_choices,
                        value="",
                        interactive=True,
                    )
                    podcast_voice_dropdowns.append(dropdown)

                    with gr.Accordion("Or upload/record new", open=False):
                        upload = gr.Audio(
                            label="Upload/Record Voice",
                            type="filepath",
                            sources=["upload", "microphone"],
                        )
                        podcast_voice_uploads.append(upload)
                podcast_voice_groups.append(voice_group)

            def refresh_all_podcast_voices():
                files = get_voice_reference_files()
                choices = [("None (No voice cloning)", "")] + files
                return [gr.update(choices=choices, value="") for _ in range(4)]

            podcast_refresh_voices_btn.click(
                fn=refresh_all_podcast_voices,
                inputs=[],
                outputs=podcast_voice_dropdowns,
            )

        # Update voice group visibility when speaker count changes
        def update_voice_visibility(count):
            count = int(count)
            return [gr.update(visible=(i < count)) for i in range(4)]

        speaker_count.change(
            fn=update_voice_visibility,
            inputs=[speaker_count],
            outputs=podcast_voice_groups,
        )

        # ============================================================
        # STEP 1 — Generate Script
        # ============================================================
        gr.Markdown(
            """<div style="border-top:1px solid var(--border); margin:1.2rem 0 0.8rem; padding-top:1rem;">
            <h3 style="margin:0;">Step 1 — Generate Script</h3>
            <p style="color:var(--text-secondary); font-size:0.9rem; margin-top:0.25rem;">
            Select a topic &amp; speakers above, then generate the script. You can edit it before producing audio.</p>
            </div>"""
        )

        with gr.Row():
            generate_script_btn = gr.Button(
                "Generate Script",
                variant="primary",
                size="lg",
                scale=2,
            )
            regenerate_script_btn = gr.Button(
                "Regenerate",
                variant="secondary",
                size="lg",
                scale=1,
            )

        podcast_status = gr.Textbox(
            label="Status",
            value="Ready — choose a topic and click 'Generate Script'",
            interactive=False,
            lines=1,
        )

        script_display = gr.Textbox(
            label="Script (review & edit before generating podcast)",
            lines=12,
            max_lines=40,
            interactive=True,
            show_copy_button=True,
            placeholder="Your podcast script will appear here after Step 1.\nYou can also paste or type your own script directly.\n\nFor multi-speaker, use the format:\nSpeaker 1: Hello everyone...\nSpeaker 2: Thanks for having me...",
        )

        with gr.Row():
            script_enhance_btn2 = gr.Button(
                "Enhance Script with Tags",
                size="sm",
                elem_classes=["enhance-btn"],
            )
            word_count_display = gr.Textbox(
                label="Word count / Est. duration",
                value="",
                interactive=False,
                lines=1,
                scale=1,
            )

        # ============================================================
        # SHOW BRANDING — Intro & Outro
        # ============================================================
        with gr.Accordion("Show Branding — Intro & Outro", open=False):
            gr.Markdown(
                "<p style='color:var(--text-secondary);font-size:0.875rem;margin:0 0 0.75rem;'>"
                "Automatically prepend an intro and append an outro clip to your podcast. "
                "Background music (if set) will play across the full audio including branding segments.</p>"
            )
            show_name_input = gr.Textbox(
                label="Show Name",
                value="SurAIverse",
                placeholder="Enter your podcast show name...",
                lines=1,
            )
            with gr.Row():
                enable_intro = gr.Checkbox(label="Add Intro", value=True, scale=1)
                enable_outro = gr.Checkbox(label="Add Outro", value=True, scale=1)
                reset_branding_btn = gr.Button(
                    "Reset to Defaults", size="sm", variant="secondary", scale=1
                )

            intro_msg = gr.Textbox(
                label="Intro Message",
                value=(
                    "Welcome to SurAIverse podcast! "
                    "Today we are taking a deep dive into today's topic. Stay tuned!"
                ),
                lines=3,
                max_lines=6,
                interactive=True,
            )
            outro_msg = gr.Textbox(
                label="Outro Message",
                value=(
                    "Thanks for listening to SurAIverse. "
                    "For more interesting episodes, please subscribe to SurAIverse. "
                    "See you next episode!"
                ),
                lines=3,
                max_lines=6,
                interactive=True,
            )

            gr.Markdown(
                "<p style='color:var(--text-secondary);font-size:0.8rem;margin:0.5rem 0 0.25rem;'>"
                "<strong>Intro/Outro Voice</strong> — leave blank to use Speaker 1's voice automatically.</p>"
            )
            branding_voice_files = get_voice_reference_files()
            branding_voice_choices = [("Speaker 1 voice (default)", "")] + branding_voice_files
            branding_voice_dd = gr.Dropdown(
                label="Select saved voice",
                choices=branding_voice_choices,
                value="",
                interactive=True,
            )
            with gr.Accordion("Or upload/record intro/outro voice", open=False):
                branding_voice_up = gr.Audio(
                    label="Upload or Record Voice",
                    type="filepath",
                    sources=["upload", "microphone"],
                )

        # ============================================================
        # STEP 2 — Generate Podcast Audio
        # ============================================================
        gr.Markdown(
            """<div style="border-top:1px solid var(--border); margin:1.2rem 0 0.8rem; padding-top:1rem;">
            <h3 style="margin:0;">Step 2 — Generate Podcast Audio</h3>
            <p style="color:var(--text-secondary); font-size:0.9rem; margin-top:0.25rem;">
            Happy with the script? Click below to produce the audio.</p>
            </div>"""
        )

        generate_podcast_btn = gr.Button(
            "Generate Podcast Audio",
            variant="primary",
            size="lg",
        )

        podcast_output = gr.Audio(
            label="Your Podcast",
            type="filepath",
            interactive=False,
        )
        podcast_download = gr.File(label="Download MP4", visible=False, interactive=False)

    # ======== Event Handlers ========

    # --- Reset branding text to show-name defaults ---
    def reset_branding_text(name):
        n = (name or "").strip() or "Your Show"
        return (
            gr.update(value=(
                f"Welcome to {n} podcast! "
                f"Today we are taking a deep dive into today's topic. Stay tuned!"
            )),
            gr.update(value=(
                f"Thanks for listening to {n}. "
                f"For more interesting episodes, please subscribe to {n}. "
                f"See you next episode!"
            )),
        )

    reset_branding_btn.click(
        fn=reset_branding_text,
        inputs=[show_name_input],
        outputs=[intro_msg, outro_msg],
    )

    # --- Trending topic buttons ---
    def fetch_trending_topic(category):
        try:
            aggregator = get_news_aggregator()
            news_items = aggregator.fetch_news(category, num_results=1)
            if news_items:
                item = news_items[0]
                title = re.sub(r'\*+', '', item.get('title', ''))
                snippet = re.sub(r'\*+', '', item.get('snippet', ''))
                return f"{title}. {snippet[:200]}"
            return f"Latest news about {category}"
        except Exception:
            return f"Trending topic in {category}"

    for btn, category in trending_btns:
        btn.click(
            fn=lambda c=category: fetch_trending_topic(c),
            inputs=[],
            outputs=[podcast_topic],
        )

    # --- Word count live update ---
    def update_word_count(text):
        if not text or not text.strip():
            return gr.update(value="")
        words = len(text.split())
        est_min = round(words / 150, 1)
        return gr.update(value=f"{words} words  ~{est_min} min")

    script_display.change(
        fn=update_word_count,
        inputs=[script_display],
        outputs=[word_count_display],
    )

    # --- Enhance script button ---
    script_enhance_btn2.click(
        fn=enhance_text,
        inputs=[script_display],
        outputs=[script_display],
    )

    # --- STEP 1: Generate Script ---
    def generate_script(mode, topic, script_text, speakers, duration, research):
        """Step 1: Generate script from topic via LLM, or accept user script."""

        # If in script mode and user already pasted something, just use it
        if mode == "script":
            if not script_text or not script_text.strip():
                return (
                    gr.update(value="Please paste or upload a script in the Script input above."),
                    gr.update(),
                )
            words = len(script_text.split())
            est = round(words / 150, 1)
            return (
                gr.update(value=f"Script loaded ({words} words, ~{est} min). Edit if needed, then click 'Generate Podcast Audio'."),
                gr.update(value=script_text.strip()),
            )

        # Topic mode — generate via LLM
        if not topic or not topic.strip():
            return (
                gr.update(value="Please enter a topic or click a trending topic first."),
                gr.update(),
            )

        try:
            generator = get_podcast_generator()
        except Exception as e:
            return (
                gr.update(value=f"LLM provider error: {str(e)}. Check Settings tab."),
                gr.update(value=f"Error: Could not connect to LLM provider.\n{str(e)}"),
            )

        try:
            podcast_data = generator.generate_podcast_content(
                topic=topic.strip(),
                speaker_count=int(speakers),
                duration_minutes=float(duration),
                deep_research=research,
            )
        except Exception as e:
            return (
                gr.update(value=f"Script generation failed: {str(e)}"),
                gr.update(value=f"Error: {str(e)}\n\nPlease check your LLM settings and try again."),
            )

        segments = podcast_data.get('segments', [])
        if not segments:
            raw = podcast_data.get('content', '')
            if raw:
                segments = [{'speaker': 'Speaker 1', 'text': raw}]
            else:
                return (
                    gr.update(value="LLM returned empty content. Try again."),
                    gr.update(value="Error: Empty response from LLM."),
                )

        # Build readable script
        if int(speakers) == 1:
            full_script = segments[0].get('text', '')
        else:
            parts = []
            for seg in segments:
                speaker = seg.get('speaker', 'Speaker 1')
                text = seg.get('text', '')
                if text.strip():
                    parts.append(f"{speaker}: {text}")
            full_script = "\n\n".join(parts)

        if not full_script.strip():
            return (
                gr.update(value="Generated content was empty. Try a different topic."),
                gr.update(value=""),
            )

        words = len(full_script.split())
        est = round(words / 150, 1)
        return (
            gr.update(value=f"Script generated! ({words} words, ~{est} min). Review & edit below, then click 'Generate Podcast Audio'."),
            gr.update(value=full_script),
        )

    # Wire Step 1 buttons
    step1_inputs = [input_mode, podcast_topic, podcast_script,
                    speaker_count, duration_minutes, deep_research]
    step1_outputs = [podcast_status, script_display]

    generate_script_btn.click(
        fn=generate_script,
        inputs=step1_inputs,
        outputs=step1_outputs,
    )
    regenerate_script_btn.click(
        fn=generate_script,
        inputs=step1_inputs,
        outputs=step1_outputs,
    )

    # --- STEP 2: Generate Podcast Audio from Script ---
    def generate_podcast_audio(script_text, speakers, music, vol,
                                add_intro, intro_text, add_outro, outro_text,
                                branding_voice_dd, branding_voice_up,
                                voice_dd_1, voice_dd_2, voice_dd_3, voice_dd_4,
                                voice_up_1, voice_up_2, voice_up_3, voice_up_4):
        """Step 2: Take the (possibly edited) script and produce TTS audio."""

        if not script_text or not script_text.strip():
            return (
                gr.update(value="No script to generate audio from. Run Step 1 first or type a script."),
                None,
                gr.update(visible=False),
            )

        def get_voice_path(dropdown, upload):
            if upload and os.path.exists(str(upload)):
                return str(upload)
            if dropdown and os.path.exists(str(dropdown)):
                return str(dropdown)
            return None

        voices = [
            get_voice_path(voice_dd_1, voice_up_1),
            get_voice_path(voice_dd_2, voice_up_2),
            get_voice_path(voice_dd_3, voice_up_3),
            get_voice_path(voice_dd_4, voice_up_4),
        ]

        try:
            tts_engine = get_engine()
            num_speakers = int(speakers)
            full_script = script_text.strip()

            if num_speakers > 1:
                # Parse "Speaker N: text" format
                segments = []
                pattern = r'(Speaker\s*\d+)\s*:\s*'
                parts = re.split(pattern, full_script)
                i = 1
                while i < len(parts) - 1:
                    speaker = parts[i].strip()
                    text = parts[i + 1].strip()
                    if text:
                        segments.append({'speaker': speaker, 'text': text})
                    i += 2

                if segments:
                    voice_map = {}
                    valid_voices = [v for v in voices if v]
                    unique_speakers = list(dict.fromkeys(seg['speaker'] for seg in segments))
                    for idx, spk in enumerate(unique_speakers):
                        if idx < len(valid_voices):
                            voice_map[spk] = valid_voices[idx]

                    speech_audio = tts_engine.generate_multi_speaker_podcast(
                        segments=segments,
                        voice_paths=voice_map if voice_map else None,
                        model_type="turbo",
                        pause_duration=0.5,
                    )
                else:
                    # Could not parse speakers, single voice fallback
                    voice_path = voices[0] if voices[0] else None
                    speech_audio = tts_engine.generate_turbo(full_script, audio_prompt_path=voice_path)
            else:
                voice_path = voices[0] if voices[0] else None
                speech_audio = tts_engine.generate_turbo(full_script, audio_prompt_path=voice_path)

            # --- Intro / Outro branding ---
            from core.audio_utils import AudioProcessor as _AudioProcessor

            # Branding voice: explicit upload > explicit dropdown > Speaker 1 voice
            branding_voice = None
            if branding_voice_up and os.path.exists(str(branding_voice_up)):
                branding_voice = str(branding_voice_up)
            elif branding_voice_dd and os.path.exists(str(branding_voice_dd)):
                branding_voice = str(branding_voice_dd)
            else:
                branding_voice = voices[0]  # falls back to Speaker 1 voice (may be None)

            audio_parts = []
            if add_intro and intro_text and intro_text.strip():
                try:
                    print("[Branding] Generating intro...")
                    intro_audio = tts_engine.generate_turbo(
                        intro_text.strip(), audio_prompt_path=branding_voice
                    )
                    audio_parts.append((intro_audio, tts_engine.sample_rate))
                except Exception as e:
                    print(f"[Branding] Intro generation failed (skipping): {e}")

            audio_parts.append((speech_audio, tts_engine.sample_rate))

            if add_outro and outro_text and outro_text.strip():
                try:
                    print("[Branding] Generating outro...")
                    outro_audio = tts_engine.generate_turbo(
                        outro_text.strip(), audio_prompt_path=branding_voice
                    )
                    audio_parts.append((outro_audio, tts_engine.sample_rate))
                except Exception as e:
                    print(f"[Branding] Outro generation failed (skipping): {e}")

            if len(audio_parts) > 1:
                speech_audio, _ = _AudioProcessor.concatenate_audio(
                    audio_parts, pause_duration=0.7
                )

            # Mix background music
            final_audio = speech_audio
            if music and os.path.exists(str(music)):
                try:
                    mixer = AudioMixer(sample_rate=tts_engine.sample_rate)
                    final_audio = mixer.mix_with_file(
                        speech_audio=speech_audio,
                        speech_sample_rate=tts_engine.sample_rate,
                        background_music_path=str(music),
                        music_volume=max(0.0, min(1.0, float(vol) / 100.0)),
                        speech_volume=1.0,
                        normalize=True,
                    )
                except Exception as e:
                    print(f"Music mixing failed: {e}")

            output_path = tempfile.mktemp(suffix=".wav")
            tts_engine.save_audio(final_audio, output_path)
            mp4_path = convert_wav_to_mp4(output_path)

            word_count = len(full_script.split())
            est_duration = round(word_count / 150, 1)

            return (
                gr.update(value=f"Podcast generated successfully! (~{est_duration} min, {word_count} words)"),
                output_path,
                gr.update(value=mp4_path, visible=True),
            )

        except Exception as e:
            return (
                gr.update(value=f"Audio generation error: {str(e)}"),
                None,
                gr.update(visible=False),
            )

    # Wire Step 2 button
    generate_podcast_btn.click(
        fn=generate_podcast_audio,
        inputs=[script_display, speaker_count,
                background_music, music_volume,
                enable_intro, intro_msg, enable_outro, outro_msg,
                branding_voice_dd, branding_voice_up] + podcast_voice_dropdowns + podcast_voice_uploads,
        outputs=[podcast_status, podcast_output, podcast_download],
    )


def create_turbo_tab():
    """Create the Turbo model tab interface with Enhance button."""
    with gr.Column():
        gr.Markdown(
            """
            ### Turbo TTS
            Fast TTS with paralinguistic tags. Add emotions like `[laugh]`, `[sigh]`, `[chuckle]` in your text,
            or use the **Enhance** button to let AI add them automatically.
            """
        )

        with gr.Row():
            with gr.Column(scale=2):
                turbo_text = gr.Textbox(
                    label="Enter your text",
                    placeholder="Hello! [chuckle] How are you doing today?",
                    lines=4,
                    max_lines=8,
                    elem_id="turbo_text_input",
                )

                with gr.Row():
                    turbo_enhance_btn = gr.Button(
                        "Enhance with Tags",
                        size="sm",
                        elem_classes=["enhance-btn"],
                    )

                gr.Markdown("**Quick Tags:**")
                tags = [
                    "[clear throat]", "[sigh]", "[shush]", "[cough]", "[groan]",
                    "[sniff]", "[gasp]", "[chuckle]", "[laugh]"
                ]
                with gr.Row():
                    tag_buttons = []
                    for tag in tags:
                        btn = gr.Button(tag, size="sm", elem_classes=["tag-btn"])
                        tag_buttons.append(btn)

                gr.Markdown("**Reference Voice:**")
                voice_files = get_voice_reference_files()
                voice_choices = [("None (No voice cloning)", "")] + voice_files

                turbo_voice_dropdown = gr.Dropdown(
                    label="Select from saved voices",
                    choices=voice_choices,
                    value="",
                    interactive=True,
                )
                turbo_refresh_btn = gr.Button("Refresh Voice List", size="sm")

                with gr.Accordion("Or upload/record new voice", open=False):
                    turbo_voice_upload = gr.Audio(
                        label="Upload or Record Voice",
                        type="filepath",
                        sources=["upload", "microphone"],
                    )

            with gr.Column(scale=1):
                turbo_output = gr.Audio(label="Generated Audio", type="filepath")
                turbo_generate = gr.Button("Generate", variant="primary", size="lg")
                turbo_download = gr.File(label="Download MP4", visible=False, interactive=False)

        # Enhance button
        turbo_enhance_btn.click(
            fn=enhance_text,
            inputs=[turbo_text],
            outputs=turbo_text,
        )

        # Tag buttons — purely client-side via JS injected in gr.Blocks(js=...)
        for btn, tag in zip(tag_buttons, tags):
            btn.click(
                fn=None,
                inputs=[],
                outputs=[],
                js=f"() => window.insertTagAtCursor('{tag}')",
            )

        turbo_refresh_btn.click(
            fn=refresh_voice_references,
            inputs=[],
            outputs=[turbo_voice_dropdown],
        )

        def generate_turbo_with_voice_selection(text, voice_dropdown, voice_upload):
            voice_path = voice_upload if voice_upload else (voice_dropdown if voice_dropdown else None)
            wav_path = generate_turbo_speech(text, voice_path)
            mp4_path = convert_wav_to_mp4(wav_path)
            return wav_path, gr.update(value=mp4_path, visible=True)

        turbo_generate.click(
            fn=generate_turbo_with_voice_selection,
            inputs=[turbo_text, turbo_voice_dropdown, turbo_voice_upload],
            outputs=[turbo_output, turbo_download],
        )


def create_multilingual_tab():
    """Create the Multilingual model tab interface."""
    from core.model_manager import ModelManager
    languages = ModelManager.get_supported_languages()

    with gr.Column():
        gr.Markdown(
            """
            ### Multilingual TTS
            Generate speech in 23+ languages with zero-shot voice cloning.
            """
        )

        with gr.Row():
            with gr.Column(scale=2):
                multi_text = gr.Textbox(
                    label="Enter your text",
                    placeholder="Bonjour! Comment allez-vous aujourd'hui?",
                    lines=4,
                    max_lines=8,
                )

                multi_lang = gr.Dropdown(
                    label="Language",
                    choices=[(v, k) for k, v in languages.items()],
                    value="en",
                    interactive=True,
                )

                gr.Markdown("**Reference Voice:**")
                voice_files = get_voice_reference_files()
                voice_choices = [("None (No voice cloning)", "")] + voice_files

                multi_voice_dropdown = gr.Dropdown(
                    label="Select from saved voices",
                    choices=voice_choices,
                    value="",
                    interactive=True,
                )
                multi_refresh_btn = gr.Button("Refresh Voice List", size="sm")

                with gr.Accordion("Or upload/record new voice", open=False):
                    multi_voice_upload = gr.Audio(
                        label="Upload or Record Voice",
                        type="filepath",
                        sources=["upload", "microphone"],
                    )

            with gr.Column(scale=1):
                multi_output = gr.Audio(label="Generated Audio", type="filepath")
                multi_generate = gr.Button("Generate", variant="primary", size="lg")
                multi_download = gr.File(label="Download MP4", visible=False, interactive=False)

        multi_refresh_btn.click(
            fn=refresh_voice_references,
            inputs=[],
            outputs=[multi_voice_dropdown],
        )

        def generate_multi_with_voice_selection(text, language, voice_dropdown, voice_upload):
            voice_path = voice_upload if voice_upload else (voice_dropdown if voice_dropdown else None)
            wav_path = generate_multilingual_speech(text, language, voice_path)
            mp4_path = convert_wav_to_mp4(wav_path)
            return wav_path, gr.update(value=mp4_path, visible=True)

        multi_generate.click(
            fn=generate_multi_with_voice_selection,
            inputs=[multi_text, multi_lang, multi_voice_dropdown, multi_voice_upload],
            outputs=[multi_output, multi_download],
        )


def create_original_tab():
    """Create the Original model tab interface."""
    with gr.Column():
        gr.Markdown(
            """
            ### Original TTS
            Fine-tune your output with CFG weight and exaggeration controls.
            """
        )

        with gr.Row():
            with gr.Column(scale=2):
                orig_text = gr.Textbox(
                    label="Enter your text",
                    placeholder="The quick brown fox jumps over the lazy dog.",
                    lines=4,
                    max_lines=8,
                )

                with gr.Row():
                    orig_exaggeration = gr.Slider(
                        label="Exaggeration",
                        minimum=0.0,
                        maximum=1.0,
                        value=0.5,
                        step=0.1,
                        info="Higher = more expressive",
                    )
                    orig_cfg = gr.Slider(
                        label="CFG Weight",
                        minimum=0.0,
                        maximum=1.0,
                        value=0.5,
                        step=0.1,
                        info="Lower = slower, more deliberate",
                    )

                gr.Markdown("**Reference Voice:**")
                voice_files = get_voice_reference_files()
                voice_choices = [("None (No voice cloning)", "")] + voice_files

                orig_voice_dropdown = gr.Dropdown(
                    label="Select from saved voices",
                    choices=voice_choices,
                    value="",
                    interactive=True,
                )
                orig_refresh_btn = gr.Button("Refresh Voice List", size="sm")

                with gr.Accordion("Or upload/record new voice", open=False):
                    orig_voice_upload = gr.Audio(
                        label="Upload or Record Voice",
                        type="filepath",
                        sources=["upload", "microphone"],
                    )

            with gr.Column(scale=1):
                orig_output = gr.Audio(label="Generated Audio", type="filepath")
                orig_generate = gr.Button("Generate", variant="primary", size="lg")
                orig_download = gr.File(label="Download MP4", visible=False, interactive=False)

        orig_refresh_btn.click(
            fn=refresh_voice_references,
            inputs=[],
            outputs=[orig_voice_dropdown],
        )

        def generate_orig_with_voice_selection(text, voice_dropdown, voice_upload, exaggeration, cfg):
            voice_path = voice_upload if voice_upload else (voice_dropdown if voice_dropdown else None)
            wav_path = generate_original_speech(text, voice_path, exaggeration, cfg)
            mp4_path = convert_wav_to_mp4(wav_path)
            return wav_path, gr.update(value=mp4_path, visible=True)

        orig_generate.click(
            fn=generate_orig_with_voice_selection,
            inputs=[orig_text, orig_voice_dropdown, orig_voice_upload, orig_exaggeration, orig_cfg],
            outputs=[orig_output, orig_download],
        )


def create_settings_tab():
    """Create the Settings tab for API key and LLM provider configuration."""
    with gr.Column():
        gr.Markdown(
            """
            ### Settings
            Configure your LLM provider, API keys, and view system information.
            """
        )

        gr.Markdown(
            """
            <div class="settings-info">
            <strong>Configure your LLM provider to get started.</strong> Choose between Google Gemini (cloud) or LM Studio (local).
            Settings are stored locally in your <code>.env</code> file and are never shared.
            </div>
            """,
        )

        # --- LLM Provider Selection ---
        gr.Markdown("**LLM Provider**")

        current_provider = os.getenv("LLM_PROVIDER", "gemini").lower().strip()

        provider_radio = gr.Radio(
            label="Select LLM Provider",
            choices=[
                ("Google Gemini (Cloud)", "gemini"),
                ("LM Studio (Local)", "lmstudio"),
            ],
            value=current_provider,
            interactive=True,
            info="Choose which AI model powers podcast generation & text enhancement",
        )

        # --- Gemini Settings ---
        with gr.Group(visible=(current_provider == "gemini")) as gemini_settings_group:
            gr.Markdown("**Google Gemini Settings**")
            gemini_key_input = gr.Textbox(
                label="Google Gemini API Key",
                placeholder="AIza...",
                type="password",
                value=_get_masked_key("GOOGLE_GEMINI_API_KEY"),
                info="Required for Gemini provider. Get yours at https://aistudio.google.com/apikey",
            )

        # --- LM Studio Settings ---
        with gr.Group(visible=(current_provider == "lmstudio")) as lmstudio_settings_group:
            gr.Markdown("**LM Studio Settings**")
            lm_studio_url_input = gr.Textbox(
                label="LM Studio Server URL",
                placeholder="http://localhost:8000",
                value=os.getenv("LM_STUDIO_URL", "http://localhost:8000"),
                info="URL where LM Studio server is running (no API key needed)",
            )
            with gr.Row():
                lm_test_btn = gr.Button("Test Connection", size="sm", variant="secondary")
                lm_refresh_model_btn = gr.Button("Refresh Model", size="sm", variant="secondary")
            lm_studio_status = gr.Textbox(
                label="LM Studio Status",
                interactive=False,
                lines=2,
                value="",
            )

        # Toggle provider settings visibility
        def toggle_provider_settings(provider):
            return (
                gr.update(visible=(provider == "gemini")),
                gr.update(visible=(provider == "lmstudio")),
            )

        provider_radio.change(
            fn=toggle_provider_settings,
            inputs=[provider_radio],
            outputs=[gemini_settings_group, lmstudio_settings_group],
        )

        # Test LM Studio connection
        def test_lm_studio_connection(url):
            if not url or not url.strip():
                return "Please enter a LM Studio URL"
            url = url.strip().rstrip("/")
            try:
                import requests as req
                resp = req.get(f"{url}/v1/models", timeout=5)
                resp.raise_for_status()
                data = resp.json()
                models = data.get("data", [])
                if models:
                    model_names = [m.get("id", "unknown") for m in models]
                    return f"Connected! Available model(s):\n" + "\n".join(f"  - {n}" for n in model_names)
                else:
                    return "Connected! Just-in-time model loading active (no model loaded yet)."
            except Exception as e:
                return f"Connection failed: {str(e)}"

        lm_test_btn.click(
            fn=test_lm_studio_connection,
            inputs=[lm_studio_url_input],
            outputs=[lm_studio_status],
        )

        # Refresh model info
        def refresh_lm_studio_model(url):
            return test_lm_studio_connection(url)

        lm_refresh_model_btn.click(
            fn=refresh_lm_studio_model,
            inputs=[lm_studio_url_input],
            outputs=[lm_studio_status],
        )

        # --- HuggingFace Token ---
        gr.Markdown("**HuggingFace Token**")

        hf_token_input = gr.Textbox(
            label="HuggingFace Token",
            placeholder="hf_...",
            type="password",
            value=_get_masked_key("HUGGINGFACE_TOKEN"),
            info="Required for TTS model downloads. Get yours at https://huggingface.co/settings/tokens",
        )

        save_keys_btn = gr.Button("Save Settings", variant="primary")
        settings_status = gr.Textbox(label="Status", interactive=False, lines=1, value="")

        def save_settings(provider, gemini_key, lm_url, hf_token):
            results = []
            env_path = str(ENV_FILE_PATH)

            # Save provider selection
            try:
                os.environ["LLM_PROVIDER"] = provider
                set_key(env_path, "LLM_PROVIDER", provider)
                results.append(f"Provider: {provider}")
            except Exception as e:
                results.append(f"Provider error: {e}")

            # Save Gemini key if changed (skip if it's a masked display value)
            if gemini_key and not _is_masked_key(gemini_key):
                try:
                    os.environ["GOOGLE_GEMINI_API_KEY"] = gemini_key
                    set_key(env_path, "GOOGLE_GEMINI_API_KEY", gemini_key)
                    results.append("Gemini key saved")
                except Exception as e:
                    results.append(f"Gemini key error: {e}")

            # Save LM Studio URL
            if lm_url and lm_url.strip():
                try:
                    os.environ["LM_STUDIO_URL"] = lm_url.strip()
                    set_key(env_path, "LM_STUDIO_URL", lm_url.strip())
                    results.append("LM Studio URL saved")
                except Exception as e:
                    results.append(f"LM Studio URL error: {e}")

            # Save HuggingFace token (skip if it's a masked display value)
            if hf_token and not _is_masked_key(hf_token):
                try:
                    os.environ["HUGGINGFACE_TOKEN"] = hf_token
                    set_key(env_path, "HUGGINGFACE_TOKEN", hf_token)
                    try:
                        from huggingface_hub import login
                        login(token=hf_token, add_to_git_credential=False)
                        results.append("HuggingFace token saved & authenticated")
                    except Exception:
                        results.append("HuggingFace token saved (auth will apply on next model load)")
                except Exception as e:
                    results.append(f"HuggingFace token error: {e}")

            # Reset all LLM clients to pick up new settings
            global gemini_client, podcast_generator, news_aggregator
            gemini_client = None
            podcast_generator = None
            news_aggregator = None

            if not results:
                return "No changes to save."
            return " | ".join(results)

        save_keys_btn.click(
            fn=save_settings,
            inputs=[provider_radio, gemini_key_input, lm_studio_url_input, hf_token_input],
            outputs=[settings_status],
        )

        # Device info
        gr.Markdown("**System Info**")

        def get_device_info_text():
            try:
                import torch
                info_parts = []
                if torch.cuda.is_available():
                    info_parts.append(f"GPU: {torch.cuda.get_device_name(0)}")
                    mem = torch.cuda.get_device_properties(0).total_mem / (1024**3)
                    info_parts.append(f"VRAM: {mem:.1f} GB")
                    info_parts.append("Device: CUDA")
                elif torch.backends.mps.is_available():
                    info_parts.append("Device: Apple Silicon (MPS)")
                else:
                    info_parts.append("Device: CPU")
                info_parts.append(f"PyTorch: {torch.__version__}")
                return "\n".join(info_parts)
            except Exception as e:
                return f"Error getting device info: {e}"

        device_info = gr.Textbox(
            label="Device Information",
            value=get_device_info_text(),
            interactive=False,
            lines=4,
        )

        # About
        gr.Markdown(
            """
            ---
            **About SurAIverse TTS Studio**

            Created by **Suresh Pydikondala**
            Based on [Chatterbox TTS](https://github.com/resemble-ai/chatterbox) by Resemble AI

            YouTube: [SurAIverse](https://www.youtube.com/@suraiverse)
            """
        )


def _get_masked_key(env_var: str) -> str:
    """Get a masked version of an API key for display.

    Uses a clear prefix so save_settings can detect masked values and skip them.
    """
    val = os.getenv(env_var, "")
    if not val or val in ("your_token_here", "your_gemini_api_key_here"):
        return ""
    if len(val) > 8:
        return "****" + val[-4:]
    return "****"


def _is_masked_key(value: str) -> bool:
    """Check if a value is a masked display key (not a real key)."""
    if not value:
        return True
    # Masked keys start with **** or contain *** in the middle
    if value.startswith("****"):
        return True
    if "***" in value and len(value) < 20:
        return True
    return False


def generate_turbo_speech(text: str, voice_path: str = None) -> str:
    """Generate speech using Turbo model."""
    if not text or not text.strip():
        raise gr.Error("Please enter some text to generate speech.")

    try:
        tts = get_engine()
        wav = tts.generate_turbo(text.strip(), audio_prompt_path=voice_path)
        output_path = tempfile.mktemp(suffix=".wav")
        tts.save_audio(wav, output_path)
        return output_path
    except Exception as e:
        raise gr.Error(f"Generation failed: {str(e)}")


def generate_multilingual_speech(text: str, language: str, voice_path: str = None) -> str:
    """Generate speech using Multilingual model."""
    if not text or not text.strip():
        raise gr.Error("Please enter some text to generate speech.")

    try:
        tts = get_engine()
        wav = tts.generate_multilingual(
            text.strip(),
            language_id=language,
            audio_prompt_path=voice_path,
        )
        output_path = tempfile.mktemp(suffix=".wav")
        tts.save_audio(wav, output_path)
        return output_path
    except Exception as e:
        raise gr.Error(f"Generation failed: {str(e)}")


def generate_original_speech(
    text: str,
    voice_path: str = None,
    exaggeration: float = 0.5,
    cfg_weight: float = 0.5,
) -> str:
    """Generate speech using Original model."""
    if not text or not text.strip():
        raise gr.Error("Please enter some text to generate speech.")

    try:
        tts = get_engine()
        wav = tts.generate_original(
            text.strip(),
            audio_prompt_path=voice_path,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
        )
        output_path = tempfile.mktemp(suffix=".wav")
        tts.save_audio(wav, output_path)
        return output_path
    except Exception as e:
        raise gr.Error(f"Generation failed: {str(e)}")


def create_app():
    """Create the Gradio application."""
    with gr.Blocks(css=CUSTOM_CSS, title="SurAIverse TTS Studio", theme=gr.themes.Base(), fill_width=True, js=QUICK_TAG_JS) as app:
        # Header
        gr.HTML(
            """
            <div class="header-container">
                <div class="header-orb header-orb-1"></div>
                <div class="header-orb header-orb-2"></div>
                <div class="header-orb header-orb-3"></div>
                <div class="header-grid"></div>
                <h1 class="header-title">SurAIverse</h1>
                <h1 class="header-title-studio">TTS Studio</h1>
                <div class="header-divider"><div class="header-divider-dot"></div></div>
                <p class="header-subtitle">AI-Powered Text-to-Speech &amp; Podcast Studio</p>
                <p class="header-author">
                    Created by <strong>Suresh Pydikondala</strong>
                    <span class="header-sep">|</span>
                    <a href="https://www.youtube.com/@suraiverse" target="_blank">YouTube</a>
                </p>
            </div>
            """
        )

        # Main tabs
        with gr.Tabs():
            with gr.Tab("Podcast", id="podcast"):
                create_podcast_tab()

            with gr.Tab("Turbo TTS", id="turbo"):
                create_turbo_tab()

            with gr.Tab("Multilingual", id="multilingual"):
                create_multilingual_tab()

            with gr.Tab("Original", id="original"):
                create_original_tab()

            with gr.Tab("Settings", id="settings"):
                create_settings_tab()

        # Footer
        gr.HTML(
            """
            <div style="text-align: center; padding: 1.5rem; margin-top: 1rem;
                        border-top: 1px solid var(--border); color: var(--text-secondary);">
                <p style="margin: 0; font-size: 0.875rem;">
                    Powered by <a href="https://github.com/resemble-ai/chatterbox"
                    style="color: var(--accent);">Chatterbox TTS</a> by Resemble AI
                    &nbsp;|&nbsp; SurAIverse TTS Studio
                </p>
            </div>
            """
        )

    return app


def get_local_ip():
    """Get the local IP address for network sharing."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="SurAIverse TTS Studio")
    parser.add_argument("--share", action="store_true",
                       help="Create a public shareable link")
    parser.add_argument("--no-share", action="store_true",
                       help="Disable public sharing (local network only)")
    parser.add_argument("--port", type=int, default=None,
                       help="Server port (default: 7860)")
    args = parser.parse_args()

    share = args.share and not args.no_share

    port = args.port or int(os.getenv("GRADIO_SERVER_PORT", 7860))
    local_ip = get_local_ip()

    print("\n" + "=" * 60)
    print("  SurAIverse TTS Studio")
    print("  Created by Suresh Pydikondala")
    print("=" * 60)
    print()
    print("  Access URLs:")
    print(f"     Local:      http://localhost:{port}")
    print(f"     Network:    http://{local_ip}:{port}")
    if share:
        print("     Public:     (will show below when ready)")
    print()
    print("=" * 60 + "\n")

    app = create_app()
    app.launch(
        server_name="127.0.0.1",
        server_port=port,
        share=share,
        show_error=True,
        favicon_path=None,
        show_api=False,
    )


if __name__ == "__main__":
    main()
