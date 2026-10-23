#!/usr/bin/env python3
"""Generate actual Gemini narration WAVs for precision puzzle videos.

Run on a network-enabled local PC/server after setting GEMINI_API_KEY.
This script NEVER prints, stores or sends the key anywhere except the official
Google Gemini API as part of the SDK authentication flow.

  python -m scripts.generate_puzzle_tts --output-dir ./rfactory_showcase

It saves sea_turtle_gemini.wav, farm_cow_gemini.wav, and
scarlet_macaw_gemini.wav. The showcase renderer mixes them into each Reel
on its next render. No offline imitation is labeled as Gemini output.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import os
import sys
import wave
import io

from services.ai.studio import GeminiCreativeStudio, VoiceBrief, MODELS

SCRIPTS = {
    "sea_turtle": "Can you complete the sea turtle? Focus on the missing shell piece. Catch the perfect fit!",
    "farm_cow": "Can you complete the cow? Stop the piece at the exact moment it matches!",
    "scarlet_macaw": "Can you solve the scarlet macaw puzzle? Stop when the feather texture lines up!",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="./rfactory_showcase")
    parser.add_argument("--voice", default="Kore")
    parser.add_argument("--model", choices=MODELS["tts"], default="gemini-3.8-flash-lite-tts")
    parser.add_argument("--language", choices=["en", "fr", "es", "ar"], default="en")
    args=parser.parse_args()
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        parser.error("Set GEMINI_API_KEY in your shell (not in source code).")
    os.environ["RFACTORY_AI_ENABLED"]="true"
    output=Path(args.output_dir)
    output.mkdir(parents=True,exist_ok=True)
    studio=GeminiCreativeStudio()
    for key,text in SCRIPTS.items():
        audio=studio.voice(VoiceBrief(
            text=text, style="Playful, friendly game-show presenter; quick, precise and upbeat.",
            language=args.language,voice=args.voice,model=args.model,
        ))
        # Gemini unary audio must be a valid WAV with a RIFF header.
        with wave.open(io.BytesIO(audio),"rb") as check:
            seconds=round(check.getnframes()/check.getframerate(),2)
        dest=output/(key+"_gemini.wav")
        dest.write_bytes(audio)
        print(f"{key}: Gemini WAV saved, {seconds}s, model={args.model}")
    print("WAV files are ready to be muxed into the 3 precision puzzle videos.")
    return 0

if __name__=="__main__":
    sys.exit(main())
