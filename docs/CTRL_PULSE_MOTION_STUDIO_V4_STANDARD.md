# Rfactory Motion Studio V4 — permanent video production standard

**Status:** Engineering standard and local 3D adapter proof of concept. This is **not** a claim that Remotion, HyperFrames, Three.js, Bang Motion or Claude Code are all installed and working in the production environment. Until a full 3D + natural-TTS integration is validated and deployed, this sample is not publishable.

## Reference breakdown (user-supplied videos)

- **64386.mp4** — 18.48s, 720 × 1280, H.264/AAC, 30 FPS. A physically coherent 3D coffee-making model: stable machine, moving pipe/liquid, process-oriented macro shots, clear material contrast and an evolving scene. The 720p input is **not** an accepted output target for CTRL Pulse.
- **64387.mp4** — 125.65s, 1080 × 1920, VP9/AAC, 30 FPS. Coherent 3D educational teardown of a game disc/console: complete models, moving internals, layer separation, close-up camera tracking, labels attached to operations, persistent staging and visual continuity.
- **Adopt:** behavior-driven geometry, object permanence, functional 3D camera, procedural light/material, tracked text, audible events, storyboard evidence, no overlapping labels.
- **Do not copy:** unique objects, captions, audio, scene geometry, shot lists, or original reference branding. The two uploaded clips are visual benchmarks, not licensed reusable footage.

## One-film architecture

```text
Verified topic + rights + audience promise
  → expert script (hook → physical mechanism → surprising payoff)
  → natural TTS + word/sentence timings (prefer generated natural speech)
  → 3D director: object inventory, parent transforms, exploded-view choreography
  → pre-built, licensed textures / models or original procedural geometry
  → one timebase and deterministic scene graph
     ├── primary: Remotion + React Three Fiber + Three.js
     ├── alternate: HTML/GSAP + Three.js with deterministic seek/capture
     ├── specialized: Bang Motion, HyperFrames, editorial 2D/illustration
     └── proof/test adapter: VTK offscreen for physical 3D geometry
  → integrated typography with explicit no-overlap zoning
  → audio engine: dialogue + music + event-driven spatial SFX
  → frame export / contact sheet / 3D visual QA / audio QA
  → final 1080x1920 30–60 FPS, H.264/AAC, +faststart
  → brand/editorial verification → publish → Facebook Page media readback
```

### Strict content rules

1. **One idea and one physical world.** Every model and visual action must explain a line of the story. A collection of moving images with random transitions fails QA. The protagonist/object persists through scene changes when appropriate.
2. **Physical 3D.** Render geometry with perspective, materials, lighting, contact shadows, depth, occlusion, animation rigs and proper camera blocking. For teardowns, each removable part must have an explicit parent, initial transform, destination transform, and insertion/removal order. Never substitute flat card graphics for mechanical 3D unless the concept justifies schematic illustration.
3. **Readable, animated editorial typography.** Three branded roles: display headline (Inter Display or another licensed design font), body/labels (Inter Medium), data annotations (mono). Text **explains** components; it does not repeat narration word for word. Story-based reveals, tracked leader lines, spring/masked emphasis, numeric build-on, diagrams. No generic fade/slide on every beat. The title-safe region is separate from moving 3D objects, backed by intentional negative space. Detect bounding-box collisions at every keyframe, plus object/title intrusion in contact sheets.
4. **Object-aware camera.** Plan wide establish → medium assembly → macro explanation → release. Camera may follow an object when a mechanism changes. Never random camera shake or constant zoom. Use physically plausible lens, near/far, framing, and exposure.
5. **Rich audio.** Natural generated English TTS by default (unless asked otherwise), music selected/composed for scene arc, and distinct SFX on real actions: mechanical lift, clicks, electrical pulses, data transmission, material interaction and resolution. SFX must not overpower narration; target platform playback approximately −14 to −16 integrated LUFS and true peak below −1 dBTP, with a separate intelligibility check. Generate SFX/audio programmatically or license source sounds. **A reel without meaningful sound design fails publication QA.**
6. **Video/image assets.** Generate several coherent scene plates/textures and one or more multi-object asset sheets when useful; cut each object with proper alpha/mattes and place it in the actual 3D/2.5D world. Use legal, sourced real photography as appropriate. Procedural 3D models count as genuinely original model assets. Never rely solely on one AI image, fake model-generated text on baked images, or generic auto-slideshow.
7. **Visual sophistication is earned by design, not effect count.** Use one principal material and accent system per film, a functional camera, negative space, restrained bloom, realistic board/cable/metal topology and purposeful kinetic callouts.
8. **Native 1080×1920 or higher.** 30 FPS minimum, 60 where fast detailed motion warrants. 720p upscaling is rejected as a 'native Full HD' claim. H.264 video and AAC 48k audio for social deliverable. Background music, sound transitions and voice must all be audibly present in the final file.

## Formal scene-manifest contract

Every visible object carries a stable ID, material provenance, 3D source model, parent group, transform/orientation tracks, appear/disappear interval, physics/ease, and important view-frustum bounds. Every text item carries exact phrase, intended spoken cue, anchor object/screen safe zone, bounding box at canonical resolution, entrance/exit type and held reading time. Every audio event carries its source/generation method, timestamp, gain, pan and associated visible action. All transforms are pure functions of `t`; no shared mutable animation clock or unseeded randomness.

## QA and release gates (fail closed)

**Technical:** decode output; verify exact dimensions, codec, frame rate and duration; check for black intervals, frozen intervals >1s (unless intentionally storyboarded), significant aspect/cropping error, missing or low-level audio, clipping, loudness. **Layout:** inspect a contact sheet with samples at cue −0.15s, cue +0.25s, midpoint and exit −0.15s and every camera cut. Reject any title above safe edges, labels covering each other, text clipping, critical object hiding narration point, physically disconnected model layers, missing rig pivots. **Audio:** match all sound events to actual visible actions; validate dialogue, ducking and loudness. **Narrative:** viewer should be able to tell what changed after watching without the caption; separate post description must link trusted factual sources.

Reels without natural voiceover, properly mixed audio, checked technical claims and attached source/media rights must carry `LAB_SAMPLE_NOT_PUBLISHED`. An upstream adapter is only marked `READY` after one real end-to-end 1080p render and QA, not because a SKILL.md file exists.

## Recommended specialized skills (reviewed as references, not automatically installed)

- **Official Remotion skills:** https://github.com/remotion-dev/skills — deterministic frame-by-frame React video composition and correct rendering rules. Check Remotion license compliance for business use.
- **HyperFrames:** https://github.com/heygen-com/hyperframes — HTML/JS, timelines, motion components and editor tooling; reviewed for available implementation and licensing.
- **Bang Motion:** https://github.com/bangtutorial/bang-motion — active-world motion rather than PowerPoint behavior, kinetic typography, camera push-through, storyboard logic.
- **Motion tools and skills:** https://github.com/VisualxIntelligence/motion-tools-and-skills — Three.js/WebGL geometry, browser frame capture, audio timing and automated visual QA.
- **GSAP skills:** https://github.com/greensock/gsap-skills — authored timeline sequencing and repeatable motion easing.
- **Rfactory Signal Lab V3:** https://github.com/ridaelalaoui42-sys/Rfactory/pull/15 — procedural frame-by-frame motion base, not yet automatically equivalent to a production 3D engine.

### Agent guidelines for Codex / Claude Code

Use this file as the acceptance specification. Agents must not improvise arbitrary animation modules or override the explicit media constraints. Build a storyboard and scene manifest first, implement one primary renderer with an isolated adapter, then render keyframes, diagnose, revise, encode and listen; **the user-facing deliverable is the verified MP4 and source, not a code plan**. A label, mechanical rig or audio clip missing from the final MP4 is a failure even if it exists in source. Every implementation PR must attach technical metadata, a contact sheet, a QA report, license inventory and a short render; no automatic merging before tests.

## Rollout stages

1. **V4.0 local reference probe:** Actual VTK 3D geometry + camera + procedural SFX + recorded bbox QA; no natural TTS—technical prototype, **not publication**.
2. **V4.1 production compositor:** Install/pin Remotion, Three.js, R3F and their audio/text modules in a Node worker; use tested media transport and deterministic headless Chromium or supported Remotion rendering. Reimplement scene graph and add native shadows and PBR materials.
3. **V4.2 TTS and editing:** Align HeyGen/Gemini narration to scene beats; add sound library/mixer and 3D object-label collision checks, auto screenshots at cut boundaries, loudness/mastering; test with 3 entirely different topics to prove real modularity.
4. **V4.3 page pipeline:** automated daily Reel + image + Story using content pillars and source rights; only publish full-production assets that pass QA, and read back actual Facebook Page media links.