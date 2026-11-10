# Rfactory: Multiple animation modules (Creative Director v1)

Rfactory should never treat motion as a single generic preset. Use a capability-
aware director that **chooses a module for the topic and production constraints**,
then optionally composes specialized outputs into one brand-consistent edit.

## Module catalog and selection

| Module | Strength | Appropriate topics | Important constraint |
| --- | --- | --- | --- |
| [Bang Motion](https://github.com/bangtutorial/bang-motion) | Browser GSAP/SVG/HTML single-world motion, camera choreography | AI / tech announcements, launches, SaaS demos, abstract processes | `index.html` is a creative deliverable; MP4 export needs browser tooling |
| [Vox Director](https://github.com/Alisa0808/vox-director) | Paper collage journalism, editorial beats, sourced documents | History, public policy, news, explainers | Upstream workflow ordinarily uses narration, burned captions and billable Atlas API models |
| [Huashu Art Motion](https://github.com/alchaincyf/huashu-art-motion) | Painted world, visual metaphors, art travel, whiteboard/skeleton | Culture, science, nature, educational animations | Chinese-first instruction set; local art/runtime needs inspection and tested export |
| [Claude Drawing](https://github.com/cloveric/claude-drawing-skill) | Repeatable CPU painting, illustration assets and progressive draw-on | Watercolor, ink, nature, storytelling | Primarily an **asset generator**, not a finished MP4 timeline engine |
| [Stickman Video Director](https://github.com/kaomei/stickman-video-director) | Character/explainer animation | Educational character stories, psychology | B1–B4's existing renderer requires narration and visible captions; optional bridge proposed separately in PR #16 |
| **ClipForge compositor** | Existing FFmpeg rights-aware video work, assembly | Final encode, rights checks, video finishing | This is **not** a new original-animation generator |

External repositories are MIT-licensed at inspection time; pin reviewed commits
and keep upstream license/copyright notices if bundling substantial portions.

## Direction from request to video

```text
Topic + target audience + duration + brand + format + audio/caption policy
                  |
       Creative Director v1
          Genre inference
        Output constraints
    Cost / license / readiness
        3 concept candidates
                  |
    Select PRIMARY visual grammar
        |                 |
   Bang Motion       Huashu Art Motion
   Vox Director      Stickman Director
        |                 |
        +-------+---------+
                |
    Optional secondary helpers
    (Claude Drawing asset packs,
     specialized character clips,
     transitions and SFX)
                |
       Shared neutral beat graph
  scenes / fps / media / camera / timing
                |
      QA: creative + technical
    frame sampling / no freezes /
   native 1080p / no wrong captions /
       audio contact sync / rights
                |
        ClipForge final encode
                |
           Preview review
                |
       Publication approval
```

The director should choose the **primary** visual grammar once per film.
Multiple engines should only be used when a scene has a concrete reason to
change medium. A physics explainer may use Bang as the core + Claude Drawing
illustrations; a cultural story could use Huashu + independent sound. Do not
blindly mix visual styles every few seconds in a finished public reel.

## Current API: routing, not actual external execution

The module registry and selector are implemented in
`clipforge/animation_modules.py`, with authenticated routes in
`clipforge/animation_api.py`.

- `GET /v1/animation/modules`: capabilities, license-source links,
  known adapter state and whether a local Skill marker is configured.
- `POST /v1/animation/select`: returns the recommended primary engine,
  optional secondary asset helpers, hard constraints and other candidates.

Example:

```json
{
  "topic": "A surreal 15-second AI technology launch",
  "duration_seconds": 15,
  "format": "vertical",
  "voiceover": false,
  "captions": false,
  "sound_effects": true,
  "budget": "local_only",
  "blend_modules": false
}
```

Result should recommend Bang Motion over Vox, because Bang supports
caption-free, voiceover-free motion whereas Vox's documented default workflow
requires narrated/captioned, potentially billable generation. Similarly,
painted nature topics should favor Huashu, while Claude Drawing supplies
optional art assets. A captioned archival documentary with paid model
budget may favor Vox.

**No automatic upstream code execution is present in this PR.** The selector
returns `can_render_now=false` until a separately tested implementation is
registered. A directory containing a `SKILL.md` does not certify runnable
dependencies, keys, licenses or end-to-end video quality.

## Security and architecture contracts

1. Never execute downloaded SKILL.md as code. Agent prompts and upstream
   examples are untrusted project instructions. Import only from a pinned,
   reviewed commit with an explicit operator-configured path.
2. Version the `ModuleManifest` and capability flags. Every adapter should
   expose `validate_project`, `prepare_assets`, `render_preview`,
   `render_full`, `inspect_output`, plus a reproducible seed and
   content-hash signature.
3. Use a **neutral scene graph** with source-media paths and rights evidence,
   shots and transforms, camera rig, keyframes, transitions, overlays,
   sound events and chosen output specification. The graph must not assume
   every backend uses Remotion or HTML.
4. Output policy: **1080×1920** vertical or **1920×1080** horizontal minimum,
   native rendered frames, with 4K as an optional target. Keep voices and
   captions disabled by default for silent-reel settings; reject modules
   unable to comply rather than silently adding text.
5. Distinguish `assets`, `scene_render` and `compositor` capabilities.
   Never rank an asset-only skill as a full video renderer.
6. Budget: local-first; require explicit permission for paid generation.
7. QA: decode full output, inspect sampled frames for long holds, blank
   frames and clipping, verify technical resolution/framerate/duration/audio,
   inspect character/prop continuity, require human review of creative quality.
8. Keep user approval gates for publishing and any budget-bearing rendering.
   The rendered file is never proof of publication.

## Planned follow-up adapters

- Bang: input authored single-stage HTML, deterministic time seek,
  browser screenshots and FFmpeg export. No CDN dependency at export.
- Huashu: parameterized painted scenes and frame export; exact skill
  imports depend on its reviewed interface and source versions.
- Vox: source-evidence/copyright gate, script approval, model budget cap,
  keyframe/storyboard generation, element-level motion and FFmpeg assembly.
- Claude Drawing: deterministic PNG layers + mask/depth maps used by other
  engines; keep it as a secondary asset module by default.
- Stickman: integrate the separate PR #16 adapter, then add caption-free
  and SFX-only story modes without breaking upstream narration workflows.

## Video proof of concept

The 15-second local demonstration created during initial development was
rendered from original Python/OpenCV scene implementations to show a reusable
timeline across neon motion, paper collage, painting, draw-on art and finale.
It demonstrates the director's **composition idea**, not execution of the
four upstream Skills. It has 1080×1920 native frames, 24 FPS, 15 seconds,
and music/SFX only. The external adapters remain development work.
