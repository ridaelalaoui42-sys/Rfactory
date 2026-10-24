# Canonical Face Asset Engine — V1

## Permanent production rule

Generate (or import) **one complete clean image**, confirm its rights and
lack of baked puzzle effects, then cut every hole, mask and moving fragment
in Rfactory itself. Never prompt an AI image model to depict a missing face.

The canonical artwork, mask and extracted puzzle fragments must come from
the same source pixels. No separately generated facial patches.

## Fully implemented modules

- `services/assets/canonical_builder.py`: validate source quality, canonical
  RGBA and content provenance; clean-source confirmation is mandatory. The
  software cannot conclusively detect all fake AI-painted cutout effects, so
  a person must inspect the image.
- `services/assets/face_cutout_engine.py`: twelve face-aware cut modes,
  three-piece human bands and triangles, manual normalized region coordinates,
  optional OpenCV human-face proposal (not guaranteed), animal ROI heuristic
  flagged as unverified.
- `services/assets/fit_validator.py`: binary-mask checking, no overlapping
  source pixels, exact matching color and alpha, and byte-identical RGBA
  reconstruction of the original.
- `services/assets/asset_packager.py`: save `source.png`,
  `hole_plate.png`, `piece_01.png`, `piece_01_mask.png`,
  `overlay_preview.png`, `cutout_debug.png` and
  `puzzle_manifest.json` plus downloadable ZIP.
- `services/engine/renderer.py`: `CANONICAL_FACE` video mode. Each
  fragment animates along its own deterministic path, returns to **one
  exact identity frame per match**, never pauses, and doesn't display a
  visual match indicator.
- `services/api/cutout_routes.py`: create inspectable cutout packs,
  preview actual generated PNGs and masks, approve and download them.
- `services/api/library_routes.py`: requires approved, same-source cutout
  packs when rendering a face puzzle. The result can be watched/downloaded.
- `apps/studio/`: original source selection, cutout creator/inspector,
  approval, continuous-motion Reel render and authenticated MP4 playback.
- `scripts/render_from_library.py`: same server-side renderer for
  private PC/VM use without Gemini paid image access.

## Operator workflow in Studio

1. Open `/studio` on local Rfactory backend, enter backend bearer token.
2. Import a **genuinely clean** original image or select an approved source.
3. Choose animal or human and the face mode.
4. Set a face bounding rectangle. For animals, manual review is recommended;
   automated proportional ROI is only a suggestion, **not face recognition**.
5. Confirm clean source and rights before creating cutout assets.
6. Inspect source, hole plate, individual pieces, masks and debug overlay.
7. Approve the exact-fit asset pack after visual inspection.
8. Choose motion style, duration and 4–7 seeded exact crossings, then render.
9. Watch/download the MP4, review manifest and frame QA.
10. Manually publish. Browser publishing is still supervised/experimental.

## API

- `GET /api/v1/assets/face-modes` — available puzzle styles.
- `POST /api/v1/assets/cutout` — create source-derived cutout pack.
- `GET /api/v1/assets/{face_id}/manifest` — region, provenance and QA.
- `GET /api/v1/assets/{face_id}/media/source.png` etc — inspect PNGs.
- `POST /api/v1/assets/{face_id}/approve` — human review gate.
- `GET /api/v1/assets/{face_id}/download` — download pack ZIP.
- `POST /api/v1/library/renders` with approved `cutout_id` — exact
  face-aware Reel; never accept a cutout from a different source.

## Delivered visual proofs (independent reference renderer)

A downloadable demonstration ZIP is attached in the conversation:

- **Snow leopard**: one organic eye/muzzle face fragment; source is a
  separately generated clean OpenAI illustration (1024×1536 original).
- **Human astronaut**: three independent face segments from a clean
  original portrait (512×512 source). The source is below the HD library
  gate, so this is a **mechanical proof**, not a final HD production image.
- Both 1080×1920, 30 FPS, 10 seconds, H.264/AAC.
- Both decode 300/300 frames and have five irregular, one-frame identity
  crossings, zero intentional pauses, local match click audio only.
- Original and restored pixels are byte-identical at the exact match frames
  before lossy H.264 compression.
- The downloadable demo's composition is an independently verified reference
  sample; Rfactory's GitHub renderer has its own code path and separate CI
  regression tests.

## Production limitations

This implementation doesn't prove general animal facial landmarks with AI
recognition: operators should check/reposition ROI before approving. It
doesn't provide a legal license for user images or a free Gemini image API.
Real social posting, Android APK, and distributed SaaS job orchestration are
separate milestones. A clean HD human photo or properly generated portrait
should be used for final video production instead of the 512px proof source.

## Four real-video demonstrations (delivered separately as media ZIP)

The accompanying downloadable verification kit contains **four actual 1080×1920,
30fps, 8-second H.264/AAC MP4 files**. Each has five irregular exact-fit
crossings, zero raw RGBA reconstruction error, no deliberate solved-state hold,
no identical consecutive piece poses, and full decoded-frame coverage
(240 checked frames per video, 960 total).

| Original clean source | Cutout type | Source quality |
|---|---|---|
| Snow leopard | Animal central face (organic) | 1024×1536 original AI-generated |
| Snow leopard | Animal eyes band (curved) | Same independently generated HD original |
| Human astronaut portrait | Three independently moving facial bands | 512×512 **reference only** |
| Human astronaut portrait | Three moving triangular regions | Same 512×512 **reference only** |

The human demo's source was an existing clean portrait reference, **not
newly generated HD human artwork**. The same clean original source pixels
were used to manufacture each cutout, not a prompt requesting fake puzzle
pieces. A new production-resolution human source must be generated or
provided and operator-approved before commercial HD use.

Each demo includes original clean source, normalized source, hole plate,
individual extracted RGBA fragments, binary masks, frame review, QA JSON,
and a standalone reference renderer. The standalone reference renderer
is not byte-identical to the GitHub application. Application-specific
integration is independently covered by CI tests rendering real MP4s.

### Standalone four-Reel campaign

`python -m scripts.render_face_campaign --animal-core face_ID --animal-eye
face_ID --human-slices face_ID --human-triangles face_ID`

Each `face_ID` must correspond to an **approved**, same-source,
previously reviewed asset pack. This command fails closed if any image
approval, manifest mode, or source hash is invalid.

### Visual face selection

The Studio now provides an interactive source-image canvas. Drag over the
animal's eyes and muzzle (or the central human face). The region is recorded
as normalized source coordinates, reviewed in the mask/preview panel,
then tied to the approved cutout's seed and canonical original image hash.
