# Multi-Snap Motion Director v4 — nonuniform, repeated perfect matches

Updated 2026-10-23. This feature is implemented on PR #1's review branch, not yet merged into `main`.

## User-facing behavior

Instead of matching once at the end or repeating the same fixed-length animation, every Reel now generates **multiple exact-fit moments at different times**.

- Default: honor Gemini's `CreativePlan.cycles` (5 by default); explicit `snap_count` overrides it.
- Input: `0` means auto, `1–12` chooses the number of matches subject to video duration.
- Durations are **seeded, randomized and intentionally nonuniform**; same seed reliably reproduces the same export.
- Every segment enters, aligns, holds, and retreats from the original target.
- All eight motion profiles (orbit, spin, elastic, flip, pendulum, spiral, zigzag, classic slide) support the timeline.
- Each match triggers its own timed sound effect.
- Puzzle-piece geometry uses the exact canonical source pixels; transformations bypass interpolation at every locked frame.
- Motion passes share a continuous off-target pose at boundaries rather than teleporting across segments.

## Backend

`services/engine/snap_timeline.py` creates the deterministic `MotionPass` windows. Each has `start_frame`, `end_frame`, `first_locked_frame`, and `last_locked_frame`.

`services/engine/renderer.py` uses full-length source frames for irregular timing rather than `ffmpeg -stream_loop` of a repeated short segment. A bounded memory cache prevents excessive RAM growth. Its QA also independently recreates and compares **every decoded MP4 frame** to the corresponding expected frame.

Outputs include:
- `<job_id>.mp4`
- `<job_id>.frameqa.json` with every-frame comparison results
- `<job_id>.snaps.json` with actual exact-fit frame windows and audio cue times

If the number of produced snap windows disagrees with the planned count, rendering fails instead of reporting a ready video.

## API and mobile support

`POST /api/v1/ai/renders` accepts:

```json
{
  "plan_id": "the-storyboard-id",
  "image_id": "approved-original-artwork-id",
  "duration_sec": 12,
  "motion_profile": "orbit_lock",
  "motion_intensity": 1.1,
  "snap_count": 5
}
```

The Studio has a selector for 3–8 repeated surprise matches, or Gemini's preferred count. Future Android clients can reuse the same field without running FFmpeg locally.

A user-supplied count that cannot fit into the selected duration is rejected. Default automatic counts are reduced for short smoke-test/preview renders.

## Tests

`tests/test_snap_timeline.py` covers:
- Several nonuniform snap windows per video.
- Determinism by seed and genuine variation between seeds.
- All motion modes returning to an **exact lossless identity pose** at *each* alignment window.
- Rejection of physically impossible event counts.
- Real H.264 MP4 render with three snap events, accompanied by QA JSON sidecars.

GitHub Actions CI run `40031761021` passed 41 automated tests and real MP4 rendering.

## Verified 12-second demonstrations

These demos are separately delivered as downloadable conversation files, and are not falsely claimed to use Gemini-generated audio. They use owned illustration assets derived from the earlier Rfactory showcase and original synthesized sound effects.

| Subject | Exact-fit starts (seconds) | Pixel-perfect solved frames | Full-frame decode comparison MAE / 255 |
|---|---|---:|---:|
| Sea turtle (orbit) | 1.400, 4.667, 7.333, 9.467, 11.100 | 80 | 1.3610 |
| Cow (pendulum) | 0.967, 3.500, 5.567, 7.533, 10.367 | 80 | 1.3993 |
| Macaw (spiral) | 1.500, 4.467, 6.500, 8.633, 10.500 | 76 | 1.3691 |

All 1,080 decoded frames from the three showcase videos were compared with their deterministic expected animation. The zero-difference alignment requirement is evaluated **before lossy H.264 encoding**. Decoded H.264 pixels differ slightly due to compression.

**Remaining production work:** tune artistic timing and captions from actual user feedback, verify live Gemini TTS if an authenticated backend is available, and fully test supervised Facebook publishing. Do not claim these showcase videos contain Gemini TTS.
