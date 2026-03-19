"""
Podcast Generator
Orchestrates podcast content generation with multi-speaker support.
Supports both Google Gemini and LM Studio as LLM providers.
"""

import os
from typing import List, Dict, Optional, Union
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def get_llm_client(provider: Optional[str] = None, gemini_api_key: Optional[str] = None, lm_studio_url: Optional[str] = None):
    """
    Get the appropriate LLM client based on provider setting.

    Args:
        provider: "gemini" or "lmstudio". If None, reads from LLM_PROVIDER env var.
        gemini_api_key: Optional Gemini API key override.
        lm_studio_url: Optional LM Studio URL override.

    Returns:
        A client instance (GeminiClient or LMStudioClient).
    """
    provider = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower().strip()

    if provider == "lmstudio":
        from .lmstudio_client import LMStudioClient
        return LMStudioClient(base_url=lm_studio_url)
    else:
        from .gemini_client import GeminiClient
        return GeminiClient(api_key=gemini_api_key)


class PodcastGenerator:
    """
    Generates podcast content with single or multi-speaker support.
    """

    def __init__(self, gemini_api_key: Optional[str] = None, provider: Optional[str] = None, lm_studio_url: Optional[str] = None):
        """
        Initialize podcast generator.

        Args:
            gemini_api_key: Google Gemini API key (optional, loads from env if not provided)
            provider: LLM provider - "gemini" or "lmstudio" (optional, loads from env)
            lm_studio_url: LM Studio server URL (optional, loads from env)
        """
        self.llm_client = get_llm_client(
            provider=provider,
            gemini_api_key=gemini_api_key,
            lm_studio_url=lm_studio_url
        )
        # Keep backward-compatible alias
        self.gemini_client = self.llm_client

    def generate_podcast_content(
        self,
        topic: str,
        speaker_count: int = 1,
        duration_minutes: float = 5.0,
        deep_research: bool = False
    ) -> Dict[str, Union[str, List[Dict[str, str]]]]:
        """
        Generate podcast content.

        Args:
            topic: Topic to generate content about, or URL
            speaker_count: Number of speakers (1-4)
            duration_minutes: Target duration in minutes (1-10)
            deep_research: Whether to do deep research

        Returns:
            Dictionary with:
            - 'content': Full content string (for single speaker)
            - 'segments': List of speaker segments (for multi-speaker)
            - 'speaker_count': Number of speakers
        """
        # Generate content using LLM client
        content = self.llm_client.generate_podcast_content(
            topic=topic,
            speaker_count=speaker_count,
            duration_minutes=duration_minutes,
            deep_research=deep_research
        )

        # Parse content based on speaker count
        if speaker_count == 1:
            return {
                'content': content,
                'segments': [{'speaker': 'Speaker 1', 'text': content}],
                'speaker_count': 1
            }
        else:
            # Parse multi-speaker content
            segments = self.llm_client.parse_multi_speaker_content(content)
            return {
                'content': content,
                'segments': segments,
                'speaker_count': speaker_count
            }

    def prepare_tts_segments(
        self,
        podcast_data: Dict[str, Union[str, List[Dict[str, str]]]]
    ) -> List[Dict[str, str]]:
        """
        Prepare segments for TTS generation.

        Args:
            podcast_data: Dictionary from generate_podcast_content

        Returns:
            List of segments with speaker and text
        """
        return podcast_data['segments']

    def get_speaker_mapping(
        self,
        segments: List[Dict[str, str]]
    ) -> Dict[str, int]:
        """
        Get mapping of speaker names to indices.

        Args:
            segments: List of speaker segments

        Returns:
            Dictionary mapping speaker names to indices
        """
        unique_speakers = []
        for seg in segments:
            speaker = seg['speaker']
            if speaker not in unique_speakers:
                unique_speakers.append(speaker)

        return {speaker: idx for idx, speaker in enumerate(unique_speakers)}

    def translate_script(self, text: str, target_language_name: str) -> str:
        """Translate a podcast script to the target language via the LLM client."""
        return self.llm_client.translate_script(text, target_language_name)
