#!/usr/bin/env python3
"""
Chatterbox TTS Model Downloader
Pre-download all models for offline use.
"""

import argparse
import gc
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
from dotenv import load_dotenv


def clear_memory():
    """Clear GPU/MPS memory."""
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    elif torch.cuda.is_available():
        torch.cuda.empty_cache()


def download_model(model_name: str, device: str = "cpu") -> bool:
    """
    Download a specific model.

    Args:
        model_name: Name of model ('turbo', 'multilingual', 'original')
        device: Device to load on (use 'cpu' for downloading only)

    Returns:
        True if successful
    """
    print(f"\n{'=' * 50}")
    print(f"  Downloading: {model_name}")
    print(f"{'=' * 50}")

    try:
        if model_name == "turbo":
            from chatterbox.tts_turbo import ChatterboxTurboTTS

            model = ChatterboxTurboTTS.from_pretrained(device=device)

        elif model_name == "multilingual":
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            model = ChatterboxMultilingualTTS.from_pretrained(device=device)

        elif model_name == "original":
            from chatterbox.tts import ChatterboxTTS

            model = ChatterboxTTS.from_pretrained(device=device)

        else:
            print(f"  ✗ Unknown model: {model_name}")
            return False

        # Clear model from memory
        del model
        clear_memory()

        print(f"  ✓ {model_name} downloaded successfully!")
        return True

    except Exception as e:
        print(f"  ✗ Failed to download {model_name}: {e}")
        return False


def main():
    """Main download function."""
    parser = argparse.ArgumentParser(
        description="Download Chatterbox TTS models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_models.py --all              # Download all models
  python download_models.py --models turbo     # Download only Turbo
  python download_models.py -m turbo original  # Download Turbo and Original
        """,
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all available models",
    )

    parser.add_argument(
        "-m",
        "--models",
        nargs="+",
        choices=["turbo", "multilingual", "original"],
        help="Specific models to download",
    )

    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "mps", "cuda"],
        help="Device for loading (default: cpu for download only)",
    )

    args = parser.parse_args()

    # Load environment for HuggingFace token
    load_dotenv()

    # Authenticate with HuggingFace
    token = os.getenv("HUGGINGFACE_TOKEN")
    if token and token != "your_token_here":
        from huggingface_hub import login

        try:
            login(token=token, add_to_git_credential=False)
            print("✓ HuggingFace authentication successful")
        except Exception as e:
            print(f"⚠ HuggingFace authentication failed: {e}")
    else:
        print("⚠ No HuggingFace token found. Some models may not be accessible.")

    # Determine models to download
    if args.all:
        models = ["turbo", "multilingual", "original"]
    elif args.models:
        models = args.models
    else:
        parser.print_help()
        print("\n⚠ Please specify --all or --models")
        return 1

    print("\n" + "=" * 50)
    print("  🎙️ Chatterbox TTS - Model Downloader")
    print("=" * 50)
    print(f"  Models: {', '.join(models)}")
    print(f"  Device: {args.device}")

    # Download models
    results = {}
    for model_name in models:
        results[model_name] = download_model(model_name, args.device)
        clear_memory()

    # Summary
    print("\n" + "=" * 50)
    print("  Download Summary")
    print("=" * 50)

    for name, success in results.items():
        icon = "✓" if success else "✗"
        status = "Downloaded" if success else "Failed"
        print(f"  {icon} {name}: {status}")

    successful = sum(results.values())
    total = len(results)

    print(f"\n  Result: {successful}/{total} models downloaded")

    if successful == total:
        print("\n  🎉 All models ready!")
        print("  You can now use Chatterbox TTS offline.")
    else:
        print("\n  ⚠ Some downloads failed. Check your internet connection and HF token.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

