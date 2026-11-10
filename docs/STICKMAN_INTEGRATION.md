# Stickman Director integration (experimental)

This module connects the existing **ClipForge/Rfactory** backend to the MIT-licensed
[kaomei/stickman-video-director](https://github.com/kaomei/stickman-video-director)
Skill. It does **not** replace ClipForge's rough-cut pipeline, private Editor V1
installation, source-rights checks, or publishing approval. It does not silently
download third-party assets or call billable AI APIs.

## Capability boundary

- **Available now in the adapter:** authenticated project registration, source-rights
  metadata, manifest preflight, deterministic process invocation, durable queued
  previews/film jobs, explicit operator preview approval, outputs behind the API
  token, and preservation of upstream preview approval fingerprints.
- **Upstream manifest renderer:** B1 Minimal Line Art, B2 Colorful Hand-Drawn,
  B3 Retro TV, B4 Survival Thriller. Uses Node 20+, local image/audio assets,
  NAPI Canvas, Sharp and FFmpeg. Their manifest-based renderer is actually
  executable; the Python adapter delegates to it rather than reimplementing it.
- **Director Mode A1–A6:** useful storyboard/prompt references, **not** the
  B1–B4 executable-manifest route. B5 Character Explainer uses a separate
  code-authored route. These are listed for discovery but cannot be registered
  in this adapter.
- **No-captions policy:** existing upstream B1–B4 requires captions and
  burns them into video. **Do not promise caption-free reels through this
  adapter yet.** The existing ClipForge rough-cut renderer can export without
  captions. To deliver caption-free animated stickman reels, implement a
  separate no-caption renderer or a tested upstream renderer extension.
- All accepted project frames must be **native 1080p or higher**, 9:16 or 16:9,
  at 30 or 60 FPS. This does not upscale a 720p input or pretend the result has
  more actual detail than its source images.
- Current adapter requires already-authored, local **project.json**,
  narration, timed captions, stills and motion layers. It is **not** yet
  topic-to-video one-click AI generation. Audio/visual services may cost money
  even though the Skill's code is open source.

## Installation

1. Install an upstream snapshot you have reviewed, **outside** the Rfactory
   application directory and outside the media/output folders. Retain the
   MIT copyright and license when distributing copied upstream code:
   https://github.com/kaomei/stickman-video-director/blob/main/LICENSE
2. In the upstream `skills/directing-stickman-videos` folder run
   `npm ci`, then `node scripts/autopilot.mjs doctor`.
3. Install Node 20+ and FFmpeg/FFprobe in the *worker* environment. The
   stock Rfactory Python Dockerfile **does not** include Node/npm; use a
   compatible custom worker image or run a local worker with Node installed.
4. Set `CLIPFORGE_STICKMAN_SKILL_ROOT` to the absolute path of that upstream
   skill folder in **both** the API and worker environments.
5. Put authored projects under `CLIPFORGE_MEDIA_ROOT`, e.g.
   `/app/media/stickman/demo/project.json`, with referenced local assets.
   The JSON manifest format is defined upstream in
   `references/autopilot-runtime.md`; use **1080x1920** (vertical)
   or **1920x1080** (horizontal), not upstream's 1280x720 scaffold default.

Upstream projects require real narration with a corresponding audio duration;
the shots must cover the timeline without gaps. Captions are burned into this
specific upstream renderer, so it is not suitable for Rfactory's caption-free
social reel setting without a separate enhancement.

## Authenticated API sequence

All routes require the existing `Authorization: Bearer <CLIPFORGE_API_TOKEN>`
header. Only authorized operator-controlled source material should be used.

1. `GET /v1/stickman/status`: view style catalog and runtime checks.
2. `POST /v1/stickman/projects` with JSON:
   `{"project_file":"/app/media/stickman/demo/project.json","rights":"owned","rights_evidence":"I created the source art and voice"}`.
   Returns a project ID.
3. `POST /v1/stickman/projects/{id}/validate` with
   `{"seconds":20}`: validate the actual local upstream preview range.
4. `POST /v1/stickman/projects/{id}/queue-preview` with
   `{"seconds":20}`: returns a durable job ID. Run the ordinary
   `python -m clipforge.worker` to execute it.
5. `GET /v1/jobs/{job_id}` and
   `GET /v1/stickman/projects/{id}/download/preview`: inspect/review the
   preview. It must be played and reviewed, not approved automatically.
6. `POST /v1/stickman/projects/{id}/approve` with
   `{"note":"I reviewed the preview and approve this exact cut"}`.
   Upstream checks the preview's content hash and configuration.
7. `POST /v1/stickman/projects/{id}/queue-render` queues the complete
   approved film. Get results through `/v1/jobs/{job_id}` and
   `/v1/stickman/projects/{id}/download/film`.

The worker rechecks the manifest and style before every operation. All local
manifests must be in the configured media volume. No shell interpolation is
used. Long-running work is queued, not executed synchronously by the API.

## Next upgrades

- Fork/adapt the upstream renderer with genuinely optional captions and
  narration-free/SFX-only output; add explicit automated tests for both.
- Introduce typed character rigs, tweened walk/run gestures, facial expression
  timelines, camera graph, transitions, and scene/character continuity.
- Build a script-to-storyboard-to-assets planner with configurable model
  providers and human-reviewed factual/rights claims.
- Add an effects-compositing pass for transparent animation over legal footage,
  motion quality checks, and contact-sheet/human video QA.
- Offer 4K, native vertical/horizontal responsive layouts and an editor UI,
  retain local cache keys and hash-based approvals, and run real smoke renders
  in CI with only synthetic assets.

## Attribution

The upstream is Copyright (c) 2026 Stickman Video Director contributors and
licensed MIT. This bridge contains original glue code and does not vendor
upstream files. Preserve upstream notices with any later source vendoring.
