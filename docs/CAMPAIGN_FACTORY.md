# Rfactory 3.3 — Original-Art Campaign Factory

## Goal

Produce 2–24 varied, real-source puzzle videos from 1–8 approved, clean HD originals. This extends the existing persistent render worker rather than simulating new AI-generated artwork or social-media publishing.

## Studio workflow

1. Run Rfactory on the local PC or VM with Docker Compose.
2. Import or generate clean original art; approve each source and artwork rights.
3. Optionally prepare reviewed face masks in Face Cutout Builder.
4. In the Studio artwork grid, tick **Use in campaign** on up to 8 approved HD subjects.
5. Choose campaign name, count (2–24), video duration, exact-fit count, and seed.
6. Confirm rights and explicitly opt into fallback media if selected.
7. Press **Produce varied Reel campaign**.
8. Track live campaign progress, open READY video previews, or cancel only pending jobs.
9. Download one ZIP containing QA-passed MP4s and a sanitized manifest.
10. Manually publish to an authorized account after review. No automatic posting.

Start the local application:

    docker compose up --build -d

Open http://localhost:8000/studio

## Protected API endpoints

All endpoints are under /api/v1/library/campaigns:

| Method | Route | Purpose |
|---|---|---|
| POST | / | Atomic, preflighted 2–24 video campaign submission |
| GET | / | Recent campaigns |
| GET | /{id} | Group progress, status and verified video links |
| POST | /{id}/cancel-pending | Cancel only QUEUED jobs |
| GET | /{id}/export | Download READY MP4s plus manifest as one ZIP |

Example POST JSON:

    {
      "name": "Wildlife Original-Art Puzzles",
      "asset_ids": ["YOUR_32_CHARACTER_APPROVED_ARTWORK_ID"],
      "count": 6,
      "base_seed": 42041,
      "duration_sec": 12,
      "exact_fit_count": 5,
      "enable_sfx": true,
      "allow_fallback": false,
      "cutout_ids": {}
    }

Idempotency-Key: use a stable unique header for repeated submissions of the same settings. The Studio hashes the submitted JSON to derive this key. Change campaign seed to intentionally create new motion variations.

## Implementation and QA

- services/worker/campaign_planner.py chooses 12 motion families and eight geometric styles with independent seeded exact-match timelines.
- services/worker/campaign_manager.py creates all jobs atomically in the existing SQLite database using BEGIN IMMEDIATE; failed submissions roll back entirely.
- services/api/campaign_routes.py preflights actual approved original files and cutout packs using existing validation. Render workers verify them again before encoding.
- apps/studio/index.html and apps/studio/app.js expose real multi-select, status, previews, safe cancellation, and ZIP exports.
- tests/test_campaign_factory.py covers deterministic plans, source approval, authenticated APIs, atomic rollback, deduplication, QA ZIP export and actual MP4 output.

Every exported video must be READY with the existing FFmpeg decode/frame QA. An incomplete campaign can export only its ready subset, explicitly marked as partial.

## Limitations and non-goals

This release does not generate independent AI pictures for each campaign item, pretend procedural test shapes are original photo assets, guarantee virality, or publish anything on Facebook. It still uses one persistent local/VM render worker with SQLite. A campaign supports at most 24 videos, 8 source originals and 30 seconds per Reel. ZIP media input is capped at 1 GiB and temporary exports are deleted after sending. Original art approvals and source hashes are required.

Gemini paid image generation, additional HD subject acquisition, distributed workers, live publishing, and Android APK are separate from this working offline campaign foundation.
