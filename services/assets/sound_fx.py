"""
Royalty-Free Procedural Sound Effects & Background Music Synthesizer.
Generates 44.1kHz 16-bit stereo WAV files timed precisely to puzzle motion & alignment frames.
"""
from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import List

import numpy as np


def synthesize_puzzle_audio_wav(
    output_wav_path: Path | str,
    duration_sec: float = 15.0,
    alignment_timestamps_sec: Optional[List[float]] = None,
    enable_music: bool = True,
    seed: int = 42,
    sample_rate: int = 44100,
) -> Path:
    """
    Synthesizes a clean stereo WAV audio track for a puzzle Reel:
    - Subtle warm marimba-like rhythmic pulse (when enable_music=True)
    - Crisp woodblock tick every 0.5s to build visual-matching anticipation
    - Harmonic two-tone chime right at each alignment timestamp (`alignment_timestamps_sec`)
    """
    out_path = Path(output_wav_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(round(duration_sec * sample_rate))
    t = np.linspace(0.0, duration_sec, n_samples, endpoint=False, dtype=np.float32)

    left = np.zeros(n_samples, dtype=np.float32)
    right = np.zeros(n_samples, dtype=np.float32)

    if enable_music:
        # Gentle pentatonic arpeggio loop (C5, D5, E5, G5, A5)
        freqs = [523.25, 587.33, 659.25, 783.99, 880.00, 783.99, 659.25, 587.33]
        step_sec = 0.375
        total_steps = int(duration_sec / step_sec)
        for idx in range(total_steps):
            start_i = int(idx * step_sec * sample_rate)
            end_i = min(n_samples, int((idx + 1) * step_sec * sample_rate))
            if start_i >= n_samples:
                break
            seg_t = np.arange(end_i - start_i, dtype=np.float32) / sample_rate
            freq = freqs[(idx + seed) % len(freqs)]
            env = np.exp(-seg_t * 9.5) * 0.08
            tone = np.sin(2.0 * math.pi * freq * seg_t) * env
            pan = 0.6 if idx % 2 == 0 else 0.4
            left[start_i:end_i] += tone * pan
            right[start_i:end_i] += tone * (1.0 - pan)

    # Soft rhythmic woodblock tick every 0.5 seconds
    tick_interval = 0.5
    n_ticks = int(duration_sec / tick_interval)
    for k in range(n_ticks):
        start_i = int(k * tick_interval * sample_rate)
        tick_len = min(int(0.045 * sample_rate), n_samples - start_i)
        if tick_len <= 0:
            break
        seg_t = np.arange(tick_len, dtype=np.float32) / sample_rate
        env = np.exp(-seg_t * 85.0) * 0.14
        tick_wave = np.sin(2.0 * math.pi * 1120.0 * seg_t) * env
        left[start_i : start_i + tick_len] += tick_wave
        right[start_i : start_i + tick_len] += tick_wave

    # Bright alignment bell chime at each exact alignment window
    for align_sec in alignment_timestamps_sec or []:
        start_i = int(max(0.0, align_sec) * sample_rate)
        chime_len = min(int(0.32 * sample_rate), n_samples - start_i)
        if chime_len <= 0:
            continue
        seg_t = np.arange(chime_len, dtype=np.float32) / sample_rate
        env = np.exp(-seg_t * 11.0) * 0.24
        chime = (
            0.65 * np.sin(2.0 * math.pi * 1046.50 * seg_t)
            + 0.35 * np.sin(2.0 * math.pi * 1567.98 * seg_t)
        ) * env
        left[start_i : start_i + chime_len] += chime
        right[start_i : start_i + chime_len] += chime

    # Normalize & convert to 16-bit PCM stereo
    stereo = np.stack([np.clip(left, -0.95, 0.95), np.clip(right, -0.95, 0.95)], axis=1)
    pcm16 = (stereo * 32767.0).astype(np.int16)

    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())

    return out_path
