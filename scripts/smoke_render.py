#!/usr/bin/env python3
"""Offline renderer smoke test; produces and validates a real vertical MP4.

Run: python -m scripts.smoke_render
No Facebook account, API key, database fixture or external AI model needed.
"""
from pathlib import Path
import tempfile

from services.engine.renderer import PuzzleVideoRenderer, RenderConfig
from services.engine.qa_validator import validate_rendered_video

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="rfactory_render_smoke_") as tmp:
        out = Path(tmp)
        renderer = PuzzleVideoRenderer(
            assets_root=ROOT / "storage" / "assets",
            outputs_root=out,
        )
        config = RenderConfig(
            job_id="smoke_donkey",
            template_id="MISSING_PIECE_SLIDE",
            species="donkey",
            seed=1002,
            width=1080,
            height=1920,
            fps=30,
            duration_sec=2.0,
            cycles=1,
            enable_audio=False,
        )
        result = renderer.render_video(config)
        qa = validate_rendered_video(
            result.mp4_path,
            expected_width=1080,
            expected_height=1920,
            expected_fps=30.0,
            expected_duration_sec=2.0,
            require_audio=False,
            missing_piece_mad=result.pixel_match_mad,
        )
        if not qa.passed:
            raise SystemExit("Renderer smoke test FAILED: " + "; ".join(qa.errors))
        print(f"PASS: 1080x1920 30fps H.264 MP4, {qa.duration_sec:.3f}s, {qa.file_size_bytes:,} bytes, MAD={result.pixel_match_mad}")


if __name__ == "__main__":
    main()
