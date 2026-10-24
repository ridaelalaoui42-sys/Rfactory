# Rfactory Social Sticker Assets + Three Reels (2026-10-24)

This optional package introduces **182 separate alpha-channel sticker cutouts**, **16 full-size colorful backgrounds** and three preview reels rendered with exact source-pixel puzzle cutouts.

## Repository changes
- scripts/social_motion.py: repeated fit scheduler (five deterministic zero-offset hits per reel), with duration/configurable hold frames.\n- tests/test_social_motion.py: prevents regressions back to single final alignment.\n- scripts/install_social_assets.py: secure local unpack from the supplied ZIP.
- scripts/render_social_reels.py: no-cloud Python/Pillow/FFmpeg renderer, exactly matching a moving puzzle part to its stationary source.
- config/social_reels_preset_2026_10.json: editable preset metadata.
- tests/test_social_reels_presets.py: smoke validation for presets.
- **Compact source-resolution pack is now committed in GitHub:** `assets/social/rfactory_social_assets_compact_v1.zip` (3.1 MB; all 182 cutouts and 16 backgrounds). The optional 70 MB full export remains a conversation-only download.
- Regenerated 3 MP4s are provided as ChatGPT downloads, not automatically published.

## Local installation
The compact 3.1 MB ZIP is stored in the Git repository under `assets/social/`, so fresh clones contain the reusable source-resolution assets.

    python scripts/install_social_assets.py assets/social/rfactory_social_assets_compact_v1.zip --dest public/rfactory-social
    python -m scripts.social_reels_from_config --settings config/social_reels_preset_2026_10.json --assets public/rfactory-social --out storage/renders/social

You need Python 3.11+, Pillow, NumPy, FFmpeg and FFprobe on PATH. The renderer produces 1080×1920, 24 FPS, H.264/AAC MP4s, posters and JSON QA results. Its new `scripts/social_motion.py` fits the source-pixel puzzle piece precisely five times per reel, with a single-frame zero-offset crossing at each hit, departure between hits, and no final solved hold.

## Presets
| Slug | Subject | Puzzle | Motion | Length | Reveal |
|------|---------|--------|--------|--------|--------|
| 01_puppy_pop | smiling puppy | round face cutout | orbit, 5 exact fits | 8s | 1.08, 2.62, 4.17, 5.75, 7.29s |
| 02_pizza_party | full pizza | triangular slice from source | bounce, 5 exact fits | 9s | 1.08, 2.88, 4.67, 6.50, 8.29s |
| 03_kitty_mixup | happy cat | band from actual face source | zigzag, 5 exact fits | 10s | 1.08, 3.12, 5.17, 7.25, 9.29s |

All text is designed for a general family audience. The videos contain synthetic beep/chirp sound effects, not copyrighted music.

**Asset-quality caveat:** Many cutouts were harvested from AI-generated multi-subject sheets. Native source resolution of most stickers is only about 100–300px. @2x exports are enlargements, not additional native detail; treat as social graphics and preview effects, NOT as production-eligible full-HD canonical animal face puzzle artwork in the existing Rfactory asset approval system. The verified full-resolution generated backgrounds are separate from these low-resolution sprites. Existing full-HD Rfactory library requirements must continue to reject ineligible reference cutouts.

To turn these into true HD puzzle production candidates, generate each animal/character as a *separate* original ≥768px source and review its alpha/mask and fit. Do not auto-approve collage crops. Do not confuse this optional sticker overlay pack with the existing strict asset importer.

## Preservation and repository size
The *full unoptimized export* ZIP is about 70 MB and remains outside Git history. The compact 3.1 MB source-resolution asset ZIP is now stored in Git. This deliberately retains 182 cutouts and all 16 backgrounds without costly upscaled PNG copies. The installer never overwrites existing branding and does not change the main video pipeline.

## Change settings without editing Python
Edit `config/social_reels_preset_2026_10.json` (headlines, duration, speed, puzzle shape, motion, **fitCount, firstFit, lastFit, holdFrames**, or background), then rerun `python -m scripts.social_reels_from_config` with `--assets` and `--out`. The JSON adapter validates supported shape/motion and reveal bounds before rendering.

## Exact repeated-match QA
Run `python -m unittest tests.test_social_motion -v` to validate 5 scheduled precise (0,0)-pixel matches per reel, zero hold frames, and sufficient departures between fits. The per-render `*_qa.json` includes `repeated_alignment.fit_frames` and `fit_times_seconds` recorded for each video. Media remains reference-only until separate full-HD original subject generation is available.

## Rfactory 3.4 — Continuous Puzzle Rule (2026-10-24)

**The earlier hold-based motion presets in this document are superseded.**
The previous optional social renderer was not consistent with the principal
Rfactory face/video engine: it froze a completed fragment for five frames,
showed a green 'MATCH' banner, and held the solution at the end. That is now
fixed in \`scripts/social_motion.py\` and \`scripts/render_social_reels.py\`.

New social exports require:

- Exactly **one** matched frame per scheduled event, not a 5-frame dwell.
- A seed-controlled, **irregular** schedule of five fits with minimum
  separation and nonzero piece movement immediately on either side.
- A nonzero departure after the final matched frame; no end-of-video hold.
- No solved-state animation, ring, badge, victory text, or MATCH counter.
- Soft optional audio only at exact crossing frames. No half-second ticking.
- Positive cutout pixels originate from the same source as the negative hole.
  The preview renderer does not paint translucent 'ghost' pixels underneath
  the missing piece, preserving composited source fidelity.
- The 3.4 settings file has \`holdFrames: 0\` and a stable random \`seed\`.
  Old social presets with \`holdFrames: 5\` are **rejected**, not silently run
  with solved-state freezing.
- Video QA reports \`exact_fit_frames_per_event: 1\`,
  \`no_visual_match_indicators: true\`, and \`final_frame_solved: false\`.

Verified independent video showcase workflow:
\`.github/workflows/nohold-social-showcase.yml\` installs the compact
**included** artwork pack, renders all three actual 1080×1920 MP4s, checks
H.264 metadata, frame counts, irregular crossing timing and zero hold, and
uploads the playable Reels + QA manifest for review.

Run locally:

\`\`\`bash
python scripts/install_social_assets.py assets/social/rfactory_social_assets_compact_v1.zip --dest public/rfactory-social
python -m scripts.social_reels_from_config \\
  --settings config/social_reels_preset_2026_10.json \\
  --assets public/rfactory-social \\
  --out storage/renders/social-nohold
\`\`\`

### Artwork eligibility warning

These are social-style **preview Reels**. The compact sticker assets were
extracted from multi-subject artwork and remain reference-only where native
resolution is insufficient. A visually acceptable preview render does **not**
turn those crops into separately generated 768px+ canonical source art, or
authorize use as production HD source for the main face puzzle editor.

The stricter Face Asset Engine in \`services/assets/\` and the approved-source
library remain in force.

## GitHub-hosted automatic Reel builds

The source-resolution cutouts and backgrounds are versioned in Git at
[`assets/social/rfactory_social_assets_compact_v1.zip`](../assets/social/rfactory_social_assets_compact_v1.zip).
They can be installed reproducibly into `public/rfactory-social` without a
Cloudinary, paid model, or external file-download dependency.

The [social-reels workflow](../.github/workflows/social-reels.yml) validates
ZIP integrity and per-asset checksums, imports the pack, runs exact-fit motion
regression tests, renders all three family-friendly H.264/AAC 1080×1920 MP4s,
checks FFprobe codec/dimensions and per-render motion QA, and uploads the
results as a **14-day GitHub Actions artifact**.

To download a recent reel build: open **GitHub → Actions → Social puzzle reels →
latest successful run → Artifacts → `rfactory-social-reels-…`**. You can also
use **Run workflow** to regenerate the current presets on demand.

The compact ZIP is durable in Git history; workflow video artifacts are
temporary build outputs, not permanent media storage. The packaged stickers are
still original-sheet reference sprites, not native-HD canonical animal subjects.
