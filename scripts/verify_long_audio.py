
import os
import sys
import torch
import torchaudio
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.getcwd())

from core.tts_engine import TTSEngine

def test_long_audio_generation():
    print("Initialize TTS Engine...")
    engine = TTSEngine()
    
    # Text longer than 400 chars (approx 1000 chars here)
    long_text = (
        "Hey everyone! Welcome back to the show. Today we are talking about something really exciting. "
        "Have you ever wondered how AI models actually work under the hood? It's fascinating stuff. "
        "Basically, these models are trained on massive amounts of data, learning patterns and relationships between words. "
        "When you give it a prompt, it's not just retrieving a pre-written answer, it's actually predicting the next most likely word "
        "sequence based on everything it has learned. [clear throat] "
        "Now, specifically with text-to-speech, things get even more interesting. The model has to understand not just the words, "
        "but the intonation, rhythm, and emotion behind them. That's why paralinguistic tags like [laugh] or [sigh] are so cool. "
        "They give us control over the non-verbal parts of speech that make it sound human. "
        "So, when we fix this truncation issue, we should be able to generate podcasts of any length without the audio cutting off abruptly. "
        "This paragraph is designed to be definitely longer than the 400 character limit we observed earlier. "
        "If the chunking logic works, this entire speech should be synthesized properly, resulting in an audio file that is "
        "roughly 30 to 40 seconds long, instead of just 7 seconds. Let's see if it works!"
    )
    
    print(f"\nScanning text length: {len(long_text)} characters")
    
    output_path = "test_long_audio.wav"
    
    print("Generating audio (this should trigger chunking)...")
    try:
        final_wav = engine.generate_turbo(long_text)
        
        # Save validation
        engine.save_audio(final_wav, output_path)
        
        # Check duration
        info = torchaudio.info(output_path)
        duration_sec = info.num_frames / info.sample_rate
        
        print(f"\n✅ Generation Complete!")
        print(f"Output saved to: {output_path}")
        print(f"Duration: {duration_sec:.2f} seconds")
        
        if duration_sec > 20:
            print("SUCCESS: Audio duration is > 20s, indicating chunking worked!")
        else:
            print("FAILURE: Audio duration is too short (< 20s), likely still truncated.")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_long_audio_generation()
