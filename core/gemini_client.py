"""
Google Gemini API Client for Content Generation
Handles podcast content generation with paralinguistic tags and duration matching.
Uses the new google.genai package (replacing deprecated google.generativeai).
"""

import logging
import os
import re
from typing import Optional, List, Dict
from urllib.parse import urlparse
import requests
from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from .text_utils import (
    PARALINGUISTIC_TAGS, AVERAGE_WPM, strip_paralinguistic_tags,
    estimate_word_count, clean_content_for_tts,
    enhance_paralinguistic_tags, inject_natural_paralinguistic_tags,
)

load_dotenv()

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Client for Google Gemini API to generate podcast content.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client.
        
        Args:
            api_key: Google Gemini API key. If None, loads from environment.
        """
        self.api_key = api_key or os.getenv("GOOGLE_GEMINI_API_KEY")
        
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            raise ValueError(
                "Google Gemini API key not found. "
                "Set GOOGLE_GEMINI_API_KEY in .env file or pass api_key parameter. "
                "Get your key from: https://makersuite.google.com/app/apikey"
            )
        
        if genai is None:
            raise ImportError(
                "google-genai package not installed. "
                "Install with: pip install google-genai"
            )
        
        # Initialize the client with API key
        self.client = genai.Client(api_key=self.api_key)
        
        # Try models in order of preference
        self.model_name = None
        model_errors = []
        
        models_to_try = [
            'gemini-3-flash-preview',
            'gemini-2.5-flash-preview-05-20',
            'gemini-2.5-flash',
            'gemini-2.0-flash',
            'gemini-1.5-flash',
        ]
        
        for model_name in models_to_try:
            try:
                # Test the model with a simple request
                response = self.client.models.generate_content(
                    model=model_name,
                    contents="Hello"
                )
                self.model_name = model_name
                logger.info("Successfully initialized %s", model_name)
                break
            except Exception as e:
                error_str = str(e)
                if "404" not in error_str and "not found" not in error_str.lower():
                    model_errors.append(f"{model_name}: {error_str[:100]}")
                continue
        
        if self.model_name is None:
            error_msg = "Failed to initialize any Gemini model."
            if model_errors:
                error_msg += "\nErrors encountered:\n" + "\n".join(model_errors[:5])
            raise RuntimeError(
                f"{error_msg}\n\n"
                f"Please check:\n"
                f"1. Your API key is valid: {self.api_key[:10]}...\n"
                f"2. Your project has Gemini API enabled in Google Cloud Console"
            )
        
        # Create a model wrapper for backward compatibility
        self.model = self._ModelWrapper(self.client, self.model_name)

        # Reusable HTTP session for URL content extraction
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    class _ModelWrapper:
        """Wrapper to provide backward-compatible model.generate_content() interface."""
        def __init__(self, client, model_name):
            self._client = client
            self._model_name = model_name
        
        def generate_content(self, prompt):
            return self._client.models.generate_content(
                model=self._model_name,
                contents=prompt
            )
    
    def _estimate_word_count(self, duration_minutes: float) -> int:
        """Estimate target word count for a given duration."""
        return estimate_word_count(duration_minutes)

    def _clean_content_for_tts(self, content: str) -> str:
        """Clean content for TTS by removing markdown formatting.

        Preserves Speaker labels (Speaker N:) and paralinguistic tags.
        """
        return clean_content_for_tts(content)

    def _inject_natural_paralinguistic_tags(self, content: str, min_tags: int = 3) -> str:
        """Inject paralinguistic tags only at clearly appropriate conversation points."""
        return inject_natural_paralinguistic_tags(content, min_tags)
    
    def _extract_url_content(self, url: str) -> str:
        """Extract text content from a URL."""
        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            
            text = response.text
            if not text:
                raise ValueError("URL returned empty content")
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text)
            if not text.strip():
                raise ValueError("No readable content found in URL")
            return text[:5000]
        except requests.Timeout:
            raise ValueError("URL request timed out.")
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch URL: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to extract content from URL: {str(e)}")
    
    def _build_prompt(
        self,
        topic: str,
        speaker_count: int,
        duration_minutes: float,
        deep_research: bool,
        is_url: bool = False
    ) -> str:
        """Build prompt for Gemini API."""
        target_words = self._estimate_word_count(duration_minutes)

        if speaker_count == 1:
            prompt = f"""You are a professional podcast scriptwriter. Write a polished, broadcast-ready solo podcast script.

Topic: {topic}
Target length: approximately {target_words} words

STYLE & TONE:
- Write like a top-tier podcast host (think NPR, TED Radio Hour, or Lex Fridman)
- Use warm, conversational language — talk TO the listener, not AT them
- Explain concepts through stories, analogies, and relatable examples — NOT technical jargon
- Build a narrative arc: hook the listener, build interest, deliver insights, close with impact
- Use short, punchy sentences mixed with longer flowing ones for rhythm
- Avoid bullet-point style, academic language, or listicle formatting
- NO markdown formatting (no **, no ##, no bullet points)

PARALINGUISTIC TAGS (for natural speech expression):
- Available: {', '.join(PARALINGUISTIC_TAGS)}
- Place tags INLINE within sentences only where they feel genuinely natural
- Use ONLY when the emotion logically fits the content:
  * [chuckle] — after a genuinely funny or ironic observation
  * [laugh] — after something truly hilarious
  * [sigh] — before a reflective or bittersweet moment
  * [gasp] — before truly surprising or shocking information
  * [clear throat] — at a major topic transition (use sparingly, max 1-2 times)
- Maximum 3-5 tags for the entire script — quality over quantity
- NEVER place tags randomly or at the start/end of every paragraph
- NEVER put tags on separate lines — always inline
- If the content doesn't warrant a specific emotion, DON'T force a tag

STRUCTURE:
- Open with a compelling hook that grabs attention
- Develop the topic naturally with insights and context
- Close with a memorable takeaway or thought-provoking conclusion

OUTPUT: Return ONLY the script text. No titles, no headers, no stage directions, no metadata."""

            if deep_research:
                prompt += """

DEPTH: Go beyond surface-level facts. Include real-world consequences, at least one counterintuitive insight, and an analogy that makes a complex idea immediately relatable. Build toward a moment of revelation — something the listener didn't expect to hear."""

            if is_url:
                prompt += """

SOURCE: Focus on the key insights from the provided URL content. Explain and contextualize the main points engagingly."""

        else:
            speaker_names = [f"Speaker {i+1}" for i in range(speaker_count)]
            names_str = ", ".join(speaker_names)

            prompt = f"""You are a professional podcast scriptwriter. Write a polished, broadcast-ready conversation between {speaker_count} speakers.

Topic: {topic}
Speakers: {names_str}
Target length: approximately {target_words} words total

STYLE & TONE:
- Write like a top-tier conversational podcast (think Joe Rogan, Freakonomics, or The Daily)
- Each speaker should have a DISTINCT personality and perspective:
  * Speaker 1: The curious host who guides the conversation, asks great questions
  * Speaker 2: The knowledgeable guest who shares insights with enthusiasm"""

            if speaker_count >= 3:
                prompt += """
  * Speaker 3: The contrarian or fresh perspective — challenges assumptions"""
            if speaker_count >= 4:
                prompt += """
  * Speaker 4: The storyteller — connects topics to real-world experiences"""

            prompt += f"""
- Create genuine back-and-forth: speakers react to each other, build on points, respectfully disagree
- Include micro-reactions: "Yeah, exactly.", "Oh interesting.", "Hmm, I hadn't thought of it that way.", "Wait, really?", "That's wild."
- Vary sentence length deliberately: short punchy reactions ("Right.", "Wow.", "Go on.") followed by longer explanatory passages
- Build emotional pacing: start conversational, build curiosity/tension in the middle, release with insight or humor near the end
- Let speakers complete each other's thoughts or lightly challenge each other: "But isn't that exactly the problem?"
- Use natural conversation patterns: interruptions, agreements, follow-up questions
- Explain concepts through stories and analogies — NOT technical jargon or data dumps
- Avoid one speaker monologuing — keep exchanges dynamic and balanced
- NO markdown formatting (no **, no ##, no bullet points)

FORMAT:
- Each line MUST start with "Speaker N: " followed by their dialogue
- Example:
  Speaker 1: So tell me, what first got you interested in this?
  Speaker 2: Oh, that's a great question [chuckle]. It actually started when...

PARALINGUISTIC TAGS (for natural speech expression):
- Available: {', '.join(PARALINGUISTIC_TAGS)}
- Place tags INLINE within dialogue only where they logically fit the emotion:
  * [chuckle] — after a genuinely funny or ironic remark
  * [laugh] — after something truly hilarious (not just mildly amusing)
  * [sigh] — before reflective or bittersweet statements
  * [gasp] — before genuinely surprising revelations
  * [clear throat] — only at major topic shifts (max 1-2 total)
- Maximum 4-6 tags total across ALL speakers — quality over quantity
- Distribute tags naturally across different speakers
- NEVER force tags where the emotion doesn't fit the actual content
- NEVER put tags on separate lines — always inline within dialogue

STRUCTURE:
- Open with a natural greeting and topic introduction
- Build the conversation through exploration, insights, and reactions
- Close with key takeaways or a thought-provoking conclusion

OUTPUT: Return ONLY the dialogue. No titles, no headers, no scene descriptions, no metadata.
Target approximately {target_words} words total."""

            if deep_research:
                prompt += """

DEPTH: Go beyond surface-level facts. Include real-world consequences, contrasting expert views, and at least one counterintuitive insight. Use analogies to make complex ideas tangible. Speakers should visibly deepen their understanding or shift position during the conversation."""

            if is_url:
                prompt += """

SOURCE: Base the discussion on the provided URL content. Each speaker can offer different insights and perspectives on the material."""

        return prompt

    def generate_podcast_content(
        self,
        topic: str,
        speaker_count: int = 1,
        duration_minutes: float = 5.0,
        deep_research: bool = False
    ) -> str:
        """Generate podcast content using Gemini API."""
        if speaker_count < 1 or speaker_count > 4:
            raise ValueError("Speaker count must be between 1 and 4")
        
        if duration_minutes < 1 or duration_minutes > 10:
            raise ValueError("Duration must be between 1 and 10 minutes")
        
        is_url = False
        topic_content = topic
        
        try:
            parsed = urlparse(topic)
            if parsed.scheme and parsed.netloc:
                is_url = True
                topic_content = self._extract_url_content(topic)
                topic_content = f"Content from {topic}:\n\n{topic_content}"
        except Exception:
            pass
        
        prompt = self._build_prompt(
            topic=topic_content,
            speaker_count=speaker_count,
            duration_minutes=duration_minutes,
            deep_research=deep_research,
            is_url=is_url
        )
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use new google.genai API
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                
                # Extract text from response
                if hasattr(response, 'text'):
                    content = response.text.strip()
                elif hasattr(response, 'candidates') and response.candidates:
                    content = response.candidates[0].content.parts[0].text.strip()
                else:
                    raise ValueError("Unexpected response format from API")
                
                if not content:
                    raise ValueError("Empty response from API")
                
                content = self._clean_content_for_tts(content)
                content = self._enhance_paralinguistic_tags(content)

                # Conservative tag injection: ~1 tag per minute, max 5
                min_tags = min(max(2, int(duration_minutes)), 5)
                content = self._inject_natural_paralinguistic_tags(content, min_tags=min_tags)

                # Auto-enhance tags with LLM for English content (non-English strips tags before TTS anyway)
                try:
                    content = self.enhance_text_with_tags(content)
                except Exception:
                    pass  # Silent fallback — original content is still valid

                if attempt == 0:
                    content = self._adjust_content_length(content, duration_minutes)

                return content
            
            except Exception as e:
                if attempt == max_retries - 1:
                    error_msg = str(e)
                    if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                        raise RuntimeError(
                            "API rate limit exceeded. Please wait a moment and try again."
                        )
                    elif "api key" in error_msg.lower() or "authentication" in error_msg.lower():
                        raise RuntimeError(
                            "API authentication failed. Please check your GOOGLE_GEMINI_API_KEY."
                        )
                    else:
                        raise RuntimeError(f"Failed to generate content after {max_retries} attempts: {error_msg}")
                import time
                time.sleep(2 ** attempt)
    
    def _enhance_paralinguistic_tags(self, content: str) -> str:
        """Ensure paralinguistic tags are inline, not on separate lines."""
        return enhance_paralinguistic_tags(content)
    
    def _adjust_content_length(
        self,
        content: str,
        target_duration_minutes: float,
        max_iterations: int = 1
    ) -> str:
        """Adjust content length to match target duration.

        Preserves Speaker N: format for multi-speaker content.
        """
        target_words = self._estimate_word_count(target_duration_minutes)
        current_words = len(content.split())

        if abs(current_words - target_words) / max(target_words, 1) < 0.15:
            return content

        # Detect if this is multi-speaker content
        has_speakers = bool(re.search(r'^Speaker\s+\d+:', content, re.MULTILINE))
        format_instruction = ""
        if has_speakers:
            format_instruction = """
CRITICAL FORMAT: This is multi-speaker dialogue. You MUST preserve the exact "Speaker N:" format for every line.
Each speaker's dialogue must start on its own line with "Speaker N: " prefix."""

        if current_words < target_words * 0.75:
            expansion_prompt = f"""The following podcast content is too short ({current_words} words). Expand it to approximately {target_words} words while maintaining natural flow and style.
{format_instruction}
Preserve all paralinguistic tags inline (tags: {', '.join(PARALINGUISTIC_TAGS)}).
Do NOT add markdown formatting. Return ONLY the expanded script.

Current content:
{content}"""

            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=expansion_prompt
                )
                if hasattr(response, 'text'):
                    expanded = response.text.strip()
                elif hasattr(response, 'candidates') and response.candidates:
                    expanded = response.candidates[0].content.parts[0].text.strip()
                else:
                    return content
                # Validate expanded content preserves Speaker format if needed
                if has_speakers and not re.search(r'^Speaker\s+\d+:', expanded, re.MULTILINE):
                    return content  # Expansion broke the format, keep original
                return expanded if expanded else content
            except Exception:
                return content

        elif current_words > target_words * 1.3:
            reduction_prompt = f"""The following podcast content is too long ({current_words} words). Condense it to approximately {target_words} words while keeping the most important points.
{format_instruction}
Preserve paralinguistic tags inline where appropriate (tags: {', '.join(PARALINGUISTIC_TAGS)}).
Do NOT add markdown formatting. Return ONLY the condensed script.

Current content:
{content}"""

            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=reduction_prompt
                )
                if hasattr(response, 'text'):
                    reduced = response.text.strip()
                elif hasattr(response, 'candidates') and response.candidates:
                    reduced = response.candidates[0].content.parts[0].text.strip()
                else:
                    return content
                # Validate reduced content preserves Speaker format if needed
                if has_speakers and not re.search(r'^Speaker\s+\d+:', reduced, re.MULTILINE):
                    return content  # Reduction broke the format, keep original
                return reduced if reduced else content
            except Exception:
                return content

        return content
    
    def enhance_text_with_tags(self, text: str) -> str:
        """
        Use Gemini to analyze text and insert paralinguistic tags at contextually appropriate positions.

        Args:
            text: Input text to enhance with emotional tags

        Returns:
            Enhanced text with paralinguistic tags inserted organically
        """
        if not text or not text.strip():
            return text

        prompt = f"""You are an expert at adding natural emotional expressions to text for text-to-speech synthesis.

Analyze the following text and insert paralinguistic tags ONLY where the emotion genuinely matches the content.
Available tags: {', '.join(PARALINGUISTIC_TAGS)}

When to use each tag (ONLY use when the content genuinely warrants it):
- [chuckle] — after a genuinely funny or ironic statement
- [laugh] — after something truly hilarious (very rare)
- [sigh] — before genuinely reflective, bittersweet, or resigned statements
- [gasp] — before truly surprising or shocking revelations
- [clear throat] — at a major topic transition (use max 1-2 times)
- [cough] — almost never, only very naturally
- [sniff] — for genuinely emotional or touching moments
- [groan] — for genuine frustration or terrible puns
- [shush] — for secretive or conspiratorial tone (very rare)

STRICT Rules:
1. Place tags INLINE within sentences, NEVER on separate lines
2. Be VERY conservative — aim for 1 tag per 3-4 sentences MAXIMUM
3. If the text is factual/neutral, use FEWER tags (or none)
4. NEVER add a tag just to fill a quota — every tag must feel earned
5. Preserve the original text EXACTLY — only ADD tags, don't change any wording
6. Return ONLY the enhanced text, nothing else (no explanations, no markdown, no quotes)

Original text:
{text}

Enhanced text with tags:"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            if hasattr(response, 'text'):
                enhanced = response.text.strip()
            elif hasattr(response, 'candidates') and response.candidates:
                enhanced = response.candidates[0].content.parts[0].text.strip()
            else:
                return text

            # Clean up any markdown formatting the LLM might add
            enhanced = self._clean_content_for_tts(enhanced)
            enhanced = self._enhance_paralinguistic_tags(enhanced)

            return enhanced if enhanced else text

        except Exception as e:
            logger.warning("Failed to enhance text: %s", e)
            return text

    def translate_script(self, text: str, target_language_name: str) -> str:
        """Translate a podcast script to the target language. Preserves Speaker N: labels."""
        # Strip paralinguistic tags before sending to LLM
        clean_text = re.sub(
            r'\[(?:laugh|chuckle|gasp|sniff|groan|cough|shush|sigh|clear throat)\]',
            '', text, flags=re.IGNORECASE
        ).strip()

        is_multi_speaker = bool(re.search(r'^Speaker\s+\d+:', clean_text, re.MULTILINE))

        if is_multi_speaker:
            prompt = (
                f"Translate the following podcast script to {target_language_name}.\n\n"
                f"CRITICAL RULES:\n"
                f"1. Preserve \"Speaker N:\" labels EXACTLY — do NOT translate them\n"
                f"2. Translate ONLY the dialogue text after each label\n"
                f"3. Preserve paragraph breaks and line structure\n"
                f"4. Write naturally in {target_language_name} — maintain conversational podcast tone\n"
                f"5. Return ONLY the translated script, nothing else\n\n"
                f"Script to translate:\n{clean_text}"
            )
        else:
            prompt = (
                f"Translate the following podcast script to {target_language_name}.\n\n"
                f"CRITICAL RULES:\n"
                f"1. Maintain the conversational podcast tone — do not translate word-for-word\n"
                f"2. Preserve paragraph breaks\n"
                f"3. Return ONLY the translated script, nothing else\n\n"
                f"Script to translate:\n{clean_text}"
            )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            if hasattr(response, 'text'):
                result = response.text.strip()
            elif hasattr(response, 'candidates') and response.candidates:
                result = response.candidates[0].content.parts[0].text.strip()
            else:
                raise ValueError("Unexpected response format")

            result = self._clean_content_for_tts(result)

            # Validate multi-speaker format preserved
            if is_multi_speaker and not re.search(r'^Speaker\s+\d+:', result, re.MULTILINE):
                return clean_text  # fallback: return stripped English

            return result if result else clean_text

        except Exception as e:
            raise RuntimeError(f"Translation to {target_language_name} failed: {str(e)}")

    def parse_multi_speaker_content(self, content: str) -> List[Dict[str, str]]:
        """Parse multi-speaker content into segments by speaker."""
        segments = []
        current_speaker = None
        current_text = []
        
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            speaker_match = re.match(r'^(Speaker\s+\d+):\s*(.+)$', line, re.IGNORECASE)
            if speaker_match:
                if current_speaker and current_text:
                    segment_text = ' '.join(current_text).strip()
                    segments.append({
                        'speaker': current_speaker,
                        'text': segment_text
                    })
                
                current_speaker = speaker_match.group(1)
                remaining_text = speaker_match.group(2)
                current_text = [remaining_text] if remaining_text.strip() else []
            else:
                if current_text:
                    current_text.append(line)
                else:
                    if not current_speaker:
                        current_speaker = "Speaker 1"
                    current_text = [line]
        
        if current_speaker and current_text:
            segments.append({
                'speaker': current_speaker,
                'text': ' '.join(current_text).strip()
            })
        
        if not segments:
            segments.append({
                'speaker': 'Speaker 1',
                'text': content
            })
        
        return segments
