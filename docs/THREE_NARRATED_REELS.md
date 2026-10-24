# Rfactory — three NEW social puzzle Reels with narration

Three kid-friendly 9:16 videos, not reuses of the older Puppy/Pizza/Kitty templates:

| Reel | Time | Voiceover | Puzzle target |
| --- | ---: | --- | --- |
| Dino Donut Dash | 10s | “Hey, explorer! The dinosaur lost a bite!…” | Doughnut bite |
| Bunny Ice Cream Mix-Up | 11s | “Oh no! Bunny's ice cream is falling apart!…” | Scoop |
| Monkey Burger Pop | 10s | “Uh oh! Monkey's burger is missing a piece!…” | Burger |

- The new generated original artwork is saved in `assets/social/voiceover/source_triptych.jpg`.
- Renderer and per-Reel English narration scripts in `scripts/render_new_voiceover_reels.py`.
- Local offline English voiceovers use eSpeak TTS plus soft synthesized musical notes and five timed match chirps per reel. **These are synthetic voices, not premium cloud neural voices.**
- All puzzle pixels are extracted from the real generated art. There are five single-frame exact matches and movement between fits; no solved reveal.
- Outputs: 1080×1920, 24 FPS H.264/AAC MP4s, JPEG posters, WAV audio mixes and JSON QA manifests.
- Generated source image is a cropped high-quality JPEG from one triptych; native subject resolution is limited. Do not relabel it as independently generated 4K art.

## Regenerate offline

Install Python 3.11+, Pillow, NumPy, SciPy, FFmpeg and eSpeak. Then run:

```bash
python -m scripts.render_new_voiceover_reels
```

By default exports to `storage/renders/social_voiceovers/`. Set `RFACTORY_VOICEOVER_OUTPUT` to override. The GitHub Actions workflow `narrated-social-reels.yml` produces a 30-day download artifact with all three MP4s and voice tracks.

No Facebook or other social posting is performed automatically.
