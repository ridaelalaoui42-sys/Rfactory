"""No-pausing motion contract: exactly one solved frame per random crossing."""
import json
import tempfile
import unittest
from pathlib import Path

from services.engine.motion_profiles import MOTION_PROFILES, continuous_motion_pose
from services.engine.snap_timeline import build_crossing_timeline
from services.engine.renderer import RenderConfig, PuzzleVideoRenderer

ASSETS = Path(__file__).resolve().parents[1] / "storage" / "assets"


class ContinuousCrossingTests(unittest.TestCase):
    def test_irregular_seeded_crossings_have_single_frame_only(self):
        t=build_crossing_timeline(360,30,5,seed=2340)
        self.assertEqual(len(t.passes),5)
        self.assertNotEqual(len(set(p.duration for p in t.passes)),1)
        self.assertEqual([p.first_locked_frame for p in t.passes],
                         [p.last_locked_frame for p in t.passes])
        self.assertEqual(sum(t.is_locked(i) for i in range(t.total_frames)),5)
        self.assertEqual(t,build_crossing_timeline(360,30,5,seed=2340))
        self.assertNotEqual(t.snap_times(),build_crossing_timeline(360,30,5,seed=2341).snap_times())

    def test_every_profile_crosses_with_nonzero_motion_and_no_pause(self):
        t=build_crossing_timeline(360,30,5,seed=49)
        for profile in MOTION_PROFILES:
            for part in t.passes:
                before=continuous_motion_pose(profile,t.phase(part.first_locked_frame-1),220,seed=2)
                fit=continuous_motion_pose(profile,t.phase(part.first_locked_frame),220,seed=2)
                after=continuous_motion_pose(profile,t.phase(part.first_locked_frame+1),220,seed=2)
                self.assertTrue(fit.identity)
                self.assertTrue(fit.locked)
                self.assertFalse(before.locked)
                self.assertFalse(after.locked)
                self.assertFalse(before.identity)
                self.assertFalse(after.identity)
                self.assertNotEqual(before,after)

    def test_no_frozen_frames_in_one_pass(self):
        timeline=build_crossing_timeline(90,30,1,seed=9)
        for profile in MOTION_PROFILES:
            poses=[continuous_motion_pose(profile,timeline.phase(i),330,seed=3) for i in range(90)]
            for i in range(1,90):
                self.assertNotEqual(poses[i],poses[i-1],(profile,i))
            # Consecutive passes join at identical off-target poses.
            self.assertEqual(
                continuous_motion_pose(profile,0,330,seed=3),
                continuous_motion_pose(profile,1,330,seed=3),
            )

    def test_actual_reel_has_five_single_frame_fits(self):
        with tempfile.TemporaryDirectory(prefix="continuous_fits_") as tmp:
            renderer=PuzzleVideoRenderer(ASSETS, Path(tmp))
            config=RenderConfig(
                job_id="five_crossings",template_id="MISSING_PIECE_SLIDE",
                species="donkey",duration_sec=4.0,fps=30,
                snap_count=5,cycles=5,seed=1407,
                enable_audio=False,motion_profile="orbit_lock",
                continuous_motion=True,
            )
            artifact=renderer.render_video(config)
            self.assertEqual(len(artifact.alignment_frames),5)
            self.assertEqual(artifact.pixel_match_mad,0.0)
            vid=Path(artifact.mp4_path)
            snaps=json.loads(vid.with_suffix(".snaps.json").read_text())
            qa=json.loads(vid.with_suffix(".frameqa.json").read_text())
            self.assertEqual(snaps["hold_frames_per_match"],1)
            self.assertTrue(snaps["continuous_motion"])
            self.assertEqual(snaps["snap_count"],5)
            self.assertEqual(qa["frames_checked"],120)
            self.assertTrue(qa["passed"])


if __name__=="__main__":
    unittest.main()
