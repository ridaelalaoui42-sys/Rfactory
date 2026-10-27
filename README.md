# ClipForge AI

Autonomous-media foundation for Moroccan and international content, with a rights-aware research and editing pipeline.

## Working first release
- YouTube Data API metadata search; local transcript indexing and timestamp search.
- Persistent SQLite sources, transcripts and editing plans with rights gate.
- Multi-segment rendering using FFmpeg for vertical (9:16), horizontal (16:9) or square (1:1).
- Private original Editor V1 skill detection and JSON editing brief output; **no redistribution of the original skill**.
- Authenticated FastAPI routes and a CLI. No unattended third-party downloads or automated social posts.

## Installation

Requires Python >= 3.11 and ffmpeg/ffprobe.

    pip install -e ".[dev]"
    clipforge init
    export CLIPFORGE_API_TOKEN=your-long-random-secret
    clipforge serve

API: http://127.0.0.1:8000/docs
Docker: set CLIPFORGE_API_TOKEN then docker compose up --build.

### Sample authorized workflow

    mkdir -p media
    cp /your/approved/recording.mp4 media/recording.mp4
    clipforge add-source --title "Own recording" --local-file media/recording.mp4 --rights owned --evidence "I recorded this"
    clipforge create-plan --source-id 1 --ranges "0:2,3:5" --format vertical --output short.mp4
    clipforge render --plan-id 1

Other format: --format horizontal --output episode.mp4. Arbitrary long episodes supported up to 4 hours per render plan.

To search YouTube metadata, set YOUTUBE_API_KEY and run:

    clipforge discover --query "Morocco technology"

Transcripts: clipforge import-transcript --source-id 1 --json transcript.json
JSON list: [{"start":0,"end":2.5,"text":"السلام عليكم","language":"ar"}]

## Current boundaries
- Short/long **rough-cut editing**, not yet full Editor V1 cinematic effects. Each render emits a .editor-v1.json creative brief for the next layer.
- Metadata discovery only. Public YouTube availability and fair-use discussion do not independently authorize downloading audiovisual content.
- Imported source media must be owned, permitted or licensed with evidence. Unreviewed fair use is not an unattended-production permission.
- Synchronous renders, local storage, no web UI / no social OAuth / no publishing yet. See docs/ROADMAP.md.

Original Rfactory content is preserved in branch backup/rfactory-before-clipforge-2026-10-27.
