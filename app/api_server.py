"""
Chatterbox TTS FastAPI Server
REST API for text-to-speech generation.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from core.tts_engine import TTSEngine
from core.model_manager import ModelManager

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Chatterbox TTS API",
    description="REST API for Chatterbox Text-to-Speech generation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware for web integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global TTS engine (lazy loaded)
_engine: Optional[TTSEngine] = None


def get_engine() -> TTSEngine:
    """Get or initialize the TTS engine."""
    global _engine
    if _engine is None:
        _engine = TTSEngine()
    return _engine


# Request/Response Models
class GenerateRequest(BaseModel):
    """Request model for text-to-speech generation."""

    text: str = Field(..., description="Text to convert to speech", min_length=1)
    model: str = Field(
        default="turbo",
        description="Model variant: turbo, multilingual, or original",
    )
    language: str = Field(
        default="en",
        description="Language code for multilingual model",
    )
    exaggeration: float = Field(
        default=0.5,
        description="Exaggeration level for original model (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    cfg_weight: float = Field(
        default=0.5,
        description="CFG weight for original model (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )


class GenerateResponse(BaseModel):
    """Response model for generation status."""

    success: bool
    message: str
    audio_url: Optional[str] = None


class LanguageInfo(BaseModel):
    """Language information model."""

    code: str
    name: str


class DeviceInfo(BaseModel):
    """Device information model."""

    device: str
    device_name: str
    mps_available: bool
    cuda_available: bool
    loaded_models: list


# API Endpoints
@app.get("/", response_class=JSONResponse)
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Chatterbox TTS API",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "generate": "/api/generate",
            "generate_with_voice": "/api/generate-with-voice",
            "languages": "/api/languages",
            "tags": "/api/tags",
            "info": "/api/info",
            "health": "/api/health",
        },
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "chatterbox-tts"}


@app.get("/api/info", response_model=DeviceInfo)
async def get_device_info():
    """Get device and system information."""
    try:
        engine = get_engine()
        info = engine.get_device_info()
        return DeviceInfo(**info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/languages", response_model=list[LanguageInfo])
async def get_languages():
    """Get supported languages for multilingual model."""
    langs = ModelManager.get_supported_languages()
    return [LanguageInfo(code=k, name=v) for k, v in langs.items()]


@app.get("/api/tags")
async def get_tags():
    """Get available paralinguistic tags for Turbo model."""
    return {
        "tags": ModelManager.get_paralinguistic_tags(),
        "usage": "Add tags directly in your text, e.g., 'Hello [laugh] there!'",
    }


@app.post("/api/generate")
async def generate_speech(request: GenerateRequest):
    """
    Generate speech from text.

    Returns the generated audio file.
    """
    try:
        engine = get_engine()

        # Build kwargs based on model
        kwargs = {}
        if request.model == "multilingual":
            kwargs["language_id"] = request.language
        elif request.model == "original":
            kwargs["exaggeration"] = request.exaggeration
            kwargs["cfg_weight"] = request.cfg_weight

        # Generate audio
        wav = engine.generate(
            text=request.text,
            model_type=request.model,
            **kwargs,
        )

        # Save to temp file
        output_path = tempfile.mktemp(suffix=".wav")
        engine.save_audio(wav, output_path)

        return FileResponse(
            output_path,
            media_type="audio/wav",
            filename="generated_speech.wav",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-with-voice")
async def generate_speech_with_voice(
    text: str = Form(..., description="Text to convert to speech"),
    model: str = Form(default="turbo", description="Model variant"),
    language: str = Form(default="en", description="Language code"),
    exaggeration: float = Form(default=0.5, description="Exaggeration level"),
    cfg_weight: float = Form(default=0.5, description="CFG weight"),
    voice_file: UploadFile = File(..., description="Reference voice audio"),
):
    """
    Generate speech with voice cloning from uploaded audio file.

    Accepts multipart form data with audio file upload.
    """
    try:
        engine = get_engine()

        # Save uploaded voice file temporarily
        voice_path = tempfile.mktemp(suffix=Path(voice_file.filename).suffix)
        with open(voice_path, "wb") as f:
            content = await voice_file.read()
            f.write(content)

        # Build kwargs based on model
        kwargs = {}
        if model == "multilingual":
            kwargs["language_id"] = language
        elif model == "original":
            kwargs["exaggeration"] = exaggeration
            kwargs["cfg_weight"] = cfg_weight

        # Generate audio with voice cloning
        wav = engine.generate(
            text=text,
            model_type=model,
            audio_prompt_path=voice_path,
            **kwargs,
        )

        # Clean up voice file
        os.unlink(voice_path)

        # Save output
        output_path = tempfile.mktemp(suffix=".wav")
        engine.save_audio(wav, output_path)

        return FileResponse(
            output_path,
            media_type="audio/wav",
            filename="generated_speech.wav",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/unload-models")
async def unload_models():
    """Unload all models from memory."""
    try:
        engine = get_engine()
        engine.unload_models()
        return {"success": True, "message": "All models unloaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run the API server."""
    import uvicorn

    port = int(os.getenv("API_SERVER_PORT", 8000))

    print("\n" + "=" * 50)
    print("  🎙️ Chatterbox TTS - API Server")
    print(f"  Docs: http://localhost:{port}/docs")
    print("=" * 50 + "\n")

    uvicorn.run(
        "app.api_server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()

