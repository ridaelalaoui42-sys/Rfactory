# Rfactory Production Audit — 2026-10-23

**Scope:** `Repo` release asset `Apf.zip` (SHA-256 verified), imported review branch, services, video tests, publishing adapter, API, Docker, dashboard generator. The repository is **not production-ready**.

## Import provenance

- Release asset: [Apf.zip](https://github.com/ridaelalaoui42-sys/Rfactory/releases/download/Repo/Apf.zip).
- `docs/RELEASE_ARCHIVE_INVENTORY.md`: all 227 ZIP file entries.
- `docs/RELEASE_IMPORT_REPORT.md`: 223 source/static files imported, 4 local runtime/generated files intentionally excluded.
- The original release remains intact; `main` was not modified.
- No archive contents were executed during import.

## Prioritized risks / fixes

| Priority | Finding | Exact files | This PR | Next acceptance criteria |
|---|---|---|---|---|
| **P0** | The so-called Playwright publisher did not invoke a browser and could fabricate successful publishing/permalinks. | `services/publisher/adapters.py` | **Mitigated:** real publishing now fails closed. Simulated DOM only allowed with `RFACTORY_ALLOW_TEST_SIMULATION=1`. | Build a separate *actual* Playwright worker, explicit manual login, dry-run capture, active Page verification, idempotent post confirmation. Never promote mocked `PUBLISHED` to a real one. |
| **P0** | API lacked authentication for management endpoints. | `services/api/server.py` | **Mitigated:** bearer auth when `RFACTORY_API_TOKEN` exists; without it only loopback management requests permitted. | Add per-user authentication/roles, reverse-proxy TLS, CSRF/CORS review, rate limits before public access. |
| **P1** | SQLite used `journal_mode=MEMORY` and `synchronous=OFF`, risking crash-related job loss. | `services/database/repository.py` | **Fixed:** WAL + NORMAL. | Exercise concurrent render/queue load and recovery. |
| **P1** | Source was shipped exclusively in a release ZIP; `main` held only README/LICENSE. | `Repo` release, review branch | **Fixed on review branch:** checksum verification and filtered import. | Review and merge PR after CI. |
| **P1** | Docker Compose referenced missing `Dockerfile.worker`, `Dockerfile.web`, and Postgres despite the actual repository layer using `sqlite3`. | `docker-compose.yml`, `Dockerfile` | **Fixed for API-only deployment:** working SQLite-oriented build is supplied; no unsupported web/worker claimed. | Build and run container with strong `RFACTORY_API_TOKEN`, then verify health. |
| **P1** | Existing tests required developer-specific expired `artifacts/file_generation/ttl=...` paths and a bundled local SQLite DB. | `tests/test_factory.py`, `tests/test_release_safety.py`, `scripts/bootstrap_factory.py` | **Fixed:** portable generated fixtures, local DB bootstrap, GitHub CI. | Full test run plus rendered video smoke must pass on clean checkout. |
| **P1** | No continuously running render worker; `POST /api/batches` currently *enqueues* but does not render. | `services/api/server.py`, `services/worker/batch_runner.py` | **Open.** | Implement durable polling/claim worker process, idempotent completion and retry policy. |
| **P1** | The advertised Next.js production dashboard is not in the ZIP. `upgrade_dashboard_app.py` is a machine-specific static HTML generator with hard-coded sample state and success toasts. | `upgrade_dashboard_app.py`, `packages/animation/src/index.ts` | **Open.** | Build a real connected dashboard with authentication, real job statuses and real API mutations; no simulated success indicators. |
| **P1** | Actual Facebook browser upload, login-session lifecycle, scheduling and telemetry are unimplemented. | `services/publisher/adapters.py` | **Open (safely blocked).** | Test with authorized Page, visible supervised dry-run and documented Meta UI limitations; retain manual export fallback. |
| **P2** | Video QA used a shared temp filename and compared the 45th frame to the first instead of inspecting the final frame. | `services/engine/qa_validator.py` | **Fixed:** unique temp probes and actual last-frame sampling. | Concurrent QA jobs should not corrupt each other. |
| **P2** | Original renderer uses a fixed global scratch directory under `/tmp`; same job IDs can collide. | `services/engine/renderer.py` | **Open.** | Per-job `TemporaryDirectory` and robust cleanup on crash/cancel. |
| **P2** | Bundled asset manifest contains absolute paths from the original machine. | `storage/assets/asset_manifest.json` | **Mitigated:** bootstrap remaps all asset paths to local checkout. | Rebuild manifest with relative paths and verify source/license provenance. |
| **P2** | Artwork metadata claims original/CC0, but references source names beginning `watermarked_img_`; the release alone does not establish rights. | `services/assets/generator.py`, `storage/assets/asset_manifest.json` | **Open.** | Confirm appropriate commercial rights; replace any unlicensed/watermarked material before public posting. |
| **P2** | Public deployment architecture, multi-user access and Postgres parity remain incomplete. | `README.md`, `services/database/repository.py` | **Open.** | Migrations, proper Postgres implementation, monitoring, media storage policy. |

## Verified tests and smoke checks

- Unit tests: `python -m unittest discover -s tests -v`.
- Database/bootstrap: `python -m scripts.bootstrap_factory`.
- Render smoke: `python -m scripts.smoke_render` (1080×1920, 30 FPS, H.264, 2 seconds, pixel-perfect alignment).
- Action: `.github/workflows/ci.yml`.
- **No Facebook live publishing is tested, enabled, or claimed.**

## Deployment and security notes

1. Keep `main` unchanged until PR review. The import branch contains assets (~30 MB), code, checks and mitigation patches.
2. Never commit `.env`, SQLite files, Chromium profile directories, Facebook credentials/cookies or generated exports. The `.gitignore` and `.dockerignore` cover common cases.
3. The seeded Facebook Pages are *placeholders* and start `NEEDS_LOGIN`, never `CONNECTED`.
4. Do not expose the API publicly without an actual operator token and independent user authentication/reverse proxy.
5. Do not treat `upgrade_dashboard_app.py`'s JavaScript mock state or `simulated_dom_state` as real metrics or activity.

## Next implementation sprint

1. Implement a durable standalone worker with bounded concurrency, per-job scratch dirs and explicit failure/retry classification.
2. Build an authenticated Next.js front end wired to actual API endpoints, asset thumbnails and queue state.
3. Implement supervised Playwright browser interaction with no simulated success path and mock HTML fixture tests.
4. Run a verified 10-video batch, save QA/artifacts in CI, and perform visual reviews for masks, duration, audio, loops and legibility.
5. Add production deployment and end-to-end publishing only after operator authorization and platform checks.
