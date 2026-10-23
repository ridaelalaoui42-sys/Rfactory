# Precision puzzle video review — 23 October 2026

## Root cause

The previous three illustration-based demo MP4s composited arbitrary, visually
similar crops over a pre-painted missing-piece slot. The cow and macaw fragments
came from unrelated image locations, so **the geometry was incapable of matching**.
Successful MP4 encoding did not mean the puzzle itself was valid.

## Correction

For each puzzle, there is now **one canonical illustrated scene**. The creator:

1. Chooses the target region in the canonical source image.
2. Generates a hard binary jigsaw mask (no semi-opaque shifting).
3. Removes exactly those source pixels to make the slot.
4. Extracts the moving piece from the identical source rectangle and mask.
5. Animates the piece by integer x/y translation without rescaling it.
6. During reveal, reconstructs the exact original pixels inside the slot.
7. Fails immediately if the revealed RGB scene differs from the canonical scene.
8. Decodes the final H.264 output, compares **all frames** to expected source
   frames, and checks that 100% of frames are present and there are no gross
   visual discontinuities.

This must be a fail-closed invariant in the app, not merely a statistical score.
**Source-space solved MAD: 0.0**. Decoded H.264 is lossy and uses tolerant metrics.

## Test results for revised local showcase

The corrected videos were generated as local conversation artifacts. They were
**not** published to Facebook or claimed as Gemini-generated video.

| Puzzle | MP4 frames decoded | Source-space solved MAD | Decoded mean per-frame MAE (0–255) | Solved region mean MAE | Result |
|---|---:|---:|---:|---:|---|
| Sea turtle | 360 | 0.0 | 1.965 | 1.888 | PASS |
| Farm cow | 360 | 0.0 | 1.900 | 1.473 | PASS |
| Scarlet macaw | 360 | 0.0 | 1.834 | 1.615 | PASS |
| **Total** | **1,080** | **0.0** | | | **PASS** |

Rendered 1080x1920, 30fps, 12 seconds, H.264 + AAC.
The first 9 seconds feature moving pieces; the last 90 frames hold the exact
solution. All 90 solved frames per video were inspected after decoding.

## New reusable regression gate

`services/engine/precision_qa.py` provides:

- `extract_canonical_piece`: source-driven slot and moving fragment.
- `exact_cutout_match`: exact whole-image proof; wrong slot, shifted source
  pixels or malformed mask must fail.
- `audit_video_every_frame`: decoded-frame coverage, blank/corruption/large
  visual jump checks.
- `audit_against_expected_frames`: compare **every** decoded video frame to
  the caller-provided reference frame; catches a one-frame error deep into
  the finished video, even when resolution/audio checks pass.

`tests/test_pixel_alignment.py` includes wrong-fragment and single-frame
drift tests. CI runs the full tests.

## Gemini voiceover integration

The reference showcase's music/SFX is original locally synthesized audio.
**Gemini TTS has not been run against the supplied account key in this
environment**. No local synthesized speech should be represented as Gemini.

Official Gemini API TTS uses `gemini-3.8-flash-lite-tts` or
`gemini-3.8-flash-tts` with `interactions.create()`. Our script
`scripts/generate_puzzle_tts.py` generates verified Gemini WAV and optionally
mixes it with a corrected MP4:

```bash
# Secret stays in your own terminal environment, never Git history.
export GEMINI_API_KEY='...'
pip install -r requirements-ai.txt
python -m scripts.generate_puzzle_tts --output-dir ./narrations \
    --input-video-dir ./corrected_v2
```

The MP4s must be present under `corrected_v2`. Outputs are written to
`<scene>_gemini_tts.mp4`. The script rejects overly long narration instead
of truncating speech.

## Remaining production-quality decisions

- Improve the base illustration quality and remove any pre-existing puzzle
  marks/arrows when art-directing the *original* AI image. The corrected
  collage can still show old decorative artifacts even though its new missing
  piece is mathematically exact.
- Integrate expected-frame callbacks directly into all four production
  animation templates before publishing.
- Verify narration language/timing on the target Gemini account with a new,
  securely stored API key. Check quota before batching.
- Render an actual sample through the full AI dashboard, obtain manual
  content approval, and keep Facebook publishing disabled until independently
  verified.

No public release or `main` merge is claimed by this document.
