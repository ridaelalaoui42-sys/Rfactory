"""Rfactory 3 motion + geometry release matrix (original bundled assets).

Generates six playable 9:16 MP4s, actual frame QA and exact-fit metadata.
Default 3-second CI smoke. Use --duration 12 for full demos on a VM.
No Gemini keys, real people, publishing or imported third-party art.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.engine.renderer import RenderConfig, PuzzleVideoRenderer
from services.engine.qa_validator import validate_rendered_video

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("fox", "bezier_sweep", "organic"),
    ("turtle", "catmull_wave", "jigsaw"),
    ("penguin", "figure_eight", "ellipse"),
    ("giraffe", "helix", "curved_band"),
    ("toucan", "vortex", "ring_sector"),
    ("astronaut_hero", "magnetic", "hexagon"),
)


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--duration",type=float,default=3.0)
    parser.add_argument("--output-dir",type=Path,default=Path("storage/rfactory3-showcase"))
    parser.add_argument("--count",type=int,default=3)
    args=parser.parse_args()
    if not 2 <= args.duration <= 30:
        parser.error("duration must be 2-30 seconds")
    if not 1 <= args.count <= 12:
        parser.error("crossing count must be 1-12")
    output=args.output_dir.resolve()
    output.mkdir(parents=True,exist_ok=True)
    renderer=PuzzleVideoRenderer(ROOT/"storage"/"assets",output)
    manifest=[]
    for index,(species, motion,geometry) in enumerate(CASES):
        cfg=RenderConfig(
            job_id=f"v3_{species}_{motion}",species=species,
            template_id="MISSING_PIECE_SLIDE",fps=30,
            duration_sec=args.duration,cycles=args.count,
            snap_count=args.count,continuous_motion=True,
            motion_profile=motion,puzzle_geometry=geometry,
            seed=37711+index*13,enable_audio=False,
            motion_intensity=1.0,
        )
        result=renderer.render_video(cfg)
        qa=validate_rendered_video(
            result.mp4_path,expected_duration_sec=args.duration,
            require_audio=False,missing_piece_mad=result.pixel_match_mad,
        )
        if not qa.passed:
            raise AssertionError(f"{species}: {qa.errors}")
        snap_meta=json.loads(Path(result.mp4_path).with_suffix(".snaps.json").read_text())
        frame_qa=json.loads(Path(result.mp4_path).with_suffix(".frameqa.json").read_text())
        if len(result.alignment_frames)!=args.count or result.pixel_match_mad!=0.0:
            raise AssertionError("Exact crossing count/accuracy failed")
        if not frame_qa.get("passed") or any(
            p["first_locked_frame"]!=p["last_locked_frame"] for p in snap_meta["snap_windows"]
        ):
            raise AssertionError("Frame QA or continuous-motion hold failure")
        manifest.append({
            "subject":species,
            "motion_profile":motion,
            "puzzle_geometry":geometry,
            "video":str(Path(result.mp4_path).relative_to(output)),
            "duration_sec":args.duration,
            "exact_fit_times_sec":snap_meta["snap_timestamps_sec"],
            "raw_exact_match_mad":result.pixel_match_mad,
            "decoded_frames_checked":frame_qa["frames_checked"],
            "audio":"none",
            "art_provenance":"original included procedural assets; no Gemini API call",
            "published":False,
        })
        print(f"PASS: {species} / {motion} / {geometry}: {snap_meta['snap_timestamps_sec']}",flush=True)
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(f"SUCCESS: six rendered cases in {output}",flush=True)


if __name__=="__main__":
    main()
