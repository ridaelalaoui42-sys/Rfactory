"""Every puzzle must solve more than once, at seeded irregular video frames."""
import json
import tempfile
import unittest
from pathlib import Path

from services.engine.snap_timeline import build_snap_timeline
from services.engine.motion_profiles import MOTION_PROFILES, motion_pose
from services.engine.renderer import RenderConfig, PuzzleVideoRenderer

ROOT = Path(__file__).resolve().parents[1]


class RandomSnapTimelineTests(unittest.TestCase):
    def test_five_nonuniform_solves_across_fifteen_seconds(self):
        track = build_snap_timeline(450, fps=30, count=5, seed=4201, hold_ratio=.16)
        self.assertEqual(len(track.passes), 5)
        self.assertEqual(track.passes[0].start_frame, 0)
        self.assertEqual(track.passes[-1].end_frame, 450)
        durations = [entry.duration for entry in track.passes]
        self.assertGreater(len(set(durations)), 1, "Timings cannot repeat fixed-length loops")
        self.assertEqual(sum(durations), 450)
        times = track.snap_times()
        self.assertEqual(len(times), 5)
        self.assertTrue(all(0.0 < s < 15.0 for s in times))
        self.assertEqual(times, sorted(times))
        self.assertLess(times[0], 5)
        self.assertGreater(times[-1], 10)
        for event in track.passes:
            self.assertGreaterEqual(event.first_locked_frame, event.start_frame + 2)
            self.assertLess(event.last_locked_frame, event.end_frame - 2)
            self.assertGreaterEqual(event.last_locked_frame - event.first_locked_frame, 3)
            self.assertFalse(track.is_locked(event.start_frame))
            self.assertFalse(track.is_locked(event.end_frame - 1))
            self.assertTrue(track.is_locked(event.first_locked_frame))

    def test_frame_positions_are_random_but_reproducible(self):
        a = build_snap_timeline(360, 30, 5, 1997)
        b = build_snap_timeline(360, 30, 5, 1997)
        c = build_snap_timeline(360, 30, 5, 1998)
        self.assertEqual(a, b)
        self.assertNotEqual(a.snap_times(), c.snap_times())
        self.assertNotEqual(
            [x.duration for x in a.passes],
            [x.duration for x in c.passes],
        )

    def test_all_profiles_snap_exactly_at_every_window(self):
        track = build_snap_timeline(360, 30, 5, seed=72, hold_ratio=.14)
        for mode in MOTION_PROFILES:
            for frame in range(track.total_frames):
                pose = motion_pose(mode, track.phase(frame), seed=13, hold_ratio=.14)
                self.assertEqual(pose.locked, track.is_locked(frame), (mode,frame))
                if pose.locked:
                    self.assertTrue(pose.identity)

    def test_overcrowded_events_are_rejected(self):
        with self.assertRaises(ValueError):
            build_snap_timeline(40, fps=30, count=8, seed=1)
        with self.assertRaises(ValueError):
            build_snap_timeline(360, fps=30, count=13, seed=1)

    def test_real_mp4_has_three_irregular_solved_windows_and_qa_sidecars(self):
        with tempfile.TemporaryDirectory(prefix="rfactory_snap_timeline_") as directory:
            renderer = PuzzleVideoRenderer(ROOT / "storage" / "assets", Path(directory))
            config = RenderConfig(
                job_id="three_snap_test", template_id="MISSING_PIECE_SLIDE",
                species="donkey", duration_sec=3.0, fps=30,
                cycles=3, snap_count=3, randomize_snap_timing=True,
                motion_profile="spin_snap", enable_audio=False, seed=9077,
            )
            result = renderer.render_video(config)
            video = Path(result.mp4_path)
            metadata = json.loads(video.with_suffix(".snaps.json").read_text())
            quality = json.loads(video.with_suffix(".frameqa.json").read_text())
            self.assertTrue(video.is_file())
            self.assertEqual(metadata["snap_count"], 3)
            self.assertEqual(len(metadata["snap_timestamps_sec"]), 3)
            self.assertEqual(len(metadata["audio_snap_times_sec"]), 3)
            self.assertEqual(quality["frames_checked"], 90)
            self.assertTrue(quality["passed"])
            self.assertEqual(result.pixel_match_mad, 0.0)
            aligned_set = set(result.alignment_frames)
            for win in metadata["snap_windows"]:
                first, last = win["first_locked_frame"], win["last_locked_frame"]
                self.assertTrue(set(range(first, last + 1)).issubset(aligned_set))
                self.assertEqual(last, first)
                self.assertEqual(len(result.alignment_frames), 3)


if __name__ == "__main__":
    unittest.main()
