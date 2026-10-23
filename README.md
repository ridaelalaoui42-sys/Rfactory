# Animal Puzzle Reels Factory

Autonomous 9:16 vertical visual-puzzle video production platform, procedural motion-graphics engine, durable batch queue, and supervised Playwright Meta Business Suite publisher.

## 1. Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                        Next.js / Canvas Production Dashboard                      |
|  Overview | Video Studio | Batch Studio | Asset Library | Calendar | Page Manager |
+-----------------------------------------+-----------------------------------------+
                                          | REST API / State Sync
                                          v
+-----------------------------------------------------------------------------------+
|                 Durable Relational Store (PostgreSQL 16 / SQLite 3)               |
|  16 Tables: users, brands, facebook_pages, assets, asset_masks, ideas,            |
|  video_projects, batches, render_jobs, render_outputs, scheduled_posts,           |
|  publish_attempts, published_posts, audit_events, metrics_snapshots, settings     |
+-------------------+-------------------------------------------+-------------------+
                    |                                           |
                    v                                           v
+---------------------------------------+   +---------------------------------------+
|   Asset & Render Worker Engine        |   |   Publisher Adapter Worker            |
| - Offline SVG + RGBA Synthesizer      |   | - ManualExportPublisher (Default)     |
| - OpenCV Exterior Flood-Fill Masking  |   | - MetaBusinessSuitePlaywrightPublisher|
| - Pixel-Perfect Slice Extraction      |   | - Persistent Profile Dir Isolation    |
| - Remotion + Fast FFmpeg Pipe (30fps) |   | - Active Page Identity Guard          |
| - FFprobe & OpenCV Automated QA       |   | - UNKNOWN_RESULT Duplicate Quarantine |
+---------------------------------------+   +---------------------------------------+
```

## 2. Database Entity-Relationship Summary (16 Tables)

- `users` -> manages operator accounts and default timezone (`Africa/Casablanca`).
- `brands` -> `facebook_pages` (1:N): stores per-Page session health, daily caps (`2/day`), quiet hours (`23:00-07:00`), and active mutex lock (`active_lock_job_id`).
- `assets` -> `asset_masks` (1:N): stores SHA-256 content hashes, CC0 provenance, alpha validation metrics, and pixel-perfect missing-piece slice coordinates (`pixel_match_mad = 0.0`).
- `ideas` -> `video_projects` -> `render_jobs` -> `render_outputs`: tracks deterministic seeds, JSON template configs, and automated FFprobe/OpenCV QA reports.
- `batches` -> `render_jobs` (1:N): tracks 10/25/50/100-video campaigns with fault isolation.
- `scheduled_posts` -> `publish_attempts` & `published_posts`: enforces idempotency keys, approval gates, and `UNKNOWN_RESULT` quarantine.
- `audit_events`, `metrics_snapshots`, `system_settings`: append-only operational audit trail and runtime switches.

## 3. Quick Start Commands (Zero Paid API Keys Required)

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Run automated test suite (10 test suites: assets, masks, pixel alignment, QA, DB, scheduler, publisher)
python3 -m unittest discover -s tests -v

# 3. Start FastAPI backend service
uvicorn services.api.server:app --host 0.0.0.0 --port 8000

# 4. Or launch full stack via Docker Compose
docker compose up --build -d
```

## 4. Authorized Playwright Human Login Setup (No Meta Graph API Required)

1. Browser automation is **disabled by default** (`BROWSER_AUTOMATION_ENABLED=false` and `browser_publishing_enabled=0` per Page).
2. To connect a Facebook Page you administer:
   - Open **Facebook Page Manager** in the dashboard and click **Launch Human Browser Login**.
   - Chromium opens with a dedicated private `--user-data-dir` under `./storage/browser_profiles/<page_id>` (never committed to Git or exposed via API).
   - Complete Facebook login and MFA/2FA interactively in the browser window.
3. Always run a **Supervised Dry-Run** (`dry_run=True`) first: the worker opens Meta Business Suite, verifies the active Page header matches `page_name`, attaches the 1080×1920 MP4, populates the caption, captures a sanitized screenshot, and halts before clicking final Publish.
4. If confirmation is ever ambiguous after submission, the post transitions to `UNKNOWN_RESULT` and is **never** automatically retried until an operator verifies the Page.
