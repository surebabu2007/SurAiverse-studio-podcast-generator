#!/usr/bin/env python3
"""
Chatterbox TTS Command-Line Interface
Generate speech from the terminal with all model variants.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv

from core.tts_engine import TTSEngine
from core.model_manager import ModelManager

# Load environment variables
load_dotenv()

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="Chatterbox TTS CLI")
def cli():
    """
    🎙️ Chatterbox TTS - Command Line Interface

    Generate high-quality speech from text using state-of-the-art TTS models.
    Supports Turbo, Multilingual, and Original model variants.
    """
    pass


@cli.command()
@click.argument("text")
@click.option(
    "-o", "--output",
    default="output.wav",
    help="Output file path (default: output.wav)",
)
@click.option(
    "-m", "--model",
    type=click.Choice(["turbo", "multilingual", "original"]),
    default="turbo",
    help="Model variant to use (default: turbo)",
)
@click.option(
    "-v", "--voice",
    type=click.Path(exists=True),
    help="Reference audio for voice cloning",
)
@click.option(
    "-l", "--language",
    default="en",
    help="Language code for multilingual model (default: en)",
)
@click.option(
    "--exaggeration",
    type=float,
    default=0.5,
    help="Exaggeration level for original model (0.0-1.0)",
)
@click.option(
    "--cfg-weight",
    type=float,
    default=0.5,
    help="CFG weight for original model (0.0-1.0)",
)
def generate(text, output, model, voice, language, exaggeration, cfg_weight):
    """
    Generate speech from text.

    TEXT: The text to convert to speech.

    Examples:

        chatterbox generate "Hello world!"

        chatterbox generate "Bonjour!" -m multilingual -l fr -o french.wav

        chatterbox generate "Hi there [laugh]" -m turbo -v voice.wav
    """
    console.print(Panel.fit(
        f"[bold cyan]🎙️ Chatterbox TTS[/bold cyan]\n"
        f"Model: [yellow]{model}[/yellow] | Output: [green]{output}[/green]",
        border_style="cyan",
    ))

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Initialize engine
            task = progress.add_task("Loading model...", total=None)
            engine = TTSEngine()

            # Generate speech
            progress.update(task, description="Generating speech...")
            
            kwargs = {}
            if model == "multilingual":
                kwargs["language_id"] = language
            elif model == "original":
                kwargs["exaggeration"] = exaggeration
                kwargs["cfg_weight"] = cfg_weight

            wav = engine.generate(
                text=text,
                model_type=model,
                audio_prompt_path=voice,
                **kwargs,
            )

            # Save output
            progress.update(task, description="Saving audio...")
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            engine.save_audio(wav, output_path)

        console.print(f"\n[bold green]✓ Audio saved to:[/bold green] {output_path.absolute()}")

    except Exception as e:
        console.print(f"\n[bold red]✗ Error:[/bold red] {str(e)}")
        sys.exit(1)


@cli.command()
def languages():
    """List all supported languages for the multilingual model."""
    langs = ModelManager.get_supported_languages()

    console.print(Panel.fit(
        "[bold cyan]🌍 Supported Languages[/bold cyan]",
        border_style="cyan",
    ))

    for code, name in sorted(langs.items(), key=lambda x: x[1]):
        console.print(f"  [yellow]{code}[/yellow] - {name}")


@cli.command()
def tags():
    """List available paralinguistic tags for the Turbo model."""
    tag_list = ModelManager.get_paralinguistic_tags()

    console.print(Panel.fit(
        "[bold cyan]⚡ Paralinguistic Tags (Turbo Model)[/bold cyan]",
        border_style="cyan",
    ))

    console.print("Add these tags directly in your text for expressive speech:\n")
    for tag in tag_list:
        console.print(f"  [cyan]{tag}[/cyan]")

    console.print("\n[dim]Example: 'Hello there! [laugh] How are you?'[/dim]")


@cli.command()
def info():
    """Show device and system information."""
    import torch

    console.print(Panel.fit(
        "[bold cyan]📊 System Information[/bold cyan]",
        border_style="cyan",
    ))

    # Device info
    device = "mps" if torch.backends.mps.is_available() else (
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    console.print(f"  [yellow]Device:[/yellow] {device}")
    console.print(f"  [yellow]MPS Available:[/yellow] {torch.backends.mps.is_available()}")
    console.print(f"  [yellow]CUDA Available:[/yellow] {torch.cuda.is_available()}")
    console.print(f"  [yellow]PyTorch Version:[/yellow] {torch.__version__}")

    # HuggingFace token status
    token = os.getenv("HUGGINGFACE_TOKEN")
    token_status = "✓ Configured" if token and token != "your_token_here" else "✗ Not configured"
    console.print(f"  [yellow]HuggingFace Token:[/yellow] {token_status}")


@cli.command()
@click.option("--all", "download_all", is_flag=True, help="Download all models")
@click.option(
    "-m", "--model",
    type=click.Choice(["turbo", "multilingual", "original"]),
    multiple=True,
    help="Specific model(s) to download",
)
def download(download_all, model):
    """Pre-download models for offline use."""
    models_to_download = []

    if download_all:
        models_to_download = ["turbo", "multilingual", "original"]
    elif model:
        models_to_download = list(model)
    else:
        console.print("[yellow]Please specify --all or -m MODEL[/yellow]")
        return

    console.print(Panel.fit(
        f"[bold cyan]📥 Downloading Models[/bold cyan]\n"
        f"Models: [yellow]{', '.join(models_to_download)}[/yellow]",
        border_style="cyan",
    ))

    engine = TTSEngine()

    for m in models_to_download:
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Downloading {m}...", total=None)
                engine.generate(
                    text="Test",
                    model_type=m,
                )
                progress.update(task, description=f"✓ {m} ready")

            console.print(f"[green]✓ {m} model downloaded successfully[/green]")

        except Exception as e:
            console.print(f"[red]✗ Failed to download {m}: {str(e)}[/red]")

    # Clear memory after downloads
    engine.unload_models()
    console.print("\n[bold green]✓ Download complete![/bold green]")


if __name__ == "__main__":
    cli()

