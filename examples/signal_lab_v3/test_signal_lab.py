"""Regression checks for the optional Signal Lab V3 engine."""
import pytest
pytest.importorskip("numpy")
pytest.importorskip("PIL")
from signal_lab_v3 import SHOTS, SECS, frame, CAPTIONS
import numpy as np

def test_timeline_is_contiguous():
    assert SHOTS[0].start == 0
    assert SHOTS[-1].end == SECS
    assert all(a.end == b.start for a,b in zip(SHOTS, SHOTS[1:]))

def test_real_frame_motion_in_every_shot():
    for shot in SHOTS:
        t = (shot.start + shot.end) / 2
        before = np.asarray(frame(t, 540, 960), dtype=np.int16)
        after = np.asarray(frame(t + 1/30, 540, 960), dtype=np.int16)
        assert np.abs(after - before).mean() > 0.025, shot.id

def test_captions_have_monotonic_timing():
    assert all(a < b for a,b,_ in CAPTIONS)
    assert all(a[0] <= b[0] for a,b in zip(CAPTIONS,CAPTIONS[1:]))
