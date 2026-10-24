# Rfactory Real-Image Production Release — 2026-10-24

## A fully demonstrated production path

A manually verified Reel was rendered locally from **one real OpenAI-generated
snow-leopard source image**, not a generic procedural animal placeholder.

- Source: `snow_leopard_original.png` (1024×1536 RGBA).
- Video: `Rfactory_Real_AI_Snow_Leopard_1080x1920.mp4` (1080×1920, H.264,
  AAC, 30 FPS, 10 seconds).
- All 300/300 decoded frames were checked.
- Exact source-pixel fit at frames **28, 92, 153, 209 and 270**, or
  0.933 / 3.067 / 5.100 / 6.967 / 9.000 seconds.
- Zero raw RGBA source-reconstruction error at the five crossings.
- Zero intentional pauses, no visible solve indicators, and no repeated
  consecutive piece transform states in the tested sample.
- Audio is locally synthesized fit cues. This is **not Gemini TTS**.
- The MP4 is `READY_FOR_REVIEW`, not published.

The downloadable Proof Kit accompanying this conversation contains the
actual original artwork, MP4, JSON QA, nine-frame visual contact sheet,
standalone reproducible source script, and local HTML player.

**Important:** The Proof Kit's standalone renderer is a separately verified
reference implementation. The GitHub application uses
`services/engine/renderer.py` through
`scripts/render_from_library.py` or `/api/v1/library/renders`.
Both take the same canonical-source-and-exact-fit approach but may have
different visual composition.

## Current operator workflow

1. Install Python requirements or start `docker compose up --build -d`.
2. Open `/studio`, enter the backend API token.
3. Install the provided generated/reference/fallback artwork ZIP.
4. Reject low-resolution reference thumbnails from production.
5. Inspect and approve a full-resolution AI artwork or explicit fallback.
6. Acknowledge rights to use that source.
7. Select a motion profile, geometric cutout, duration, and exact-fit count.
8. Press **Render approved artwork into a Reel**.
9. Preview and download the verified 9:16 MP4. Inspect the crossing timing
   and exact source-matching QA.
10. Review and manually publish through the destination platform.

Offline rendering does **not** require a Google Gemini key or paid model
access. Gemini-only storyboarding, generated-image and TTS features remain
optional and must be tested against real provider credentials and quotas.

### Major implementation features

- Original high-resolution media library with SHA256 provenance and review
  gates, binary image-pack imports and strict fallback opt-in.
- Real positive/negative puzzle fragments extracted from one canonical source.
- 16 continuous motion trajectories, deterministic irregular single-frame
  exact-fit crossings, 8 reusable cutout geometries.
- Authenticated real-image rendering route `POST /api/v1/library/renders`,
  playback `GET /api/v1/library/renders/{id}/video`, and QA/provenance
  `GET /api/v1/library/renders/{id}/report`.
- Responsive Studio with asset gallery, approvals, movement control,
  geometry picker, video preview and MP4 download.
- Independent persistent local SQLite queue worker through Docker Compose.
  (The synchronous library render API is single-user by design; high-volume
  multi-user jobs should move to a leased queue.)
- Python unit/integration tests, actual FFmpeg render tests, strict per-frame
  QA, and CI verification.

## Known unfinished modules — do not claim otherwise

- No provider-billed, live Gemini image/TTS call was performed during this
  release verification. The fake test responses verify client contracts only.
- Facebook browser publisher is **not a working live uploader**. Publishing
  remains supervised manual export; no fabricated post IDs or links.
- Android API groundwork exists, but no compiled Android APK has been built.
- A scalable multi-tenant SaaS, OAuth accounts, cloud distributed worker pool,
  and public deployment have not been verified.
- This pack's other 48 small images are **references**, not full-HD source art.
  Three HD options come from one independent snow-leopard original and two
  derivatives; a diverse HD animal library still requires generating or
  importing separately authorized originals.
- Full mobile timeline editing, sophisticated scene graph and automated
  Gemini image quality critic remain future milestones.

## Releasing safely

Only merge a PR after its **final HEAD** passes all unit/integration and
full-HD smoke checks. Verify Docker Compose syntax, static JS compilation,
privacy of runtime tokens, paths, exact-match QA and non-publishing defaults.
Do not commit any Gemini API key or Facebook session.
