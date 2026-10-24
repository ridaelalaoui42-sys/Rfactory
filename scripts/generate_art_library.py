#!/usr/bin/env python3
"""Generate actual HD puzzle-ready source images through the Gemini image API.

This script NEVER silently substitutes procedural art. The production image
models may require a paid API project. --execute and --allow-paid-image-api
are BOTH necessary before any provider call; --dry-run only prints plans.

Usage:
  python -m scripts.generate_art_library --dry-run
  RFACTORY_AI_ENABLED=true GEMINI_API_KEY=... \
    python -m scripts.generate_art_library --execute --allow-paid-image-api \
      --category animals --count 3 --model gemini-3.1-flash-lite-image
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from services.ai.studio import GeminiCreativeStudio, ImageBrief, MODELS
from services.assets.library import AssetLibrary, LibraryError

ROOT=Path(__file__).resolve().parents[1]
SUBJECTS = {
    "animals": (
        "snow leopard", "red panda", "octopus", "seahorse",
        "kingfisher", "golden eagle", "arctic fox", "chameleon",
        "macaw", "sea turtle", "wolf", "penguin",
    ),
    "characters": (
        "original futuristic astronaut", "friendly original explorer robot",
        "original woodland wizard", "friendly fantasy knight",
        "original sci-fi pilot", "stylized submarine explorer",
    ),
    "fantasy": (
        "original mechanical dragon", "golden feather phoenix",
        "luminous forest guardian", "crystalline sea serpent",
        "enchanted griffin", "clockwork steampunk owl",
    ),
    "vehicles": (
        "concept hypercar without branding", "vintage space rover",
        "original exploration submarine", "futuristic rescue helicopter",
    ),
    "objects": (
        "antique astrolabe", "crystal geode", "precision mechanical clock",
        "antique treasure chest", "vintage film camera",
    ),
}
DEFAULT_IMAGE_MODEL="gemini-3.1-flash-lite-image"


def prompt_for(subject: str, category: str, style: str) -> str:
    return (
        f"Create ONE complete, standalone {subject} as a premium {style} subject asset "
        "for a visual puzzle game. The animal or figure must be anatomically coherent, "
        "recognizable and visually original, with rich authentic texture, realistic "
        "material response, beautifully controlled studio lighting, and professional "
        "color grading. Entire subject visible from head to toe/tail or complete "
        "object borders, centered with 12 percent generous clean margins. "
        "Single isolated object, no scenery or secondary characters, no frame, "
        "no split-panel collage, no holes or missing pieces, no labels, no logos, "
        "no stylized user-interface elements. Smooth pure white background. "
        "One flawless canonical image: all puzzle pieces are extracted later "
        "from its exact original pixels. Aim for polished production illustration."
    )


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--category",choices=["all",*SUBJECTS],default="animals")
    parser.add_argument("--count",type=int,default=6)
    parser.add_argument("--style",choices=["premium_3d","editorial","hand_painted","clay","storybook","neon"],default="premium_3d")
    parser.add_argument("--model",choices=MODELS["image"],default=DEFAULT_IMAGE_MODEL)
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--allow-paid-image-api",action="store_true")
    parser.add_argument("--storage-root",type=Path,default=ROOT/"storage")
    args=parser.parse_args()
    if not 1 <= args.count <= 36:
        parser.error("--count must be 1 to 36")
    available=[
        (cat,subj) for cat,subjects in SUBJECTS.items()
        for subj in subjects if args.category in ("all",cat)
    ][:args.count]
    summary={
        "model":args.model,
        "requested":len(available),
        "paid_image_calls_required":not args.dry_run,
        "prompts":[{"category":cat,"subject":subject,
                    "prompt":prompt_for(subject,cat,args.style)} for cat,subject in available],
    }
    if not args.execute or args.dry_run:
        print(json.dumps(summary,indent=2,ensure_ascii=False))
        print("DRY RUN ONLY. NO GEMINI IMAGE API CALLS WERE MADE.")
        return 0
    if not args.allow_paid_image_api:
        parser.error("Image generation can require paid access. Supply --allow-paid-image-api explicitly.")
    if os.getenv("RFACTORY_AI_ENABLED","false").lower()!="true" or not (
        os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    ):
        parser.error("Enable Gemini and configure server GEMINI_API_KEY first.")

    library=AssetLibrary(args.storage_root)
    provider=GeminiCreativeStudio()
    generated=[]
    for category, subject in available:
        brief=ImageBrief(prompt=prompt_for(subject,category,args.style),
                         style=args.style,model=args.model)
        try:
            real_bytes, actual_prompt=provider.image(brief)
            result=library.add_image(
                real_bytes,subject,category,
                tier="production_generated",
                provenance="gemini_generated",
                source_description=f"Actual Google Gemini model {args.model}. Prompt: {actual_prompt[:340]}",
            )
        except Exception as exc:
            print(f"FAIL {subject}: {type(exc).__name__}: provider/media generation unsuccessful")
            raise SystemExit(1) from None
        if not result["production_eligible"]:
            print(f"FAIL {subject}: provider returned an undersized image; human review required")
            raise SystemExit(1)
        generated.append({"id":result["id"],"subject":subject,"source":"gemini",
                          "model":args.model,"approved":False})
        print(f"CREATED {subject}: {result['id']} (awaiting review)",flush=True)
    print(json.dumps({"generated":generated},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
