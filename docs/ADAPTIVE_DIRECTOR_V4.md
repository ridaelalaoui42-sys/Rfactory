# CTRL PULSE — Adaptive Director V4 (working prototype)

Topic-aware procedural animation router and five native-Full-HD animation adapters. The five adapters are **original lightweight implementations inspired by** their upstream open-source skills; this ZIP does **not** vendor the entire upstream renderers, paid APIs or their asset libraries. See `references.json`.

## Why

The source video showcases five independent motion languages. A generic transition template cannot reproduce them. This project has a `choose_style(topic)` router, a shot-level override, a plan validator, five frame-time-driven animation modules, and a native 1080 x 1920 renderer. Rendering is deterministic and seekable. Every module draws real, time-changing objects; there are no still-image slide dissolves.

| Topic / intent | Preferred module | Why |
| --- | --- | --- |
| Software launch, AI tool demo, application UI | Bang | persistent world, camera-aware UI, moving interactions |
| Investigative news, money, data, company reporting | Vox | source-linked clippings, investigative line work, temporal evidence |
| History, science, art, ecology | Huashu | artwork with changing internal motifs and object motion |
| Tutorials, algorithms, circuits, mechanisms | Drawing | precise stroke-by-stroke procedural illustrations |
| Storytelling, humor, habits, psychology | Stickman | pose graph and semantic gestures instead of static figures |

**Shared brand:** forest ink `#152723`, warm paper `#F2EEDD`, orange `#F36642`, citron `#D8EE6D`, sage `#A9B4A8`. Blue and rose are secondary data highlights, not default backgrounds.

## Output restrictions (hard gates)

- Videos are **English**, native portrait **1080×1920 or larger**. No 720p, no fake upscales.
- **No on-video subtitles or closed/open captions**; original diagram labels and source identifiers are allowed.
- Voiceover may be mixed from an approved external TTS provider via FFmpeg. The sample source timing references a HeyGen English voice; the source code does not embed copyrighted audio or credentials.
- Source evidence must be authentic; editorial art is marked as illustrative rather than passed off as documentation.
- Each publication needs rights evidence, media manifest, and final QA before sending to Metricool/Upload-Post. This preview does not auto-post.

## Try it

```bash
pip install Pillow
python -m adaptive_director.render --out output/v4_motion_test.mp4 --fps 24
python -m unittest discover -s tests -v
python -m adaptive_director.demo_plan --topic "How do AI coding tools work?"
python -m adaptive_director.render --topic "AI software launch" --out output/bang_example.mp4 --seconds 5
python -m adaptive_director.render --style huashu --out output/art_example.mp4 --seconds 5
python -m adaptive_director.render --plan output/example_plan.json --out output/mixed_modules.mp4
python -m adaptive_director.demo_plan --topic "NVIDIA shares after regulatory news" --style vox
```

Generated sample contains scenes: intro, Bang product UI, Vox evidence table, Huashu living artwork, Drawing traced circuitry, Stickman interaction, router, outro. **These demonstrate the local adapters, not the full functionality of the upstream skills.**

## Production integration path

1. `topic -> brief / research and evidence manifest` (rights checked)
2. `select_primary_style(topic, reference, editor_override)`; router stores score and rationale
3. `shot planner -> active scene grammar, purpose, assets, intervals, camera/motion` (one main art direction, short module variations)
4. `generate/look-dev -> native-layer assets + seeded procedural geometry` (upstream official skills can be executed here by dedicated adapters)
5. `voice synthesis -> measured narration timing` (audio is the master clock)
6. `compile scene graph -> deterministic frame(t)`; async per-shot CPU/GPU workers
7. `review -> contact sheet / motion metrics / text legibility / original asset provenance`;
8. `final 1080x1920+ with narration/SFX; no subtitles`; then publish.

Scene plan can override a single beat's style while retaining the branded colors. A hybrid mixing disparate art styles with no rationale is a QA failure; the primary selected style owns the video and secondary modules are overlays or meaningful brief exceptions.

## Next milestone

Create mature adapters that run upstream Bang Motion browser/GSAP player, Huashu JS Canvas grammars, full Claude procedural drawing recipes, Vox's keyframe pipeline (requires Atlas Cloud API + budget) and Stickman mode B scripts without copying entire repos or infringing their assets. These integrations are **not** falsely claimed here; local proof-of-concept shaders and procedural drawings run today.