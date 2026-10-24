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

# Continuous crossing mode: only one exact-fit frame per motion pass.
# Keep build_snap_timeline for legacy projects, but new renders default here.
@dataclass(frozen=True)
class CrossingTimeline:
    total_frames: int
    fps: int
    seed: int
    passes: tuple[MotionPass, ...]

    def _pass_for(self, frame: int) -> MotionPass:
        if not 0 <= frame < self.total_frames:
            raise IndexError(frame)
        return self.passes[bisect.bisect_right(
            [event.end_frame for event in self.passes], frame
        )]

    def phase(self, frame: int) -> float:
        part = self._pass_for(frame)
        cross = part.first_locked_frame
        if frame <= cross:
            return 0.5 * (frame - part.start_frame) / max(1, cross - part.start_frame)
        # Sample just BEFORE phase 1 at the last frame. The next pass begins
        # at phase 0, so the moving sprite never repeats the identical end
        # and start pose on consecutive encoded frames (no boundary freeze).
        return 0.5 + 0.5 * (frame - cross) / max(1, part.end_frame - cross)

    def is_locked(self, frame: int) -> bool:
        return frame == self._pass_for(frame).first_locked_frame

    def snap_times(self) -> list[float]:
        return [round(p.first_locked_frame / self.fps, 3) for p in self.passes]

    def metadata(self) -> dict:
        return {
            "timing_mode": "seeded_irregular_continuous",
            "continuous_motion": True,
            "hold_frames_per_match": 1,
            "fps": self.fps,
            "seed": self.seed,
            "total_frames": self.total_frames,
            "snap_count": len(self.passes),
            "snap_timestamps_sec": self.snap_times(),
            "snap_windows": [asdict(p) for p in self.passes],
        }


def build_crossing_timeline(
    total_frames: int,
    fps: int,
    count: int,
    seed: int,
    hold_ratio: float = 0.14,  # compatibility only; never used for dwell
) -> CrossingTimeline:
    """Create irregular, reproducible single-frame crossings with no hold."""
    if not 12 <= total_frames <= 18000:
        raise ValueError("Timeline must contain 12 to 18000 frames")
    if not 1 <= fps <= 120 or not 1 <= count <= 12:
        raise ValueError("Invalid frame rate or crossing count")
    minimum = max(15, int(round(fps * 0.55)))
    if total_frames < minimum * count:
        raise ValueError("Too many crossings for the requested duration")
    randomizer = random.Random(seed ^ 0xC1A70)
    raw_weights = [randomizer.uniform(0.45, 1.75) for _ in range(count)]
    available = total_frames - count * minimum
    weight_sum = sum(raw_weights)
    extra = [int(available * w / weight_sum) for w in raw_weights]
    remainders = [available * w / weight_sum - n for w, n in zip(raw_weights, extra)]
    for index in sorted(range(count), key=lambda idx: -remainders[idx])[:available - sum(extra)]:
        extra[index] += 1
    start = 0
    events = []
    for frames in extra:
        end = start + minimum + frames
        # The exact crossing frame is not forced into a repeated wall-clock
        # grid; one central frame is snapped losslessly to the source.
        match = start + (end - start - 1) // 2
        events.append(MotionPass(start, end, match, match))
        start = end
    if start != total_frames:
        raise AssertionError("Frame partition is not exhaustive")
    return CrossingTimeline(total_frames, fps, seed, tuple(events))
