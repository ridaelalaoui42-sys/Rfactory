# Rfactory — Puzzle Reels Video Engine

Offline procedural video generation for original, 9:16 visual-puzzle Reels. This repository was recovered from the verified `Repo/Apf.zip` release on 23 October 2026.

**Status: render engine works; this is an early-stage developer project, NOT a production Facebook automation service.** The archive's HTML dashboard is a static demo generator and the Playwright publisher is simulated. Real Facebook publishing is intentionally blocked until a verified browser workflow is implemented.

## Verified capabilities

- Original bundled artwork and offline animal/object generation.
- Four deterministic animation styles: outline matching, missing vertical piece, face slice, and three-band face split.
- FFmpeg output and FFprobe/OpenCV QA for H.264 vertical video.
- SQLite project/job states, batch queue, offline batch renderer and manual export adapter.
- 15 self-contained tests and a smoke render in GitHub Actions, with no Facebook connections.
- Local FastAPI management endpoints (bearer authentication for remote access).

See [production audit](docs/PRODUCTION_AUDIT.md) for risks and remaining milestones.

## Requirements

- Python 3.11+
- FFmpeg and FFprobe available on PATH
- Enough disk for rendered videos and bundled static assets

Quick start from the repository root:

```bash
python -m venv .venv
# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Initialize local database, seed placeholder Pages and register 23 bundled assets:
python -m scripts.bootstrap_factory

# Generate two 15-second videos completely offline:
python -m scripts.run_batch --count 2 --duration 15 --audio

# Generate ten puzzle videos:
python -m scripts.run_batch --count 10 --duration 15 --template ALL --audio

# Run tests (use pip install -r requirements-dev.txt first):
python -m unittest discover -s tests -v

# Single 2-second 1080×1920 MP4 QA verification:
python -m scripts.smoke_render
```

Output files are written to `storage/renders/` and the local state database to `storage/factory.db`. Both are ignored by Git.

## API

Start locally with:

```bash
python -m scripts.bootstrap_factory
uvicorn services.api.server:app --host 127.0.0.1 --port 8000
```

API: `GET /api/health`, `GET /api/overview`, `POST /api/batches`, `POST /api/schedule`.

**Important:** `POST /api/batches` currently queues jobs only. Process them with the standalone worker/CLI; there is no always-on queue consumer yet. Do not bind the API to a public interface without `RFACTORY_API_TOKEN` and a proper access-control/reverse-proxy strategy.

When `RFACTORY_API_TOKEN` is configured, send `Authorization: Bearer <token>` with all management API requests.

## Docker Compose

The branch includes a working **API-only** Dockerfile/Compose target using SQLite, not the unimplemented PostgreSQL/Next.js services previously claimed by the archived README:

```bash
# Supply a strong random token through your environment:
export RFACTORY_API_TOKEN='REPLACE_WITH_A_STRONG_SECRET'
docker compose up --build
```

The API listens on `127.0.0.1:8000` on the host. Docker data is persisted in a named volume `rfactory_data` (not host `./storage`); this lets the unprivileged container user write runtime files. Export videos from the container or volume as needed. Docker packaging is supplied but end-to-end container runtime verification should be completed on the deployment host.

## Facebook publishing: not yet implemented

- No Meta Graph API access is needed to generate videos.
- The imported `MetaBusinessSuitePlaywrightPublisher` only simulates UI behavior; it is **not real Playwright automation**.
- This branch blocks normal publishing operations, avoiding false `PUBLISHED` records and invented Facebook links.
- Explicit DOM simulation is confined to tests via `RFACTORY_ALLOW_TEST_SIMULATION=1`.
- Manual export is the only currently meaningful publishing handoff.
- Real Playwright automation needs a separately tested manual-login browser worker, Page identity verification, supervised dry-run, UI change handling and restrictions/compliance review.

Do not post without verifying rights for any bundled artwork: some metadata references studio files named `watermarked_img_...`; the release alone does not demonstrate commercial licensing.

## Release recovery and audit

- [Read-only ZIP inventory](docs/RELEASE_ARCHIVE_INVENTORY.md)
- [Safe import report](docs/RELEASE_IMPORT_REPORT.md)
- [Prioritized technical audit](docs/PRODUCTION_AUDIT.md)

The protected `main` branch remains unchanged until the reviewed pull request is merged.

## AI Creative Studio (experimental, opt-in)

This branch now includes a **real Gemini service adapter** and a mobile-first creative workflow at `http://127.0.0.1:8000/studio`.

Capabilities: structured Gemini storyboards, Nano Banana 2.1 image generation and revisions, selectable Gemini TTS narration, alpha-cutout QA, 1080×1920 Reels built using unique AI assets, optional audio mixing, artwork approval, local asset library and media playback/download. Automated tests use mocked Gemini responses; **live billing/authentication still requires your own valid Gemini API key**.

```bash
pip install -r requirements-ai.txt
# Enable explicitly; NEVER place your provider key in the browser or Android client.
export RFACTORY_AI_ENABLED=true
export GEMINI_API_KEY='YOUR_KEY'
export RFACTORY_API_TOKEN='LONG_RANDOM_SECRET'
python -m scripts.bootstrap_factory
uvicorn services.api.server:app --host 127.0.0.1 --port 8000
```

Open `/studio` and paste the backend token. Begin with a creative brief, generate an AI storyboard, refine unique artwork, preview the WAV narration and approve the image before video generation. No automatic Facebook publishing occurs.

See [AI Studio documentation and Android plan](docs/AI_STUDIO_AND_ANDROID_PLAN.md). The API at `/api/v1/ai` intentionally separates Gemini credentials and FFmpeg workers from the frontend; `/openapi.json` can later support Capacitor or native Kotlin/Compose Android clients.


## Rfactory 3.0 (development branch, not production)

This branch is being implemented and validated in [PR #2](https://github.com/ridaelalaoui42-sys/Rfactory/pull/2).
It upgrades the source-accurate engine, **not** Facebook publishing or native Android.

**Motion:** sixteen deterministic continuous profiles; seeded, irregular, single-frame exact-fit crossings with no visible solve cue. Available in the Studio motion selector and through \`GET /api/v1/creative/capabilities\`. Preview the real pose path using \`POST /api/v1/creative/motion/preview\`.

**Geometry:** eight pixel-derived mask geometries with positive/negative reconstruction and canonical artwork hash validation. Select a geometry when rendering a \`MISSING_PIECE_SLIDE\` puzzle. Multi-piece reconstruction validates 2–5 nonoverlapping fragments, but independent multi-piece rendering is still in development.

**Live Gemini model discovery:** use \`GET /api/v1/ai/provider-models\` with the configured backend bearer token after enabling AI. This only lists models visible to the account and **does not prove free-tier quotas** or image/TTS authorization.

**Single-host render daemon:** with the runtime installed and bootstrap completed, start:

\`\`\`bash
python -m scripts.daemon_worker --poll-seconds 4
# Or process existing queued jobs once and exit:
python -m scripts.daemon_worker --once
\`\`\`

A local exclusive lock prevents duplicate worker processes sharing the same storage directory. This is **not** a multi-host or distributed worker leasing solution.

**Motion/geometry showcase:** six original bundled characters in distinct motion/cutout combinations:

\`\`\`bash
python -m scripts.render_rfactory3_showcase --duration 3 --count 3
# Longer examples on a capable PC/VM:
python -m scripts.render_rfactory3_showcase --duration 12 --count 5
\`\`\`

The GitHub workflow \`.github/workflows/rfactory3-showcase.yml\` uploads actual MP4s and their QA metadata. Artwork is bundled procedural artwork and audio is disabled in these technical demos: do not describe them as live Gemini outputs.

See \`docs/RFACTORY_3_AUDIT.md\` for the complete implementation status and remaining work.
