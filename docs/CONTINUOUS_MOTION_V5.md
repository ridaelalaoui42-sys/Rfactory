# Continuous Crossing Puzzle Engine — v5

**Implementation:** `services/engine/motion_profiles.py`, `services/engine/snap_timeline.py`, `services/engine/renderer.py`.

Every new Reel uses **continuous motion**. No deliberate freeze, hold window, glow, highlight, bounce-to-rest, end-frame solution, or other visual cue is allowed at the correct position. Optionally play a short subtle sound **only at the exact-fit frame**.

## Exact match behavior

The piece is cut once from the original canonical artwork. All transforms are affine during travel, but at every predetermined crossing the compositor uses the **original RGBA data without rotation, scaling, or interpolation**, at the original integer target position.

- Each pass has exactly **one** match frame, with `dx=dy=0`, `angle_deg=0`, `scale_x=scale_y=1`.
- The frames immediately before and after are **different moving poses**.
- A seeded, irregular timeline determines the multiple crossing frame indices; no predictable evenly spaced cycle.
- End pose of one motion pass matches the starting pose of the next one, minimizing loop-boundary jumps.
- No text or graphics announce a correct match.
- A short synthesized crossing chime can play; music and periodic ticks are disabled by default through `sound_mode="match_only"`.
- Video frame QA compares **every decoded H.264 frame** against its source frame and rejects mismatches.
- `*.snaps.json` records fit events with `first_locked_frame==last_locked_frame` and `hold_frames_per_match=1`.
- `*.frameqa.json` records per-video frame comparison results.

Legacy paused-motion functions remain in the repository for backward compatibility and regression comparison; new `RenderConfig` and AI Studio renders default to `continuous_motion=True`.

## Renderer options

```python
RenderConfig(
    job_id="example",
    template_id="MISSING_PIECE_SLIDE",
    species="fox",
    duration_sec=12.0,
    seed=4601,
    snap_count=5,
    randomize_snap_timing=True,
    continuous_motion=True,
    motion_profile="orbit_lock",
    motion_intensity=1.0,
    enable_audio=True,
    sound_mode="match_only",
)
```

Supported motion modes: slide, spin_snap, orbit_lock, pendulum, spiral, elastic, flip_reveal, zigzag. Gemini can suggest a profile, but it cannot override the exact-fit pixel integrity requirement. AI Studio returns output as **READY_FOR_REVIEW, not PUBLISHED**.

## Three reproducible new showcases

Run this command from the repository root, with FFmpeg/FFprobe installed and requirements available:

```bash
python -m scripts.render_continuous_variants --duration 12 --count 5
```

Three original illustrated characters are produced:

| Subject | Puzzle | Continuous movement |
|---|---|---|
| Snow Leopard | Missing body fragment | Orbit and counter-rotation |
| Red Panda | Moving facial-feature band | Pendulum crossing |
| Astronaut | Three-band portrait | Spiral rotation |

Outputs live under `storage/showcase_continuous/` with PNG artwork under `storage/assets/showcase/`. These character images are **procedurally illustrated**, not Google Nano Banana output, and audio uses local chimes, not Gemini TTS. Gemini image/TTS are optional separate services and must be tested with a real key on a network-enabled worker.

The GitHub Actions workflow `.github/workflows/continuous-showcase.yml` renders and attaches all three reels, QA sidecars, and artwork, without embedding generated binary media in the source repository.

## Acceptance gates

1. Every expected match frame exists and is unique; count equals `snap_count`.
2. Exactly one matching frame per pass: **no holding or pausing**.
3. No transform resampling at the matching frame; uncompressed pixel MAD is zero.
4. Each match is bracketed by visibly different positions.
5. No jumps when crossing the boundary between passes.
6. Full MP4 duration, FPS, codec and every decoded frame verified.
7. No fabricated provider provenance, no auto-upload or publishing without operator approval.
