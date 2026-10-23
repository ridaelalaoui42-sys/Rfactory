#!/usr/bin/env python3
"""Generate actual Gemini WAV narration and optionally mux corrected puzzle Reels.

Use your own valid Gemini free-tier API key on a network-connected computer:

  GEMINI_API_KEY=... python -m scripts.generate_puzzle_tts \\
    --output-dir ./narrations \\
    --input-video-dir ./corrected_v2

No live Gemini request occurs unless this script is executed by the operator.
The API key stays in the process environment and is never printed/committed.
"""
from __future__ import annotations

import argparse
import io
import os
from pathlib import Path
import subprocess
import sys
import wave

from services.ai.studio import GeminiCreativeStudio, VoiceBrief, MODELS

SCRIPTS = {
    "sea_turtle": "Can you complete this turtle's shell? Watch the moving piece. Three, two, one! Perfect fit!",
    "farm_cow": "Can you fix the cow? Pause when the missing piece fits exactly. Three, two, one!",
    "scarlet_macaw": "Complete the macaw's feathers! Watch for the perfect fit. Three, two, one!",
}


def mux_tts(video: Path, wav: Path, output: Path) -> None:
    """Keep original music quietly under verified Gemini speech."""
    with wave.open(str(wav), "rb") as reader:
        duration = reader.getnframes() / reader.getframerate()
    if duration > 10.8:
        raise RuntimeError(
            f"Narration {duration:.2f}s is too long for a 12s Reel. "
            "Shorten text or use a quicker voice; never silently cut dialogue."
        )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video), "-i", str(wav),
        "-filter_complex",
        "[0:a]volume=0.22[bed];"
        "[1:a]adelay=650|650,volume=1.30[speech];"
        "[bed][speech]amix=inputs=2:duration=first:dropout_transition=0,"
        "alimiter=limit=0.93[mixed]",
        "-map", "0:v:0", "-map", "[mixed]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        "-t", "12", "-movflags", "+faststart", str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError("FFmpeg TTS mux failed: " + result.stderr[-600:])


def main() -> int:
    parser = argparse.ArgumentParser(description="Gemini TTS for exact-fitting puzzle Reels")
    parser.add_argument("--output-dir", default="./narrations")
    parser.add_argument("--input-video-dir", default=None, help="Folder with *_corrected.mp4 files")
    parser.add_argument("--voice", default="Kore")
    parser.add_argument("--model", choices=MODELS["tts"], default="gemini-3.8-flash-lite-tts")
    args = parser.parse_args()
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        parser.error("Set GEMINI_API_KEY securely in your shell. Never paste into repo.")
    os.environ["RFACTORY_AI_ENABLED"] = "true"
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    provider = GeminiCreativeStudio()
    for scene, transcript in SCRIPTS.items():
        audio = provider.voice(VoiceBrief(
            text=transcript,
            style="Upbeat, friendly family game-show host, brisk but clear; no extra words.",
            voice=args.voice,
            language="en",
            model=args.model,
        ))
        with wave.open(io.BytesIO(audio), "rb") as reader:
            seconds = reader.getnframes() / reader.getframerate()
        wav = out / (scene + ".wav")
        wav.write_bytes(audio)
        print(f"{scene}: actual Gemini WAV {seconds:.2f}s, {len(audio)} bytes, model={args.model}")
        if args.input_video_dir:
            folder = Path(args.input_video_dir)
            source = folder / (scene + "_corrected.mp4")
            if not source.exists():
                raise FileNotFoundError(f"Missing source video: {source}")
            final = folder / (scene + "_gemini_tts.mp4")
            mux_tts(source, wav, final)
            print(f"Mixed verified Gemini narration: {final}")
    print("Finished. Source narration is real Gemini TTS; no offline substitution.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
