# Frame-Accurate Puzzle Production Standard

Date: 2026-10-23

## Root cause in early showcase samples

The first hand-built 12-second demos used a three-panel AI collage showing visual
puzzles. Their animation code attempted to simulate puzzle-piece restoration
by cropping a cow piece **from the separate preview tile below the cow** and
cropping macaw feathers **from the palette tiles to the right**. Those regions
had different scale, lighting, textures, silhouettes and source coordinates than
the 'missing' region embedded in the illustration. No motion interpolation
can repair a mismatch between two unrelated source areas.

The turtle demo animated a choice highlight but did not solve a pixel-exact
outline/egg geometry puzzle. The generated file's H.264 validity therefore
said nothing about semantic puzzle correctness.

## Mandatory revised implementation

1. **Generate one complete canonical subject illustration first.**
   This includes Gemini/Nano Banana artworks; it is the only source of truth
   for the positive tile and negative target.
2. **Cut from the same image pixels** at a fixed target `(x,y,w,h)` and
   validated binary alpha mask. Record crop bounds and a hash of the parent art.
3. **Create the hole by removing those same masked pixels**, never by painting
   an independently imagined silhouette or inserting a separate swatch.
4. **Animate only the tile's integer position.** Do not independently zoom,
   rotate, resize or recolor the piece relative to the target, unless the
   inverse transform is exactly reproduced at the snap pose.
5. **Pre-encode QA:** overlay the exact source pixels at target and assert
   mean absolute RGB difference `0.0` over the canonical image.
6. **Hold a solved alignment state** for a visible ending. Verify every snap
   frame before encoding.
7. **Decode every MP4 frame** after muxing and inspect for missing frames,
   blanks, unexpected jumps, duration, FPS, bitrate/audio and H.264 codec.
   *Never* treat `ffprobe codec==h264` as puzzle-validation evidence.
8. **Voice and narration:** use Gemini TTS only when an actual Gemini-generated
   WAV is present. Do not label synthesized music or offline speech as Gemini.
   Keep TTS-provider provenance in the video manifest.
9. **Manual visual QA:** for each template, review at least the start, near-fit
   movement, and fully solved frame, plus failures flagged by automated scan.

## New code

- `services/engine/precision_qa.py`: hard binary source cutouts, whole-canvas
  pixel-accurate reconstruction test, all-frame decoder checks.
- `services/engine/qa_validator.py`: calls exhaustive decoder review in
  addition to codec metadata and the alignment MAD already tracked.
- `tests/test_pixel_alignment.py`: deliberate wrong-source/1px-shift and
  mid-video blank-frame regressions.
- `scripts/generate_puzzle_tts.py`: real Gemini TTS for three approved
  example scripts; no API key in source.

## Examples delivered separately

Three rebuilt puzzle-video demos were rendered with a single-source cutout
pipeline (turtle, cow, macaw). For each video:

- 1080 × 1920 H.264 with 30 FPS and 12s duration.
- 360 decoded frames reviewed.
- 81 final aligned frames, all pixel-perfect in the raw compositor.
- Uncompressed snap-image MAD 0.0.
- On-screen reveals inspected visually.

The preview videos have local synthesized music/SFX, **not** Gemini narration.
Gemini requires an authenticated live API call and is implemented as an optional
TTS augmentation on a network-enabled worker. The user-provided key was not
committed, printed, or inserted into an automated GitHub workflow.

The separate examples deliver their source file and a contact sheet; the
repo does not bundle their generated media or claim to regenerate them
without that source image.

## Acceptance gates for production

A Reel cannot be promoted from `QA` to `READY` unless its actual output video
decodes in full and passes the frame-integrity checks. For missing-piece and
slice puzzles, also require exact reconstruction on the raw frame at the final
alignment pose. Keep failed videos accessible to operators as
`FAILED_QA` with details, not as successfully published content.
