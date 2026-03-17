"""
Unified TTS Engine for Chatterbox
Provides a single interface for all model variants.
"""

import os
from pathlib import Path
from typing import Optional, Union, List, Dict

import torch
import torchaudio

from .audio_utils import AudioProcessor
from .model_manager import ModelManager, ModelType


class TTSEngine:
    """
    Unified Text-to-Speech engine supporting all Chatterbox models.
    Optimized for Mac M4 with MPS acceleration.
    """

    def __init__(self, device: Optional[str] = None):
        """
        Initialize the TTS engine.

        Args:
            device: Target device (auto-detected if None)
        """
        self.model_manager = ModelManager(device=device)
        self.audio_processor = AudioProcessor()
        self.device = self.model_manager.device

    @property
    def sample_rate(self) -> int:
        """Get the output sample rate."""
        return self.model_manager.sample_rate

    def generate_turbo(
        self,
        text: str,
        audio_prompt_path: Optional[Union[str, Path]] = None,
    ) -> torch.Tensor:
        """
        Generate speech using Chatterbox-Turbo model.
        Handles long text by chunking into smaller segments.

        Args:
            text: Input text (can be any length)
            audio_prompt_path: Path to reference audio for voice cloning

        Returns:
            Generated audio tensor
        """
        model = self.model_manager.get_turbo()

        # Chunk long text (Chatterbox works best with ~400 chars)
        MAX_CHUNK_SIZE = 400

        with torch.inference_mode(), self._autocast_context():
            if len(text) <= MAX_CHUNK_SIZE:
                kwargs = {"text": text}
                if audio_prompt_path:
                    kwargs["audio_prompt_path"] = str(audio_prompt_path)
                wav = model.generate(**kwargs)
                return self._process_output(wav)

            # Long text - split into chunks and concatenate
            chunks = self._split_text_into_chunks(text, MAX_CHUNK_SIZE)

            audio_segments = []
            for i, chunk in enumerate(chunks):
                kwargs = {"text": chunk}
                if audio_prompt_path:
                    kwargs["audio_prompt_path"] = str(audio_prompt_path)
                try:
                    wav = model.generate(**kwargs)
                    processed = self._process_output(wav)
                    audio_segments.append((processed, self.sample_rate))
                except Exception as e:
                    print(f"[TTS] Warning: Chunk {i+1} failed: {e}")
                    continue

            if not audio_segments:
                raise RuntimeError("All chunks failed to generate")

            from .audio_utils import AudioProcessor
            concatenated, sr = AudioProcessor.concatenate_audio(
                audio_segments, pause_duration=0.1
            )
            return concatenated

    def generate_multilingual(
        self,
        text: str,
        language_id: str = "en",
        audio_prompt_path: Optional[Union[str, Path]] = None,
    ) -> torch.Tensor:
        """
        Generate speech using Chatterbox-Multilingual model.
        Supports 23+ languages. Handles long text by chunking into segments.

        Args:
            text: Input text
            language_id: Language code (e.g., 'en', 'fr', 'zh', 'hi')
            audio_prompt_path: Path to reference audio for voice cloning

        Returns:
            Generated audio tensor
        """
        model = self.model_manager.get_multilingual()

        # Normalize language-specific punctuation before passing to library.
        # The library's punc_norm doesn't handle Devanagari danda (।), so
        # replace it with a period to prevent a spurious trailing "." being added.
        text = text.replace("।", ".").replace("॥", ".")

        # Chunk long text (same limit as Turbo — model has max_new_tokens=1000)
        MAX_CHUNK_SIZE = 400

        if len(text) <= MAX_CHUNK_SIZE:
            kwargs = {"text": text, "language_id": language_id}
            if audio_prompt_path:
                kwargs["audio_prompt_path"] = str(audio_prompt_path)
            with torch.inference_mode(), self._autocast_context():
                wav = model.generate(**kwargs)
            return self._process_output(wav)

        # Long text — split into chunks and concatenate
        chunks = self._split_text_into_chunks(text, MAX_CHUNK_SIZE)

        audio_segments = []
        for i, chunk in enumerate(chunks):
            kwargs = {"text": chunk, "language_id": language_id}
            if audio_prompt_path:
                kwargs["audio_prompt_path"] = str(audio_prompt_path)
            try:
                with torch.inference_mode(), self._autocast_context():
                    wav = model.generate(**kwargs)
                processed = self._process_output(wav)
                audio_segments.append((processed, self.sample_rate))
            except Exception as e:
                print(f"[TTS] Warning: Multilingual chunk {i+1} failed: {e}")
                continue

        if not audio_segments:
            raise RuntimeError("All multilingual chunks failed to generate")

        from .audio_utils import AudioProcessor
        concatenated, sr = AudioProcessor.concatenate_audio(
            audio_segments, pause_duration=0.1
        )
        return concatenated

    def generate_original(
        self,
        text: str,
        audio_prompt_path: Optional[Union[str, Path]] = None,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
    ) -> torch.Tensor:
        """
        Generate speech using original Chatterbox model.
        Supports CFG and exaggeration tuning.

        Args:
            text: Input text
            audio_prompt_path: Path to reference audio for voice cloning
            exaggeration: Exaggeration level (0.0-1.0, default 0.5)
            cfg_weight: CFG weight (0.0-1.0, default 0.5)

        Returns:
            Generated audio tensor
        """
        model = self.model_manager.get_original()

        kwargs = {
            "text": text,
            "exaggeration": exaggeration,
            "cfg_weight": cfg_weight,
        }
        if audio_prompt_path:
            kwargs["audio_prompt_path"] = str(audio_prompt_path)

        with torch.inference_mode(), self._autocast_context():
            wav = model.generate(**kwargs)
        return self._process_output(wav)

    def generate(
        self,
        text: str,
        model_type: str = "turbo",
        audio_prompt_path: Optional[Union[str, Path]] = None,
        language_id: str = "en",
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
    ) -> torch.Tensor:
        """
        Unified generation method supporting all models.

        Args:
            text: Input text
            model_type: Model to use ('turbo', 'multilingual', 'original')
            audio_prompt_path: Path to reference audio for voice cloning
            language_id: Language code (for multilingual model)
            exaggeration: Exaggeration level (for original model)
            cfg_weight: CFG weight (for original model)

        Returns:
            Generated audio tensor
        """
        model_type = model_type.lower()

        if model_type == "turbo":
            return self.generate_turbo(text, audio_prompt_path)
        elif model_type == "multilingual":
            return self.generate_multilingual(text, language_id, audio_prompt_path)
        elif model_type == "original":
            return self.generate_original(
                text, audio_prompt_path, exaggeration, cfg_weight
            )
        else:
            raise ValueError(
                f"Unknown model type: {model_type}. "
                f"Choose from: turbo, multilingual, original"
            )

    def _autocast_context(self):
        """Return an autocast context manager for the current device."""
        if self.device == "cuda":
            return torch.amp.autocast("cuda", dtype=torch.float16)
        # No autocast benefit on CPU/MPS — use a no-op context
        import contextlib
        return contextlib.nullcontext()

    def _process_output(self, wav: torch.Tensor) -> torch.Tensor:
        """Process and normalize output audio."""
        # Ensure correct shape
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)

        # Move to CPU for saving
        if wav.device.type != "cpu":
            wav = wav.cpu()

        return wav
    
    def _split_text_into_chunks(self, text: str, max_chunk_size: int) -> List[str]:
        """
        Split long text into chunks at sentence boundaries.
        
        Args:
            text: Input text
            max_chunk_size: Maximum characters per chunk
            
        Returns:
            List of text chunks
        """
        import re
        
        # Split on sentence boundaries (includes Devanagari danda for Hindi)
        sentences = re.split(r'(?<=[.!?।॥])\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence exceeds the limit, save current chunk
            if len(current_chunk) + len(sentence) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks

    def save_audio(
        self,
        wav: torch.Tensor,
        output_path: Union[str, Path],
    ) -> Path:
        """
        Save generated audio to file.

        Args:
            wav: Audio tensor
            output_path: Path to save audio

        Returns:
            Path to saved file
        """
        return self.audio_processor.save_audio(wav, output_path, self.sample_rate)

    def generate_and_save(
        self,
        text: str,
        output_path: Union[str, Path],
        model_type: str = "turbo",
        audio_prompt_path: Optional[Union[str, Path]] = None,
        **kwargs,
    ) -> Path:
        """
        Generate speech and save to file in one step.

        Args:
            text: Input text
            output_path: Path to save audio
            model_type: Model to use
            audio_prompt_path: Path to reference audio
            **kwargs: Additional model-specific arguments

        Returns:
            Path to saved file
        """
        wav = self.generate(
            text=text,
            model_type=model_type,
            audio_prompt_path=audio_prompt_path,
            **kwargs,
        )
        return self.save_audio(wav, output_path)

    def get_supported_languages(self) -> dict:
        """Get supported languages for multilingual model."""
        return self.model_manager.get_supported_languages()

    def get_paralinguistic_tags(self) -> list:
        """Get available paralinguistic tags for Turbo model."""
        return self.model_manager.get_paralinguistic_tags()

    def unload_models(self) -> None:
        """Unload all models to free memory."""
        self.model_manager.unload_all()

    def get_device_info(self) -> dict:
        """Get information about the current device."""
        info = {
            "device": self.device,
            "mps_available": torch.backends.mps.is_available(),
            "cuda_available": torch.cuda.is_available(),
            "loaded_models": [m.value for m in self.model_manager.get_loaded_models()],
        }

        if self.device == "mps":
            info["device_name"] = "Apple Silicon (MPS)"
        elif self.device == "cuda":
            info["device_name"] = torch.cuda.get_device_name(0)
        else:
            info["device_name"] = "CPU"

        return info
    
    def generate_batch(
        self,
        texts: List[str],
        model_type: str = "turbo",
        audio_prompt_paths: Optional[List[Optional[str]]] = None,
        **kwargs
    ) -> List[torch.Tensor]:
        """
        Generate speech for multiple text inputs in batch.
        
        Args:
            texts: List of text strings to convert to speech
            model_type: Model to use ('turbo', 'multilingual', 'original')
            audio_prompt_paths: Optional list of voice prompt paths (one per text)
            **kwargs: Additional model-specific arguments
            
        Returns:
            List of generated audio tensors
        """
        results = []
        audio_prompts = audio_prompt_paths or [None] * len(texts)
        
        for text, audio_prompt in zip(texts, audio_prompts):
            audio = self.generate(
                text=text,
                model_type=model_type,
                audio_prompt_path=audio_prompt,
                **kwargs
            )
            results.append(audio)
        
        return results
    
    def generate_multi_speaker_podcast(
        self,
        segments: List[Dict[str, str]],
        voice_paths: Optional[Dict[str, Optional[str]]] = None,
        model_type: str = "turbo",
        pause_duration: float = 0.5,
        **kwargs
    ) -> torch.Tensor:
        """
        Generate multi-speaker podcast from segments.
        
        Args:
            segments: List of dicts with 'speaker' and 'text' keys
            voice_paths: Optional dict mapping speaker names to voice paths
            model_type: Model to use ('turbo', 'multilingual', 'original')
            pause_duration: Duration of pause between segments in seconds
            **kwargs: Additional model-specific arguments
            
        Returns:
            Concatenated audio tensor for entire podcast
        """
        audio_segments = []
        failed_segments = []
        
        for idx, segment in enumerate(segments):
            speaker = segment.get('speaker', 'Speaker 1')
            text = segment.get('text', '')
            
            if not text.strip():
                continue
            
            # Get voice path for this speaker
            voice_path = None
            if voice_paths:
                voice_path = voice_paths.get(speaker) or voice_paths.get('default')
            
            # Debug: Log segment being processed (check for tags)
            has_tags = any(tag in text for tag in ['[laugh]', '[chuckle]', '[sigh]', '[gasp]', '[cough]', '[clear throat]', '[sniff]', '[groan]', '[shush]'])
            if has_tags:
                print(f"[TTS] Segment {idx+1} ({speaker}) contains paralinguistic tags. Text preview: {text[:150]}...")
            
            # Generate audio for this segment (with error handling)
            try:
                audio = self.generate(
                    text=text,
                    model_type=model_type,
                    audio_prompt_path=voice_path,
                    **kwargs
                )
                
                # Validate audio was generated
                if audio is None or audio.numel() == 0:
                    raise ValueError(f"Empty audio generated for segment {idx + 1}")
                
                # Convert to tuple format for concatenation
                audio_segments.append((audio, self.sample_rate))
            except Exception as e:
                # Log failed segment but continue with others
                failed_segments.append((idx + 1, speaker, str(e)))
                print(f"Warning: Failed to generate audio for segment {idx + 1} (Speaker: {speaker}): {e}")
                # Continue with next segment instead of failing entirely
        
        # Concatenate all segments with pauses
        if not audio_segments:
            error_msg = "No audio segments to concatenate - all segments failed or were empty"
            if failed_segments:
                error_msg += f". Failed segments: {len(failed_segments)}"
            raise ValueError(error_msg)
        
        # Warn if some segments failed
        if failed_segments:
            print(f"Warning: {len(failed_segments)} segment(s) failed to generate, continuing with {len(audio_segments)} successful segments")
        
        try:
            from .audio_utils import AudioProcessor
            concatenated, sr = AudioProcessor.concatenate_audio(
                audio_segments,
                pause_duration=pause_duration
            )
        except Exception as e:
            raise RuntimeError(f"Failed to concatenate audio segments: {str(e)}")
        
        return concatenated

