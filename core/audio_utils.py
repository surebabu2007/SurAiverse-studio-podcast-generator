"""
Audio Processing Utilities for Chatterbox TTS
Handles audio loading, saving, and preprocessing.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torchaudio


class AudioProcessor:
    """Handles audio processing for TTS operations."""

    SUPPORTED_FORMATS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
    DEFAULT_SAMPLE_RATE = 24000  # Chatterbox default

    @staticmethod
    def get_device() -> str:
        """Get the best available device for audio processing."""
        if torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        return "cpu"

    @classmethod
    def load_audio(
        cls,
        audio_path: Union[str, Path],
        target_sr: Optional[int] = None,
    ) -> Tuple[torch.Tensor, int]:
        """
        Load audio file and optionally resample.

        Args:
            audio_path: Path to audio file
            target_sr: Target sample rate (None keeps original)

        Returns:
            Tuple of (audio_tensor, sample_rate)
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if audio_path.suffix.lower() not in cls.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: {audio_path.suffix}. "
                f"Supported: {cls.SUPPORTED_FORMATS}"
            )

        waveform, sr = torchaudio.load(str(audio_path))

        # Convert stereo to mono if needed
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        # Resample if needed
        if target_sr and sr != target_sr:
            resampler = torchaudio.transforms.Resample(sr, target_sr)
            waveform = resampler(waveform)
            sr = target_sr

        return waveform, sr

    @classmethod
    def save_audio(
        cls,
        waveform: torch.Tensor,
        output_path: Union[str, Path],
        sample_rate: int,
    ) -> Path:
        """
        Save audio tensor to file.

        Args:
            waveform: Audio tensor (1, samples) or (samples,)
            output_path: Path to save audio
            sample_rate: Sample rate of audio

        Returns:
            Path to saved file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Ensure correct shape
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)

        # Move to CPU for saving
        if waveform.device.type != "cpu":
            waveform = waveform.cpu()

        torchaudio.save(str(output_path), waveform, sample_rate)
        return output_path

    @classmethod
    def validate_reference_audio(
        cls,
        audio_path: Union[str, Path],
        min_duration: float = 3.0,
        max_duration: float = 30.0,
    ) -> Tuple[bool, str]:
        """
        Validate reference audio for voice cloning.

        Args:
            audio_path: Path to audio file
            min_duration: Minimum duration in seconds
            max_duration: Maximum duration in seconds

        Returns:
            Tuple of (is_valid, message)
        """
        try:
            waveform, sr = cls.load_audio(audio_path)
            duration = waveform.shape[1] / sr

            if duration < min_duration:
                return False, f"Audio too short ({duration:.1f}s). Minimum: {min_duration}s"

            if duration > max_duration:
                return False, f"Audio too long ({duration:.1f}s). Maximum: {max_duration}s"

            return True, f"Valid audio: {duration:.1f}s at {sr}Hz"

        except Exception as e:
            return False, f"Error loading audio: {str(e)}"

    @classmethod
    def trim_silence(
        cls,
        waveform: torch.Tensor,
        threshold_db: float = -40.0,
        min_silence_duration: float = 0.1,
        sample_rate: int = 24000,
    ) -> torch.Tensor:
        """
        Trim leading and trailing silence from audio.

        Args:
            waveform: Audio tensor
            threshold_db: Silence threshold in dB
            min_silence_duration: Minimum silence duration to trim
            sample_rate: Sample rate of audio

        Returns:
            Trimmed audio tensor
        """
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)

        # Convert threshold to linear
        threshold = 10 ** (threshold_db / 20)

        # Get absolute values
        abs_audio = torch.abs(waveform[0])

        # Find non-silent regions
        non_silent = abs_audio > threshold

        if not non_silent.any():
            return waveform

        # Find start and end indices
        non_silent_indices = torch.where(non_silent)[0]
        start_idx = max(0, non_silent_indices[0].item() - int(0.1 * sample_rate))
        end_idx = min(len(abs_audio), non_silent_indices[-1].item() + int(0.1 * sample_rate))

        return waveform[:, start_idx:end_idx]

    @classmethod
    def normalize_audio(
        cls,
        waveform: torch.Tensor,
        target_db: float = -3.0,
    ) -> torch.Tensor:
        """
        Normalize audio to target dB level.

        Args:
            waveform: Audio tensor
            target_db: Target peak level in dB

        Returns:
            Normalized audio tensor
        """
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)

        # Get current peak
        current_peak = torch.max(torch.abs(waveform))

        if current_peak == 0:
            return waveform

        # Calculate gain
        target_linear = 10 ** (target_db / 20)
        gain = target_linear / current_peak

        return waveform * gain

    @classmethod
    def create_temp_file(cls, suffix: str = ".wav") -> str:
        """Create a temporary file path for audio."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        return path
    
    # Resampler cache: avoids re-creating Resample transforms for the same rate pair
    _resampler_cache: Dict[Tuple[int, int], torchaudio.transforms.Resample] = {}

    @classmethod
    def _get_resampler(cls, src_sr: int, tgt_sr: int) -> torchaudio.transforms.Resample:
        """Return a cached Resample transform for the given rate pair."""
        key = (src_sr, tgt_sr)
        if key not in cls._resampler_cache:
            cls._resampler_cache[key] = torchaudio.transforms.Resample(src_sr, tgt_sr)
        return cls._resampler_cache[key]

    @classmethod
    def concatenate_audio(
        cls,
        audio_segments: List[Tuple[torch.Tensor, int]],
        pause_duration: float = 0.5,
    ) -> Tuple[torch.Tensor, int]:
        """
        Concatenate multiple audio segments with optional pauses.

        Uses a single torch.cat call over a pre-built list to avoid the O(N²)
        intermediate tensor copies produced by iterative cat.

        Args:
            audio_segments: List of (waveform, sample_rate) tuples
            pause_duration: Duration of pause between segments in seconds

        Returns:
            Tuple of (concatenated_waveform, sample_rate)
        """
        if not audio_segments:
            raise ValueError("No audio segments provided")

        # Get sample rate from first segment (assume all have same rate)
        sample_rate = audio_segments[0][1]

        # Create pause tensor once
        pause_samples = int(pause_duration * sample_rate)
        pause = torch.zeros(1, pause_samples)

        # Build flat list: [seg0, pause, seg1, pause, seg2, ...]
        parts: List[torch.Tensor] = []
        for idx, (waveform, sr) in enumerate(audio_segments):
            if sr != sample_rate:
                waveform = cls._get_resampler(sr, sample_rate)(waveform)

            # Ensure mono and correct shape
            if waveform.dim() == 1:
                waveform = waveform.unsqueeze(0)
            elif waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            if idx > 0:
                parts.append(pause)
            parts.append(waveform)

        return torch.cat(parts, dim=1), sample_rate
    
    @classmethod
    def pad_audio(
        cls,
        waveform: torch.Tensor,
        target_length: int,
        mode: str = "center"
    ) -> torch.Tensor:
        """
        Pad audio to target length.
        
        Args:
            waveform: Audio tensor (1, samples) or (samples,)
            target_length: Target length in samples
            mode: Padding mode: "center", "start", or "end"
            
        Returns:
            Padded audio tensor
        """
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)
        
        current_length = waveform.shape[1]
        
        if current_length >= target_length:
            # Trim if longer
            return waveform[:, :target_length]
        
        padding_needed = target_length - current_length
        
        if mode == "center":
            pad_start = padding_needed // 2
            pad_end = padding_needed - pad_start
            return torch.nn.functional.pad(waveform, (pad_start, pad_end))
        elif mode == "start":
            return torch.nn.functional.pad(waveform, (padding_needed, 0))
        elif mode == "end":
            return torch.nn.functional.pad(waveform, (0, padding_needed))
        else:
            raise ValueError(f"Unknown padding mode: {mode}")

