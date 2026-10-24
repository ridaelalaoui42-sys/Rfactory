# Rfactory 3.0 — Implementation Audit and Release Gates

Date: 2026-10-24
Base: main at start of PR #2 (release ZIP recovery merged via PR #1)
Implementation branch: codex/rfactory-3-advanced-engine

## Baseline audit

- Original main was **not release-ready**: GitHub Actions run
  [40041239864](https://github.com/ridaelalaoui42-sys/Rfactory/actions/runs/40041239864)
  failed in \`test_no_frozen_frames_in_one_pass\`.
- Root cause: \`continuous_motion_pose(..., phase=1.0)\` computed trigonometric
  residues instead of mapping to phase=0.0. At pixel rounding boundaries, a
  1-pixel mismatch could arise between nominally identical pass endpoints.
- Repair in \`services/engine/motion_profiles.py\`: normalize phase 1.0 to
  0.0 before computing the pose. No removal of the regression check.
- A three-subject demonstration completed successfully on main in Actions
  [40041234350](https://github.com/ridaelalaoui42-sys/Rfactory/actions/runs/40041234350),
  which is **not** proof that the entire Python test suite passed.
- Existing Playwright publisher uses a test simulator only. Live browser
  publishing is deliberately blocked. Do not claim Facebook integration works.
- Gemini provider configuration and live generation require a separately
  configured, valid account/API key. Tests with mocks are not live billing tests.

## Features implemented in PR #2

### Continuous Motion Engine (phase 1)

- 16 selectable profile names, including 8 new harmonic continuous trajectories:
  \`bezier_sweep\`, \`catmull_wave\`, \`figure_eight\`, \`vortex\`,
  \`ricochet\`, \`helix\`, \`magnetic\`, and \`opposed_spin\`.
- All new trajectories pass through the mathematical identity pose; original
  source bytes are used without resampling at an exact-fit crossing.
- Input-domain validation rejects NaN/infinite/out-of-range travel and intensity.
- The deterministic renderer accepts the new profiles through its existing
  \`RenderConfig.motion_profile\` field.
- Existing seeded, irregularly spaced crossing schedule remains in place.
- Note: the new Bézier and Catmull modes are *curve-inspired parametric*
  paths; they are not a user-editable full spline editor or physical solver.
- The existing engine is primarily 2D with faux-depth transformations, not
  a true 3D physics engine.

### Precision puzzle geometry (phase 2 foundation)

- \`services/engine/puzzle_geometry.py\` implements binary source-derived
  masks: rectangle, ellipse, organic, jigsaw, curved band, hexagon,
  ring sector, triangle.
- Canonical-artwork SHA-256 validation and byte-exact RGBA reconstruction.
- 2–5 simultaneous source-derived pieces can be checked for overlap and
  rebuilt against a single canonical illustration.
- Eight mask choices are integrated into the \`MISSING_PIECE_SLIDE\` branch
  of the live renderer through \`RenderConfig.puzzle_geometry\`.
- Existing template modes remain unchanged; other puzzle templates have not
  yet been redesigned as the user requested.
- Rendering a fragment always reuses pixels from its original accepted image.
  No separate AI-generated lookalike image is used for the positive fragment.

### API + Studio

- \`services/api/creative_routes.py\`:
  - \`GET /api/v1/creative/capabilities\`
  - \`POST /api/v1/creative/motion/preview\`
  - \`POST /api/v1/creative/motion/diversity\`
- All calls are protected by existing API bearer middleware.
- Preview uses actual seeded crossing frames, returned as sampled positional,
  rotational, and scale values. It does not require Gemini credits.
- Heuristic normalized pose-distance detects trivial or near-identical
  choreography before expensive rendering, but is not a trained perceptual
  embedding model. It must not be called an AI visual critic.
- The existing Studio offers all 16 motion types, a trajectory inspector,
  actual crossing times, and geometry dropdown for missing-piece puzzles.
- \`/api/v1/ai/renders\` accepts geometry/motion choices and applies them in
  the actual renderer. Endpoints stay compatible with future Android clients.

### Tests

- New \`tests/test_advanced_geometry.py\` covers all eight geometries, source
  hash protection, 3-piece assembly, overlap rejection, bounds checking,
  16 continuous profile invariants, and a real jigsaw/helix MP4 render.
- New \`tests/test_creative_routes.py\` covers authenticated discovery,
  deterministic previews, exact-fit records, parameter rejection and motion
  similarity.
- Existing tests continue to run with GitHub Actions; changes must not be
  merged if the latest complete test run is failing.

## Deployment and publishing safeguards

- Never put Gemini keys in the frontend, APK, GitHub secrets output, or logs.
- Do not automatically publish to Facebook or claim publishing happened.
- Do not treat normalized pose distance as ground-truth originality.
- Full 1080x1920 rendering is expensive; test small matrix combinations before
  generating large batches.
- Store outputs, runtime database files, credentials and browser profiles
  outside the Git source repository.

## Major requested systems that are NOT implemented by PR #2

- Genuine user-editable transform/scene graph with multi-piece motion.
- Per-pixel automatic geometric repair and configurable offscreen constraints.
- Live Gemini model capability discovery, auto-directed agent DAG, and visual
  critic approval loop.
- Cost ledger with actual provider invoices and paid/free quota distinctions.
- Lyria generation and multi-speaker speech personalization.
- Persistent multi-user render queue with renewable leases, heartbeats,
  cancellation and recovery under concurrent load.
- Complete React/TypeScript timeline editor and professional dashboard.
- Production Playwright Facebook publisher (current code is a simulator).
- Public OAuth/OIDC with tenant isolation and token revocation.
- Native Android/Capacitor APK and secure mobile distribution.
- All six user-requested showcase subjects with art-provenance verification.

These remain follow-on milestones; do not claim completion of the entire
master prompt until they are genuinely implemented and tested.

## Release gates

1. **Green full CI** on the final PR head SHA, not a previous commit.
2. All eight new geometries reconstruct the same source at raw pixel MAD=0.
3. All 16 motion profiles cross the identity exactly and have no intentional
   matched-frame holds.
4. Real MP4 tests validate encoded frame count, H.264 codec and source-frame
   comparisons. H.264 differences are tolerance-based, not asserted zero.
5. The API returns 401 without authorization and rejects invalid parameters.
6. No user or third-party credentials or unlicensed assets added to Git.
7. Screenshots/video artifact reviews before any deployment.
8. Only merge after the complete set of required checks passes.

## Additional modules delivered

- \`services/ai/provider_catalog.py\` queries the official Google Gen AI SDK
  \`client.models.list()\` API on demand. New protected
  \`GET /api/v1/ai/provider-models\` endpoint. It never reports inferred paid
  access or free-tier entitlements. Unit tests use a fake model list.
- \`scripts/daemon_worker.py\` is a continuous local render queue consumer
  with a single-instance advisory file lock and graceful SIGTERM handling.
  It runs separately from FastAPI, but this is not multi-host leasing or
  a fully asynchronous user-account processing system.
- \`scripts/render_rfactory3_showcase.py\` produces six **real 1080x1920**
  playable MP4 demos, each using a different bundled character, profile
  and canonical-source mask. The GitHub Actions workflow generates ZIP artifacts.
  Smoke-video durations are 3 seconds, not final 12–15-second deliverables.

### Verified GitHub Actions artifact

Run [40047756181](https://github.com/ridaelalaoui42-sys/Rfactory/actions/runs/40047756181)
succeeded and uploaded artifact \`rfactory3-six-video-showcase\` (6 actual MP4s,
13 MB archive). The six demonstrations verify 3 exact-fit crossings each and
frame-QA completeness. That is separate from full Python CI, which must pass
on the final PR head before the branch is considered mergeable.
