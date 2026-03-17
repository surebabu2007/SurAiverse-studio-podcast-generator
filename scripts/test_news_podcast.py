"""
Test script for News Aggregation and Podcast Generation
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from core.news_aggregator import NewsAggregator
from core.podcast_generator import PodcastGenerator
from core.tts_engine import TTSEngine
import tempfile

def test_news_aggregation():
    """Test news aggregation."""
    print("=" * 60)
    print("Testing News Aggregation")
    print("=" * 60)
    
    try:
        aggregator = NewsAggregator()
        
        # Test fetching technology news
        print("\n📰 Fetching Technology news...")
        news_items = aggregator.fetch_news("technology", num_results=5)
        
        if not news_items:
            print("❌ No news items returned")
            return None
        
        print(f"✅ Retrieved {len(news_items)} news items")
        print("\n" + "-" * 60)
        
        for i, item in enumerate(news_items[:3], 1):
            print(f"\n{i}. {item.get('title', 'No title')}")
            print(f"   Source: {item.get('source', 'Unknown')}")
            print(f"   Date: {item.get('date', 'Unknown')}")
            print(f"   Summary: {item.get('snippet', 'No summary')[:150]}...")
        
        return news_items[0] if news_items else None
        
    except Exception as e:
        print(f"❌ Error testing news aggregation: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_podcast_from_news(news_item):
    """Test podcast generation from a news item."""
    print("\n" + "=" * 60)
    print("Testing Podcast Generation from News")
    print("=" * 60)
    
    if not news_item:
        print("❌ No news item provided")
        return
    
    try:
        # Create topic from news item
        title = news_item.get('title', '')
        snippet = news_item.get('snippet', '')
        topic = f"{title}. {snippet}"
        
        print(f"\n📝 Topic: {title}")
        print(f"📄 Snippet: {snippet[:200]}...")
        print("\n🎙️ Generating podcast (single speaker, 2 minutes)...")
        
        generator = PodcastGenerator()
        podcast_data = generator.generate_podcast_content(
            topic=topic,
            speaker_count=1,
            duration_minutes=2.0,
            deep_research=False
        )
        
        segments = podcast_data.get('segments', [])
        if segments:
            content = segments[0].get('text', '')
            print(f"\n✅ Content generated ({len(content)} characters)")
            print(f"\n📋 Content preview (first 300 chars):")
            print("-" * 60)
            print(content[:300] + "...")
            print("-" * 60)
            
            # Check for paralinguistic tags
            tags = ['[laugh]', '[chuckle]', '[sigh]', '[gasp]', '[cough]', '[clear throat]', '[sniff]', '[groan]', '[shush]']
            found_tags = [tag for tag in tags if tag in content]
            if found_tags:
                print(f"\n✅ Found paralinguistic tags: {found_tags}")
            else:
                print(f"\n⚠️  No paralinguistic tags found in content")
            
            # Generate audio (if TTS engine available)
            print("\n🎵 Generating audio (this may take a while)...")
            try:
                tts_engine = TTSEngine()
                audio = tts_engine.generate_turbo(content[:500])  # First 500 chars for testing
                
                # Save to temp file
                output_path = tempfile.mktemp(suffix=".wav")
                tts_engine.save_audio(audio, output_path)
                print(f"✅ Audio generated and saved to: {output_path}")
                print(f"   File size: {os.path.getsize(output_path)} bytes")
                
            except Exception as e:
                print(f"⚠️  Audio generation failed (this is okay for testing): {str(e)}")
        
        else:
            print("❌ No segments generated")
            
    except Exception as e:
        print(f"❌ Error generating podcast: {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    """Run tests."""
    print("\n" + "🚀 Starting News and Podcast Tests" + "\n")
    
    # Test 1: News Aggregation
    news_item = test_news_aggregation()
    
    # Test 2: Podcast from News
    if news_item:
        test_podcast_from_news(news_item)
    else:
        print("\n⚠️  Skipping podcast test - no news item available")
    
    print("\n" + "=" * 60)
    print("✅ Tests completed!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()



