# Rfactory 3.2 — Durable Reel Production Queue

## Why this exists

The previous Studio kept an HTTP request open while encoding, muxing,
and checking every frame of a full-HD puzzle Reel. Longer exports could
time out and the operator could not track the job after closing the tab.

**The Studio now submits a 202 Accepted job** to durable SQLite storage and
the existing Docker/PC render daemon processes it separately.

## Run locally

\`\`\`bash
# Set a strong server-side RFACTORY_API_TOKEN, then:
docker compose up --build -d
\`\`\`

The API and worker already share the persistent \`rfactory_data\` volume.
For bare-metal Windows/Linux:

\`\`\`bash
python -m scripts.bootstrap_factory
# Terminal A:
uvicorn services.api.server:app --host 127.0.0.1 --port 8000
# Terminal B:
python -m scripts.daemon_worker --poll-seconds 4
\`\`\`

Open \`/studio\`, choose a *reviewed* original artwork (and face pack where
relevant), then press **Queue Reel render**. The production queue panel shows
status, verified percent progress, recent jobs, and finished MP4 playback.

Queue work continues even if Studio reloads or its browser tab is closed.
The queue is scoped to a single private server/operator.

## REST API (bearer token required)

- \`POST /api/v1/library/render-jobs\` — create a render job, returns 202.
- \`GET /api/v1/library/render-jobs\` — list the most recent jobs.
- \`GET /api/v1/library/render-jobs/{id}\` — read status, progress and results.
- \`POST /api/v1/library/render-jobs/{id}/cancel\` — cancel only queued/failed jobs.
- \`POST /api/v1/library/render-jobs/{id}/retry\` — requeue failed/cancelled jobs.
- \`GET /api/v1/library/renders/{video_id}/video\` — authenticated MP4 download.
- \`GET /api/v1/library/renders/{video_id}/report\` — frame QA/provenance.

Example:

\`\`\`bash
curl -X POST http://127.0.0.1:8000/api/v1/library/render-jobs \
  -H "Authorization: Bearer $RFACTORY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: my-video-01" \
  -d '{"asset_id":"APPROVED_ASSET_ID","cutout_id":null,
       "duration_sec":12,"exact_fit_count":5,
       "motion_profile":"helix","geometry":"organic",
       "seed":42041,"enable_sfx":true}'
\`\`\`

An identical idempotency key and identical request return the same job.
Reusing that key for different settings returns HTTP 409. If a client
disconnects just after submitting, it can safely retry with the same key.

## Persistence and safety

- \`art_render_jobs\` is created with an idempotent SQLite migration; your
  existing 16-table Rfactory database and older batch-render jobs remain.
- Atomic \`BEGIN IMMEDIATE\` job claiming prevents two consumers claiming
  the same queued work.
- A single-host advisory lock restricts this deployment to one render
  daemon. PostgreSQL distributed leasing is **not implemented**.
- Worker leases expire after 15 minutes without a progress heartbeat.
  An interrupted job is automatically requeued until the bounded retry
  count is exhausted; then it is marked FAILED.
- Worker must validate the approved HD artwork *again*, including the
  exact decoded source-pixel hash captured at enqueue. Approved face packs
  are checked against their reviewed mask/piece hashes before rendering.
- Progress is updated during frame encoding, with an honest plateau near
  85% while muxing and decoded-frame QA complete. 100% means an actual
  successfully validated MP4 was produced.
- Queue responses contain opaque IDs and authenticated media URLs, not
  internal server file paths. Provider errors, keys and private media
  paths are not returned by job polling.
- Existing synchronous \`POST /api/v1/library/renders\` remains available
  for legacy/local integrations. Studio no longer relies on it.

## Known limitations

- In-progress FFmpeg cancellation is deliberately disabled; cancellation
  is allowed while a job is QUEUED or FAILED. A process-safe cancellation
  mechanism and subprocess cleanup need a separate implementation.
- The worker is single-host and serial. It is **not** a horizontally scaled
  job service, does not provision GPUs, and has no user-account billing.
- Very long FFmpeg phases without progress for over 15 minutes may expire
  a lease; tune limits for slower hardware after measuring benchmark data.
- Rendered MP4s are still reviewed/manual-export only; Facebook publishing
  remains disabled and no live Gemini generation is claimed.
- Old already-queued jobs created before the 3.2 source-hash pin are not
  automatically processed as successful; resubmit with the current Studio.

## Regression coverage

\`tests/test_art_render_queue.py\` checks durable reads across independent
queue connections, atomic claims, idempotency conflicts, cancellation, retry,
bounded expired-lease recovery, strict API authentication, safe result
serialization and a real no-Gemini two-second H.264 Reel through the queue.
Full CI checks the existing renderer/face-puzzle tests as well.
