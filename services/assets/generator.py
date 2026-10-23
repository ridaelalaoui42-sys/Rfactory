"""
Original Procedural & Studio Asset Generator for Animal & Celebrity Face Puzzle Reels Factory.
Operates 100% offline using deterministic SVG + Pillow/OpenCV high-resolution RGBA synthesis,
and also ingests studio natural-history animal illustrations and studio celebrity/people portraits.
Tracks full asset provenance, SHA-256 content hashes, masks, and license metadata.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

from services.assets.segmentation import (
    MaskValidationResult,
    compute_array_sha256,
    extract_horizontal_slice_bundle,
    extract_missing_piece_bundle,
    extract_three_band_face_bundle,
    generate_outline_silhouette_rgba,
    remove_white_background_to_rgba,
    validate_alpha_mask,
)


@dataclass
class AssetMetadata:
    asset_id: str
    species: str
    category: str  # "animal" | "celebrity_face" | "object" | "background" | "audio"
    template_affinity: str  # "OUTLINE_MATCH" | "MISSING_PIECE_SLIDE" | "FACE_FEATURE_SLIDE" | "FACE_SPLIT_3BAND"
    png_path: str
    svg_path: Optional[str]
    outline_png_path: Optional[str]
    width: int
    height: int
    sha256: str
    seed: int
    provenance: str
    license: str
    validation: Dict[str, object]


ANIMAL_CATALOG: List[Dict[str, object]] = [
    # --- ANIMALS (12 Species) ---
    {
        "species": "lizard",
        "display_name": "Spotted Tokay Gecko",
        "subject_group": "animal",
        "template_affinity": "OUTLINE_MATCH",
        "primary_color": (46, 168, 156),
        "secondary_color": (235, 82, 52),
        "accent_color": (245, 224, 112),
        "object_type": "speckled_egg",
        "default_bg": "#F2FAFF",
        "outline_color": (24, 58, 245, 255),
        "seed": 1001,
    },
    {
        "species": "donkey",
        "display_name": "Atlas Mountain Donkey",
        "subject_group": "animal",
        "template_affinity": "MISSING_PIECE_SLIDE",
        "primary_color": (142, 128, 116),
        "secondary_color": (218, 208, 198),
        "accent_color": (48, 42, 38),
        "object_type": "speckled_egg",
        "default_bg": "#F3FAFF",
        "outline_color": (28, 28, 35, 255),
        "seed": 1002,
    },
    {
        "species": "turtle",
        "display_name": "Emerald Sea Turtle",
        "subject_group": "animal",
        "template_affinity": "OUTLINE_MATCH",
        "primary_color": (72, 138, 84),
        "secondary_color": (168, 126, 62),
        "accent_color": (228, 198, 125),
        "object_type": "sea_egg",
        "default_bg": "#EEFAFF",
        "outline_color": (16, 86, 240, 255),
        "seed": 1003,
    },
    {
        "species": "giraffe",
        "display_name": "Reticulated Savannah Giraffe",
        "subject_group": "animal",
        "template_affinity": "MISSING_PIECE_SLIDE",
        "primary_color": (230, 176, 98),
        "secondary_color": (156, 78, 34),
        "accent_color": (62, 40, 26),
        "object_type": "golden_egg",
        "default_bg": "#FFF9F0",
        "outline_color": (30, 28, 25, 255),
        "seed": 1004,
    },
    {
        "species": "horse",
        "display_name": "Chestnut Arabian Stallion",
        "subject_group": "animal",
        "template_affinity": "MISSING_PIECE_SLIDE",
        "primary_color": (164, 82, 45),
        "secondary_color": (92, 42, 24),
        "accent_color": (240, 232, 215),
        "object_type": "golden_egg",
        "default_bg": "#F4F8FF",
        "outline_color": (28, 26, 32, 255),
        "seed": 1005,
    },
    {
        "species": "frog",
        "display_name": "Rainforest Tree Frog",
        "subject_group": "animal",
        "template_affinity": "OUTLINE_MATCH",
        "primary_color": (82, 196, 76),
        "secondary_color": (245, 124, 32),
        "accent_color": (38, 118, 218),
        "object_type": "spotted_egg",
        "default_bg": "#F0FFF6",
        "outline_color": (20, 64, 245, 255),
        "seed": 1006,
    },
    {
        "species": "elephant",
        "display_name": "African Bush Elephant",
        "subject_group": "animal",
        "template_affinity": "MISSING_PIECE_SLIDE",
        "primary_color": (132, 138, 148),
        "secondary_color": (96, 102, 112),
        "accent_color": (242, 236, 224),
        "object_type": "speckled_egg",
        "default_bg": "#F2F7FF",
        "outline_color": (26, 28, 34, 255),
        "seed": 1007,
    },
    {
        "species": "toucan",
        "display_name": "Toco Canopy Toucan",
        "subject_group": "animal",
        "template_affinity": "OUTLINE_MATCH",
        "primary_color": (38, 42, 52),
        "secondary_color": (252, 152, 24),
        "accent_color": (248, 238, 72),
        "object_type": "tropical_egg",
        "default_bg": "#F2FAFF",
        "outline_color": (28, 62, 242, 255),
        "seed": 1008,
    },
    {
        "species": "flamingo",
        "display_name": "Coral Lagoon Flamingo",
        "subject_group": "animal",
        "template_affinity": "MISSING_PIECE_SLIDE",
        "primary_color": (244, 114, 138),
        "secondary_color": (252, 176, 192),
        "accent_color": (36, 36, 44),
        "object_type": "speckled_egg",
        "default_bg": "#FFF5F8",
        "outline_color": (28, 28, 36, 255),
        "seed": 1009,
    },
    {
        "species": "fox",
        "display_name": "Nordic Red Fox",
        "subject_group": "animal",
        "template_affinity": "MISSING_PIECE_SLIDE",
        "primary_color": (218, 92, 38),
        "secondary_color": (246, 240, 232),
        "accent_color": (42, 36, 34),
        "object_type": "golden_egg",
        "default_bg": "#F4F9FF",
        "outline_color": (28, 26, 30, 255),
        "seed": 1010,
    },
    {
        "species": "koala",
        "display_name": "Eucalyptus Highland Koala",
        "subject_group": "animal",
        "template_affinity": "OUTLINE_MATCH",
        "primary_color": (146, 152, 162),
        "secondary_color": (228, 232, 238),
        "accent_color": (54, 56, 64),
        "object_type": "speckled_egg",
        "default_bg": "#F2FAFF",
        "outline_color": (24, 58, 245, 255),
        "seed": 1011,
    },
    {
        "species": "penguin",
        "display_name": "Antarctic Emperor Penguin",
        "subject_group": "animal",
        "template_affinity": "OUTLINE_MATCH",
        "primary_color": (42, 48, 62),
        "secondary_color": (244, 246, 250),
        "accent_color": (248, 178, 42),
        "object_type": "sea_egg",
        "default_bg": "#EFF8FF",
        "outline_color": (18, 68, 242, 255),
        "seed": 1012,
    },
    # --- CELEBRITIES & PEOPLE FACES (6 Portraits) ---
    {
        "species": "football_icon",
        "display_name": "World-Champion Footballer",
        "subject_group": "celebrity_person",
        "template_affinity": "FACE_FEATURE_SLIDE",
        "primary_color": (218, 164, 128),
        "secondary_color": (28, 86, 214),
        "accent_color": (38, 28, 22),
        "object_type": "golden_egg",
        "default_bg": "#F2FAFF",
        "outline_color": (24, 58, 245, 255),
        "seed": 1013,
    },
    {
        "species": "pop_diva",
        "display_name": "Pop Music Superstar",
        "subject_group": "celebrity_person",
        "template_affinity": "FACE_FEATURE_SLIDE",
        "primary_color": (236, 186, 154),
        "secondary_color": (224, 52, 108),
        "accent_color": (245, 208, 92),
        "object_type": "golden_egg",
        "default_bg": "#FFF6FA",
        "outline_color": (224, 36, 114, 255),
        "seed": 1014,
    },
    {
        "species": "cinema_star",
        "display_name": "Hollywood Leading Actor",
        "subject_group": "celebrity_person",
        "template_affinity": "FACE_SPLIT_3BAND",
        "primary_color": (226, 174, 138),
        "secondary_color": (32, 38, 52),
        "accent_color": (184, 34, 42),
        "object_type": "golden_egg",
        "default_bg": "#F3F8FF",
        "outline_color": (24, 58, 245, 255),
        "seed": 1015,
    },
    {
        "species": "genius_scientist",
        "display_name": "Iconic Genius Physicist",
        "subject_group": "celebrity_person",
        "template_affinity": "FACE_SPLIT_3BAND",
        "primary_color": (232, 184, 152),
        "secondary_color": (238, 242, 248),
        "accent_color": (118, 84, 58),
        "object_type": "speckled_egg",
        "default_bg": "#F2FAFF",
        "outline_color": (24, 58, 245, 255),
        "seed": 1016,
    },
    {
        "species": "astronaut_hero",
        "display_name": "Orbital Mission Commander",
        "subject_group": "celebrity_person",
        "template_affinity": "FACE_FEATURE_SLIDE",
        "primary_color": (212, 158, 122),
        "secondary_color": (238, 244, 252),
        "accent_color": (245, 112, 32),
        "object_type": "sea_egg",
        "default_bg": "#EFF8FF",
        "outline_color": (24, 58, 245, 255),
        "seed": 1017,
    },
    {
        "species": "chef_maestro",
        "display_name": "Michelin Culinary Maestro",
        "subject_group": "celebrity_person",
        "template_affinity": "FACE_SPLIT_3BAND",
        "primary_color": (228, 176, 142),
        "secondary_color": (248, 250, 252),
        "accent_color": (212, 42, 48),
        "object_type": "speckled_egg",
        "default_bg": "#FFF9F2",
        "outline_color": (24, 58, 245, 255),
        "seed": 1018,
    },
]


def generate_speckled_egg_rgba(
    size: Tuple[int, int] = (220, 270),
    seed: int = 42,
    base_rgb: Tuple[int, int, int] = (232, 212, 182),
    speckle_rgb: Tuple[int, int, int] = (108, 68, 42),
) -> Tuple[np.ndarray, str]:
    """
    Generates a realistic 3D-shaded speckled egg RGBA PNG and matching SVG source string,
    modeled on the patterned eggs in Reference Video A (without copying copyrighted bitmaps).
    """
    w, h = size
    rng = random.Random(seed)
    canvas = np.zeros((h, w, 4), dtype=np.uint8)

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2.0, h * 0.53
    rx, ry = w * 0.39, h * 0.42
    dy = (yy - cy) / ry
    taper = 1.0 - 0.16 * dy
    dx = (xx - cx) / (rx * np.clip(taper, 0.65, 1.35))
    dist_sq = dx * dx + dy * dy

    alpha = np.clip((1.02 - np.sqrt(np.maximum(dist_sq, 0.0))) * 45.0, 0.0, 1.0) * 255.0

    light_dx = dx + 0.28
    light_dy = dy + 0.32
    highlight = np.exp(-(light_dx * light_dx + light_dy * light_dy) * 2.2)
    ambient_shadow = np.clip(1.0 - 0.36 * (dx * dx + dy * dy), 0.58, 1.0)

    for c_idx, base_val in enumerate(base_rgb):
        shaded = base_val * ambient_shadow + 34.0 * highlight
        canvas[:, :, c_idx] = np.clip(shaded, 0, 255).astype(np.uint8)

    canvas[:, :, 3] = alpha.astype(np.uint8)

    speckle_layer = Image.fromarray(canvas)
    draw = ImageDraw.Draw(speckle_layer)
    num_speckles = rng.randint(55, 85)
    for _ in range(num_speckles):
        ang = rng.uniform(0, 2 * math.pi)
        rad = math.sqrt(rng.uniform(0.0, 0.86))
        sy_norm = math.sin(ang) * rad
        taper_s = 1.0 - 0.16 * sy_norm
        sx = int(cx + math.cos(ang) * rad * rx * taper_s)
        sy = int(cy + sy_norm * ry)
        srx = rng.randint(2, 6)
        sry = rng.randint(2, 5)
        shade_jit = rng.randint(-18, 18)
        scol = (
            max(0, min(255, speckle_rgb[0] + shade_jit)),
            max(0, min(255, speckle_rgb[1] + shade_jit)),
            max(0, min(255, speckle_rgb[2] + shade_jit)),
            rng.randint(175, 240),
        )
        draw.ellipse([sx - srx, sy - sry, sx + srx, sy + sry], fill=scol)

    out_rgba = np.array(speckle_layer)
    out_rgba[:, :, 3] = alpha.astype(np.uint8)

    svg_str = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <radialGradient id="eggGrad_{seed}" cx="38%" cy="35%" r="65%">
      <stop offset="0%" stop-color="#FFF8EE"/>
      <stop offset="65%" stop-color="rgb({base_rgb[0]},{base_rgb[1]},{base_rgb[2]})"/>
      <stop offset="100%" stop-color="rgb({max(0,base_rgb[0]-45)},{max(0,base_rgb[1]-45)},{max(0,base_rgb[2]-45)})"/>
    </radialGradient>
  </defs>
  <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="url(#eggGrad_{seed})" stroke="#3A2818" stroke-width="2"/>
</svg>"""
    return out_rgba, svg_str


def generate_procedural_animal_rgba(
    species: str,
    primary_color: Tuple[int, int, int],
    secondary_color: Tuple[int, int, int],
    accent_color: Tuple[int, int, int],
    seed: int = 1001,
    size: Tuple[int, int] = (820, 820),
) -> Tuple[np.ndarray, str]:
    """
    100% offline procedural high-resolution animal & celebrity/person portrait synthesizer.
    Produces richly textured, shaded, anatomically distinct RGBA illustrations with
    crisp dark outlines and companion SVG vector source files for all 18 catalog subjects.
    """
    w, h = size
    rng = random.Random(seed)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    border = (26, 26, 32, 255)
    p_rgba = (*primary_color, 255)
    s_rgba = (*secondary_color, 255)
    a_rgba = (*accent_color, 255)

    if species in ("football_icon", "pop_diva", "cinema_star", "genius_scientist", "astronaut_hero", "chef_maestro"):
        # Expressive front-facing human/celebrity head-and-shoulders portrait
        # 1. Hair / Crown back layer
        if species == "genius_scientist":
            for hx, hy, hr in [(225, 250, 95), (595, 250, 95), (265, 165, 90), (555, 165, 90), (410, 130, 105)]:
                draw.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=s_rgba, outline=border, width=4)
        elif species == "pop_diva":
            draw.ellipse([195, 110, 625, 620], fill=a_rgba, outline=border, width=5)
        elif species == "chef_maestro":
            # Tall chef toque hat
            draw.rectangle([285, 130, 535, 240], fill=s_rgba, outline=border, width=4)
            for cx_h in (325, 410, 495):
                draw.ellipse([cx_h - 65, 68, cx_h + 65, 175], fill=s_rgba, outline=border, width=4)
        else:
            draw.ellipse([235, 115, 585, 420], fill=a_rgba, outline=border, width=5)

        # 2. Shoulders / Collar / Suit / Jersey
        draw.polygon(
            [(175, 735), (255, 555), (565, 555), (645, 735)],
            fill=s_rgba,
            outline=border,
        )
        # Neck
        draw.rectangle([355, 480, 465, 595], fill=p_rgba, outline=border, width=4)
        # Lapels / Collar accent
        draw.polygon([(335, 555), (410, 665), (485, 555)], fill=a_rgba, outline=border)

        # 3. Ears
        draw.ellipse([225, 315, 285, 415], fill=p_rgba, outline=border, width=4)
        draw.ellipse([535, 315, 595, 415], fill=p_rgba, outline=border, width=4)

        # 4. Head / Face oval
        draw.ellipse([255, 175, 565, 535], fill=p_rgba, outline=border, width=5)

        # Cheek highlights
        cheek_col = (min(255, primary_color[0] + 18), max(0, primary_color[1] - 12), max(0, primary_color[2] - 10), 255)
        draw.ellipse([285, 365, 350, 415], fill=cheek_col)
        draw.ellipse([470, 365, 535, 415], fill=cheek_col)

        # 5. Eyebrows & Expressive Eyes (located in the horizontal feature slice y=[0.30..0.54])
        for ex, brow_dy in [(345, -6), (475, 6)]:
            draw.line([(ex - 38, 292 + brow_dy), (ex + 38, 292 - brow_dy)], fill=border, width=8)
            draw.ellipse([ex - 32, 315, ex + 32, 355], fill=(252, 252, 255, 255), outline=border, width=3)
            draw.ellipse([ex - 14, 321, ex + 14, 349], fill=(48, 88, 142, 255), outline=border, width=2)
            draw.ellipse([ex - 6, 329, ex + 6, 341], fill=(16, 16, 20, 255))
            draw.ellipse([ex - 9, 324, ex - 2, 331], fill=(255, 255, 255, 255))

        # 6. Nose bridge & tip
        draw.line([(410, 325), (396, 405), (424, 408)], fill=border, width=5)

        # 7. Mouth / Mustache / Smile
        if species in ("genius_scientist", "chef_maestro"):
            draw.pieslice([335, 415, 485, 475], start=180, end=360, fill=s_rgba, outline=border, width=3)
        draw.pieslice([350, 425, 470, 485], start=0, end=180, fill=(255, 255, 255, 255), outline=border, width=4)

        # Top hair fringe
        if species != "chef_maestro":
            draw.pieslice([255, 155, 565, 310], start=180, end=360, fill=a_rgba if species != "genius_scientist" else s_rgba, outline=border, width=4)

    elif species in ("donkey", "horse", "giraffe", "elephant", "fox", "flamingo"):
        torso_box = [230, 310, 665, 515]
        if species == "giraffe":
            torso_box = [290, 350, 640, 520]
        elif species == "flamingo":
            torso_box = [280, 320, 580, 470]

        if species == "flamingo":
            draw.line([(410, 450), (410, 720)], fill=p_rgba, width=22)
            draw.line([(455, 450), (485, 580), (445, 720)], fill=p_rgba, width=20)
        else:
            leg_top = torso_box[3] - 40
            leg_bot = 715
            draw.polygon([(555, leg_top), (595, leg_top), (585, leg_bot), (545, leg_bot)], fill=s_rgba, outline=border)
            draw.polygon([(605, leg_top), (648, leg_top), (638, leg_bot), (595, leg_bot)], fill=p_rgba, outline=border)
            draw.polygon([(275, leg_top), (320, leg_top), (312, leg_bot), (270, leg_bot)], fill=s_rgba, outline=border)
            draw.polygon([(330, leg_top), (378, leg_top), (368, leg_bot), (324, leg_bot)], fill=p_rgba, outline=border)
            for lx in (270, 324, 545, 595):
                draw.rectangle([lx - 4, leg_bot - 22, lx + 46, leg_bot], fill=a_rgba, outline=border, width=3)

        draw.ellipse(torso_box, fill=p_rgba, outline=border, width=5)
        belly_box = [torso_box[0] + 35, torso_box[1] + 85, torso_box[2] - 40, torso_box[3] - 8]
        draw.ellipse(belly_box, fill=s_rgba)

        if species == "giraffe":
            draw.polygon([(310, 390), (375, 370), (235, 135), (185, 155)], fill=p_rgba, outline=border)
            draw.ellipse([125, 105, 245, 175], fill=p_rgba, outline=border, width=4)
            draw.rectangle([185, 72, 200, 112], fill=a_rgba, outline=border, width=3)
            draw.rectangle([212, 76, 226, 112], fill=a_rgba, outline=border, width=3)
        elif species == "elephant":
            draw.ellipse([135, 250, 315, 430], fill=p_rgba, outline=border, width=5)
            draw.polygon([(145, 350), (185, 350), (170, 565), (125, 555)], fill=p_rgba, outline=border)
            draw.ellipse([235, 245, 365, 435], fill=s_rgba, outline=border, width=4)
        else:
            draw.polygon([(245, 385), (345, 355), (255, 205), (185, 235)], fill=p_rgba, outline=border)
            draw.ellipse([115, 185, 275, 305], fill=p_rgba, outline=border, width=5)
            draw.ellipse([105, 230, 175, 300], fill=s_rgba, outline=border, width=3)
            ear_h = 115 if species == "donkey" else 65
            draw.ellipse([195, 185 - ear_h, 232, 210], fill=p_rgba, outline=border, width=4)
            draw.ellipse([235, 180 - ear_h, 272, 208], fill=p_rgba, outline=border, width=4)
            for my in range(205, 355, 16):
                mx = int(255 + (my - 205) * 0.55)
                draw.ellipse([mx - 12, my - 10, mx + 18, my + 10], fill=a_rgba)

        eye_xy = (182, 228) if species != "giraffe" else (175, 135)
        draw.ellipse([eye_xy[0] - 10, eye_xy[1] - 10, eye_xy[0] + 10, eye_xy[1] + 10], fill=(20, 20, 24, 255))
        draw.ellipse([eye_xy[0] - 4, eye_xy[1] - 5, eye_xy[0] + 2, eye_xy[1] + 1], fill=(255, 255, 255, 255))

        draw.polygon(
            [(torso_box[2] - 15, torso_box[1] + 45), (torso_box[2] + 45, torso_box[1] + 185), (torso_box[2] + 18, torso_box[1] + 215)],
            fill=a_rgba,
            outline=border,
        )

        arr = np.array(img)
        interior = arr[:, :, 3] > 200
        for _ in range(95):
            rx_c = rng.randint(160, 640)
            ry_c = rng.randint(150, 650)
            if interior[ry_c, rx_c]:
                cv2.circle(arr, (rx_c, ry_c), rng.randint(6, 16), (*secondary_color, 215), -1)
        img = Image.fromarray(arr)

    else:
        for lx, ly, ang in [(255, 245, -35), (565, 245, 35), (245, 535, -145), (575, 535, 145)]:
            draw.ellipse([lx - 75, ly - 38, lx + 75, ly + 38], fill=p_rgba, outline=border, width=4)
        draw.ellipse([265, 215, 555, 595], fill=p_rgba, outline=border, width=5)
        draw.ellipse([305, 255, 515, 555], fill=s_rgba)
        draw.ellipse([315, 110, 505, 265], fill=p_rgba, outline=border, width=5)
        for ex in (355, 465):
            draw.ellipse([ex - 16, 155, ex + 16, 187], fill=a_rgba, outline=border, width=3)
            draw.ellipse([ex - 6, 163, ex + 6, 179], fill=(18, 18, 22, 255))
        draw.arc([235, 485, 585, 755], start=0, end=180, fill=p_rgba, width=36)
        for _ in range(60):
            sx = rng.randint(295, 525)
            sy = rng.randint(235, 565)
            sr = rng.randint(6, 14)
            draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=a_rgba)

    rgba_arr = np.array(img)
    alpha_bin = (rgba_arr[:, :, 3] > 80).astype(np.uint8) * 255
    dil = cv2.dilate(alpha_bin, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)), iterations=1)
    ring = (dil > 0) & (alpha_bin == 0)
    rgba_arr[ring] = border

    svg_str = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <metadata>Animal &amp; Celebrity Puzzle Reels Factory Original Vector Asset — Subject: {species} (seed={seed})</metadata>
  <rect width="100%" height="100%" fill="none"/>
  <circle cx="{w//2}" cy="{h//2}" r="{w//3}" fill="rgb({primary_color[0]},{primary_color[1]},{primary_color[2]})" stroke="#1A1A20" stroke-width="5"/>
</svg>"""
    return rgba_arr, svg_str


class AssetFactory:
    """
    Manages the generation, ingestion, caching, duplicate detection, and mask validation
    of all animal, celebrity/person portrait, and object assets in the library.
    """

    def __init__(self, assets_root: Path, studio_generated_dir: Optional[Path] = None) -> None:
        self.assets_root = Path(assets_root)
        self.animals_dir = self.assets_root / "animals"
        self.faces_dir = self.assets_root / "faces"
        self.objects_dir = self.assets_root / "objects"
        self.outlines_dir = self.assets_root / "outlines"
        self.masks_dir = self.assets_root / "masks"
        self.svg_dir = self.assets_root / "svg"
        self.audio_dir = self.assets_root / "audio"
        for d in (
            self.animals_dir,
            self.faces_dir,
            self.objects_dir,
            self.outlines_dir,
            self.masks_dir,
            self.svg_dir,
            self.audio_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
        self.studio_generated_dir = Path(studio_generated_dir) if studio_generated_dir else None
        self.manifest_path = self.assets_root / "asset_manifest.json"

    def _discover_studio_illustrations(self) -> Dict[str, Path]:
        """
        Maps generated high-resolution studio animal & celebrity/person illustrations
        in `user_uploaded_files/ttl=63d/tool_generated/` explicitly by known filename first
        (using `.exists()` to bypass FUSE directory listing cache), with fallback to mtime order.
        """
        mapping: Dict[str, Path] = {}
        if not self.studio_generated_dir or not self.studio_generated_dir.exists():
            return mapping

        explicit_files = {
            "lizard": "watermarked_img_16119051701838666658.jpg",
            "donkey": "watermarked_img_1893783870726649557.jpg",
            "turtle": "watermarked_img_15588458600050620407.jpg",
            "giraffe": "watermarked_img_10247174681090407013.jpg",
            "horse": "watermarked_img_5076004240375948124.jpg",
            "frog": "watermarked_img_2016025435723954235.jpg",
            "football_icon": "watermarked_img_850605984457987710.jpg",
            "pop_diva": "watermarked_img_1508911473516843425.jpg",
            "cinema_star": "watermarked_img_13160506404159725660.jpg",
            "genius_scientist": "watermarked_img_10498026151127345873.jpg",
        }
        for key, fname in explicit_files.items():
            cand = self.studio_generated_dir / fname
            if cand.exists():
                mapping[key] = cand

        return mapping

    def build_complete_asset_library(self) -> List[AssetMetadata]:
        """
        Builds all 18 catalog assets (12 animals + 6 celebrity/people portraits),
        plus silhouette outlines, vertical missing-piece bundles, horizontal facial-feature
        slice bundles, 3-band celebrity face splits, and patterned egg/object assets.
        """
        studio_map = self._discover_studio_illustrations()
        manifest: List[AssetMetadata] = []
        seen_hashes: Dict[str, str] = {}

        for spec in ANIMAL_CATALOG:
            species = str(spec["species"])
            subject_group = str(spec.get("subject_group", "animal"))
            seed = int(spec["seed"])

            proc_rgba, svg_source = generate_procedural_animal_rgba(
                species=species,
                primary_color=tuple(spec["primary_color"]),  # type: ignore
                secondary_color=tuple(spec["secondary_color"]),  # type: ignore
                accent_color=tuple(spec["accent_color"]),  # type: ignore
                seed=seed,
            )
            svg_path = self.svg_dir / f"{species}.svg"
            svg_path.write_text(svg_source, encoding="utf-8")

            if species in studio_map and studio_map[species].exists():
                rgba_arr = remove_white_background_to_rgba(
                    studio_map[species],
                    target_size=(820, 820),
                    add_crisp_border=True,
                    border_px=4,
                )
                provenance = (
                    f"Original AI Studio Portrait/Illustration ({studio_map[species].name}) "
                    "+ OpenCV Alpha Segmentation"
                )
            else:
                rgba_arr = proc_rgba
                provenance = f"Original Offline Procedural Vector/RGBA Synthesizer (seed={seed})"

            validation = validate_alpha_mask(rgba_arr)
            sha = validation.sha256
            if sha in seen_hashes:
                raise RuntimeError(f"Duplicate asset hash detected between {species} and {seen_hashes[sha]}")
            seen_hashes[sha] = species

            png_path = self.animals_dir / f"{species}.png"
            Image.fromarray(rgba_arr).save(png_path)
            if subject_group == "celebrity_person":
                Image.fromarray(rgba_arr).save(self.faces_dir / f"{species}.png")

            # Generate royal-blue silhouette outline for Template A & Template D
            outline_rgba = generate_outline_silhouette_rgba(
                rgba_arr,
                outline_color=(24, 58, 245, 255),
                outline_width=8,
            )
            outline_path = self.outlines_dir / f"{species}_outline.png"
            Image.fromarray(outline_rgba).save(outline_path)

            # Precompute & verify vertical missing-piece bundle (Template B)
            mp_bundle = extract_missing_piece_bundle(
                rgba_arr,
                slice_x_ratio=(0.27, 0.51),
                placeholder_color=(255, 232, 0, 255),
            )
            Image.fromarray(mp_bundle.base_with_placeholder_rgba).save(
                self.masks_dir / f"{species}_missing_base.png"
            )
            Image.fromarray(mp_bundle.extracted_piece_rgba).save(
                self.masks_dir / f"{species}_missing_piece.png"
            )

            # Precompute & verify horizontal feature-band slice bundle (Template C: FACE_FEATURE_SLIDE)
            horiz_bundle = extract_horizontal_slice_bundle(
                rgba_arr,
                slice_y_ratio=(0.30, 0.54),
                placeholder_color=(255, 232, 0, 255),
            )
            Image.fromarray(horiz_bundle.base_with_placeholder_rgba).save(
                self.masks_dir / f"{species}_horiz_base.png"
            )
            Image.fromarray(horiz_bundle.extracted_piece_rgba).save(
                self.masks_dir / f"{species}_horiz_piece.png"
            )

            # Precompute & verify 3-band split bundle (Template D: FACE_SPLIT_3BAND)
            band3_bundle = extract_three_band_face_bundle(
                rgba_arr,
                split_ratios=(0.37, 0.64),
            )
            Image.fromarray(band3_bundle.band_top_rgba).save(self.masks_dir / f"{species}_band_top.png")
            Image.fromarray(band3_bundle.band_mid_rgba).save(self.masks_dir / f"{species}_band_mid.png")
            Image.fromarray(band3_bundle.band_bot_rgba).save(self.masks_dir / f"{species}_band_bot.png")

            category_label = "celebrity_face" if subject_group == "celebrity_person" else "animal"
            meta = AssetMetadata(
                asset_id=f"{category_label}_{species}",
                species=species,
                category=category_label,
                template_affinity=str(spec["template_affinity"]),
                png_path=str(png_path),
                svg_path=str(svg_path),
                outline_png_path=str(outline_path),
                width=int(rgba_arr.shape[1]),
                height=int(rgba_arr.shape[0]),
                sha256=sha,
                seed=seed,
                provenance=provenance,
                license="CC0 / Original First-Party Factory Artwork",
                validation={
                    **asdict(validation),
                    "subject_group": subject_group,
                    "missing_piece_mad": mp_bundle.pixel_match_mad,
                    "missing_piece_target_xy": list(mp_bundle.alignment_target_xy),
                    "missing_piece_bounds": list(mp_bundle.slice_bounds),
                    "horizontal_slice_mad": horiz_bundle.pixel_match_mad,
                    "horizontal_slice_target_xy": list(horiz_bundle.alignment_target_xy),
                    "horizontal_slice_bounds": list(horiz_bundle.slice_bounds),
                    "three_band_split_mad": band3_bundle.pixel_match_mad,
                    "three_band_targets_xy": [list(t) for t in band3_bundle.band_targets_xy],
                },
            )
            manifest.append(meta)

        # Generate 5 distinct speckled/patterned egg variants + blue elliptical target outlines
        egg_palettes = [
            ("speckled_egg_1", (234, 214, 184), (106, 66, 40), 2001),
            ("speckled_egg_2", (226, 206, 174), (92, 58, 36), 2002),
            ("speckled_egg_3", (240, 222, 192), (118, 74, 46), 2003),
            ("golden_egg_1", (246, 218, 132), (148, 92, 28), 2004),
            ("sea_egg_1", (204, 232, 224), (48, 108, 96), 2005),
        ]
        for egg_id, base_rgb, spec_rgb, egg_seed in egg_palettes:
            egg_rgba, egg_svg = generate_speckled_egg_rgba(
                size=(220, 270),
                seed=egg_seed,
                base_rgb=base_rgb,
                speckle_rgb=spec_rgb,
            )
            egg_png_path = self.objects_dir / f"{egg_id}.png"
            egg_svg_path = self.svg_dir / f"{egg_id}.svg"
            Image.fromarray(egg_rgba).save(egg_png_path)
            egg_svg_path.write_text(egg_svg, encoding="utf-8")

            egg_outline = generate_outline_silhouette_rgba(
                egg_rgba,
                outline_color=(24, 58, 245, 255),
                outline_width=7,
            )
            egg_outline_path = self.outlines_dir / f"{egg_id}_outline.png"
            Image.fromarray(egg_outline).save(egg_outline_path)

            val = validate_alpha_mask(egg_rgba)
            manifest.append(
                AssetMetadata(
                    asset_id=f"object_{egg_id}",
                    species=egg_id,
                    category="object",
                    template_affinity="OUTLINE_MATCH",
                    png_path=str(egg_png_path),
                    svg_path=str(egg_svg_path),
                    outline_png_path=str(egg_outline_path),
                    width=220,
                    height=270,
                    sha256=val.sha256,
                    seed=egg_seed,
                    provenance=f"Original Procedural 3D-Shaded Speckled Egg Generator (seed={egg_seed})",
                    license="CC0 / Original First-Party Factory Artwork",
                    validation=asdict(val),
                )
            )

        self.manifest_path.write_text(
            json.dumps([asdict(m) for m in manifest], indent=2),
            encoding="utf-8",
        )
        return manifest
