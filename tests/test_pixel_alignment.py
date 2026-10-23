"""Regression tests that disallow visual lookalikes as puzzle fragments."""
import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np

from services.engine.precision_qa import (
    audit_video_every_frame, exact_cutout_match, extract_canonical_piece,
    audit_against_expected_frames,
)


class PixelExactPuzzleTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(42)
        self.image=rng.integers(0,255,(210,320,3),dtype=np.uint8)
        self.mask=np.zeros((65,90),dtype=np.uint8)
        cv2.rectangle(self.mask,(7,10),(82,59),255,-1)
        cv2.circle(self.mask,(45,9),9,255,-1)
        self.target=(110,70)

    def test_correct_fragment_reconstructs_canonical(self):
        base,piece=extract_canonical_piece(self.image,self.mask,self.target)
        report=exact_cutout_match(self.image,base,piece,self.mask,self.target)
        self.assertTrue(report.exact)
        self.assertEqual(report.mad,0.0)
        self.assertEqual(report.mismatch_count,0)

    def test_independently_generated_lookalike_fails(self):
        base,piece=extract_canonical_piece(self.image,self.mask,self.target)
        wrong=np.roll(piece,1,axis=1)  # visually similar, 1-pixel texture shift
        report=exact_cutout_match(self.image,base,wrong,self.mask,self.target)
        self.assertFalse(report.exact)
        self.assertGreater(report.mismatch_count,100)
        self.assertGreater(report.mad,0.01)

    def test_wrong_slot_or_soft_alpha_rejected(self):
        base,piece=extract_canonical_piece(self.image,self.mask,self.target)
        bad_mask=self.mask.copy();bad_mask[0,0]=128
        with self.assertRaises(ValueError):
            exact_cutout_match(self.image,base,piece,bad_mask,self.target)
        wrong_slot=(self.target[0]+1,self.target[1])
        report=exact_cutout_match(self.image,base,piece,self.mask,wrong_slot)
        self.assertFalse(report.exact)

    def test_full_video_fails_on_blank_middle_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"frames.avi"
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"MJPG"),10,(180,320))
            self.assertTrue(writer.isOpened())
            for idx in range(10):
                image=np.zeros((320,180,3),np.uint8)
                image[:,:,0]=np.arange(180,dtype=np.uint8)[None,:]
                image[:,:,1]=np.arange(320,dtype=np.uint8)[:,None]
                image[:,:,2]=(idx%2)*15
                if idx==5:image[:]=0
                writer.write(image)
            writer.release()
            with self.assertRaises(AssertionError):
                audit_video_every_frame(path,expected_frames=10,min_frame_std=10)


    def test_every_decoded_frame_matches_source_and_detects_drift(self):
        # The old QA checked only frame 0..44 and the final frame. Deliberately
        # corrupt a middle-frame EXPECTATION: an actual match detector must fail.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reference.avi"
            rng = np.random.default_rng(13)
            rgb = rng.integers(35, 210, (320, 180, 3), dtype=np.uint8)
            writer = cv2.VideoWriter(
                str(out), cv2.VideoWriter_fourcc(*"MJPG"), 10, (180, 320)
            )
            self.assertTrue(writer.isOpened())
            for _ in range(12):
                writer.write(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
            writer.release()

            report = audit_against_expected_frames(
                out, expected_frame=lambda idx: rgb, expected_frames=12,
                max_frame_mae=25.0, max_average_mae=15.0,
                sample_wh=(90, 160),
            )
            self.assertTrue(report["passed"])
            self.assertEqual(report["frames_checked"], 12)

            def wrong_reference(index):
                return np.roll(rgb, 70, axis=1) if index == 7 else rgb

            with self.assertRaises(AssertionError):
                audit_against_expected_frames(
                    out, expected_frame=wrong_reference, expected_frames=12,
                    max_frame_mae=25.0, max_average_mae=15.0,
                    sample_wh=(90, 160),
                )

    def test_full_video_checks_frame_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"frames.avi"
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"MJPG"),10,(180,320))
            self.assertTrue(writer.isOpened())
            rng=np.random.default_rng(5)
            frame=rng.integers(20,210,(320,180,3),dtype=np.uint8)
            for _ in range(10):writer.write(frame)
            writer.release()
            status=audit_video_every_frame(path,expected_frames=10)
            self.assertEqual(status["decoded_frames"],10)
            self.assertTrue(status["passed"])
            with self.assertRaises(AssertionError):
                audit_video_every_frame(path,expected_frames=11)


if __name__=="__main__":
    unittest.main()
