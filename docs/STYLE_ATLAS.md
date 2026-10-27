# Atlas-inspired motion-style presets (first integration)

Source of visual inspiration: [Futurepedia AI Style Atlas](https://www.futurepedia.io/resources/ai-style-atlas/view), viewed October 27, 2026. The site advertises 86 styles across 14 families; public page descriptions plus a user-supplied screenshot established the names of 18 entries. **This repository contains 18 newly written adaptation briefs, not the original 86 full prompts, code implementations, example videos, fonts, assets, or sound kits.** No claim of license to redistribute the original resources is made.

## Implemented

- `clipforge/style_atlas.py` defines 18 curated, self-authored direction presets. Each has family, best-for, visual language, animation operations, audio-design cue names and typography.
- `EditPlan.style_preset` is optional. Unsupported IDs fail validation; existing projects are unchanged.
- `GET /v1/styles` provides the protected catalog; `GET /v1/styles/{style_id}?output_format=vertical` previews a detailed brief. `POST /v1/styles/prompt` compiles an original source-editable creative prompt from a topic, optional narration, duration and selected style.
- When a render plan declares a style, its existing `.editor-v1.json` creative brief includes a `visual_style` object with output-specific layout rules, normalized story beats and QA requirements. The default remains unchanged.
- No upstream Editor V1 files are redistributed or executed; the existing private `CLIPFORGE_EDITOR_V1_PATH` contract remains intact.

## API example

```json
{
  "source_id": 1,
  "ranges": [{"start": 10, "end": 25}],
  "format": "vertical",
  "output_name": "science-short.mp4",
  "captions": true,
  "style_preset": "flat_vector_science"
}
```

Send this object to `POST /v1/plans` with the configured Bearer token. List available presets with `GET /v1/styles`.

## Rendering boundary

**Visual styles currently describe intended effects; they do not cause FFmpeg to animate them.** The current FFmpeg exporter remains a deterministic rough-cut renderer. The original Editor V1 private cinematic pipeline requires independent installation and an implementation of style-specific motion operators (not present here). Do not label outputs 'Atlas-style rendered' merely because their JSON contains the metadata.

## Suggested next integration (separate review)

1. Inspect the privately installed Editor V1 `SKILL.md`, existing scripts and rendering assumptions on the operator's machine, without uploading or bundling them.
2. Build an original operation renderer for `stroke_reveal`, `shape_morph`, `paper_cutout`, `graph_trace`, `connector_draw`, `product_orbit`, `jointed_puppet`, etc., using supported HTML Canvas/GSAP/HyperFrames commands or safe native effects.
3. Bind word-level SRT/VTT timings to animation trigger clocks; storyboard first, then per-scene previews, deterministic full renders with an explicit seed.
4. Add original SFX synthesis or licensed SFX libraries. Current `sound_cues` are **descriptive cue labels only**, not audio files.
5. Build two render profiles: 1920×1080 long-form and 1080×1920 Shorts/Reels; support longer scene queues, captions, safe areas, narration ducking and stereo loudness QA.
6. Add style-operator visual regression tests, anti-strobe checks, title-overflow checks and frozen-frame detection; inspect contact sheets and audio sync before publishing.
7. Inspect each of the remaining 68 atlas entries manually with authorized browser access, then create new original directions only where verified. Keep source attributions and permissions clear.

## Example style selection

| Use case | Suggested preset |
| --- | --- |
| Science short or school explanation | `flat_vector_science` or `whiteboard_explainer` |
| Coding and AI system breakdown | `tech_glow_explainer` |
| Documentary, source comparison | `editorial_essay_collage` |
| Mathematics tutorial | `manim_math` |
| Product hero ad | `product_launch_reveal` |
| Crime/history introduction | `film_noir_1940s` |
| Funny youth-friendly character | `claymation_set` or `halftone_pop_panel` |

The 18 styles are inspirations from common visual concepts, not copies of the site’s source animation code. Respect source rights, third-party software licenses and editorial human approval.
