"""Pixel-exact puzzle integrity checks and exhaustive decoded-frame QA.

Use one canonical source image for both target slot and moving piece. Never
generate the piece independently from a prompt or a separate crop of an AI
collage. For full-frame-video review, inspect every decoded frame and report
integrity / motion discontinuity metrics. H.264 is lossy, so pixel-zero
requirements apply BEFORE encoding; decoded media uses tolerances.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass
class PixelMatch:
    exact: bool
    mismatch_count: int
    total_pixels: int
    mad: float


def exact_cutout_match(
    canonical_rgb: np.ndarray,
    hole_base_rgb: np.ndarray,
    original_piece_rgb: np.ndarray,
    binary_mask: np.ndarray,
    target_xy: tuple[int, int],
) -> PixelMatch:
    """Reconstruct and check an entire image, not merely alpha-mask bounds.

    All RGB arrays must be uint8. The source piece is cropped once from the
    same canonical frame. Mask values must be binary (0 or 255). If the piece
    is generated independently or shifted, the comparison will fail.
    """
    if canonical_rgb.ndim != 3 or canonical_rgb.shape[2] != 3:
        raise ValueError("Canonical image must be 3-channel RGB")
    if canonical_rgb.dtype != np.uint8 or hole_base_rgb.dtype != np.uint8:
        raise ValueError("RGB images must be uint8")
    if canonical_rgb.shape != hole_base_rgb.shape:
        raise ValueError("Canonical and base frame shapes differ")
    x, y = target_xy
    ph, pw = binary_mask.shape
    if binary_mask.dtype != np.uint8 or np.any((binary_mask != 0) & (binary_mask != 255)):
        raise ValueError("Puzzle mask must be hard binary alpha (0/255)")
    if original_piece_rgb.shape != (ph, pw, 3) or original_piece_rgb.dtype != np.uint8:
        raise ValueError("Extracted tile and mask dimensions differ")
    if x < 0 or y < 0 or x + pw > canonical_rgb.shape[1] or y + ph > canonical_rgb.shape[0]:
        raise ValueError("Target lies outside the canonical image")
    composed = hole_base_rgb.copy()
    target = composed[y:y+ph, x:x+pw]
    target[binary_mask == 255] = original_piece_rgb[binary_mask == 255]
    abs_diff = np.abs(composed.astype(np.int16) - canonical_rgb.astype(np.int16))
    return PixelMatch(
        exact=bool(np.array_equal(composed, canonical_rgb)),
        mismatch_count=int(np.count_nonzero(np.any(abs_diff != 0, axis=2))),
        total_pixels=int(canonical_rgb.shape[0] * canonical_rgb.shape[1]),
        mad=float(np.mean(abs_diff)),
    )


def extract_canonical_piece(
    canonical_rgb: np.ndarray,
    mask: np.ndarray,
    xy: tuple[int, int],
    hole_color: tuple[int, int, int] = (23, 35, 52),
) -> tuple[np.ndarray, np.ndarray]:
    """Crop source pixels and create the complementary hole in one operation."""
    x, y = xy
    ph, pw = mask.shape
    if not (0 <= x and 0 <= y and x + pw <= canonical_rgb.shape[1] and y + ph <= canonical_rgb.shape[0]):
        raise ValueError("Extracted tile bounds exceed source image")
    fragment = canonical_rgb[y:y+ph, x:x+pw].copy()
    base = canonical_rgb.copy()
    base[y:y+ph, x:x+pw][mask > 0] = np.asarray(hole_color, dtype=np.uint8)
    return base, fragment


def audit_video_every_frame(
    path: str | Path,
    expected_frames: int | None = None,
    resize_wh: tuple[int, int] = (180, 320),
    min_frame_std: float = 10.0,
    max_mean_jump: float = 50.0,
) -> dict[str, Any]:
    """Decode all frames sequentially, detect blanks, broken files and jumps.

    Resize is for inexpensive *integrity* metrics, not proof of puzzle match.
    Pixel-exact alignment is measured on uncompressed compositor frames.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(str(file_path))
    capture = cv2.VideoCapture(str(file_path))
    if not capture.isOpened():
        raise ValueError("Unable to decode the video")
    frames = 0
    bad_frames = 0
    largest_jump = 0.0
    smallest_std = float("inf")
    prev = None
    try:
        while True:
            valid, frame = capture.read()
            if not valid:
                break
            sample = cv2.resize(frame, resize_wh, interpolation=cv2.INTER_AREA)
            deviation = float(np.std(sample))
            smallest_std = min(smallest_std, deviation)
            if deviation < min_frame_std:
                bad_frames += 1
            if prev is not None:
                difference = float(np.mean(np.abs(sample.astype(np.int16) - prev.astype(np.int16))))
                largest_jump = max(largest_jump, difference)
            prev = sample
            frames += 1
    finally:
        capture.release()
    if expected_frames is not None and frames != expected_frames:
        raise AssertionError(f"Video decoded {frames}/{expected_frames} frames")
    if frames == 0 or bad_frames:
        raise AssertionError(f"Empty or blank frames detected: {bad_frames}")
    if largest_jump > max_mean_jump:
        raise AssertionError(f"Excessive frame discontinuity: {largest_jump:.3f}")
    return {
        "decoded_frames": frames,
        "blank_frames": bad_frames,
        "min_frame_std": round(smallest_std, 3),
        "max_mean_frame_jump": round(largest_jump, 3),
        "passed": True,
    }
