#!/usr/bin/env python3
"""Render a self-contained batch of original puzzle videos.

Example:
    python -m scripts.run_batch --count 10 --duration 15 --template ALL
Creates /storage/renders and records jobs in the local SQLite DB.
No Facebook publishing is performed.
"""
import argparse
from pathlib import Path
import sys

from scripts.bootstrap_factory import bootstrap
from services.content.agent import ContentGenerationAgent
from services.engine.renderer import PuzzleVideoRenderer
from services.worker.batch_runner import BatchProductionWorker

ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "storage"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render original puzzle videos offline")
    parser.add_argument("--count", type=int, default=2, help="Number of distinct puzzles, 1 to 100")
    parser.add_argument("--duration", type=float, default=15.0, help="Duration in seconds, 2 to 30")
    parser.add_argument("--template", choices=["ALL", "OUTLINE_MATCH", "MISSING_PIECE_SLIDE", "FACE_FEATURE_SLIDE", "FACE_SPLIT_3BAND"], default="ALL")
    parser.add_argument("--seed", type=int, default=1001)
    parser.add_argument("--audio", action="store_true", help="Include synthesized SFX")
    args = parser.parse_args()
    if not 1 <= args.count <= 100:
        parser.error("--count must be between 1 and 100")
    if not 2.0 <= args.duration <= 30.0:
        parser.error("--duration must be between 2 and 30 seconds")

    repo = bootstrap()
    renderer = PuzzleVideoRenderer(
        assets_root=STORAGE / "assets",
        outputs_root=STORAGE / "renders",
    )
    worker = BatchProductionWorker(
        repo=repo,
        renderer=renderer,
        content_agent=ContentGenerationAgent(),
    )
    batch_id, jobs = worker.enqueue_batch_campaign(
        name="Local offline puzzle batch",
        count=args.count,
        duration_sec=args.duration,
        template_filter=args.template,
        enable_audio=args.audio,
        base_seed=args.seed,
    )
    print(f"Enqueued {len(jobs)} render jobs in batch {batch_id}")
    results = worker.process_all_queued_jobs(limit=args.count)
    failures = 0
    for item in results:
        status = item.get("status")
        if status != "READY":
            failures += 1
        artifact = item.get("artifact", {})
        print(f"{status:6} {item.get('job_id')}: {artifact.get('mp4_path', item.get('error', ''))}")
    print(f"Completed: {len(results)-failures}/{len(results)} — exports in {STORAGE / 'renders'}")
    return 1 if failures or len(results) != args.count else 0


if __name__ == "__main__":
    sys.exit(main())
