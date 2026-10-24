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

You need Python 3.11+, Pillow, NumPy, FFmpeg and FFprobe on PATH. The renderer produces 1080×1920, 24 FPS, H.264/AAC MP4s, posters and JSON QA results. Its new `scripts/social_motion.py` fits the source-pixel puzzle piece precisely five times per reel, with a 5-frame dwell at each hit, departures between hits, and an exact final hold.

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
Run `python -m unittest tests.test_social_motion -v` to validate 5 scheduled precise (0,0)-pixel matches per reel, 5-frame visible holds, and sufficient departures between fits. The per-render `*_qa.json` includes `repeated_alignment.fit_frames` and `fit_times_seconds` recorded for each video. Media remains reference-only until separate full-HD original subject generation is available.
