"""
News Aggregator
Fetches trending news using LLM (Google Gemini or LM Studio).
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
import time
from dotenv import load_dotenv
from .podcast_generator import get_llm_client

load_dotenv()

# News categories
NEWS_CATEGORIES = {
    "technology": "Technology",
    "ai": "Artificial Intelligence AI",
    "world": "World News",
    "politics": "Politics",
    "sports": "Sports",
    "science": "Science",
    "video_games": "Video Games Gaming",
    "entertainment": "Entertainment",
    "movies": "Movies Film Cinema",
    "business": "Business Finance Economy",
    "health": "Health Wellness Medicine",
    "education": "Education Learning",
    "environment": "Environment Climate Change",
    "space": "Space Astronomy NASA",
    "crypto": "Cryptocurrency Blockchain Web3",
    "startups": "Startups Entrepreneurship Venture Capital",
    "cybersecurity": "Cybersecurity Data Privacy",
    "music": "Music Industry Artists",
    "food": "Food Culinary Nutrition",
    "travel": "Travel Tourism Destinations",
    "automotive": "Automotive Cars EV Electric Vehicles",
    "lifestyle": "Lifestyle Culture Trends",
    "true_crime": "True Crime Investigation",
    "history": "History Historical Events",
    "comedy": "Comedy Humor Funny",
    "motivation": "Motivation Self Improvement Personal Growth",
    "relationships": "Relationships Dating Social",
    "parenting": "Parenting Family Kids",
    "mental_health": "Mental Health Psychology Therapy",
}


class NewsAggregator:
    """
    Aggregates news from various sources using LLM search.
    """

    def __init__(self, gemini_api_key: Optional[str] = None, provider: Optional[str] = None, lm_studio_url: Optional[str] = None):
        """
        Initialize news aggregator.

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
        self._cache: Dict[str, tuple] = {}  # (results, timestamp)
        self._cache_duration = 300  # 5 minutes cache

    def fetch_news(
        self,
        category: str,
        num_results: int = 10,
        use_cache: bool = True
    ) -> List[Dict[str, str]]:
        """
        Fetch trending news for a category.

        Args:
            category: News category (from NEWS_CATEGORIES)
            num_results: Number of news items to fetch
            use_cache: Whether to use cached results if available

        Returns:
            List of news items with title, snippet, source, link, date
        """
        category_key = category.lower()

        # Check cache
        if use_cache and category_key in self._cache:
            results, timestamp = self._cache[category_key]
            if time.time() - timestamp < self._cache_duration:
                return results

        # Build search query
        category_name = NEWS_CATEGORIES.get(category_key, category)
        search_query = f"trending {category_name} news today"

        # Use LLM to search and format news
        news_items = self._search_news_with_llm(search_query, category_name, num_results)

        # Cache results
        self._cache[category_key] = (news_items, time.time())

        return news_items

    def _search_news_with_llm(
        self,
        query: str,
        category: str,
        num_results: int
    ) -> List[Dict[str, str]]:
        """
        Use LLM API to search for and format news.

        Args:
            query: Search query
            category: News category
            num_results: Number of results

        Returns:
            List of formatted news items
        """
        prompt = f"""Search for and provide the top {num_results} trending news articles about {category} from today.

For each news item, provide:
1. Title (clear and descriptive)
2. Brief summary/snippet (2-3 sentences)
3. Source/publication name
4. Key information/date if available

Format the response as a numbered list with clear separation between items.
Focus on the most recent and trending news.

Search query: {query}

Provide news items in this format:
1. Title: [title]
   Summary: [brief summary]
   Source: [source name]
   Key Info: [date or additional context]

[Continue for all items]"""

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.llm_client.model.generate_content(prompt)

                # Handle different response formats
                if hasattr(response, 'text'):
                    content = response.text.strip()
                elif hasattr(response, 'candidates') and response.candidates:
                    content = response.candidates[0].content.parts[0].text.strip()
                else:
                    raise ValueError("Unexpected response format from API")

                if not content:
                    raise ValueError("Empty response from API")

                # Parse the response into structured news items
                news_items = self._parse_news_response(content, category)

                if news_items:
                    return news_items[:num_results]
                else:
                    raise ValueError("No news items parsed from response")

            except Exception as e:
                if attempt == max_retries - 1:
                    # Last attempt failed, return error message
                    error_msg = str(e)
                    if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                        return [{
                            'title': f'API Rate Limit',
                            'snippet': f'API rate limit exceeded for {category} news. Please wait a moment and try again.',
                            'source': 'System',
                            'link': '',
                            'date': datetime.now().strftime('%Y-%m-%d')
                        }]
                    elif "connect" in error_msg.lower():
                        provider = os.getenv("LLM_PROVIDER", "gemini")
                        return [{
                            'title': f'Connection Error',
                            'snippet': f'Cannot connect to {provider} server. Please check your settings.',
                            'source': 'System',
                            'link': '',
                            'date': datetime.now().strftime('%Y-%m-%d')
                        }]
                    else:
                        return [{
                            'title': f'Error fetching {category} news',
                            'snippet': f'Unable to fetch news: {error_msg}. Please try again later.',
                            'source': 'System',
                            'link': '',
                            'date': datetime.now().strftime('%Y-%m-%d')
                        }]
                # Wait before retry
                time.sleep(1)

    def _parse_news_response(
        self,
        content: str,
        category: str
    ) -> List[Dict[str, str]]:
        """
        Parse LLM response into structured news items.

        Args:
            content: LLM response text
            category: News category

        Returns:
            List of parsed news items
        """
        news_items = []
        lines = content.split('\n')

        current_item = {}
        current_field = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line starts a new item (numbered)
            if line and line[0].isdigit() and '.' in line:
                # Save previous item if exists
                if current_item and 'title' in current_item:
                    news_items.append(self._finalize_news_item(current_item, category))

                # Start new item
                current_item = {}
                # Extract title from numbered line
                title = line.split('.', 1)[-1].strip()
                if title.startswith('Title:'):
                    title = title[6:].strip()
                current_item['title'] = title
                current_field = 'title'

            # Parse fields
            elif line.startswith('Title:'):
                current_item['title'] = line[6:].strip()
                current_field = 'title'
            elif line.startswith('Summary:'):
                current_item['snippet'] = line[8:].strip()
                current_field = 'snippet'
            elif line.startswith('Source:'):
                current_item['source'] = line[7:].strip()
                current_field = 'source'
            elif line.startswith('Key Info:') or line.startswith('Date:'):
                current_item['date'] = line.split(':', 1)[-1].strip()
                current_field = 'date'
            elif current_field and current_item:
                # Continuation of previous field
                if current_field == 'snippet':
                    current_item['snippet'] += ' ' + line
                elif current_field == 'title':
                    current_item['title'] += ' ' + line

        # Save last item
        if current_item and 'title' in current_item:
            news_items.append(self._finalize_news_item(current_item, category))

        # If parsing failed, create a single item from content
        if not news_items:
            news_items.append({
                'title': f'{category} News',
                'snippet': content[:200] + '...' if len(content) > 200 else content,
                'source': 'Various Sources',
                'link': '',
                'date': datetime.now().strftime('%Y-%m-%d')
            })

        return news_items

    def _finalize_news_item(
        self,
        item: Dict[str, str],
        category: str
    ) -> Dict[str, str]:
        """
        Finalize a news item with all required fields.

        Args:
            item: Partial news item dictionary
            category: News category

        Returns:
            Complete news item dictionary
        """
        # Ensure all fields exist
        finalized = {
            'title': item.get('title', f'{category} News Item'),
            'snippet': item.get('snippet', 'No summary available'),
            'source': item.get('source', 'Various Sources'),
            'link': item.get('link', ''),
            'date': item.get('date', datetime.now().strftime('%Y-%m-%d'))
        }

        # Clean up fields
        finalized['title'] = finalized['title'].strip()
        finalized['snippet'] = finalized['snippet'].strip()
        finalized['source'] = finalized['source'].strip()

        return finalized

    def get_categories(self) -> Dict[str, str]:
        """
        Get available news categories.

        Returns:
            Dictionary mapping category keys to display names
        """
        return NEWS_CATEGORIES.copy()

    def clear_cache(self):
        """Clear cached news results."""
        self._cache.clear()
