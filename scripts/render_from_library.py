#!/usr/bin/env python3
"""Render a real-image puzzle from an approved, canonical library asset.

Free/offline mode: no Gemini generation and no procedural animal substitution.
The image source and fragment must be exact same accepted media.

python -m scripts.render_from_library --asset-id <id> --duration 12 \
  --geometry organic --motion orbit_lock --crossings 5

If the selected asset is labeled fallback, add --allow-fallback explicitly.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import uuid

from services.assets.library import AssetLibrary, LibraryError
from services.engine.motion_profiles import MOTION_PROFILES
from services.engine.puzzle_geometry import GEOMETRIES
from services.engine.renderer import PuzzleVideoRenderer, RenderConfig
from services.engine.qa_validator import validate_rendered_video

ROOT = Path(__file__).resolve().parents[1]


def render_approved_asset(
    asset_id: str, *,
    storage_root: Path,
    allow_fallback: bool,
    geometry: str,
    motion: str,
    duration: float,
    crossings: int,
    seed: int,
    enable_sfx: bool,
) -> dict:
    library=AssetLibrary(storage_root)
    asset=library.get(asset_id)
    if not asset["approved"] or not asset["production_eligible"]:
        raise LibraryError("Only approved original high-resolution artwork can be rendered")
    if asset["is_fallback"] and not allow_fallback:
        raise LibraryError("Opt in to explicitly labeled fallback by passing --allow-fallback")
    if geometry not in GEOMETRIES or motion not in MOTION_PROFILES:
        raise LibraryError("Unknown puzzle geometry or motion profile")
    if not 2 <= duration <= 30 or not 1 <= crossings <= 12:
        raise LibraryError("Duration must be 2-30s and crossings must be 1-12")
    video_id="library_"+uuid.uuid4().hex[:14]
    renderer=PuzzleVideoRenderer(storage_root/"assets",storage_root/"renders")
    config=RenderConfig(
        job_id=video_id,
        template_id="MISSING_PIECE_SLIDE",
        species="curated_artwork",
        asset_path=f"library/images/{asset_id}.png",
        duration_sec=duration, fps=30,
        cycles=crossings, snap_count=crossings,
        motion_profile=motion, puzzle_geometry=geometry,
        randomize_snap_timing=True, continuous_motion=True,
        enable_audio=enable_sfx, sound_mode="match_only",
        seed=seed,
    )
    rendered=renderer.render_video(config)
    qa=validate_rendered_video(
        rendered.mp4_path, expected_duration_sec=duration,
        require_audio=enable_sfx,
        missing_piece_mad=rendered.pixel_match_mad,
    )
    if not qa.passed or len(rendered.alignment_frames)!=crossings or rendered.pixel_match_mad!=0.0:
        raise RuntimeError("Video alignment or decoding QA failed; output is not ready")
    video=Path(rendered.mp4_path)
    snap=json.loads(video.with_suffix(".snaps.json").read_text())
    frameqa=json.loads(video.with_suffix(".frameqa.json").read_text())
    if not frameqa.get("passed"):
        raise RuntimeError("Full-frame QA did not pass")
    provenance={
        "video":str(video),
        "source_asset_id":asset_id,
        "source_subject":asset["subject"],
        "source_provenance":asset["provenance"],
        "source_sha256":asset["sha256"],
        "generated_with_gemini_during_this_render":False,
        "explicit_fallback":bool(asset["is_fallback"]),
        "render_mode":"canonical-original-image",
        "geometry":geometry,
        "motion_profile":motion,
        "continuous_motion":True,
        "exact_fit_frames":rendered.alignment_frames,
        "exact_fit_times_sec":snap["snap_timestamps_sec"],
        "raw_alignment_mad":rendered.pixel_match_mad,
        "all_frames_checked":frameqa["frames_checked"],
        "qa_passed":True,
        "published":False,
    }
    video.with_suffix(".provenance.json").write_text(
        json.dumps(provenance,indent=2),encoding="utf-8"
    )
    return provenance


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--asset-id",required=True)
    parser.add_argument("--storage-root",type=Path,default=ROOT/"storage")
    parser.add_argument("--allow-fallback",action="store_true")
    parser.add_argument("--geometry",choices=GEOMETRIES,default="organic")
    parser.add_argument("--motion",choices=MOTION_PROFILES,default="orbit_lock")
    parser.add_argument("--duration",type=float,default=12.0)
    parser.add_argument("--crossings",type=int,default=5)
    parser.add_argument("--seed",type=int,default=77013)
    parser.add_argument("--no-sfx",action="store_true")
    args=parser.parse_args()
    try:
        report=render_approved_asset(
            args.asset_id,storage_root=args.storage_root,
            allow_fallback=args.allow_fallback,geometry=args.geometry,
            motion=args.motion,duration=args.duration,
            crossings=args.crossings,seed=args.seed,
            enable_sfx=not args.no_sfx,
        )
    except (LibraryError,ValueError,FileNotFoundError,RuntimeError) as exc:
        print(f"FAILED: {exc}",file=sys.stderr)
        return 1
    print(json.dumps(report,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
