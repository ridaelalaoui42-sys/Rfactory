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

## Render and Editor V1

    clipforge create-plan --source-id 1 --ranges "10:35,46:88" --format vertical --output my-short.mp4
    clipforge render --plan-id 1

Allowed format names: vertical, horizontal and square. Plans support up to 200 segments and 4 hours of assembled output.

Burning source-aligned captions is available through the dashboard / API. Every export produces a JSON brief for the separately installed original Editor V1 skill. The original skill is not bundled or resold. Set CLIPFORGE_EDITOR_V1_PATH to its privately installed skill root and use the API prepare-editor-v1 endpoint for approved horizontal outputs. That handoff creates an upstream project workspace; it does not automatically create the final HyperFrames cinematic edit.

## Boundaries

Not delivered yet: fully autonomous original Editor V1 effects, AI B-roll and full scriptwriting, multi-user SaaS, OAuth account onboarding and live-tested public publishing, a hosted server, or legal copyright/fair-use clearance. Optional private YouTube and draft Facebook upload adapters are implemented but require your authorized credentials and operator approval. Read docs/PUBLISHING.md. Source rights and platform terms are mandatory.

Original Rfactory code and branding assets remain preserved on branch backup/rfactory-before-clipforge-2026-10-27. Read docs/BUILD_PROGRESS.md for current implementation details.

Tests: python -m pytest -q. The GitHub Actions workflow renders synthetic videos for regression coverage.
