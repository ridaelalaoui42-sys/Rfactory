"""
Deterministic 1080x1920 @ 30fps Procedural Animation Engine for Animal & Celebrity Face Puzzle Reels Factory.
Implements 4 production templates:
  - Template A: OUTLINE_MATCH (Reference 1 reconstruction with original artwork, royal-blue outlines, and 3-8 patterned objects)
  - Template B: MISSING_PIECE_SLIDE (Reference 2 reconstruction with pixel-perfect vertical missing-piece slice restoration)
  - Template C: FACE_FEATURE_SLIDE (Celebrity & People horizontal facial-feature band slide into high-contrast cutout, MAD == 0.0)
  - Template D: FACE_SPLIT_3BAND (Celebrity & People 3-Band Face Split puzzle with opposing horizontal phase oscillation, MAD == 0.0)
Uses uint16 vectorized alpha compositing + cycle-level FFmpeg stream looping with `-threads 2 -loglevel error`
to render full 15s 1080x1920 @ 30fps H.264/AAC MP4s in ~2.5 seconds.
"""
from __future__ import annotations

import hashlib
import json
import math
import uuid
import shutil
import subprocess
import time
from dataclasses import dataclass
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from services.assets.segmentation import (
    extract_horizontal_slice_bundle,
    extract_missing_piece_bundle,
    extract_three_band_face_bundle,
    generate_outline_silhouette_rgba,
)
from services.assets.sound_fx import synthesize_puzzle_audio_wav
from services.engine.motion_profiles import motion_pose, continuous_motion_pose, transformed_sprite, MOTION_PROFILES, MotionPose
from services.engine.snap_timeline import build_snap_timeline, build_crossing_timeline
from services.engine.puzzle_geometry import GEOMETRIES, cut_exact_fragment
from services.assets.face_cutout_engine import FACE_MODES, face_cutout
from services.assets.face_cutout_engine import FACE_MODES, face_cutout
from services.assets.fit_validator import validate_face_bundle
from services.assets.asset_packager import package_face_bundle


@dataclass
class RenderConfig:
    job_id: str
    template_id: str
    species: str
    asset_path: str = ""  # storage/assets-relative original AI sprite (optional)
    narration_wav: str = ""  # generated TTS WAV; server-side path only
    seed: int = 1001
    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration_sec: float = 15.0
    background_hex: str = "#F2FAFF"
    outline_color_rgba: Tuple[int, int, int, int] = (24, 58, 245, 255)
    placeholder_color_rgba: Tuple[int, int, int, int] = (255, 232, 0, 255)
    object_count: int = 5
    offset_distance_px: int = 165
    ease_type: str = "easeInOutSine"
    cycles: int = 5
    hold_ratio: float = 0.14
    slice_x_ratio: Tuple[float, float] = (0.27, 0.51)
    slice_y_ratio: Tuple[float, float] = (0.30, 0.54)
    direction: str = "top_to_bottom"
    enable_audio: bool = True
    safe_area_guides: bool = False
    motion_profile: str = "slide"
    motion_intensity: float = 1.0
    randomize_snap_timing: bool = True
    continuous_motion: bool = True  # exact matches are single crossing frames; no freeze
    sound_mode: str = "match_only"  # sound at exact fit; no ticking or music
    snap_count: int = 0  # 0 = follow cycles; positive sets exact number of solves
    puzzle_geometry: str = "legacy"  # optional new organic/jigsaw/ring/etc cutouts
    face_mode: str = ""  # required when template_id=FACE_CANONICAL
    face_subject_type: str = "animal"
    face_bbox_norm: tuple[float,float,float,float] | None = None

    face_mode: str = ""  # CANONICAL_FACE: meaningful animal/human feature fragments
    subject_type: str = "animal"  # animal, human or portrait
    face_bbox_norm: tuple[float,float,float,float] | None = None


@dataclass
class RenderArtifact:
    job_id: str
    template_id: str
    species: str
    seed: int
    mp4_path: str
    thumbnail_path: str
    alignment_frame_png_path: str
    width: int
    height: int
    fps: int
    duration_sec: float
    total_frames: int
    alignment_frames: List[int]
    alignment_timestamps_sec: List[float]
    pixel_match_mad: float
    render_time_sec: float
    sha256: str


class BoundedFrameCache(OrderedDict):
    """Prevent multi-gigabyte frame cache when verifying entire timelines."""
    def __setitem__(self, key, value):
        if key in self:
            del self[key]
        super().__setitem__(key, value)
        while len(self) > 5:
            self.popitem(last=False)


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return (242, 250, 255)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def alpha_composite_inplace(canvas_rgb: np.ndarray, sprite_rgba: np.ndarray, top_left_xy: Tuple[int, int]) -> None:
    ch, cw = canvas_rgb.shape[:2]
    sh, sw = sprite_rgba.shape[:2]
    x, y = int(round(top_left_xy[0])), int(round(top_left_xy[1]))

    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(cw, x + sw)
    y2 = min(ch, y + sh)
    if x1 >= x2 or y1 >= y2:
        return

    sx1 = x1 - x
    sy1 = y1 - y
    sx2 = sx1 + (x2 - x1)
    sy2 = sy1 + (y2 - y1)

    sub_sprite = sprite_rgba[sy1:sy2, sx1:sx2]
    alpha = sub_sprite[:, :, 3:4].astype(np.uint16)
    inv_alpha = 255 - alpha

    roi = canvas_rgb[y1:y2, x1:x2].astype(np.uint16)
    blended = (sub_sprite[:, :, :3].astype(np.uint16) * alpha + roi * inv_alpha) // 255
    canvas_rgb[y1:y2, x1:x2] = blended.astype(np.uint8)


def draw_motion_sprite(canvas_rgb: np.ndarray, sprite_rgba: np.ndarray,
                       target_xy: Tuple[int, int], pose: MotionPose) -> None:
    """Affine motion with a lossless, interpolation-free identity snap."""
    transformed, (ox, oy) = transformed_sprite(sprite_rgba, pose)
    alpha_composite_inplace(canvas_rgb, transformed,
                            (target_xy[0] + pose.dx + ox, target_xy[1] + pose.dy + oy))


def evaluate_periodic_displacement(
    phase_0_to_1: float,
    hold_ratio: float = 0.14,
    ease_type: str = "easeInOutSine",
) -> float:
    p = phase_0_to_1 % 1.0
    half_hold = min(0.18, max(0.02, hold_ratio * 0.5))

    if p < half_hold or p > (1.0 - half_hold):
        return 0.0
    if abs(p - 0.5) < half_hold:
        return 0.0

    if p < 0.5:
        u = (p - half_hold) / (0.5 - 2.0 * half_hold)
        return math.sin(u * math.pi)
    else:
        u = (p - (0.5 + half_hold)) / (0.5 - 2.0 * half_hold)
        return -math.sin(u * math.pi)


class PuzzleVideoRenderer:
    def __init__(self, assets_root: Path, outputs_root: Path) -> None:
        self.assets_root = Path(assets_root)
        self.outputs_root = Path(outputs_root)
        self.outputs_root.mkdir(parents=True, exist_ok=True)

    def _compute_egg_slot_positions(self, object_count: int, width: int = 1080) -> List[Tuple[int, int]]:
        cx = width // 2
        if object_count == 5:
            return [
                (cx, 935),
                (cx, 1210),
                (cx - 215, 1485),
                (cx, 1495),
                (cx + 215, 1485),
            ]
        elif object_count == 3:
            return [(cx, 960), (cx - 190, 1340), (cx + 190, 1340)]
        elif object_count == 4:
            return [(cx - 175, 1020), (cx + 175, 1020), (cx - 175, 1390), (cx + 175, 1390)]
        else:
            slots: List[Tuple[int, int]] = []
            cols = 3
            for i in range(object_count):
                r = i // cols
                c = i % cols
                slots.append((cx + (c - 1) * 215, 940 + r * 275))
            return slots

    def render_video(
        self,
        config: RenderConfig,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> RenderArtifact:
        start_t = time.time()
        if config.motion_profile not in MOTION_PROFILES:
            raise ValueError("Unsupported motion profile: " + config.motion_profile)
        if config.puzzle_geometry != "legacy" and config.puzzle_geometry not in GEOMETRIES:
            raise ValueError("Unsupported puzzle geometry: " + config.puzzle_geometry)
        if config.template_id == "FACE_CANONICAL":
            if config.face_mode not in FACE_MODES:
                raise ValueError("Select a real face-cutout mode")
            if config.face_subject_type not in {"animal", "human", "portrait"}:
                raise ValueError("Subject type must identify the actual face")
            if config.face_bbox_norm is None:
                raise ValueError("A reviewed face rectangle is required for face-puzzle production")
        if config.puzzle_geometry != "legacy" and config.template_id != "MISSING_PIECE_SLIDE":
            raise ValueError("Custom geometry currently requires MISSING_PIECE_SLIDE template")
        if config.template_id == "CANONICAL_FACE":
            if config.face_mode not in FACE_MODES:
                raise ValueError("CANONICAL_FACE requires a supported face mode")
            if config.subject_type not in {"animal","human","portrait"}:
                raise ValueError("Unsupported face subject type")
        if config.sound_mode not in {"match_only", "music_and_ticks"}:
            raise ValueError("Unsupported sound mode")
        if not 0.0 <= config.motion_intensity <= 2.0:
            raise ValueError("motion_intensity must be 0 to 2")
        w, h = config.width, config.height
        fps = config.fps
        total_frames = int(round(config.duration_sec * fps))
        cycles = max(1, config.cycles)
        # Auto mode adapts to short preview renders: each pass needs at least
        # ~0.55s, but explicit snap_count requests must pass validation.
        min_pass_frames = max(12, int(round(0.55 * fps)))
        event_count = (
            config.snap_count
            if config.snap_count
            else min(cycles, max(1, total_frames // min_pass_frames))
        )
        timeline = (
            (build_crossing_timeline if config.continuous_motion else build_snap_timeline)(
                total_frames=total_frames, fps=fps, count=event_count,
                seed=config.seed, hold_ratio=config.hold_ratio,
            )
            if config.randomize_snap_timing else None
        )
        # Distinguish the new continuous trajectories from legacy pause
        # animations without changing the old testable helper functions.
        def _resolve_pose(*args, **kwargs):
            provider = continuous_motion_pose if config.continuous_motion else motion_pose
            return provider(*args, **kwargs)
        # Irregular windows require a unique full-length render rather than
        # looping the same short movie through FFmpeg.
        cycle_frames = total_frames if timeline else max(15, int(round(total_frames / float(cycles))))
        def phase_for_frame(idx: int) -> float:
            return timeline.phase(idx) if timeline is not None else idx / float(cycle_frames)
        bg_rgb = hex_to_rgb(config.background_hex)

        job_dir = self.outputs_root / config.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        mp4_path = job_dir / f"{config.job_id}.mp4"
        # Per-render scratch directory prevents collisions during concurrent jobs.
        scratch_dir = job_dir / ("scratch_" + uuid.uuid4().hex)
        scratch_dir.mkdir(parents=True, exist_ok=True)
        cycle_mp4_path = scratch_dir / f"{config.job_id}_cycle.mp4"
        thumb_path = job_dir / f"{config.job_id}_thumb.png"
        align_png_path = job_dir / f"{config.job_id}_aligned.png"
        wav_path = scratch_dir / f"{config.job_id}_audio.wav"

        if config.asset_path:
            # Only allow assets beneath the trusted private asset library;
            # never interpret arbitrary client-supplied absolute file paths.
            animal_png = (self.assets_root / config.asset_path).resolve()
            if not animal_png.is_relative_to(self.assets_root.resolve()) or animal_png.suffix.lower() != ".png":
                raise ValueError("Invalid AI subject asset path")
            if not animal_png.is_file():
                raise FileNotFoundError("Requested AI subject asset is missing")
        else:
            animal_png = self.assets_root / "animals" / f"{config.species}.png"
            if not animal_png.exists():
                face_png = self.assets_root / "faces" / f"{config.species}.png"
                if face_png.exists():
                    animal_png = face_png
                else:
                    raise FileNotFoundError(f"Subject asset not found: {animal_png}")
        raw_animal_rgba = np.array(Image.open(animal_png).convert("RGBA"))

        alignment_frames: List[int] = []
        pixel_match_mad = 0.0

        static_base_rgb = np.full((h, w, 3), bg_rgb, dtype=np.uint8)
        yy = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
        xx = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
        vignette = np.clip(1.0 - 0.035 * (xx * xx + yy * yy), 0.94, 1.0)[:, :, None]
        static_base_rgb = (static_base_rgb.astype(np.float32) * vignette).astype(np.uint8)

        frame_cache: Dict[int, Tuple[bytes, np.ndarray]] = BoundedFrameCache()

        if config.template_id == "OUTLINE_MATCH":
            animal_w, animal_h = 720, 640
            animal_rgba = cv2.resize(raw_animal_rgba, (animal_w, animal_h), interpolation=cv2.INTER_LANCZOS4)
            animal_outline_rgba = generate_outline_silhouette_rgba(
                animal_rgba,
                outline_color=config.outline_color_rgba,
                outline_width=8,
            )
            animal_target_x = (w - animal_w) // 2
            animal_target_y = 165

            alpha_composite_inplace(static_base_rgb, animal_outline_rgba, (animal_target_x, animal_target_y))

            speckled_default = self.assets_root / "objects" / "speckled_egg_1.png"
            egg_names = ["speckled_egg_1.png", "speckled_egg_2.png", "speckled_egg_3.png", "golden_egg_1.png", "sea_egg_1.png"]
            egg_files = [self.assets_root / "objects" / n for n in egg_names if (self.assets_root / "objects" / n).exists()]
            if not egg_files:
                raise RuntimeError("No egg/object assets found in assets_root/objects")
            chosen_egg = speckled_default if (config.seed == 1001 and speckled_default.exists()) else egg_files[config.seed % len(egg_files)]
            egg_rgba_raw = np.array(Image.open(chosen_egg).convert("RGBA"))

            egg_slots = self._compute_egg_slot_positions(config.object_count, w)
            egg_sprites: List[Tuple[np.ndarray, int, int, float]] = []
            for idx, (slot_cx, slot_cy) in enumerate(egg_slots):
                scale_factor = 1.06 if idx in (0, 1, 3) else 0.88
                ew = int(round(205 * scale_factor))
                eh = int(round(252 * scale_factor))
                e_rgba = cv2.resize(egg_rgba_raw, (ew, eh), interpolation=cv2.INTER_LANCZOS4)
                e_outline = generate_outline_silhouette_rgba(
                    e_rgba,
                    outline_color=config.outline_color_rgba,
                    outline_width=7,
                )
                ex = slot_cx - ew // 2
                ey = slot_cy - eh // 2
                alpha_composite_inplace(static_base_rgb, e_outline, (ex, ey))
                amp_factor = 1.0 + 0.08 * ((idx + config.seed) % 3 - 1)
                egg_sprites.append((e_rgba, ex, ey, amp_factor))

            def get_cycle_frame(c_idx: int) -> Tuple[bytes, np.ndarray, bool]:
                phase = phase_for_frame(c_idx)
                if config.motion_profile != "slide" or timeline is not None:
                    pose = _resolve_pose(config.motion_profile, phase, config.offset_distance_px,
                                       config.hold_ratio, config.seed, config.motion_intensity,
                                       "horizontal")
                    if c_idx in frame_cache:
                        encoded, cached = frame_cache[c_idx]
                        return encoded, cached, pose.locked
                    frame = static_base_rgb.copy()
                    for idx, (e_rgba, ex, ey, amp_f) in enumerate(egg_sprites):
                        egg_pose = _resolve_pose(config.motion_profile, phase,
                                               config.offset_distance_px * amp_f,
                                               config.hold_ratio, config.seed + idx + 1,
                                               config.motion_intensity, "horizontal")
                        draw_motion_sprite(frame, e_rgba, (ex, ey), egg_pose)
                    draw_motion_sprite(frame, animal_rgba,
                                       (animal_target_x, animal_target_y), pose)
                    encoded = frame.tobytes()
                    frame_cache[c_idx] = (encoded, frame)
                    return encoded, frame, pose.locked
                disp = evaluate_periodic_displacement(phase, hold_ratio=config.hold_ratio, ease_type=config.ease_type)
                animal_dx = int(round((disp * config.offset_distance_px) / 12.0)) * 12
                is_aligned = animal_dx == 0

                if animal_dx in frame_cache:
                    b_data, f_arr = frame_cache[animal_dx]
                    return b_data, f_arr, is_aligned

                frame = static_base_rgb.copy()
                for e_rgba, ex, ey, amp_f in egg_sprites:
                    dx = int(round(animal_dx * amp_f))
                    alpha_composite_inplace(frame, e_rgba, (ex + dx, ey))
                alpha_composite_inplace(frame, animal_rgba, (animal_target_x + animal_dx, animal_target_y))
                b_data = frame.tobytes()
                frame_cache[animal_dx] = (b_data, frame)
                return b_data, frame, is_aligned

        elif config.template_id == "CANONICAL_FACE":
            # One approved, clean source image drives the plate, positive pieces
            # and the exact solved state. Never use an AI-drawn cutout collage.
            face_w, face_h = 860, 860
            source_rgba = cv2.resize(raw_animal_rgba, (face_w, face_h),
                                     interpolation=cv2.INTER_LANCZOS4)
            face_bundle = face_cutout(
                source_rgba, config.face_mode, subject_type=config.subject_type,
                seed=config.seed, face_bbox_norm=config.face_bbox_norm,
            )
            face_qa = validate_face_bundle(face_bundle)
            pixel_match_mad = face_qa["exact_raw_rgba_mad"]
            face_x, face_y = (w-face_w)//2, (h-face_h)//2-40
            alpha_composite_inplace(
                static_base_rgb, face_bundle.hole_plate_rgba,
                (face_x,face_y),
            )
            package_face_bundle(
                face_bundle, job_dir/"cutout_assets",
                provenance="approved_source:" + str(config.asset_path or config.species),
                approved=False,
            )
            # Multi-piece fragments have independent spatial paths. All
            # fragments cross identity on precisely the same single frame.
            # No status lights, pauses, solve overlay or victory animation.
            def get_cycle_frame(c_idx: int) -> Tuple[bytes,np.ndarray,bool]:
                phase = phase_for_frame(c_idx)
                main_pose = _resolve_pose(
                    config.motion_profile, phase,
                    max(200,config.offset_distance_px*1.4),
                    config.hold_ratio,config.seed,config.motion_intensity,
                    "horizontal",
                )
                if c_idx in frame_cache:
                    data, frame = frame_cache[c_idx]
                    return data,frame,main_pose.locked
                frame=static_base_rgb.copy()
                for idx, piece in enumerate(face_bundle.pieces):
                    x,y,_,_=piece.bounds_xywh
                    pose = _resolve_pose(
                        config.motion_profile,phase,
                        max(200,config.offset_distance_px*(1.3+idx*.17)),
                        config.hold_ratio,config.seed+idx*37,
                        config.motion_intensity,
                        "horizontal" if idx%2==0 else "vertical",
                    )
                    draw_motion_sprite(
                        frame,piece.piece_rgba,
                        (face_x+x,face_y+y),pose,
                    )
                data=frame.tobytes()
                frame_cache[c_idx]=(data,frame)
                return data,frame,main_pose.locked

        elif config.template_id == "FACE_CANONICAL":
            # All fragments and the negative plate are extracted from ONE
            # accepted, complete image; generative models do not draw holes.
            portrait_w, portrait_h = 860, 860
            subject_rgba = cv2.resize(
                raw_animal_rgba, (portrait_w, portrait_h), interpolation=cv2.INTER_LANCZOS4
            )
            bundle = face_cutout(
                subject_rgba, config.face_mode,
                subject_type=config.face_subject_type, seed=config.seed,
                face_bbox_norm=config.face_bbox_norm,
            )
            from services.assets.fit_validator import validate_face_bundle
            face_qa = validate_face_bundle(bundle)
            pixel_match_mad = face_qa["exact_raw_rgba_mad"]
            subject_x = (w - portrait_w)//2
            subject_y = (h - portrait_h)//2 - 40
            alpha_composite_inplace(
                static_base_rgb, bundle.hole_plate_rgba, (subject_x,subject_y)
            )
            parts = [
                (p.piece_rgba, subject_x+p.bounds_xywh[0],
                 subject_y+p.bounds_xywh[1])
                for p in bundle.pieces
            ]

            def get_cycle_frame(c_idx: int) -> Tuple[bytes, np.ndarray, bool]:
                phase = phase_for_frame(c_idx)
                main_pose = _resolve_pose(
                    config.motion_profile, phase, max(220,config.offset_distance_px*1.8),
                    config.hold_ratio, config.seed, config.motion_intensity,"horizontal",
                )
                if c_idx in frame_cache:
                    data, cached = frame_cache[c_idx]
                    return data,cached,main_pose.locked
                frame = static_base_rgb.copy()
                for idx,(image,tx,ty) in enumerate(parts):
                    # Independent piece movement, simultaneously exact only at
                    # the true crossing frame, no visual solve indication.
                    pose = _resolve_pose(
                        config.motion_profile, phase,
                        max(185,config.offset_distance_px*(1.65+idx*.2)),
                        config.hold_ratio, config.seed+idx*7,
                        config.motion_intensity,"horizontal",
                    )
                    draw_motion_sprite(frame,image,(tx,ty),pose)
                data=frame.tobytes()
                frame_cache[c_idx]=(data,frame)
                return data,frame,main_pose.locked

        elif config.template_id == "MISSING_PIECE_SLIDE":
            animal_w, animal_h = 860, 860
            animal_rgba = cv2.resize(raw_animal_rgba, (animal_w, animal_h), interpolation=cv2.INTER_LANCZOS4)
            animal_x = (w - animal_w) // 2
            animal_y = (h - animal_h) // 2 - 40

            if config.puzzle_geometry == "legacy":
                mp_bundle = extract_missing_piece_bundle(
                    animal_rgba,
                    slice_x_ratio=config.slice_x_ratio,
                    placeholder_color=config.placeholder_color_rgba,
                )
                pixel_match_mad = mp_bundle.pixel_match_mad
                base_rgba = mp_bundle.base_with_placeholder_rgba
                piece_rgba = mp_bundle.extracted_piece_rgba
                target_px = animal_x + mp_bundle.alignment_target_xy[0]
                target_py = animal_y + mp_bundle.alignment_target_xy[1]
            else:
                # Canonical texture is sampled ONLY once, from the image that
                # also defines the negative space. This is true jigsaw geometry,
                # not an independently generated visual lookalike.
                fragment_w = int(round(animal_w * 0.38))
                fragment_h = int(round(animal_h * 0.29))
                fragment_x = int(round(animal_w * 0.31))
                fragment_y = int(round(animal_h * 0.33))
                cut = cut_exact_fragment(
                    animal_rgba,
                    (fragment_x, fragment_y, fragment_w, fragment_h),
                    geometry=config.puzzle_geometry,
                    seed=config.seed,
                )
                pixel_match_mad = 0.0
                base_rgba = cut.base_rgba
                piece_rgba = cut.piece_rgba
                target_px = animal_x + fragment_x
                target_py = animal_y + fragment_y

            alpha_composite_inplace(static_base_rgb, base_rgba, (animal_x, animal_y))
            ph, _ = piece_rgba.shape[:2]

            def get_cycle_frame(c_idx: int) -> Tuple[bytes, np.ndarray, bool]:
                cycle_p = phase_for_frame(c_idx)
                if config.motion_profile != "slide" or timeline is not None:
                    pose = _resolve_pose(
                        config.motion_profile, cycle_p,
                        max(220, config.offset_distance_px * 1.9),
                        config.hold_ratio, config.seed, config.motion_intensity,
                        "vertical",
                    )
                    if c_idx in frame_cache:
                        encoded, cached = frame_cache[c_idx]
                        return encoded, cached, pose.locked
                    frame = static_base_rgb.copy()
                    draw_motion_sprite(frame, piece_rgba, (target_px, target_py), pose)
                    encoded = frame.tobytes()
                    frame_cache[c_idx] = (encoded, frame)
                    return encoded, frame, pose.locked
                hold_w = config.hold_ratio * 0.5

                if abs(cycle_p - 0.5) <= hold_w:
                    norm_offset = 0.0
                    is_aligned = True
                elif cycle_p < 0.5 - hold_w:
                    u = cycle_p / (0.5 - hold_w)
                    norm_offset = -1.0 + math.sin(u * math.pi * 0.5)
                    is_aligned = False
                else:
                    u = (cycle_p - (0.5 + hold_w)) / (0.5 - hold_w)
                    norm_offset = 1.0 - math.cos(u * math.pi * 0.5)
                    is_aligned = False

                if config.direction == "bottom_to_top":
                    norm_offset = -norm_offset

                travel_span = h // 2 + ph // 2 + 120
                cur_py = target_py if is_aligned else (int(round((target_py + norm_offset * travel_span) / 12.0)) * 12)

                if cur_py in frame_cache:
                    b_data, f_arr = frame_cache[cur_py]
                    return b_data, f_arr, is_aligned

                frame = static_base_rgb.copy()
                alpha_composite_inplace(frame, piece_rgba, (target_px, cur_py))
                b_data = frame.tobytes()
                frame_cache[cur_py] = (b_data, frame)
                return b_data, frame, is_aligned

        elif config.template_id == "FACE_FEATURE_SLIDE":
            # Template C: Horizontal facial-feature band (eyes & nose bridge) sliding across portrait
            face_w, face_h = 860, 860
            face_rgba = cv2.resize(raw_animal_rgba, (face_w, face_h), interpolation=cv2.INTER_LANCZOS4)
            horiz_bundle = extract_horizontal_slice_bundle(
                face_rgba,
                slice_y_ratio=config.slice_y_ratio,
                placeholder_color=config.placeholder_color_rgba,
            )
            pixel_match_mad = horiz_bundle.pixel_match_mad

            face_x = (w - face_w) // 2
            face_y = (h - face_h) // 2 - 40

            alpha_composite_inplace(static_base_rgb, horiz_bundle.base_with_placeholder_rgba, (face_x, face_y))

            piece_rgba = horiz_bundle.extracted_piece_rgba
            _, pw = piece_rgba.shape[:2]
            target_px = face_x + horiz_bundle.alignment_target_xy[0]
            target_py = face_y + horiz_bundle.alignment_target_xy[1]

            def get_cycle_frame(c_idx: int) -> Tuple[bytes, np.ndarray, bool]:
                cycle_p = phase_for_frame(c_idx)
                if config.motion_profile != "slide" or timeline is not None:
                    pose = _resolve_pose(
                        config.motion_profile, cycle_p,
                        max(220, config.offset_distance_px * 1.9),
                        config.hold_ratio, config.seed, config.motion_intensity,
                        "horizontal",
                    )
                    if c_idx in frame_cache:
                        encoded, cached = frame_cache[c_idx]
                        return encoded, cached, pose.locked
                    frame = static_base_rgb.copy()
                    draw_motion_sprite(frame, piece_rgba, (target_px, target_py), pose)
                    encoded = frame.tobytes()
                    frame_cache[c_idx] = (encoded, frame)
                    return encoded, frame, pose.locked
                hold_w = config.hold_ratio * 0.5

                if abs(cycle_p - 0.5) <= hold_w:
                    norm_offset = 0.0
                    is_aligned = True
                elif cycle_p < 0.5 - hold_w:
                    u = cycle_p / (0.5 - hold_w)
                    norm_offset = -1.0 + math.sin(u * math.pi * 0.5)
                    is_aligned = False
                else:
                    u = (cycle_p - (0.5 + hold_w)) / (0.5 - hold_w)
                    norm_offset = 1.0 - math.cos(u * math.pi * 0.5)
                    is_aligned = False

                travel_span = w // 2 + pw // 2 + 80
                cur_px = target_px if is_aligned else (int(round((target_px + norm_offset * travel_span) / 10.0)) * 10)

                if cur_px in frame_cache:
                    b_data, f_arr = frame_cache[cur_px]
                    return b_data, f_arr, is_aligned

                frame = static_base_rgb.copy()
                alpha_composite_inplace(frame, piece_rgba, (cur_px, target_py))
                b_data = frame.tobytes()
                frame_cache[cur_px] = (b_data, frame)
                return b_data, frame, is_aligned

        elif config.template_id == "FACE_SPLIT_3BAND":
            # Template D: 3-Band Celebrity Face Split (Forehead/Hair, Eyes/Nose, Mouth/Chin)
            face_w, face_h = 860, 860
            face_rgba = cv2.resize(raw_animal_rgba, (face_w, face_h), interpolation=cv2.INTER_LANCZOS4)
            band3 = extract_three_band_face_bundle(
                face_rgba,
                split_ratios=(0.37, 0.64),
                guide_outline_color=config.outline_color_rgba,
            )
            pixel_match_mad = band3.pixel_match_mad

            face_x = (w - face_w) // 2
            face_y = (h - face_h) // 2 - 40

            alpha_composite_inplace(static_base_rgb, band3.guide_outline_rgba, (face_x, face_y))

            tx_top, ty_top = face_x + band3.band_targets_xy[0][0], face_y + band3.band_targets_xy[0][1]
            tx_mid, ty_mid = face_x + band3.band_targets_xy[1][0], face_y + band3.band_targets_xy[1][1]
            tx_bot, ty_bot = face_x + band3.band_targets_xy[2][0], face_y + band3.band_targets_xy[2][1]

            def get_cycle_frame(c_idx: int) -> Tuple[bytes, np.ndarray, bool]:
                phase = phase_for_frame(c_idx)
                if config.motion_profile != "slide" or timeline is not None:
                    pose_top = _resolve_pose(config.motion_profile, phase,
                        config.offset_distance_px * 1.2, config.hold_ratio,
                        config.seed, config.motion_intensity, "horizontal")
                    if c_idx in frame_cache:
                        encoded, cached = frame_cache[c_idx]
                        return encoded, cached, pose_top.locked
                    pose_mid = _resolve_pose(config.motion_profile, phase,
                        config.offset_distance_px * 1.3, config.hold_ratio,
                        config.seed + 1, config.motion_intensity, "horizontal")
                    pose_bot = _resolve_pose(config.motion_profile, phase,
                        config.offset_distance_px, config.hold_ratio,
                        config.seed + 2, config.motion_intensity, "horizontal")
                    frame = static_base_rgb.copy()
                    draw_motion_sprite(frame, band3.band_top_rgba, (tx_top, ty_top), pose_top)
                    draw_motion_sprite(frame, band3.band_mid_rgba, (tx_mid, ty_mid), pose_mid)
                    draw_motion_sprite(frame, band3.band_bot_rgba, (tx_bot, ty_bot), pose_bot)
                    encoded = frame.tobytes()
                    frame_cache[c_idx] = (encoded, frame)
                    return encoded, frame, pose_top.locked
                disp = evaluate_periodic_displacement(phase, hold_ratio=config.hold_ratio, ease_type=config.ease_type)
                dx = int(round((disp * config.offset_distance_px) / 10.0)) * 10
                is_aligned = dx == 0

                if dx in frame_cache:
                    b_data, f_arr = frame_cache[dx]
                    return b_data, f_arr, is_aligned

                frame = static_base_rgb.copy()
                # Top & bottom bands slide in +dx/-dx while middle eyes band slides in opposite -1.15*dx
                alpha_composite_inplace(frame, band3.band_top_rgba, (tx_top + dx, ty_top))
                alpha_composite_inplace(frame, band3.band_mid_rgba, (tx_mid - int(round(dx * 1.15)), ty_mid))
                alpha_composite_inplace(frame, band3.band_bot_rgba, (tx_bot + int(round(dx * 0.85)), ty_bot))
                b_data = frame.tobytes()
                frame_cache[dx] = (b_data, frame)
                return b_data, frame, is_aligned

        else:
            raise ValueError(f"Unsupported template_id: {config.template_id}")

        for f_idx in range(total_frames):
            c_idx = f_idx if timeline is not None else f_idx % cycle_frames
            if timeline is not None:
                aligned = timeline.is_locked(f_idx)
            elif config.motion_profile != "slide":
                aligned = _resolve_pose(config.motion_profile, c_idx / float(cycle_frames),
                    config.offset_distance_px, config.hold_ratio, config.seed,
                    config.motion_intensity).locked
            elif config.template_id in ("OUTLINE_MATCH", "FACE_SPLIT_3BAND"):
                phase = phase_for_frame(c_idx)
                disp = evaluate_periodic_displacement(phase, hold_ratio=config.hold_ratio, ease_type=config.ease_type)
                aligned = abs(disp) < 1e-4
            else:
                cycle_p = phase_for_frame(c_idx)
                aligned = abs(cycle_p - 0.5) <= (config.hold_ratio * 0.5)
            if aligned:
                alignment_frames.append(f_idx)

        alignment_onsets_sec: List[float] = []
        prev_f = -999
        for f_idx in alignment_frames:
            if f_idx - prev_f > 5:
                alignment_onsets_sec.append(round(f_idx / float(fps), 3))
            prev_f = f_idx

        if config.enable_audio:
            synthesize_puzzle_audio_wav(
                output_wav_path=wav_path,
                duration_sec=config.duration_sec,
                alignment_timestamps_sec=alignment_onsets_sec,
                enable_music=config.sound_mode == "music_and_ticks",
                enable_ticks=config.sound_mode == "music_and_ticks",
                seed=config.seed,
            )

        cycle_cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-threads",
            "2",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-s",
            f"{w}x{h}",
            "-pix_fmt",
            "rgb24",
            "-r",
            str(fps),
            "-i",
            "-",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-preset",
            "ultrafast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(cycle_mp4_path),
        ]
        proc = subprocess.Popen(
            cycle_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        saved_align_png = False
        saved_thumb_png = False
        thumb_frame_target = min(cycle_frames - 1, int(cycle_frames * 0.24))

        assert proc.stdin is not None
        for c_idx in range(cycle_frames):
            b_data, frame_rgb, is_aligned = get_cycle_frame(c_idx)
            proc.stdin.write(b_data)

            if is_aligned and not saved_align_png:
                Image.fromarray(frame_rgb).save(align_png_path)
                saved_align_png = True
            if c_idx == thumb_frame_target and not saved_thumb_png:
                Image.fromarray(frame_rgb).save(thumb_path)
                saved_thumb_png = True
            if progress_callback and (c_idx % 30 == 0 or c_idx == cycle_frames - 1):
                progress_callback(c_idx + 1, cycle_frames)

        proc.stdin.close()
        stderr_bytes = proc.stderr.read() if proc.stderr else b""
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"FFmpeg cycle encode failed ({ret}): {stderr_bytes.decode('utf-8', errors='replace')}")

        mux_cmd = ["ffmpeg", "-y", "-loglevel", "error", "-threads", "2"]
        if timeline is None:
            mux_cmd.extend(["-stream_loop", str(cycles)])
        mux_cmd.extend(["-i", str(cycle_mp4_path)])
        sfx = config.enable_audio and wav_path.is_file()
        speech_path = Path(config.narration_wav).resolve() if config.narration_wav else None
        if speech_path is not None:
            # A generated voice file must belong to the local Rfactory storage
            # area; reject attempts to read system files through renderer config.
            storage_root = self.assets_root.resolve().parent
            if not speech_path.is_relative_to(storage_root) or speech_path.suffix.lower() != ".wav":
                raise ValueError("Narration must be a server-owned WAV asset")
            if not speech_path.is_file():
                raise FileNotFoundError("Narration WAV is missing")
        if sfx:
            mux_cmd.extend(["-i", str(wav_path)])
        if speech_path is not None:
            mux_cmd.extend(["-i", str(speech_path)])

        mux_cmd.extend(["-map", "0:v:0", "-t", f"{config.duration_sec:.3f}", "-c:v", "copy"])
        if sfx and speech_path:
            mux_cmd.extend([
                "-filter_complex",
                "[1:a]volume=0.22[sfx];[sfx][2:a]amix=inputs=2:duration=longest:dropout_transition=0[mixed]",
                "-map", "[mixed]", "-c:a", "aac", "-b:a", "128k",
            ])
        elif sfx or speech_path:
            mux_cmd.extend(["-map", "1:a:0", "-c:a", "aac", "-b:a", "128k"])
        else:
            mux_cmd.append("-an")
        mux_cmd.extend(["-movflags", "+faststart", str(mp4_path)])

        mux_res = subprocess.run(mux_cmd, capture_output=True, text=True, check=False)
        if mux_res.returncode != 0:
            raise RuntimeError(f"FFmpeg mux failed: {mux_res.stderr}")

        # Exhaustive actual-vs-expected QA: check every encoded frame against
        # its canonical pre-encode animation. This is stricter than 'decodable'.
        # Any wrong-piece, desynchronized trajectory or codec corruption blocks
        # the job BEFORE it can become READY or reach the publishing queue.
        from services.engine.precision_qa import audit_against_expected_frames
        frame_report = audit_against_expected_frames(
            mp4_path,
            expected_frame=lambda i: get_cycle_frame(i if timeline is not None else i % cycle_frames)[1],
            expected_frames=total_frames,
            max_frame_mae=12.0,
            max_average_mae=6.0,
            sample_wh=(180, 320),
        )
        frame_report.update({
            "motion_profile": config.motion_profile,
            "motion_intensity": config.motion_intensity,
            "snap_alignment_mad_uncompressed": pixel_match_mad,
        })
        frame_report_path = mp4_path.with_suffix(".frameqa.json")
        frame_report_path.write_text(json.dumps(frame_report, indent=2), encoding="utf-8")
        if timeline is not None:
            snap_metadata = timeline.metadata()
            snap_metadata["observed_alignment_frames"] = len(alignment_frames)
            snap_metadata["audio_snap_times_sec"] = alignment_onsets_sec
            if len(alignment_onsets_sec) != len(timeline.passes):
                raise RuntimeError("Snap timeline did not produce the expected number of match events")
            if config.continuous_motion:
                if len(alignment_frames) != len(timeline.passes):
                    raise RuntimeError("Continuous motion must have one exact-fit frame per pass")
                if any(event.first_locked_frame != event.last_locked_frame for event in timeline.passes):
                    raise RuntimeError("Continuous motion unexpectedly contains a hold window")
            mp4_path.with_suffix(".snaps.json").write_text(
                json.dumps(snap_metadata, indent=2), encoding="utf-8"
            )

        if not saved_align_png and thumb_path.exists():
            Image.open(thumb_path).save(align_png_path)

        if cycle_mp4_path.exists():
            cycle_mp4_path.unlink()
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir, ignore_errors=True)

        sha256_hash = hashlib.sha256(mp4_path.read_bytes()).hexdigest()
        elapsed = round(time.time() - start_t, 3)

        return RenderArtifact(
            job_id=config.job_id,
            template_id=config.template_id,
            species=config.species,
            seed=config.seed,
            mp4_path=str(mp4_path),
            thumbnail_path=str(thumb_path),
            alignment_frame_png_path=str(align_png_path),
            width=w,
            height=h,
            fps=fps,
            duration_sec=config.duration_sec,
            total_frames=total_frames,
            alignment_frames=alignment_frames,
            alignment_timestamps_sec=alignment_onsets_sec,
            pixel_match_mad=pixel_match_mad,
            render_time_sec=elapsed,
            sha256=sha256_hash,
        )
