"""
Image Segmentation, Alpha Masking, Silhouette Outline & Missing-Piece Extraction Engine.
Supports both Animals and Celebrity/People Face Portraits:
  - Exterior border-connected flood-fill alpha segmentation (preserves internal whites like eyes, teeth, muzzles)
  - Silhouette outline generation (Template A: OUTLINE_MATCH)
  - Vertical missing-piece slice extraction (Template B: MISSING_PIECE_SLIDE)
  - Horizontal facial-feature band slice extraction (Template C: FACE_FEATURE_SLIDE)
  - 3-Band Celebrity Face Split extraction (Template D: FACE_SPLIT_3BAND)
All slice/band extractors guarantee pixel-perfect restoration (MAD == 0.0) at the target alignment coordinate.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image


@dataclass
class MaskValidationResult:
    valid: bool
    non_empty_ratio: float
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    edge_smoothness_score: float
    touches_border: bool
    sha256: str
    errors: List[str]


@dataclass
class MissingPieceBundle:
    full_animal_rgba: np.ndarray
    base_with_placeholder_rgba: np.ndarray
    extracted_piece_rgba: np.ndarray
    mask_binary: np.ndarray
    slice_bounds: Tuple[int, int, int, int]  # (x1, y1, x2, y2) in canvas coords
    alignment_target_xy: Tuple[int, int]     # top-left (x, y) where piece restores full subject
    pixel_match_mad: float                   # Mean Absolute Difference when piece is composited at target


@dataclass
class ThreeBandFaceBundle:
    full_face_rgba: np.ndarray
    guide_outline_rgba: np.ndarray
    band_top_rgba: np.ndarray
    band_mid_rgba: np.ndarray
    band_bot_rgba: np.ndarray
    band_targets_xy: List[Tuple[int, int]]   # [(x_top, y_top), (x_mid, y_mid), (x_bot, y_bot)]
    band_bounds: List[Tuple[int, int, int, int]]
    pixel_match_mad: float


def compute_array_sha256(arr: np.ndarray) -> str:
    return hashlib.sha256(arr.tobytes()).hexdigest()


def remove_white_background_to_rgba(
    img_path: Path | str,
    target_size: Tuple[int, int] = (820, 820),
    white_thresh: int = 238,
    add_crisp_border: bool = True,
    border_color: Tuple[int, int, int, int] = (28, 28, 35, 255),
    border_px: int = 4,
) -> np.ndarray:
    """
    Converts an isolated illustration on a white background into a clean RGBA image
    using exterior border-connected flood-fill so internal white features (such as
    eyes, teeth, collars, white hair, or animal muzzles) remain 100% solid while
    exterior white canvas and faint cast shadows are cleanly stripped.
    """
    pil_img = Image.open(img_path).convert("RGBA")
    arr = np.array(pil_img)
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.float32)

    max_c = np.max(rgb, axis=2)
    min_c = np.min(rgb, axis=2)
    sat = np.where(max_c > 0, (max_c - min_c) / (max_c + 1e-5), 0.0)
    luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

    # Candidate background pixels: pure white OR low-saturation light grey cast shadow
    is_bg_candidate = (luma >= white_thresh) | ((luma >= 198) & (sat < 0.11))

    # Bridge tiny 1-2px gaps in dark contour lines before flood-filling from the border
    fg_prelim = (~is_bg_candidate).astype(np.uint8) * 255
    close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    fg_sealed = cv2.morphologyEx(fg_prelim, cv2.MORPH_CLOSE, close_k, iterations=2)

    # Flood-fill exterior background from all border pixels on fg_sealed
    exterior_bg = np.zeros((h + 2, w + 2), dtype=np.uint8)
    flood_canvas = fg_sealed.copy()
    for bx in range(0, w, 8):
        if flood_canvas[0, bx] == 0:
            cv2.floodFill(flood_canvas, exterior_bg, (bx, 0), 128)
        if flood_canvas[h - 1, bx] == 0:
            cv2.floodFill(flood_canvas, exterior_bg, (bx, h - 1), 128)
    for by in range(0, h, 8):
        if flood_canvas[by, 0] == 0:
            cv2.floodFill(flood_canvas, exterior_bg, (0, by), 128)
        if flood_canvas[by, w - 1] == 0:
            cv2.floodFill(flood_canvas, exterior_bg, (w - 1, by), 128)

    # Any pixel not reached by exterior flood-fill is part of the subject interior
    fg_mask = (flood_canvas != 128).astype(np.uint8) * 255

    # Remove enclosed pure-white background pockets while keeping genuine features
    inv_prelim = (fg_prelim == 0).astype(np.uint8) * 255
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inv_prelim)
    for lbl in range(1, num_labels):
        comp_mask = labels == lbl
        area = int(stats[lbl, cv2.CC_STAT_Area]) if hasattr(cv2, "CC_STAT_Area") else int(stats[lbl, 4])
        if area > 450:
            mean_luma = float(np.mean(luma[comp_mask]))
            mean_sat = float(np.mean(sat[comp_mask]))
            if mean_luma > 246.0 and mean_sat < 0.025:
                fg_mask[comp_mask] = 0

    # Keep largest connected subject component(s)
    contours, _ = cv2.findContours(fg_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        num_fg, fg_labels, fg_stats, _ = cv2.connectedComponentsWithStats(fg_mask)
        if num_fg > 1:
            max_fg_area = max(int(fg_stats[i, 4]) for i in range(1, num_fg))
            for i in range(1, num_fg):
                if int(fg_stats[i, 4]) < max_fg_area * 0.05:
                    fg_mask[fg_labels == i] = 0

    erode_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    clean_mask = cv2.erode(fg_mask, erode_k, iterations=1)
    smooth_alpha = cv2.GaussianBlur(clean_mask, (3, 3), 0)

    out_rgba = arr.copy()
    out_rgba[:, :, 3] = smooth_alpha

    ys, xs = np.where(smooth_alpha > 16)
    if len(xs) > 0 and len(ys) > 0:
        x1, x2 = int(xs.min()), int(xs.max())
        y1, y2 = int(ys.min()), int(ys.max())
        crop = out_rgba[y1 : y2 + 1, x1 : x2 + 1]
    else:
        crop = out_rgba

    tw, th = target_size
    pad = 44
    avail_w, avail_h = tw - 2 * pad, th - 2 * pad
    ch, cw = crop.shape[:2]
    scale = min(avail_w / max(cw, 1), avail_h / max(ch, 1))
    nw, nh = max(1, int(round(cw * scale))), max(1, int(round(ch * scale)))

    resized = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    canvas = np.zeros((th, tw, 4), dtype=np.uint8)
    ox = (tw - nw) // 2
    oy = (th - nh) // 2
    canvas[oy : oy + nh, ox : ox + nw] = resized

    if add_crisp_border and border_px > 0:
        alpha_bin = (canvas[:, :, 3] > 96).astype(np.uint8) * 255
        dil_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (border_px * 2 + 1, border_px * 2 + 1))
        dilated = cv2.dilate(alpha_bin, dil_k, iterations=1)
        border_ring = (dilated > 0) & (alpha_bin == 0)
        canvas[border_ring] = border_color

    return canvas


def generate_outline_silhouette_rgba(
    rgba_img: np.ndarray,
    outline_color: Tuple[int, int, int, int] = (24, 58, 245, 255),
    outline_width: int = 8,
    inner_fill_color: Optional[Tuple[int, int, int, int]] = None,
) -> np.ndarray:
    """
    Creates the crisp colored contour outline silhouette (used in Template A: OUTLINE_MATCH
    and Template D guide outlines) from any transparent RGBA animal, face, or object asset.
    """
    h, w = rgba_img.shape[:2]
    alpha = (rgba_img[:, :, 3] > 80).astype(np.uint8) * 255

    k_out = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (outline_width * 2 + 1, outline_width * 2 + 1))
    dilated = cv2.dilate(alpha, k_out, iterations=1)
    eroded = cv2.erode(alpha, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)

    ring = cv2.subtract(dilated, eroded)
    ring_aa = cv2.GaussianBlur(ring, (3, 3), 0)

    out = np.zeros((h, w, 4), dtype=np.uint8)
    if inner_fill_color is not None:
        inner_mask = eroded > 0
        out[inner_mask] = inner_fill_color

    r, g, b, a = outline_color
    ring_idx = ring_aa > 12
    out[ring_idx, 0] = r
    out[ring_idx, 1] = g
    out[ring_idx, 2] = b
    out[ring_idx, 3] = np.clip(ring_aa[ring_idx].astype(np.float32) * (a / 255.0), 0, 255).astype(np.uint8)
    return out


def validate_alpha_mask(rgba_img: np.ndarray) -> MaskValidationResult:
    """
    Validates that an RGBA asset has a non-empty alpha channel, smooth contour edges,
    and does not clip against the outer border of its bounding canvas.
    """
    errors: List[str] = []
    if rgba_img.ndim != 3 or rgba_img.shape[2] != 4:
        return MaskValidationResult(
            valid=False,
            non_empty_ratio=0.0,
            bbox=(0, 0, 0, 0),
            edge_smoothness_score=0.0,
            touches_border=True,
            sha256="",
            errors=["Image does not have 4 RGBA channels"],
        )

    h, w = rgba_img.shape[:2]
    alpha = rgba_img[:, :, 3]
    fg = alpha > 32
    non_empty_ratio = float(np.count_nonzero(fg)) / float(h * w)
    if non_empty_ratio < 0.03:
        errors.append(f"Mask non-empty ratio too small ({non_empty_ratio:.4f})")
    if non_empty_ratio > 0.92:
        errors.append(f"Mask fills almost entire frame ({non_empty_ratio:.4f}), likely missing transparency")

    ys, xs = np.where(fg)
    if len(xs) == 0:
        return MaskValidationResult(
            valid=False,
            non_empty_ratio=0.0,
            bbox=(0, 0, 0, 0),
            edge_smoothness_score=0.0,
            touches_border=False,
            sha256=compute_array_sha256(rgba_img),
            errors=["Completely empty alpha mask"],
        )

    x1, x2 = int(xs.min()), int(xs.max())
    y1, y2 = int(ys.min()), int(ys.max())
    bbox = (x1, y1, x2 - x1 + 1, y2 - y1 + 1)

    touches_border = (x1 <= 2) or (y1 <= 2) or (x2 >= w - 3) or (y2 >= h - 3)
    if touches_border:
        errors.append("Subject touches or clips against canvas border")

    contours, _ = cv2.findContours((fg.astype(np.uint8) * 255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    smoothness = 1.0
    if contours:
        largest = max(contours, key=cv2.contourArea)
        perim = max(cv2.arcLength(largest, True), 1.0)
        hull = cv2.convexHull(largest)
        hull_perim = max(cv2.arcLength(hull, True), 1.0)
        smoothness = float(min(1.0, hull_perim / perim))

    return MaskValidationResult(
        valid=len(errors) == 0,
        non_empty_ratio=round(non_empty_ratio, 4),
        bbox=bbox,
        edge_smoothness_score=round(smoothness, 4),
        touches_border=touches_border,
        sha256=compute_array_sha256(rgba_img),
        errors=errors,
    )


def extract_missing_piece_bundle(
    full_animal_rgba: np.ndarray,
    slice_x_ratio: Tuple[float, float] = (0.27, 0.51),
    placeholder_color: Tuple[int, int, int, int] = (255, 232, 0, 255),
    border_color: Tuple[int, int, int, int] = (25, 25, 30, 255),
    border_width: int = 4,
) -> MissingPieceBundle:
    """
    Implements Template B (MISSING_PIECE_SLIDE) vertical slice masking and verifies
    pixel-perfect restoration (MAD == 0.0) when aligned.
    """
    h, w = full_animal_rgba.shape[:2]
    alpha = full_animal_rgba[:, :, 3]
    fg = alpha > 40
    ys, xs = np.where(fg)
    if len(xs) == 0:
        raise ValueError("Cannot extract missing piece from empty RGBA image")

    ax1, ax2 = int(xs.min()), int(xs.max())
    aw = ax2 - ax1 + 1

    sx1 = int(round(ax1 + aw * slice_x_ratio[0]))
    sx2 = int(round(ax1 + aw * slice_x_ratio[1]))
    sx1 = max(0, min(w - 2, sx1))
    sx2 = max(sx1 + 20, min(w, sx2))

    band_mask = np.zeros((h, w), dtype=np.uint8)
    band_mask[:, sx1:sx2] = 255
    piece_mask = cv2.bitwise_and(band_mask, (alpha > 0).astype(np.uint8) * 255)

    pys, _ = np.where(piece_mask > 0)
    sy1, sy2 = int(pys.min()), int(pys.max()) + 1

    extracted_piece_rgba = np.zeros((sy2 - sy1, sx2 - sx1, 4), dtype=np.uint8)
    extracted_piece_rgba[:, :] = full_animal_rgba[sy1:sy2, sx1:sx2]

    base_rgba = full_animal_rgba.copy()
    animal_binary = (alpha > 96).astype(np.uint8) * 255
    eroded_interior = cv2.erode(
        animal_binary,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (border_width * 2 + 1, border_width * 2 + 1)),
        iterations=1,
    )
    outer_contour_ring = (animal_binary > 0) & (eroded_interior == 0)

    slice_region = np.zeros((h, w), dtype=bool)
    slice_region[:, sx1:sx2] = True

    interior_slice = slice_region & (eroded_interior > 0)
    contour_slice = slice_region & outer_contour_ring

    base_rgba[interior_slice] = placeholder_color
    base_rgba[contour_slice] = border_color

    restored = base_rgba.copy()
    piece_nonzero = extracted_piece_rgba[:, :, 3] > 0
    target_view = restored[sy1:sy2, sx1:sx2]
    target_view[piece_nonzero] = extracted_piece_rgba[piece_nonzero]

    mad = float(np.mean(np.abs(restored.astype(np.float32) - full_animal_rgba.astype(np.float32))))

    return MissingPieceBundle(
        full_animal_rgba=full_animal_rgba,
        base_with_placeholder_rgba=base_rgba,
        extracted_piece_rgba=extracted_piece_rgba,
        mask_binary=piece_mask,
        slice_bounds=(sx1, sy1, sx2, sy2),
        alignment_target_xy=(sx1, sy1),
        pixel_match_mad=round(mad, 6),
    )


def extract_horizontal_slice_bundle(
    full_face_rgba: np.ndarray,
    slice_y_ratio: Tuple[float, float] = (0.30, 0.54),
    placeholder_color: Tuple[int, int, int, int] = (255, 232, 0, 255),
    border_color: Tuple[int, int, int, int] = (25, 25, 30, 255),
    border_width: int = 4,
) -> MissingPieceBundle:
    """
    Implements Template C (FACE_FEATURE_SLIDE) horizontal facial-feature band masking
    (e.g., Celebrity Eyes & Nose-Bridge band sliding horizontally into the portrait)
    and verifies pixel-perfect restoration (MAD == 0.0) when aligned.
    """
    h, w = full_face_rgba.shape[:2]
    alpha = full_face_rgba[:, :, 3]
    fg = alpha > 40
    ys, xs = np.where(fg)
    if len(ys) == 0:
        raise ValueError("Cannot extract horizontal face slice from empty RGBA image")

    ay1, ay2 = int(ys.min()), int(ys.max())
    ah = ay2 - ay1 + 1

    sy1 = int(round(ay1 + ah * slice_y_ratio[0]))
    sy2 = int(round(ay1 + ah * slice_y_ratio[1]))
    sy1 = max(0, min(h - 2, sy1))
    sy2 = max(sy1 + 20, min(h, sy2))

    band_mask = np.zeros((h, w), dtype=np.uint8)
    band_mask[sy1:sy2, :] = 255
    piece_mask = cv2.bitwise_and(band_mask, (alpha > 0).astype(np.uint8) * 255)

    _, pxs = np.where(piece_mask > 0)
    sx1, sx2 = int(pxs.min()), int(pxs.max()) + 1

    extracted_piece_rgba = np.zeros((sy2 - sy1, sx2 - sx1, 4), dtype=np.uint8)
    extracted_piece_rgba[:, :] = full_face_rgba[sy1:sy2, sx1:sx2]

    base_rgba = full_face_rgba.copy()
    face_binary = (alpha > 96).astype(np.uint8) * 255
    eroded_interior = cv2.erode(
        face_binary,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (border_width * 2 + 1, border_width * 2 + 1)),
        iterations=1,
    )
    outer_contour_ring = (face_binary > 0) & (eroded_interior == 0)

    slice_region = np.zeros((h, w), dtype=bool)
    slice_region[sy1:sy2, :] = True

    interior_slice = slice_region & (eroded_interior > 0)
    contour_slice = slice_region & outer_contour_ring

    base_rgba[interior_slice] = placeholder_color
    base_rgba[contour_slice] = border_color

    restored = base_rgba.copy()
    piece_nonzero = extracted_piece_rgba[:, :, 3] > 0
    target_view = restored[sy1:sy2, sx1:sx2]
    target_view[piece_nonzero] = extracted_piece_rgba[piece_nonzero]

    mad = float(np.mean(np.abs(restored.astype(np.float32) - full_face_rgba.astype(np.float32))))

    return MissingPieceBundle(
        full_animal_rgba=full_face_rgba,
        base_with_placeholder_rgba=base_rgba,
        extracted_piece_rgba=extracted_piece_rgba,
        mask_binary=piece_mask,
        slice_bounds=(sx1, sy1, sx2, sy2),
        alignment_target_xy=(sx1, sy1),
        pixel_match_mad=round(mad, 6),
    )


def extract_three_band_face_bundle(
    full_face_rgba: np.ndarray,
    split_ratios: Tuple[float, float] = (0.37, 0.64),
    guide_outline_color: Tuple[int, int, int, int] = (24, 58, 245, 255),
) -> ThreeBandFaceBundle:
    """
    Implements Template D (FACE_SPLIT_3BAND): splits a Celebrity/Person portrait into 3 horizontal
    anatomical bands (Forehead/Hair, Eyes/Nose, Mouth/Chin) that slide in opposing horizontal phases
    and lock into pixel-perfect alignment (MAD == 0.0) at the target frame.
    """
    h, w = full_face_rgba.shape[:2]
    alpha = full_face_rgba[:, :, 3]
    fg = alpha > 0
    ys, xs = np.where(fg)
    if len(ys) == 0:
        raise ValueError("Cannot split empty RGBA image into 3 face bands")

    ay1, ay2 = int(ys.min()), int(ys.max()) + 1
    ax1, ax2 = int(xs.min()), int(xs.max()) + 1
    ah = ay2 - ay1

    y_mid1 = max(ay1 + 10, min(ay2 - 20, int(round(ay1 + ah * split_ratios[0]))))
    y_mid2 = max(y_mid1 + 10, min(ay2 - 10, int(round(ay1 + ah * split_ratios[1]))))

    ranges = [(ay1, y_mid1), (y_mid1, y_mid2), (y_mid2, ay2)]
    bands: List[np.ndarray] = []
    targets: List[Tuple[int, int]] = []
    bounds: List[Tuple[int, int, int, int]] = []

    restored = np.zeros_like(full_face_rgba)
    for by1, by2 in ranges:
        sub = full_face_rgba[by1:by2, ax1:ax2].copy()
        bands.append(sub)
        targets.append((ax1, by1))
        bounds.append((ax1, by1, ax2, by2))
        restored[by1:by2, ax1:ax2] = sub

    mad = float(np.mean(np.abs(restored.astype(np.float32) - full_face_rgba.astype(np.float32))))
    guide_outline = generate_outline_silhouette_rgba(
        full_face_rgba,
        outline_color=guide_outline_color,
        outline_width=7,
    )

    return ThreeBandFaceBundle(
        full_face_rgba=full_face_rgba,
        guide_outline_rgba=guide_outline,
        band_top_rgba=bands[0],
        band_mid_rgba=bands[1],
        band_bot_rgba=bands[2],
        band_targets_xy=targets,
        band_bounds=bounds,
        pixel_match_mad=round(mad, 6),
    )
