#!/bin/bash
# SurAIverse TTS Studio — Mac one-click launcher
# Double-click this file in Finder to launch the app

# Change to the directory containing this script
cd "$(dirname "$0")"

# Hand off to run.sh (handles venv, updates, and launch)
bash run.sh "$@"
