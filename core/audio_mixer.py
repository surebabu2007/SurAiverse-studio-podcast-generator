"""
Audio Mixing Utilities
Handles background music mixing with volume control and looping.
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple, Union
import numpy as np
import torch
import torchaudio

from .audio_utils import AudioProcessor


class AudioMixer:
    """
    Mixes background music with speech audio.
    """
    
    def __init__(self, sample_rate: int = 24000):
        """
        Initialize audio mixer.
        
        Args:
            sample_rate: Target sample rate for mixing
        """
        self.sample_rate = sample_rate
    
    def load_background_music(
        self,
        music_path: Union[str, Path],
        target_duration: Optional[float] = None
    ) -> Tuple[torch.Tensor, int]:
        """
        Load background music and optionally loop/extend to target duration.
        
        Args:
            music_path: Path to background music file
            target_duration: Target duration in seconds (if None, use original)
            
        Returns:
            Tuple of (audio_tensor, sample_rate)
        """
        music_path = Path(music_path)
        
        if not music_path.exists():
            raise FileNotFoundError(f"Background music file not found: {music_path}")
        
        # Load audio (handles format errors)
        try:
            waveform, sr = AudioProcessor.load_audio(music_path, target_sr=self.sample_rate)
        except Exception as e:
            raise ValueError(
                f"Failed to load audio file '{music_path}': {str(e)}. "
                f"Supported formats: {', '.join(AudioProcessor.SUPPORTED_FORMATS)}"
            )
        
        # If target duration specified and music is shorter, loop it
        if target_duration is not None:
            current_duration = waveform.shape[1] / sr
            if current_duration < target_duration:
                # Calculate how many loops needed
                num_loops = int(np.ceil(target_duration / current_duration))
                # Repeat the waveform
                waveform = waveform.repeat(1, num_loops)
                # Trim to exact target duration
                target_samples = int(target_duration * sr)
                waveform = waveform[:, :target_samples]
            elif current_duration > target_duration:
                # Trim to target duration
                target_samples = int(target_duration * sr)
                waveform = waveform[:, :target_samples]
        
        return waveform, sr
    
    def mix_audio(
        self,
        speech_audio: torch.Tensor,
        background_music: torch.Tensor,
        music_volume: float = 0.3,
        speech_volume: float = 1.0,
        normalize: bool = True
    ) -> torch.Tensor:
        """
        Mix speech audio with background music.
        
        Args:
            speech_audio: Speech audio tensor (1, samples) or (samples,)
            background_music: Background music tensor (1, samples) or (samples,)
            music_volume: Background music volume (0.0 to 1.0, default 0.3 = 30%)
            speech_volume: Speech volume (0.0 to 1.0, default 1.0 = 100%)
            normalize: Whether to normalize final output to prevent clipping
            
        Returns:
            Mixed audio tensor
        """
        # Ensure correct shapes
        if speech_audio.dim() == 1:
            speech_audio = speech_audio.unsqueeze(0)
        if background_music.dim() == 1:
            background_music = background_music.unsqueeze(0)
        
        # Ensure same sample rate (should already be, but double check)
        speech_samples = speech_audio.shape[1]
        music_samples = background_music.shape[1]
        
        # Match lengths - trim or pad music to match speech
        if music_samples < speech_samples:
            # Loop music if shorter
            num_loops = int(np.ceil(speech_samples / music_samples))
            background_music = background_music.repeat(1, num_loops)
            background_music = background_music[:, :speech_samples]
        elif music_samples > speech_samples:
            # Trim music if longer
            background_music = background_music[:, :speech_samples]
        
        # Apply volume scaling
        speech_scaled = speech_audio * speech_volume
        music_scaled = background_music * music_volume
        
        # Mix audio (simple addition)
        mixed = speech_scaled + music_scaled
        
        # Normalize to prevent clipping
        if normalize:
            mixed = self._normalize_audio(mixed)
        
        return mixed
    
    def _normalize_audio(self, audio: torch.Tensor, target_db: float = -3.0) -> torch.Tensor:
        """
        Normalize audio to prevent clipping.
        
        Args:
            audio: Audio tensor
            target_db: Target peak level in dB (default -3.0 to leave headroom)
            
        Returns:
            Normalized audio tensor
        """
        if audio.dim() == 1:
            audio = audio.unsqueeze(0)
        
        # Get current peak
        current_peak = torch.max(torch.abs(audio))
        
        if current_peak == 0:
            return audio
        
        # Calculate gain to normalize to target_db
        target_linear = 10 ** (target_db / 20)
        gain = target_linear / current_peak
        
        # Only apply gain if it would reduce amplitude (prevent amplification above 0dB)
        if gain < 1.0:
            audio = audio * gain
        
        return audio
    
    def mix_with_file(
        self,
        speech_audio: torch.Tensor,
        speech_sample_rate: int,
        background_music_path: Union[str, Path],
        music_volume: float = 0.3,
        speech_volume: float = 1.0,
        normalize: bool = True
    ) -> torch.Tensor:
        """
        Mix speech audio with background music from file.
        
        Args:
            speech_audio: Speech audio tensor
            speech_sample_rate: Sample rate of speech audio
            background_music_path: Path to background music file
            music_volume: Background music volume (0.0 to 1.0)
            speech_volume: Speech volume (0.0 to 1.0)
            normalize: Whether to normalize final output
            
        Returns:
            Mixed audio tensor at speech_sample_rate
        """
        # Calculate speech duration
        speech_duration = speech_audio.shape[1] / speech_sample_rate
        
        # Load and prepare background music
        background_music, _ = self.load_background_music(
            background_music_path,
            target_duration=speech_duration
        )
        
        # Ensure speech is at correct sample rate
        if speech_sample_rate != self.sample_rate:
            speech_audio = AudioProcessor._get_resampler(speech_sample_rate, self.sample_rate)(speech_audio)
            speech_sample_rate = self.sample_rate
        
        # Mix audio
        mixed = self.mix_audio(
            speech_audio,
            background_music,
            music_volume=music_volume,
            speech_volume=speech_volume,
            normalize=normalize
        )
        
        return mixed
    
    def concatenate_audio_segments(
        self,
        segments: List[torch.Tensor],
        sample_rate: int,
        pause_duration: float = 0.5
    ) -> torch.Tensor:
        """
        Concatenate multiple audio segments with optional pauses.
        
        Args:
            segments: List of audio tensors to concatenate
            sample_rate: Sample rate of audio segments
            pause_duration: Duration of pause between segments in seconds
            
        Returns:
            Concatenated audio tensor
        """
        if not segments:
            raise ValueError("No audio segments provided")
        
        # Ensure all segments have correct shape
        processed_segments = []
        for seg in segments:
            if seg.dim() == 1:
                seg = seg.unsqueeze(0)
            processed_segments.append(seg)
        
        # Create pause (silence)
        pause_samples = int(pause_duration * sample_rate)
        pause = torch.zeros(1, pause_samples)

        # Build flat list then call torch.cat once — avoids O(N²) intermediate copies
        parts = []
        for idx, seg in enumerate(processed_segments):
            if idx > 0:
                parts.append(pause)
            parts.append(seg)

        return torch.cat(parts, dim=1)

