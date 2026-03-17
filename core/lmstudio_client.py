"""
LM Studio Client for Content Generation
Provides the same interface as GeminiClient but uses LM Studio's OpenAI-compatible API.
Automatically detects available models and handles model changes gracefully.
"""

import os
import re
import requests
from typing import Optional, List, Dict
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# Paralinguistic tags supported (same as gemini_client)
PARALINGUISTIC_TAGS = [
    "[laugh]", "[chuckle]", "[gasp]", "[sniff]", "[groan]",
    "[cough]", "[shush]", "[sigh]", "[clear throat]"
]

# Average speaking rate: words per minute
AVERAGE_WPM = 150


class LMStudioClient:
    """
    Client for LM Studio's OpenAI-compatible API to generate podcast content.
    Mirrors the GeminiClient interface so they can be used interchangeably.
    """

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize LM Studio client.

        Args:
            base_url: LM Studio server URL. If None, loads from environment.
        """
        self.base_url = (base_url or os.getenv("LM_STUDIO_URL", "http://localhost:8000")).rstrip("/")
        self.model_name = None
        self._session = requests.Session()

        # Discover available model
        self._discover_model()

        # Create a model wrapper for backward compatibility (used by news_aggregator)
        self.model = self._ModelWrapper(self)

    def _discover_model(self):
        """Discover the currently loaded model from LM Studio."""
        try:
            resp = self._session.get(f"{self.base_url}/v1/models", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", [])
            if models:
                self.model_name = models[0].get("id", "default")
                print(f"✓ LM Studio connected - model: {self.model_name}")
            else:
                # LM Studio with just-in-time loading may have no models listed yet
                self.model_name = "default"
                print("✓ LM Studio connected - just-in-time model loading active")
        except requests.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to LM Studio at {self.base_url}. "
                f"Make sure LM Studio server is running."
            )
        except Exception as e:
            raise RuntimeError(f"Failed to connect to LM Studio: {e}")

    def _refresh_model(self):
        """Refresh the current model name (in case user changed it in LM Studio)."""
        try:
            resp = self._session.get(f"{self.base_url}/v1/models", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", [])
            if models:
                self.model_name = models[0].get("id", "default")
        except Exception:
            pass  # Keep existing model name

    def _chat_completion(self, prompt: str, max_tokens: int = 4096, temperature: float = 0.7) -> str:
        """
        Send a chat completion request to LM Studio.

        Args:
            prompt: The user prompt text
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        # Refresh model in case user changed it in LM Studio
        self._refresh_model()

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        try:
            resp = self._session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()

            choices = data.get("choices", [])
            if not choices:
                raise ValueError("Empty response from LM Studio")

            content = choices[0].get("message", {}).get("content", "").strip()
            if not content:
                raise ValueError("Empty content in LM Studio response")

            return content

        except requests.ConnectionError:
            raise ConnectionError(
                f"Lost connection to LM Studio at {self.base_url}. "
                f"Make sure LM Studio server is still running."
            )
        except requests.Timeout:
            raise RuntimeError(
                "LM Studio request timed out. The model may be loading or the prompt is too long."
            )
        except requests.HTTPError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("error", {}).get("message", "")
            except Exception:
                error_detail = e.response.text[:200] if e.response else ""
            raise RuntimeError(f"LM Studio error: {error_detail or str(e)}")

    class _ModelWrapper:
        """Wrapper to provide backward-compatible model.generate_content() interface."""
        def __init__(self, client):
            self._client = client

        def generate_content(self, prompt):
            text = self._client._chat_completion(prompt)
            return _SimpleResponse(text)

    def _estimate_word_count(self, duration_minutes: float) -> int:
        """Estimate target word count for a given duration."""
        return int(duration_minutes * AVERAGE_WPM * 0.9)

    def _clean_content_for_tts(self, content: str) -> str:
        """Clean content for TTS by removing markdown formatting.

        Preserves Speaker labels (Speaker N:) and paralinguistic tags.
        """
        # Remove markdown bold
        content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
        content = re.sub(r'__([^_]+)__', r'\1', content)

        # Remove markdown italic (but not paralinguistic tags in brackets)
        content = re.sub(r'(?<!\[)\*([^*\[\]]+)\*(?!\])', r'\1', content)
        content = re.sub(r'(?<!\[)_([^_\[\]]+)_(?!\])', r'\1', content)

        # Remove markdown headers
        content = re.sub(r'^#{1,6}\s*', '', content, flags=re.MULTILINE)

        # Remove bullet points but NOT lines starting with "Speaker"
        content = re.sub(r'^[\s]*[-*•]\s+(?!Speaker)', '', content, flags=re.MULTILINE)
        content = re.sub(r'^[\s]*\d+\.\s+(?!Speaker)', '', content, flags=re.MULTILINE)

        # Remove URLs and markdown links
        content = re.sub(r'https?://\S+', '', content)
        content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)

        # Remove extra newlines
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Remove HTML tags
        content = re.sub(r'<[^>]+>', '', content)

        # Clean up spaces
        content = re.sub(r'[ \t]+', ' ', content)

        # Remove separator lines
        content = re.sub(r'^[-=]{3,}$', '', content, flags=re.MULTILINE)

        # Remove stage directions but NOT paralinguistic tags
        valid_tags_pattern = '|'.join(re.escape(tag) for tag in PARALINGUISTIC_TAGS)
        content = re.sub(r'\[(?!' + valid_tags_pattern.replace(r'\[', '').replace(r'\]', '') + r')[A-Z][A-Z\s]+\]', '', content)
        content = re.sub(r'\((?:pauses?|laughs?|sighs?|music|beat|transition)[^)]*\)', '', content, flags=re.IGNORECASE)

        # Clean whitespace per line
        lines = [line.strip() for line in content.split('\n')]
        content = '\n'.join(lines)

        # Final cleanup of multiple blank lines
        content = re.sub(r'\n{3,}', '\n\n', content)

        return content.strip()

    def _inject_natural_paralinguistic_tags(self, content: str, min_tags: int = 3) -> str:
        """Inject paralinguistic tags only at clearly appropriate conversation points.

        Conservative approach: only inject where the emotion clearly matches content.
        Avoids matching common words that would create weird output.
        """
        existing_tags = sum(content.count(tag) for tag in PARALINGUISTIC_TAGS)

        if existing_tags >= min_tags:
            return content

        tags_needed = min(min_tags - existing_tags, 3)  # Cap at 3 injected tags

        # Only match phrases that CLEARLY indicate an emotion — no common words
        contextual_patterns = [
            # Genuine humor indicators (multi-word phrases only)
            (r'(that\'s (?:so )?funny|that\'s hilarious|I\'m kidding|just joking)', r'\1 [chuckle]', '[chuckle]'),
            # Genuine surprise (multi-word phrases only)
            (r'(can you believe that|would you believe|hard to believe)', r'\1 [gasp]', '[gasp]'),
            (r'(I was shocked|blew my mind|didn\'t see that coming)', r'[gasp] \1', '[gasp]'),
            # Genuine reflection (multi-word phrases only)
            (r'(unfortunately though|the sad truth is|it\'s a shame)', r'[sigh] \1', '[sigh]'),
            # Natural transitions (only full transitional phrases)
            (r'(Alright, let\'s move on to|Now, here\'s where it gets interesting)', r'[clear throat] \1', '[clear throat]'),
        ]

        tags_added = 0
        modified_content = content

        for pattern, replacement, tag in contextual_patterns:
            if tags_added >= tags_needed:
                break
            if modified_content.count(tag) < 1:
                new_content = re.sub(pattern, replacement, modified_content, count=1, flags=re.IGNORECASE)
                if new_content != modified_content:
                    modified_content = new_content
                    tags_added += 1

        # If still not enough tags, add at most 1-2 at natural paragraph breaks
        if tags_added < tags_needed:
            paragraphs = modified_content.split('\n\n')
            if len(paragraphs) >= 3:
                mid = len(paragraphs) // 2
                if not any(tag in paragraphs[mid][:30] for tag in PARALINGUISTIC_TAGS):
                    paragraphs[mid] = '[clear throat] ' + paragraphs[mid]
                    tags_added += 1
                modified_content = '\n\n'.join(paragraphs)

        return modified_content

    def _extract_url_content(self, url: str) -> str:
        """Extract text content from a URL."""
        try:
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
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
        """Build prompt for LM Studio API."""
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

DEPTH: Provide thorough, well-researched content with multiple perspectives, data points, and expert-level insights while keeping the conversational tone."""

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

DEPTH: Include thorough analysis with multiple perspectives, expert insights, and nuanced discussion while keeping the conversational feel."""

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
        """Generate podcast content using LM Studio API."""
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
                content = self._chat_completion(prompt, max_tokens=4096, temperature=0.7)

                if not content:
                    raise ValueError("Empty response from API")

                content = self._clean_content_for_tts(content)
                content = self._enhance_paralinguistic_tags(content)

                # Conservative tag injection: ~1 tag per minute, max 5
                min_tags = min(max(2, int(duration_minutes)), 5)
                content = self._inject_natural_paralinguistic_tags(content, min_tags=min_tags)

                if attempt == 0:
                    content = self._adjust_content_length(content, duration_minutes)

                return content

            except Exception as e:
                if attempt == max_retries - 1:
                    error_msg = str(e)
                    if "connection" in error_msg.lower():
                        raise RuntimeError(
                            f"Cannot connect to LM Studio at {self.base_url}. "
                            f"Make sure LM Studio server is running."
                        )
                    else:
                        raise RuntimeError(f"Failed to generate content after {max_retries} attempts: {error_msg}")
                import time
                time.sleep(2 ** attempt)

    def _enhance_paralinguistic_tags(self, content: str) -> str:
        """Ensure paralinguistic tags are inline, not on separate lines."""
        has_tags = any(tag in content for tag in PARALINGUISTIC_TAGS)

        if has_tags:
            lines = content.split('\n')
            fixed_lines = []
            for line in lines:
                line_stripped = line.strip()
                if line_stripped in PARALINGUISTIC_TAGS:
                    if fixed_lines:
                        fixed_lines[-1] = fixed_lines[-1].rstrip() + f" {line_stripped} "
                    else:
                        fixed_lines.append(line)
                    continue
                fixed_lines.append(line)
            return '\n'.join(fixed_lines)

        return content

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
                expanded = self._chat_completion(expansion_prompt)
                if has_speakers and expanded and not re.search(r'^Speaker\s+\d+:', expanded, re.MULTILINE):
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
                reduced = self._chat_completion(reduction_prompt)
                if has_speakers and reduced and not re.search(r'^Speaker\s+\d+:', reduced, re.MULTILINE):
                    return content  # Reduction broke the format, keep original
                return reduced if reduced else content
            except Exception:
                return content

        return content

    def enhance_text_with_tags(self, text: str) -> str:
        """
        Use LM Studio to analyze text and insert paralinguistic tags at contextually appropriate positions.
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
            enhanced = self._chat_completion(prompt, temperature=0.5)
            enhanced = self._clean_content_for_tts(enhanced)
            enhanced = self._enhance_paralinguistic_tags(enhanced)
            return enhanced if enhanced else text
        except Exception as e:
            print(f"[Enhance] Failed to enhance text via LM Studio: {e}")
            return text

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


class _SimpleResponse:
    """Simple response wrapper to mimic Gemini response object."""
    def __init__(self, text: str):
        self.text = text
        self.candidates = []
