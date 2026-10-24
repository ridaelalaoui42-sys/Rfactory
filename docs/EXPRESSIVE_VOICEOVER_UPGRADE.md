# Rfactory expressive voiceover upgrade

This module adds a **real Gemini 3.8 TTS pipeline** to the three new puzzle Reels (Dino, Bunny, Monkey), including three voice identities, sentence-by-sentence emotion and pacing, soft game-show backing music, five synchronized cues, and unchanged video frames.

## Three modes and provenance
- `gemini` (REAL neural audio): authenticated Gemini 3.8 Flash-Lite TTS. Only available with `GEMINI_API_KEY` / `GOOGLE_API_KEY`, Internet access, a working model entitlement and an explicit `--allow-paid-tts` flag. No automatic offline substitute.
- `wav` (provider-agnostic): load three externally generated/recorded WAV segments per Reel. Audio may be neural or not; code does **not assert neural provenance** for externally supplied media.
- `offline-preview`: a local eSpeak voice with per-line prosody, speech-aware audio ducking, and polished music/cues. **Not neural speech.** Useful for free previews and CI tests.

## New narration
| Reel | Voice | Delivery |
|---|---|---|
| Dino Donut Dash | Puck | Surprised explorer, curious challenge |
| Bunny Ice Cream Mix-Up | Aoede | Gentle surprise, encouragement |
| Monkey Burger Pop | Kore | Energetic and cheeky game-show host |

Each narration has three brief phrases placed at deliberate points along the existing video. The actual puzzle animation is untouched. FFmpeg streams the H.264 video **without re-encoding** and the manifest compares SHA-256 hashes of original and resulting video streams. Five exact crossing frames remain unchanged.

## Generate genuine neural versions

Use an authenticated network-connected machine or a manually triggered GitHub Actions workflow with a protected secret. Install `requirements-ai.txt` and `ffmpeg`; render the three base clips as documented in `docs/THREE_NARRATED_REELS.md`. Then run:

```bash
# GEMINI_API_KEY must be configured in the shell or in GitHub Actions Secrets.
python -m scripts.upgrade_social_voiceovers \
  --provider gemini \
  --allow-paid-tts \
  --model gemini-3.8-flash-lite-tts \
  --input-dir storage/renders/social_voiceovers \
  --output-dir storage/renders/social_neural
```

This calls the Gemini API for nine small speech segments and may incur usage charges. It fails if the API key, network or valid speech output is missing. Do not commit keys or WAVs of uncertain provenance. Gemini narration is identified as such **only after valid model-produced WAV bytes are returned**.

The optional workflow `neural-voiceover-production.yml` runs only on manual dispatch after checking a GitHub secret named `GEMINI_API_KEY` and explicit payment approval.

To preview the best available local version without any provider credentials:

```bash
python -m scripts.upgrade_social_voiceovers --provider offline-preview
```

For audio already generated in a connected voice service, save the nine WAVs as `04_dino_donut_dash_01.wav`, `..._02.wav`, `..._03.wav`, etc., and use `--provider wav --voice-dir /path/to/voices`.

## Quality safeguards
- No duplicated fake narration, no silent reversion from paid neural mode to eSpeak.
- No cropping words to fit: safe speed adjustment only within a 28% factor; otherwise reject.
- Source H.264 frames and five pixel-exact puzzle crossings unchanged.
- Voice speech balanced over original-style music with audio ducking.
- Machine-readable provenance/clip hashes per output Reel.
- AI voice disclosure should accompany publishing (e.g., `AI-generated voiceover` in social metadata).
