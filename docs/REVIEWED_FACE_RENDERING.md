# Rfactory 3.1 — Reviewed Cutout Integrity Standard

## Previously discovered production bug

Before this update, the Cutout Builder sliced images at the original resolution,
while the face video renderer letterboxed them onto its 860×860 canvas and
generated the geometry again. Even with the same random seed and facial region,
users could approve one shape and render a slightly different one.

**Rfactory 3.1 fixes this at the asset boundary, not just the preview UI.**

## Canonical production workflow

1. Import an intact real original image (not an AI-generated puzzle collage).
2. Approve the original artwork and verify rights.
3. Drag-select the face on the original asset in Studio.
4. The server letterboxes the source **once** with aspect ratio preserved to
   the exact same 860×860 canvas used by video production.
5. Source-pixel cuts generate the hole plate, 1–3 moving RGBA pieces, and
   their binary masks; exact restoration and transparent-hole QA run.
6. Review the preview PNGs, then approve the cutout pack. Approval re-reads
   and validates the files on disk and hashes every source/plate/piece/mask.
7. Choose an animation style, 4–7 irregular exact-fit crossings and render.
8. The renderer opens those **same approved PNGs** (never generates another
   mask), checks their approval hashes against current bytes and verifies that
   the unchanged canonical artwork has exactly matching pixels.
9. Three-piece modes use distinctive trajectories for each moving part.
10. Every uncompressed matching frame is compared against the correctly
    composited original portrait with no cutouts, on the scene background.
11. Full decoded-frame QA must pass before the output is returned as
    READY_FOR_REVIEW. Nothing is automatically published.

### Files

- `services/assets/face_canvas.py` — shared preview/export canvas.
- `services/assets/approved_face_pack.py` — approved artifact loader,
  source binding, SHA256 validation, mask reading.
- `services/api/cutout_routes.py` — generation and hash-locking approval.
- `services/api/library_routes.py` — authenticated direct-to-MP4 entry point.
- `services/engine/renderer.py` — consumes the actual approved PNGs.
- `scripts/render_from_library.py` — trusted CLI, supports
  `--approved-face-pack-id face_<24 hex>`.
- `tests/test_approved_face_pack.py` — tamper rejection and real MP4 creation.

## Regression and safety rules

- Changed mask, hole plate or moving piece after approval: **reject render**.
- Changed original image: **reject render**.
- Wrong source artwork or cutout mode: **reject render**.
- Transparent or semi-transparent images: compute the uncut scene from the
  pre-artwork background, never by drawing the source over the hole plate.
- Separate masks/slices may move differently, but they must all pass identity
  on the same single crossing frame, with no intentional solution pause.
- Verify exactness from raw uncompressed RGBA and scene RGB; H.264 decoding
  uses documented compression tolerances instead of false zero-MAD claims.
- API tokens and provider credentials never appear in browser media URLs,
  Git commits or generated manifest JSON.

## Compatibility note

Old face packs without an `approved_media_sha256` dictionary were created
before these integrity checks. They are **not grandfathered into production**.
Generate a new cutout preview from the original source, review and approve it
again. This rebinds the exact source/canvas/pieces to the final video.

## Deployment status

This update ships behind the GitHub pull request release gate. Green unit,
integrated MP4 and post-merge CI checks are required before calling it
production-ready. A production-grade multi-tenant job queue and live browser
publishing remain separate projects.
