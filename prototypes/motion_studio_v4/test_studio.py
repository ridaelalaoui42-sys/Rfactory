"""Regression tests for optional VTK 3D engineering prototype."""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from studio import CUES, DURATION, LabelBox, TextGuard, synth_sounds


class MotionStudioTest(unittest.TestCase):
    def test_beats_cover_story_without_gaps(self):
        self.assertEqual(CUES[0].begin, 0)
        for left, right in zip(CUES, CUES[1:]):
            self.assertAlmostEqual(left.end, right.begin)
        self.assertEqual(CUES[-1].end, DURATION)

    def test_collision_is_rejected(self):
        guard = TextGuard(1080, 1920)
        guard.label(LabelBox("A", (100, 300, 330, 440), 1, 1, "title"))
        guard.label(LabelBox("B", (250, 370, 530, 510), 1, 1, "label"))
        self.assertTrue(any(v["type"] == "overlap" for v in guard.violations))

    def test_outside_safe_area_is_rejected(self):
        guard = TextGuard(1080, 1920)
        guard.label(LabelBox("outside", (1, 30, 100, 200), 1, 1, "label"))
        self.assertTrue(any(v["type"] == "unsafe" for v in guard.violations))

    def test_deterministic_audio_events_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = synth_sounds(pathlib.Path(tmp) / "sfx.wav", dur=0.6)
            self.assertGreater(meta["peak"], 0.05)
            self.assertGreater(pathlib.Path(meta["path"]).stat().st_size, 10000)


if __name__ == "__main__":
    unittest.main()
