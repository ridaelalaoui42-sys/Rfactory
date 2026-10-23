"""Motion Director v2: physically distinct, reversible puzzle-piece trajectories.

All paths have an exact integer-pixel locked pose (dx=dy=angle=0,
scale_x=scale_y=1) during a deliberate hold. That makes it impossible for a
rotation or elastic deformation to destroy the puzzle's actual answer.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

import cv2
import numpy as np

MotionName = Literal[
    "slide", "spin_snap", "orbit_lock", "pendulum", "spiral", "elastic",
    "flip_reveal", "zigzag",
]
MOTION_PROFILES = (
    "slide", "spin_snap", "orbit_lock", "pendulum", "spiral",
    "elastic", "flip_reveal", "zigzag",
)


@dataclass(frozen=True)
class MotionPose:
    dx: int = 0
    dy: int = 0
    angle_deg: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    locked: bool = False

    @property
    def identity(self) -> bool:
        return (
            self.dx == 0 and self.dy == 0
            and abs(self.angle_deg) < 1e-8
            and abs(self.scale_x - 1.0) < 1e-8
            and abs(self.scale_y - 1.0) < 1e-8
        )


def _ease(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def motion_pose(
    profile: str,
    phase: float,
    travel_px: float = 180.0,
    hold_ratio: float = 0.14,
    seed: int = 0,
    intensity: float = 1.0,
    direction: str = "vertical",
) -> MotionPose:
    """Return motion pose for phase [0,1) of a looping challenge.

    The exact locked pose is centered at phase=.5; visually distinct lead-in
    and lead-out trajectories produce a seamless repeated challenge.
    Intensity adjusts travel and angular excitement, never snap precision.
    """
    if profile not in MOTION_PROFILES:
        raise ValueError(f"Unknown motion profile: {profile}")
    if not (0.0 < hold_ratio <= 0.35 and 0.0 <= intensity <= 2.0):
        raise ValueError("Invalid hold ratio or motion intensity")
    p = phase % 1.0
    hw = hold_ratio / 2.0
    if abs(p - 0.5) <= hw:
        return MotionPose(locked=True)
    if p < 0.5 - hw:
        u = p / max(1e-6, (0.5 - hw))
    else:
        # Follow the same trajectory backwards on departure. Both cycle
        # boundaries now share exactly the same pose. Earlier versions
        # jumped from +travel to -travel on every loop.
        u = (1.0 - p) / max(1e-6, (0.5 - hw))
    tail = 1.0 - _ease(u)
    a = max(0.0, travel_px) * intensity
    sign = -1
    handed = -1 if seed % 2 else 1
    px = py = 0.0
    deg = 0.0
    sx = sy = 1.0

    if profile == "slide":
        if direction == "horizontal":
            px = sign * a * tail
        else:
            py = sign * a * tail
    elif profile == "spin_snap":
        # Full turn while entering, opposite turn while leaving.
        deg = sign * handed * 360.0 * tail * intensity
        px = sign * a * tail * 0.45
        py = sign * a * tail * 0.70
    elif profile == "orbit_lock":
        # Two independent orbit axes, radius shrinks precisely to zero.
        theta = math.tau * (1.25 * u + 0.12 * (seed % 3))
        px = math.cos(theta) * a * tail
        py = math.sin(theta) * a * tail * 0.73
        deg = sign * 85.0 * tail * math.sin(theta) * handed
    elif profile == "pendulum":
        # Swing with gradually decaying angular momentum.
        deg = handed * 42.0 * intensity * tail * math.cos(u * math.tau * 1.25)
        px = handed * a * 0.72 * tail * math.sin(u * math.pi * 1.3)
        py = -a * 0.50 * tail
    elif profile == "spiral":
        theta = math.tau * (1.6 * u + (seed % 5) / 5.0)
        px = a * tail * math.cos(theta)
        py = a * tail * math.sin(theta)
        deg = handed * 620.0 * intensity * tail * sign
    elif profile == "elastic":
        # Springs move *through* and around the target before final lock.
        damping = math.exp(-4.0 * u)
        vibration = math.cos(u * math.tau * 2.0) * damping
        if direction == "horizontal":
            px = sign * a * (tail + vibration * 0.4 * tail)
            py = a * 0.18 * tail * math.sin(u * math.tau * 2.0)
        else:
            py = sign * a * (tail + vibration * 0.4 * tail)
            px = a * 0.20 * tail * math.sin(u * math.tau * 2.0)
        deg = 13.0 * tail * math.sin(u * math.tau * 2.0)
        sx = 1.0 + 0.08 * tail * math.sin(u * math.tau * 2.0)
        sy = 1.0 / sx
    elif profile == "flip_reveal":
        # Apparent 3D flip simulated by perspective-like horizontal squash.
        px = sign * a * 0.65 * tail
        py = sign * a * 0.36 * tail
        sx = max(0.16, abs(math.cos(math.pi * 1.35 * tail)))
        deg = handed * 22.0 * tail
    elif profile == "zigzag":
        px = sign * a * 0.80 * tail * math.sin(3.0 * math.pi * u)
        py = sign * a * 0.80 * tail
        deg = handed * 28.0 * tail * math.sin(math.tau * u)
    return MotionPose(
        dx=int(round(px)), dy=int(round(py)),
        angle_deg=round(deg, 4),
        scale_x=round(sx, 5), scale_y=round(sy, 5),
        locked=False,
    )


def transformed_sprite(
    rgba: np.ndarray,
    pose: MotionPose,
) -> tuple[np.ndarray, tuple[int, int]]:
    """Return rotated/scaled sprite and top-left offset relative to original.

    CRITICAL: identity returns original bytes *without resampling*. At snap,
    overlays are mathematically exact, not approximately rotated back.
    """
    if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("Expected uint8 RGBA")
    if pose.identity:
        return rgba, (0, 0)
    h, w = rgba.shape[:2]
    theta = math.radians(pose.angle_deg)
    co, si = math.cos(theta), math.sin(theta)
    ax = co * pose.scale_x
    bx = -si * pose.scale_y
    ay = si * pose.scale_x
    by = co * pose.scale_y
    new_w = max(1, int(math.ceil(abs(ax) * w + abs(bx) * h)) + 4)
    new_h = max(1, int(math.ceil(abs(ay) * w + abs(by) * h)) + 4)
    center_x = w / 2.0
    center_y = h / 2.0
    m = np.array([
        [ax, bx, new_w / 2.0 - ax * center_x - bx * center_y],
        [ay, by, new_h / 2.0 - ay * center_x - by * center_y],
    ], dtype=np.float32)
    transformed = cv2.warpAffine(
        rgba, m, (new_w, new_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return transformed, ((w - new_w) // 2, (h - new_h) // 2)

def continuous_motion_pose(
    profile: str,
    phase: float,
    travel_px: float = 180.0,
    hold_ratio: float = 0.14,  # unused compatibility argument
    seed: int = 0,
    intensity: float = 1.0,
    direction: str = "vertical",
) -> MotionPose:
    """Motion passes directly THROUGH identity with no solved-state dwell.

    For phase=0.5, return untransformed source pixels for one video frame only.
    At phase immediately before/after, position and/or rotation is nonzero,
    including continuous nonzero velocity at crossing. At phase=0 and 1 the
    transform is identical, preventing discontinuities between passes.
    """
    if profile not in MOTION_PROFILES:
        raise ValueError("Unknown motion profile")
    if not 0 < intensity <= 2.0:
        raise ValueError("Continuous motion intensity must be in (0,2]")
    if not 0.0 <= phase <= 1.0:
        raise ValueError("Motion phase must be in [0,1]")
    if direction not in {"horizontal", "vertical"}:
        raise ValueError("Unknown motion direction")
    if abs(phase - 0.5) < 1e-12:
        return MotionPose(locked=True)

    u = 2.0 * math.pi * phase
    s = math.sin(u)
    e = 0.5 * (1.0 + math.cos(u))
    travel = travel_px * intensity
    hand = -1.0 if seed % 2 else 1.0
    # Each profile uses harmonics with a NONZERO derivative at phase .5.
    # e is nonzero at pass boundaries, so those frames are NOT false solves.
    x = y = angle = 0.0
    sx = sy = 1.0

    if profile == "slide":
        primary = travel * (0.6 * e + 0.7 * s)
        if direction == "horizontal":
            x = primary
        else:
            y = primary
    elif profile == "spin_snap":
        x = travel * (0.38 * e + 0.48 * s)
        y = travel * (0.45 * e - 0.35 * s)
        angle = hand * (220 * e + 185 * s) * intensity
    elif profile == "orbit_lock":
        x = travel * (0.55 * e + 0.68 * s)
        y = travel * (0.30 * e - 0.57 * s)
        angle = hand * (72 * e + 40 * s)
    elif profile == "pendulum":
        x = hand * travel * (0.18 * e + 0.8 * s)
        y = -travel * (0.6 * e + 0.2 * s)
        angle = hand * (34 * e + 48 * s) * intensity
    elif profile == "spiral":
        # Phase winds a continuous orbit around the target and passes through
        # center with nonzero tangent, not a damped stop.
        x = travel * (0.40 * e + 0.65 * s + 0.14 * e * math.sin(3*u))
        y = travel * (0.32 * e - 0.72 * s + 0.12 * e * math.cos(3*u))
        angle = hand * (400 * e + 270 * s) * intensity
    elif profile == "elastic":
        x = travel * (0.20 * e + 0.52 * s + 0.18 * e * math.sin(4*u))
        y = travel * (0.42 * e - 0.60 * s)
        angle = hand * (15 * e + 19 * s)
        sx = 1.0 + 0.06 * (e + s)
        sy = 1.0 / sx
    elif profile == "flip_reveal":
        x = travel * (0.28 * e + 0.71 * s)
        y = travel * (0.21 * e - 0.30 * s)
        angle = hand * (24 * e + 24 * s)
        sx = 1.0 - 0.75 * e
    elif profile == "zigzag":
        x = travel * (0.36 * e + 0.66 * s + 0.15 * e * math.sin(5*u))
        y = travel * (0.40 * e - 0.65 * s)
        angle = hand * (23 * e + 26 * s)
    return MotionPose(
        dx=int(round(x)), dy=int(round(y)),
        angle_deg=round(angle, 4),
        scale_x=round(sx, 5), scale_y=round(sy, 5),
        locked=False,
    )
