# Motion Studio V4 — VTK scene-graph prototype

**Status: laboratory proof of concept; not publication-ready.** Original physical 3D meshes and event-driven SFX; does **not** yet integrate natural generated TTS, a production asset library, licensed music or final editorial QA. Use the [V4 production standard](../../docs/CTRL_PULSE_MOTION_STUDIO_V4_STANDARD.md) for full acceptance criteria.

Render native vertical Full HD:

```bash
python -m pip install -r prototypes/motion_studio_v4/requirements-extra.txt
sudo apt-get install ffmpeg
python prototypes/motion_studio_v4/studio.py --width 1080 --height 1920 --fps 30 --seconds 16 --output-dir /tmp/rfactory-v4
python prototypes/motion_studio_v4/qa.py /tmp/rfactory-v4/CTRL_PULSE_GPS_3D_MOTION_STUDIO_V4.mp4 /tmp/rfactory-v4/manifest.json
python -m unittest discover -s prototypes/motion_studio_v4 -p 'test_*.py'
```

Uses VTK 9.6 (EGL-capable offscreen rendering on this test host), Pillow for vector-sized Inter text, NumPy for reproducible sound design and FFmpeg for native H.264/AAC. The example scene is a phone/GNSS receiver physical teardown. It is **not Three.js/Remotion** and never represents itself as such.

The current renderer does *not* automatically generate voiceover. V4 is an engineering model for the future production worker, not a replacement for the complete story + TTS workflow. `qa.py` marks it `publishable: false` because the model requires external editorial and audio gates even if technical tests pass. Do not publish this standalone sample as finished CTRL Pulse content.

Use **different story graph and 3D models** for different topics. Never clone this exact phone geometry or title movement as a universal Reel template. No reference-video frame/audio was imported or redistributed.