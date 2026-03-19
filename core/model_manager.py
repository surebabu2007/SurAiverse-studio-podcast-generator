"""
Model Manager for Chatterbox TTS
Handles lazy loading and memory management for Mac M4.
"""

import gc
import logging
import os
import threading
import time
from enum import Enum
from typing import Any, Dict, Optional

import torch
from dotenv import load_dotenv
from huggingface_hub import login

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Available Chatterbox model types."""

    TURBO = "turbo"
    MULTILINGUAL = "multilingual"
    ORIGINAL = "original"


class ModelManager:
    """
    Manages Chatterbox model loading with lazy initialization
    and memory optimization for Mac M4.
    """

    def __init__(self, device: Optional[str] = None):
        """
        Initialize the model manager.

        Args:
            device: Target device (auto-detected if None)
        """
        load_dotenv()

        self.device = device or self._detect_device()
        self._models: Dict[ModelType, Any] = {}
        self._current_model: Optional[ModelType] = None
        self._lock = threading.Lock()  # Prevent concurrent model loads

        # Apply GPU optimizations
        self._apply_gpu_optimizations()

        # Authenticate with HuggingFace
        self._authenticate_hf()

    def _apply_gpu_optimizations(self) -> None:
        """Apply GPU-specific optimizations for faster inference."""
        if self.device == "cuda":
            # Enable cuDNN auto-tuner for optimal convolution algorithms
            torch.backends.cudnn.benchmark = True
            logger.info("CUDA optimizations enabled (cuDNN benchmark)")
        elif self.device == "mps":
            logger.info("MPS (Apple Silicon) acceleration enabled")

    def _detect_device(self) -> str:
        """Detect the best available device."""
        env_device = os.getenv("DEVICE")
        if env_device:
            return env_device

        if torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _authenticate_hf(self) -> None:
        """Authenticate with HuggingFace using token from environment."""
        token = os.getenv("HUGGINGFACE_TOKEN")
        if token and token != "your_token_here":
            try:
                login(token=token, add_to_git_credential=False)
                logger.info("HuggingFace authentication successful")
            except Exception as e:
                logger.warning("HuggingFace authentication failed: %s", e)
        else:
            logger.warning("No HuggingFace token found. Some models may not be accessible.")

    def _clear_memory(self) -> None:
        """Clear GPU/MPS memory to prevent OOM errors."""
        gc.collect()
        if self.device == "mps":
            torch.mps.empty_cache()
        elif self.device == "cuda":
            torch.cuda.empty_cache()

    def _unload_current_model(self) -> None:
        """Unload the currently loaded model to free memory."""
        if self._current_model and self._current_model in self._models:
            del self._models[self._current_model]
            self._current_model = None
            self._clear_memory()
            logger.info("Previous model unloaded to free memory")

    def get_model(self, model_type: ModelType, force_reload: bool = False) -> Any:
        """
        Get a model instance, loading it if necessary.
        Uses lazy loading to conserve memory on Mac M4.

        Args:
            model_type: Type of model to load
            force_reload: Force reload even if already loaded

        Returns:
            Loaded model instance
        """
        with self._lock:
            # Check again inside lock (another thread may have loaded it)
            if not force_reload and model_type in self._models:
                return self._models[model_type]

            # Unload current model to free memory
            if self._current_model and self._current_model != model_type:
                self._unload_current_model()

            # Load the requested model
            logger.info("Loading %s model on %s", model_type.value, self.device)
            t0 = time.perf_counter()

            try:
                model = self._load_model(model_type)
                self._models[model_type] = model
                self._current_model = model_type
                elapsed = time.perf_counter() - t0
                logger.info("%s model loaded in %.1fs", model_type.value, elapsed)
                self._log_gpu_memory()
                self._warmup_model(model, model_type)
                return model

            except Exception as e:
                self._clear_memory()
                raise RuntimeError(f"Failed to load {model_type.value} model: {e}") from e

    def _load_model(self, model_type: ModelType) -> Any:
        """Load a specific model type."""
        if model_type == ModelType.TURBO:
            from chatterbox.tts_turbo import ChatterboxTurboTTS

            return ChatterboxTurboTTS.from_pretrained(device=self.device)

        elif model_type == ModelType.MULTILINGUAL:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            return ChatterboxMultilingualTTS.from_pretrained(device=self.device)

        elif model_type == ModelType.ORIGINAL:
            from chatterbox.tts import ChatterboxTTS

            return ChatterboxTTS.from_pretrained(device=self.device)

        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def _log_gpu_memory(self) -> None:
        """Log current GPU memory usage after model load."""
        if self.device == "cuda":
            allocated = torch.cuda.memory_allocated() / 1024 ** 3
            reserved = torch.cuda.memory_reserved() / 1024 ** 3
            logger.info("GPU memory — allocated: %.2f GB, reserved: %.2f GB", allocated, reserved)
        elif self.device == "mps":
            allocated = torch.mps.current_allocated_memory() / 1024 ** 3
            logger.info("MPS memory — allocated: %.2f GB", allocated)

    def _warmup_model(self, model: Any, model_type: ModelType) -> None:
        """Run a short dummy forward pass to trigger CUDA kernel compilation."""
        try:
            logger.info("Warming up %s model...", model_type.value)
            t0 = time.perf_counter()
            with torch.inference_mode():
                if model_type == ModelType.TURBO:
                    model.generate(text="Hi")
                elif model_type == ModelType.MULTILINGUAL:
                    model.generate(text="Hi", language_id="en")
                elif model_type == ModelType.ORIGINAL:
                    model.generate(text="Hi")
            elapsed = time.perf_counter() - t0
            logger.info("%s warmup done in %.1fs", model_type.value, elapsed)
        except Exception as e:
            logger.debug("Warmup skipped (%s): %s", model_type.value, e)

    def get_turbo(self) -> Any:
        """Get the Turbo model."""
        return self.get_model(ModelType.TURBO)

    def get_multilingual(self) -> Any:
        """Get the Multilingual model."""
        return self.get_model(ModelType.MULTILINGUAL)

    def get_original(self) -> Any:
        """Get the Original model."""
        return self.get_model(ModelType.ORIGINAL)

    def get_loaded_models(self) -> list:
        """Get list of currently loaded model types."""
        return list(self._models.keys())

    def unload_all(self) -> None:
        """Unload all models from memory."""
        self._models.clear()
        self._current_model = None
        self._clear_memory()
        logger.info("All models unloaded")

    @property
    def sample_rate(self) -> int:
        """Get sample rate (consistent across all models)."""
        return 24000

    @staticmethod
    def get_supported_languages() -> Dict[str, str]:
        """Get supported languages for multilingual model."""
        return {
            "ar": "Arabic",
            "da": "Danish",
            "de": "German",
            "el": "Greek",
            "en": "English",
            "es": "Spanish",
            "fi": "Finnish",
            "fr": "French",
            "he": "Hebrew",
            "hi": "Hindi",
            "it": "Italian",
            "ja": "Japanese",
            "ko": "Korean",
            "ms": "Malay",
            "nl": "Dutch",
            "no": "Norwegian",
            "pl": "Polish",
            "pt": "Portuguese",
            "ru": "Russian",
            "sv": "Swedish",
            "sw": "Swahili",
            "tr": "Turkish",
            "zh": "Chinese",
        }

    @staticmethod
    def get_paralinguistic_tags() -> list:
        """Get available paralinguistic tags for Turbo model."""
        return [
            "[clear throat]",
            "[sigh]",
            "[shush]",
            "[cough]",
            "[groan]",
            "[sniff]",
            "[gasp]",
            "[chuckle]",
            "[laugh]",
        ]

