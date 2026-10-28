# ClipForge AI — Automated Media Production Studio

ClipForge AI builds vertical (9:16) and horizontal (16:9) videos from authorized media. It combines YouTube discovery, transcript indexing, high-moment candidate ranking, FFmpeg rendering, timed captions, and a private Editor V1 creative workflow.

**Current version:** 0.2 development release. A functioning single-operator dashboard and background worker, not yet a fully automatic social publishing platform.

## Quick start with Docker

Prerequisites: Docker Engine + Docker Compose plugin. Download or clone this repository.

1. Set a strong random environment secret CLIPFORGE_API_TOKEN (required).
2. Optionally set YOUTUBE_API_KEY for official YouTube Data API search.
3. Start: docker compose up --build
4. Visit http://127.0.0.1:8000, enter the configured API token.
5. Upload footage you own or are authorized to use, and save rights evidence.
6. Import a timestamped transcript or run optional on-device transcription.
7. Select candidate moments, export format and optional burned subtitles.
8. Queue the render; the worker produces MP4 and an Editor V1 creative brief.

To use faster-whisper in Docker, build a worker image with the optional speech extra installed. In a Python environment, run: python -m pip install -e ".[speech]". Default Docker installation intentionally excludes large AI model downloads.

## Python local mode

Requires Python 3.11+, FFmpeg and FFprobe.

    python -m pip install -e ".[dev]"
    clipforge init
    export CLIPFORGE_API_TOKEN=your-secret
    clipforge serve

In a separate terminal run: python -m clipforge.worker

The API listens only on localhost in local CLI mode. The Docker binding is also localhost-only by default. Use authenticated TLS reverse proxy when hosting elsewhere.

## Research

Official discovery:

    clipforge discover --query "Moroccan entrepreneurship"

The optional independent ytb-cli can search public metadata and timestamped caption tracks, using unofficial YouTube endpoints. This tool is not affiliated with Google and its access methods may be brittle or restricted by YouTube terms. ClipForge does not automatically download YouTube video/audio.

To import a transcript using an approved workflow:

    clipforge add-source --title "My podcast" --rights owned --evidence "Recording contract" --local-file media/podcast.mp4
    clipforge import-transcript --source-id 1 --json transcript.json

Transcript format is a JSON list with start/end seconds and text fields. ytb-cli transcript research is also available through the authenticated API, but it does not authorize downloading or republishing a source video.

## Scheduled topic watches

In the dashboard, search a topic and select "Watch daily" with a market and language. The Docker worker automatically refreshes pending watches using the official YouTube Data API, stores deduplicated video metadata, and enforces a daily query limit. This research catalog never automatically imports third-party footage for publishing.

API endpoints: POST /v1/topics, GET /v1/topics, GET /v1/topic-results, POST /v1/topics/{id}/scan.

## Render and Editor V1

    clipforge create-plan --source-id 1 --ranges "10:35,46:88" --format vertical --output my-short.mp4
    clipforge render --plan-id 1

Allowed format names: vertical, horizontal and square. Plans support up to 200 segments and 4 hours of assembled output.

Burning source-aligned captions is available through the dashboard / API. Every export produces a JSON brief for the separately installed original Editor V1 skill. The original skill is not bundled or resold. Set CLIPFORGE_EDITOR_V1_PATH to its privately installed skill root and use the API prepare-editor-v1 endpoint for approved horizontal outputs. That handoff creates an upstream project workspace; it does not automatically create the final HyperFrames cinematic edit.

## Atlas-inspired motion-style briefs

Choose from 18 original motion-style direction presets inspired by the public Futurepedia Style Atlas (catalog: 86 styles). `GET /v1/styles` lists available IDs, `GET /v1/styles/{style_id}` returns design directions, and `POST /v1/styles/prompt` generates a structured original animation prompt. Include optional `style_preset` in `POST /v1/plans` to embed the direction in the Editor V1 JSON handoff after rendering. These are **creative briefs, not rendered effects**; original Futurepedia prompts/sound kits and the private Editor V1 skill are not bundled. See [docs/STYLE_ATLAS.md](docs/STYLE_ATLAS.md).

## Executable Visual Style Engine (prototype)

The first original executable style is **Risograph Zine**. Source: [visual_style_engine/](visual_style_engine/docs/README.md). It renders deterministic three-ink procedural frames with synthesized SFX and exports horizontal/vertical/square MP4 files.

Run from the repository root:

```sh
python -m pip install -r visual_style_engine/requirements-dev.txt
npm install --prefix visual_style_engine
python visual_style_engine/scripts/render_style.py --format vertical --width 540 --fps 24 --output out/risograph-demo.mp4
```

The optional web preview and storyboard are served by ClipForge at `/style-engine/player.html?format=vertical` and `/style-engine/storyboard.html` when the repository's `visual_style_engine/web` directory exists. The preview is separate from the FFmpeg footage rough cut; it is **not** private Editor V1 cinematic rendering.

Only **one** native style is implemented; the other Atlas-inspired style IDs remain creative-brief-only. No proprietary upstream prompt bundle or privately installed skill is included.

## Boundaries

Not delivered yet: fully autonomous original Editor V1 effects, AI B-roll and full scriptwriting, multi-user SaaS, OAuth account onboarding and live-tested public publishing, a hosted server, or legal copyright/fair-use clearance. Optional private YouTube and draft Facebook upload adapters are implemented but require your authorized credentials and operator approval. Read docs/PUBLISHING.md. Source rights and platform terms are mandatory.

Original Rfactory code and branding assets remain preserved on branch backup/rfactory-before-clipforge-2026-10-27. Read docs/BUILD_PROGRESS.md for current implementation details.

Tests: python -m pytest -q. The GitHub Actions workflow renders synthetic videos for regression coverage.
