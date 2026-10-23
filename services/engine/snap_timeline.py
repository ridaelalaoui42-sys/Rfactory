"""Seeded, irregularly timed exact-fit windows for puzzle motion.

A video consists of consecutive motion passes with different durations.
Every pass has a short, pixel-accurate snap centered in its own time window.
All passes use the same canonical profile/seed, making consecutive endpoints
continuous rather than teleporting. Same seed => identical frame indices.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import bisect
import random


@dataclass(frozen=True)
class MotionPass:
    start_frame: int
    end_frame: int   # exclusive
    first_locked_frame: int
    last_locked_frame: int  # inclusive

    @property
    def duration(self) -> int:
        return self.end_frame - self.start_frame


@dataclass(frozen=True)
class SnapTimeline:
    total_frames: int
    fps: int
    seed: int
    hold_ratio: float
    passes: tuple[MotionPass, ...]

    def phase(self, frame: int) -> float:
        if not 0 <= frame < self.total_frames:
            raise IndexError(f"Frame outside timeline: {frame}")
        ends = [event.end_frame for event in self.passes]
        index = bisect.bisect_right(ends, frame)
        part = self.passes[index]
        return (frame - part.start_frame) / max(1, part.duration - 1)

    def is_locked(self, frame: int) -> bool:
        if not 0 <= frame < self.total_frames:
            raise IndexError(frame)
        ends = [event.end_frame for event in self.passes]
        part = self.passes[bisect.bisect_right(ends, frame)]
        return part.first_locked_frame <= frame <= part.last_locked_frame

    def snap_times(self) -> list[float]:
        return [round(p.first_locked_frame / self.fps, 3) for p in self.passes]

    def metadata(self) -> dict:
        return {
            "timing_mode": "seeded_irregular",
            "fps": self.fps,
            "seed": self.seed,
            "total_frames": self.total_frames,
            "snap_count": len(self.passes),
            "snap_timestamps_sec": self.snap_times(),
            "snap_windows": [asdict(p) for p in self.passes],
        }


def build_snap_timeline(
    total_frames: int,
    fps: int,
    count: int,
    seed: int,
    hold_ratio: float = 0.14,
) -> SnapTimeline:
    if not 12 <= total_frames <= 18000:
        raise ValueError("Timeline must contain 12 to 18000 frames")
    if not 1 <= fps <= 120:
        raise ValueError("Invalid FPS")
    if not 1 <= count <= 12:
        raise ValueError("Choose between 1 and 12 snap events")
    if not 0.06 <= hold_ratio <= 0.30:
        raise ValueError("hold_ratio must be 0.06 to 0.30")
    minimum = max(12, int(round(0.55 * fps)))
    if count * minimum > total_frames:
        raise ValueError("Too many snap events for requested duration/FPS")

    # Minima keep the art legible. Randomized surplus makes event times
    # irregular without creating impossibly rapid back-to-back matches.
    rng = random.Random(seed ^ 0xC1A70)
    weights = [rng.uniform(0.35, 1.75) for _ in range(count)]
    available = total_frames - count * minimum
    norm = sum(weights)
    allocations = [int(available * w / norm) for w in weights]
    for i in sorted(range(count), key=lambda i: -(available * weights[i] / norm - allocations[i]))[:available - sum(allocations)]:
        allocations[i] += 1

    start = 0
    passes = []
    for extra in allocations:
        length = minimum + extra
        end = start + length
        locked = []
        for frame in range(start, end):
            phase = (frame - start) / max(1, length - 1)
            if abs(phase - 0.5) <= hold_ratio * 0.5:
                locked.append(frame)
        if not locked:
            raise ValueError("Snap window has no frames")
        passes.append(MotionPass(start, end, locked[0], locked[-1]))
        start = end
    if start != total_frames:
        raise AssertionError("Timeline does not cover the full video")
    return SnapTimeline(total_frames, fps, seed, hold_ratio, tuple(passes))
