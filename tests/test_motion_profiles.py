"""Regression checks for cinematic movements with mathematically exact solved frames."""
from pathlib import Path
import tempfile
import unittest

import numpy as np

from services.engine.motion_profiles import MOTION_PROFILES, MotionPose, motion_pose, transformed_sprite
from services.engine.renderer import RenderConfig, PuzzleVideoRenderer
from services.engine.qa_validator import validate_rendered_video

ASSETS = Path(__file__).resolve().parents[1] / "storage" / "assets"


class CinematicMotionTests(unittest.TestCase):
    def test_every_motion_profile_holds_exact_identity(self):
        source = np.random.default_rng(987).integers(0, 256, (79, 97, 4), dtype=np.uint8)
        for name in MOTION_PROFILES:
            for phase in (0.44, 0.50, 0.56):
                pose = motion_pose(name, phase, travel_px=240, seed=1)
                self.assertTrue(pose.locked, (name, phase))
                self.assertTrue(pose.identity, (name, phase))
                actual, offset = transformed_sprite(source, pose)
                self.assertIs(actual, source)
                self.assertEqual(offset, (0, 0))
                self.assertTrue(np.array_equal(actual, source))

    def test_profiles_are_visual_distinct_with_real_transformations(self):
        source = np.zeros((95, 120, 4), dtype=np.uint8)
        source[15:55, 10:95, :] = (220, 111, 56, 255)
        signatures = set()
        for name in MOTION_PROFILES:
            pose = motion_pose(name, 0.12, travel_px=230, seed=2)
            self.assertFalse(pose.locked)
            self.assertFalse(pose.identity)
            transformed, offset = transformed_sprite(source, pose)
            self.assertEqual(transformed.shape[2], 4)
            self.assertGreater(int(transformed[:, :, 3].max()), 0)
            signature = (pose.dx, pose.dy, round(pose.angle_deg, 1),
                         round(pose.scale_x, 2), round(pose.scale_y, 2))
            self.assertNotIn(signature, signatures, name)
            signatures.add(signature)
        self.assertEqual(len(signatures), len(MOTION_PROFILES))

    def test_intensity_does_not_affect_pixel_perfect_snap(self):
        for intensity in (0.0, 0.6, 1.0, 1.8, 2.0):
            for name in MOTION_PROFILES:
                pose = motion_pose(name, .5, travel_px=430,
                                   hold_ratio=.14, intensity=intensity)
                self.assertEqual(pose, MotionPose(locked=True))

    def test_validation_rejects_unknown_profiles_and_bad_intensity(self):
        with self.assertRaises(ValueError):
            motion_pose("unknown", .1)
        with self.assertRaises(ValueError):
            motion_pose("spin_snap", .1, intensity=3)

    def test_end_to_end_rotating_missing_piece_reel_is_decodable(self):
        with tempfile.TemporaryDirectory(prefix="rfactory_rotations_") as folder:
            renderer = PuzzleVideoRenderer(ASSETS, Path(folder))
            for profile in ("spin_snap", "orbit_lock", "flip_reveal"):
                config = RenderConfig(
                    job_id="motion_" + profile, template_id="MISSING_PIECE_SLIDE",
                    species="donkey", duration_sec=2.0, fps=30, cycles=1,
                    enable_audio=False, motion_profile=profile,
                    hold_ratio=0.18, motion_intensity=1.0,
                )
                artifact = renderer.render_video(config)
                self.assertGreater(len(artifact.alignment_frames), 3)
                self.assertAlmostEqual(artifact.pixel_match_mad, 0.0)
                report = validate_rendered_video(
                    artifact.mp4_path, expected_duration_sec=2.0,
                    require_audio=False, missing_piece_mad=artifact.pixel_match_mad,
                )
                self.assertTrue(report.passed, (profile, report.errors))
                self.assertTrue(Path(artifact.mp4_path).is_file())


if __name__ == "__main__":
    unittest.main()
