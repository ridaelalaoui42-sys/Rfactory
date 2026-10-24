# Rfactory Social Sticker Assets + Three Reels (2026-10-24)

This optional package introduces **182 separate alpha-channel sticker cutouts**, **16 full-size colorful backgrounds** and three preview reels rendered with exact source-pixel puzzle cutouts.

## Repository changes
- scripts/install_social_assets.py: secure local unpack from the supplied ZIP.
- scripts/render_social_reels.py: no-cloud Python/Pillow/FFmpeg renderer, exactly matching a moving puzzle part to its stationary source.
- config/social_reels_preset_2026_10.json: editable preset metadata.
- tests/test_social_reels_presets.py: smoke validation for presets.
- Source images: **separate downloadable ZIP; not committed to Git history** to avoid ballooning repository/storage with ~70 MB of generated image derivatives.
- Example videos: separately delivered MP4s; not claimed to be published to Facebook or GitHub.

## Local installation
Obtain Rfactory_Social_Assets_Pack.zip from the delivery conversation; put it in the repository directory. The ZIP is not a public URL and is not automatically downloadable from GitHub Actions.

    python scripts/install_social_assets.py ./Rfactory_Social_Assets_Pack.zip --dest public/rfactory-social
    python -m scripts.social_reels_from_config --settings config/social_reels_preset_2026_10.json --assets public/rfactory-social --out storage/renders/social

You need Python 3.11+, Pillow, NumPy, FFmpeg and FFprobe on PATH. The renderer produces 1080×1920, 24 FPS, H.264/AAC MP4s, posters and JSON QA results.

## Presets
| Slug | Subject | Puzzle | Motion | Length | Reveal |
|------|---------|--------|--------|--------|--------|
| 01_puppy_pop | smiling puppy | round face cutout | orbit | 8s | 6.45s |
| 02_pizza_party | full pizza | triangular slice from source | bounce | 9s | 7.3s |
| 03_kitty_mixup | happy cat | band from actual face source | zigzag | 10s | 8.3s |

All text is designed for a general family audience. The videos contain synthetic beep/chirp sound effects, not copyrighted music.

**Asset-quality caveat:** Many cutouts were harvested from AI-generated multi-subject sheets. Native source resolution of most stickers is only about 100–300px. @2x exports are enlargements, not additional native detail; treat as social graphics and preview effects, NOT as production-eligible full-HD canonical animal face puzzle artwork in the existing Rfactory asset approval system. The verified full-resolution generated backgrounds are separate from these low-resolution sprites. Existing full-HD Rfactory library requirements must continue to reject ineligible reference cutouts.

To turn these into true HD puzzle production candidates, generate each animal/character as a *separate* original ≥768px source and review its alpha/mask and fit. Do not auto-approve collage crops. Do not confuse this optional sticker overlay pack with the existing strict asset importer.

## Preservation and repository size
The provided ZIP is approximately 70 MB. Keep the ZIP outside Git history, preferably in artifact storage, object storage, or a GitHub Release asset uploaded separately. The installer never overwrites existing branding and does not change the main video pipeline.

## Change settings without editing Python
Edit `config/social_reels_preset_2026_10.json` (headlines, duration, speed, puzzle shape, motion, reveal time or background), then rerun `python -m scripts.social_reels_from_config` with `--assets` and `--out`. The JSON adapter validates supported shape/motion and reveal bounds before rendering.
