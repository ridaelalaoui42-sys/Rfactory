# ClipForge Procedural Visual Style Engine — first production prototype

## What is actually implemented

An **original and runnable** Risograph-inspired visual style pack with 3 separable spot-ink canvases, mechanical registration offsets, stochastic 8 FPS ink imperfections, flecked paper, procedural dot tint, 3 scene compositions, 6 timed narrative beats, scene transitions, synthesized print sounds, HTML scrub/play player, 6-panel storyboard, deterministic frame seeking, 16:9 + 9:16 + 1:1 output, browser/FFmpeg MP4 rendering, FFmpeg optional voiceover ducking and repeatability QA. This implementation does not copy or redistribute the Futurepedia source code or bundled licensed Editor V1 scripts/assets.

The current demonstration script is **illustrative**, not scientifically validated: 97% is a fictional example confidence value and explicitly labeled “DEMO ONLY.” No spoken voiceover is bundled. To add voiceover use `--voiceover local/path.wav` and replace scene text/timings with the approved transcript before publishing. Sound kit events are synthesized locally and contain no third-party audio files.

## Requirements

Python 3.11+, Node.js 20+, `npm install` (Skia Canvas), `numpy`, `ffmpeg`, `ffprobe`. The browser preview needs only a modern browser. The production renderer uses the same JS draw functions with Node/Skia Canvas, so Chromium is not required for MP4 rendering.

## Interactive preview

`npm install && python -m http.server 8765 --directory web` from this folder and open `http://localhost:8765/player.html`.

`http://localhost:8765/storyboard.html` renders the 6-beat storyboard with frames captured from the same drawing implementation.

`player.html?format=vertical` previews portrait framing; `format=square` produces 1:1.

## Example renders

```sh
python scripts/render_style.py --format horizontal --width 960 --fps 24 --output out/riso-landscape.mp4
python scripts/render_style.py --format vertical --width 540 --fps 24 --output out/riso-portrait.mp4
python scripts/render_style.py --format horizontal --width 1280 --fps 30 --voiceover media/voice.wav --output out/voiced.mp4
```

The renderer saves `<name>.poster.png` and `<name>.qa.json`; QA verifies exact pixel-level repeatability between independent native renders. The Node renderer streams JPEG frames to FFmpeg without temporary image sequences. Browser preview and Node native rendering use exactly the same style drawing code.

## Important limitations and next work

- Currently one original hardcoded demonstration script, not a generic storyboard compiler. For personalized stories the beat data, drawing assets and timings still require code changes.
- Only one visual style is executable; existing 18 Atlas-inspired ClipForge presets remain metadata until their runtime code is implemented.
- The reference's complete custom halftone/ink-transfer simulation is not replicated exactly; this is our own lightweight, stylized spot-ink renderer.
- Actual Editor V1 skill scripts are privately installed and intentionally **not** bundled or called. Exported MP4 footage can be imported by existing ClipForge/Editor V1 workflows.
- Needs performance profiling at 1080p, multilingual text layout, gallery integration, and optional GPU print filters before release.
- Do not execute unreviewed remote style source in the authenticated ClipForge app.

## File contract for future styles

A style provides `id`, `duration`, `beats[]`, `draw(ctx,width,height,t)`, and `getSoundEvents()`; renderer requires `window.seek(t)`, `window.DURATION` and `window.scoreSound` in the preview page. Styles share deterministic helpers and offline sound synthesis. Future runtime will use manifests and dynamic style discovery.
