# ClipForge development status (October 2026)

## Implemented, verifiable
- Responsive single-operator dashboard at root URL, authenticated admin API and local media upload.
- YouTube Data API video metadata search and optional ytb-cli research for discovery and transcript import.
- Rights-labelled sources; evidence required for unattended media rendering.
- Searchable transcript segments, explainable clip candidate scoring, optional CPU faster-whisper transcription.
- SQLite durable render/transcribe job queue, atomic claims and Docker worker process.
- FFmpeg 9:16 / 16:9 / 1:1 multi-segment exports up to a 4-hour total timeline.
- Optional SRT captions retimed to the edited timeline and burned into finished exports.
- Private Editor V1 availability detector, editing briefs, and explicit upstream 16:9 project bootstrap.
- Signed-in operator download of completed videos, GitHub CI with synthetic media renders.

## Not implemented (no claim to completeness)
- Full automatic cinematic Editor V1 effect design and HyperFrames render.
- AI-driven documentary scripts, scene-aware composition, dynamic original B-roll and voiceovers.
- Robust redis/postgres multi-machine rendering with leases, retries and resource quotas.
- OAuth-based YouTube/Meta publishing; platform verification and credentials required.
- Per-tenant SaaS security and external media storage.
- Legal clearance/fair-use approval or unrestricted third-party video downloads.
- A continuously running hosted production server; Docker runs on the operator's infrastructure.

## Running locally
1. export CLIPFORGE_API_TOKEN to a strong secret.
2. docker compose up --build.
3. Visit http://127.0.0.1:8000
4. Enter token and upload owned/licensed footage with evidence.
5. Import transcript via API/CLI, or install the speech extra on the worker and queue transcription.
6. Select candidate moments, set vertical/horizontal orientation, optionally burn captions, queue.
7. Worker renders to persistent output volume; use dashboard to download.
8. For original Editor V1 16:9 handoff, configure CLIPFORGE_EDITOR_V1_PATH privately and call POST /v1/plans/{id}/prepare-editor-v1 after a complete render. Original upstream dependencies must already be installed.
