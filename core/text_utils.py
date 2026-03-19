"""
Shared text utilities for SurAIverse TTS Studio.
Single source of truth for paralinguistic tag definitions and text processing helpers.
"""

import re

# Paralinguistic tags supported by Chatterbox Turbo
PARALINGUISTIC_TAGS = [
    "[laugh]", "[chuckle]", "[gasp]", "[sniff]", "[groan]",
    "[cough]", "[shush]", "[sigh]", "[clear throat]"
]

# Average human speaking rate (words per minute)
AVERAGE_WPM = 150

# Compiled regex for stripping paralinguistic tags
_TAG_STRIP_RE = re.compile(
    r'\[(?:laugh|chuckle|gasp|sniff|groan|cough|shush|sigh|clear throat)\]',
    re.IGNORECASE
)


def strip_paralinguistic_tags(text: str) -> str:
    """Remove all paralinguistic tags from text."""
    return _TAG_STRIP_RE.sub('', text).strip()


def estimate_word_count(duration_minutes: float) -> int:
    """Estimate target word count for a given duration."""
    return int(duration_minutes * AVERAGE_WPM * 0.9)


def clean_content_for_tts(content: str) -> str:
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
    # Remove numbered list items but NOT "Speaker N:" patterns
    content = re.sub(r'^[\s]*\d+\.\s+(?!Speaker)', '', content, flags=re.MULTILINE)

    # Remove URLs and markdown links
    content = re.sub(r'https?://\S+', '', content)
    content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)

    # Remove extra newlines
    content = re.sub(r'\n{3,}', '\n\n', content)

    # Remove HTML tags
    content = re.sub(r'<[^>]+>', '', content)

    # Clean up spaces (but preserve newlines)
    content = re.sub(r'[ \t]+', ' ', content)

    # Remove separator lines
    content = re.sub(r'^[-=]{3,}$', '', content, flags=re.MULTILINE)

    # Remove stage directions like (pauses), (laughs), [INTRO], etc. but NOT paralinguistic tags
    valid_tags_pattern = '|'.join(re.escape(tag) for tag in PARALINGUISTIC_TAGS)
    content = re.sub(
        r'\[(?!' + valid_tags_pattern.replace(r'\[', '').replace(r'\]', '') + r')[A-Z][A-Z\s]+\]',
        '', content
    )
    content = re.sub(
        r'\((?:pauses?|laughs?|sighs?|music|beat|transition)[^)]*\)', '', content,
        flags=re.IGNORECASE
    )

    # Clean whitespace per line
    lines = [line.strip() for line in content.split('\n')]
    content = '\n'.join(lines)

    # Final cleanup of multiple blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content.strip()


def enhance_paralinguistic_tags(content: str) -> str:
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


def inject_natural_paralinguistic_tags(content: str, min_tags: int = 3) -> str:
    """Inject paralinguistic tags only at clearly appropriate conversation points.

    Conservative approach: only inject where the emotion clearly matches content.
    Expanded to 13 contextual patterns covering humor, surprise, reflection,
    emotion, frustration, transitions, and conspiratorial tone.
    """
    existing_tags = sum(content.count(tag) for tag in PARALINGUISTIC_TAGS)

    if existing_tags >= min_tags:
        return content

    tags_needed = min(min_tags - existing_tags, 3)  # Cap at 3 injected tags

    # 13 contextual patterns — only match phrases that CLEARLY indicate an emotion
    contextual_patterns = [
        # Humor indicators
        (r'(that\'s (?:so )?funny|that\'s hilarious|I\'m kidding|just joking)', r'\1 [chuckle]', '[chuckle]'),
        (r'(of all things|the irony is)', r'\1 [chuckle]', '[chuckle]'),
        # Surprise indicators
        (r'(can you believe that|would you believe|hard to believe)', r'\1 [gasp]', '[gasp]'),
        (r'(blew my mind|I was shocked|didn\'t see that coming)', r'[gasp] \1', '[gasp]'),
        (r'(figures are astonishing|the numbers are staggering)', r'[gasp] \1', '[gasp]'),
        # Reflection indicators
        (r'(unfortunately though|the sad truth is|it\'s a shame)', r'[sigh] \1', '[sigh]'),
        (r'(looking back on it|in retrospect)', r'[sigh] \1', '[sigh]'),
        # Emotion indicators
        (r'(it\'s genuinely moving|it\'s deeply touching)', r'[sniff] \1', '[sniff]'),
        # Frustration indicators
        (r'(drives me up the wall|incredibly frustrating)', r'[groan] \1', '[groan]'),
        # Transitions
        (r'(Alright,?\s+let\'s move on(?:\s+to)?|Now,\s+here\'s where it gets interesting)',
         r'[clear throat] \1', '[clear throat]'),
        (r'(So,\s+shifting gears)', r'[clear throat] \1', '[clear throat]'),
        # Conspiratorial tone
        (r'(between you and me|just between us)', r'[shush] \1', '[shush]'),
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

    # If still not enough tags, add at most 1 at a natural paragraph break
    if tags_added < tags_needed:
        paragraphs = modified_content.split('\n\n')
        if len(paragraphs) >= 3:
            mid = len(paragraphs) // 2
            if not any(tag in paragraphs[mid][:30] for tag in PARALINGUISTIC_TAGS):
                paragraphs[mid] = '[clear throat] ' + paragraphs[mid]
                tags_added += 1
            modified_content = '\n\n'.join(paragraphs)

    return modified_content
