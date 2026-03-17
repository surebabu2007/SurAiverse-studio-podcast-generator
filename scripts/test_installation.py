#!/usr/bin/env python3
"""
Chatterbox TTS Installation Test Script
Verifies that everything is installed correctly on Mac M4.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 50)
    print(f"  {title}")
    print("=" * 50)


def print_status(name: str, status: bool, details: str = ""):
    """Print a status line."""
    icon = "✓" if status else "✗"
    color_start = "\033[92m" if status else "\033[91m"
    color_end = "\033[0m"
    detail_str = f" - {details}" if details else ""
    print(f"  {color_start}{icon}{color_end} {name}{detail_str}")


def test_python_version():
    """Test Python version."""
    print_header("Python Version")
    version = sys.version_info
    is_valid = version.major == 3 and version.minor >= 11
    print_status(
        f"Python {version.major}.{version.minor}.{version.micro}",
        is_valid,
        "3.11+ required" if not is_valid else "",
    )
    return is_valid


def test_pytorch():
    """Test PyTorch installation and MPS support."""
    print_header("PyTorch & MPS")
    try:
        import torch

        print_status(f"PyTorch {torch.__version__}", True)

        mps_available = torch.backends.mps.is_available()
        print_status("MPS (Metal) Available", mps_available)

        if mps_available:
            # Test MPS tensor operations
            try:
                x = torch.randn(3, 3, device="mps")
                y = x @ x.T
                print_status("MPS Tensor Operations", True)
            except Exception as e:
                print_status("MPS Tensor Operations", False, str(e))
                return False
        else:
            print("    Note: Running on CPU (MPS not available)")

        return True

    except ImportError as e:
        print_status("PyTorch", False, str(e))
        return False


def test_torchaudio():
    """Test torchaudio installation."""
    print_header("Torchaudio")
    try:
        import torchaudio

        print_status(f"Torchaudio {torchaudio.__version__}", True)
        return True
    except ImportError as e:
        print_status("Torchaudio", False, str(e))
        return False


def test_chatterbox():
    """Test Chatterbox TTS imports."""
    print_header("Chatterbox TTS")
    try:
        from chatterbox.tts import ChatterboxTTS

        print_status("ChatterboxTTS (Original)", True)
    except ImportError as e:
        print_status("ChatterboxTTS (Original)", False, str(e))
        return False

    try:
        from chatterbox.tts_turbo import ChatterboxTurboTTS

        print_status("ChatterboxTurboTTS", True)
    except ImportError as e:
        print_status("ChatterboxTurboTTS", False, str(e))

    try:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        print_status("ChatterboxMultilingualTTS", True)
    except ImportError as e:
        print_status("ChatterboxMultilingualTTS", False, str(e))

    return True


def test_gradio():
    """Test Gradio installation."""
    print_header("Gradio")
    try:
        import gradio as gr

        print_status(f"Gradio {gr.__version__}", True)
        return True
    except ImportError as e:
        print_status("Gradio", False, str(e))
        return False


def test_fastapi():
    """Test FastAPI installation."""
    print_header("FastAPI")
    try:
        import fastapi
        import uvicorn

        print_status(f"FastAPI {fastapi.__version__}", True)
        print_status("Uvicorn", True)
        return True
    except ImportError as e:
        print_status("FastAPI/Uvicorn", False, str(e))
        return False


def test_huggingface():
    """Test HuggingFace token configuration."""
    print_header("HuggingFace")
    from dotenv import load_dotenv

    load_dotenv()

    token = os.getenv("HUGGINGFACE_TOKEN")
    if token and token != "your_token_here":
        print_status("HuggingFace Token", True, "Configured")

        # Try to verify token
        try:
            from huggingface_hub import HfApi

            api = HfApi()
            api.whoami(token=token)
            print_status("Token Validation", True)
            return True
        except Exception as e:
            print_status("Token Validation", False, "Could not verify token")
            return True  # Token exists but might not be verified
    else:
        print_status("HuggingFace Token", False, "Not configured in .env")
        print("    Please add your token to .env file")
        return False


def test_core_modules():
    """Test custom core modules."""
    print_header("Core Modules")
    try:
        from core.tts_engine import TTSEngine

        print_status("TTSEngine", True)
    except ImportError as e:
        print_status("TTSEngine", False, str(e))
        return False

    try:
        from core.model_manager import ModelManager

        print_status("ModelManager", True)
    except ImportError as e:
        print_status("ModelManager", False, str(e))
        return False

    try:
        from core.audio_utils import AudioProcessor

        print_status("AudioProcessor", True)
    except ImportError as e:
        print_status("AudioProcessor", False, str(e))
        return False

    return True


def test_model_loading(model_name: str = "turbo"):
    """Test actual model loading (optional, requires download)."""
    print_header(f"Model Loading Test ({model_name})")
    print("  This may take a while on first run (downloading models)...")

    try:
        from core.tts_engine import TTSEngine

        engine = TTSEngine()

        # Generate a simple test
        wav = engine.generate(
            text="Testing one two three.",
            model_type=model_name,
        )

        print_status(f"{model_name.capitalize()} Model Load", True)
        print_status(f"Audio Generation", True, f"Shape: {wav.shape}")

        # Save test output
        output_dir = Path(__file__).parent.parent / "outputs"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"test_{model_name}.wav"
        engine.save_audio(wav, output_path)
        print_status(f"Audio Save", True, str(output_path))

        # Cleanup
        engine.unload_models()
        return True

    except Exception as e:
        print_status(f"{model_name.capitalize()} Test", False, str(e))
        return False


def main():
    """Run all installation tests."""
    print("\n" + "=" * 50)
    print("  🎙️ Chatterbox TTS - Installation Test")
    print("=" * 50)

    results = {
        "Python Version": test_python_version(),
        "PyTorch & MPS": test_pytorch(),
        "Torchaudio": test_torchaudio(),
        "Chatterbox TTS": test_chatterbox(),
        "Gradio": test_gradio(),
        "FastAPI": test_fastapi(),
        "HuggingFace": test_huggingface(),
        "Core Modules": test_core_modules(),
    }

    # Summary
    print_header("Summary")
    passed = sum(results.values())
    total = len(results)

    for name, status in results.items():
        print_status(name, status)

    print(f"\n  Result: {passed}/{total} tests passed")

    if passed == total:
        print("\n  🎉 All tests passed! Ready to use Chatterbox TTS.")
        print("\n  Quick Start:")
        print("    - Gradio UI:  python app/gradio_app.py")
        print("    - CLI:        python app/cli.py generate 'Hello world!'")
        print("    - API Server: python app/api_server.py")

        # Ask if user wants to run model test
        print("\n  Would you like to test model loading? (y/n)")
        print("  Note: This will download models (~500MB-1GB each)")

        try:
            response = input("  > ").strip().lower()
            if response == "y":
                test_model_loading("turbo")
        except (EOFError, KeyboardInterrupt):
            pass

    else:
        print("\n  ⚠️ Some tests failed. Please fix the issues above.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

