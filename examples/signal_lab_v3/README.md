# CTRL PULSE — SIGNAL LAB V3

**A procedural motion-graphics prototype** built as a reusable, deterministic scene-graph renderer. Unlike a slide editor, it computes every video frame from time, object state and animation curves. It is built with Python, Pillow and NumPy, and uses FFmpeg for efficient video encoding.

## What this prototype actually does

- Six authored scenes across **25.6 seconds**; resolution and FPS configurable (tested at **720×1280 / 60 FPS**).
- Continuous, dynamic elements: spring-driven mascot rig, per-particle morphing, live plotted waveforms, geometric orbital systems, movement along plotted network paths, animated source/evidence masks, type kinetics, procedural logo construction, and scene-specific live frame counters.
- Four custom AI illustrations generated for the brand and separated into independent transparent PNG layers.
- Verified web sources: a NASA Suomi NPP/VIIRS Earth view and NASA supercomputer photography; their original files are **hosted as licensed/credited source assets** and included in the hosted video compositing pass, not redistributed without credits.
- English voiceover generated with HeyGen and **original, programmatically synthesized** musical accents/SFX.
- Exact TTS sentence onset/offset timings used for on-screen sentence captions. Word-level karaoke is not claimed.
- Colors preserve the V2 palette with additional electric blue and rose for richer visual contrast.

## Render the local code-driven visual master

```bash
pip install -r requirements.txt
# Install system ffmpeg and ffprobe.
python signal_lab_v3.py --output signal_lab_v3_silent.mp4 --width 720 --height 1280 --fps 60
```

The local renderer outputs visuals and English captions, not bundled narration. Mix narration plus music in post. The *hosted complete mix* also overlays the actual NASA image assets at 0.1–1.8 seconds and 8.15–10.15 seconds. This asset-first final pass should be done with your hosting/video processing system (Cloudinary in this demonstration). To reproduce exactly, resolve the licensed asset URLs in `asset_manifest.json` and the source tracks under the hosting platform.

## Architecture

- `Shot`: immutable scene/timing declaration.
- `frame(t,w,h)`: pure deterministic per-frame composition.
- `scene0..scene5`: each contains moving/transforming objects with their own space/time transforms.
- `sprite()`: 2.5D scene actors using isolated illustration layers.
- `morph_target()`: deterministic particle topology that converges into the brand C mark.
- `txt()`: cached high-contrast vector-like typography rasterized at the target resolution.
- `CAPTIONS`: timestamped sentence cue boundaries from the recorded TTS.
- `asset_manifest.json`: provenance, Creative Commons/official-media credits, source vs illustration distinction, and rights gate data.

## Quality gate

Before publishing a Reel: verify the final mix contains the intended voiceover, verify sample frames/animation, captions, actual photo references, license source, original illustration designation, text-safe margins and at least one full playback. Rendering a script or still storyboard alone is not publication-ready. **No automatic Facebook publication is enabled by this package.**

## How to extend this beyond a demo

1. Replace authored `scene0..scene5` with declarative JSON nodes for path, sprite, text, photo, masks, particles, lighting and timed camera actions.
2. Add a layout solver and subject-safe bounds to keep source material and captions legible.
3. Add audio-driven keyframe/bpm curves and accurate forced alignment for captions.
4. Add real photo ingestion/downloading with rights, provenance, checksum, author, source URL, crop tracking, and fail-closed licenses.
5. Add motion and readability QA, 9:16 / 16:9 / 1:1 output profiles, automated performance benchmarks, and a reusable theme catalog.
6. Integrate this optional module into the existing ClipForge render job pipeline, preserving its user-approved-source gate.

**This is a working engine prototype and showreel, not a promise that it already matches Claude's full animation stack or replaces Editor V1 end to end.**

**Repository note:** The original AI-generated PNG sprites and rendered MP4 are distributed as a separate downloadable asset package, not checked into source control. A missing sprite layer is skipped automatically by the renderer. Download/copy all four `assets/*.png` next to this module for full fidelity.
