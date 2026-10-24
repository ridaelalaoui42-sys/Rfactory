"""Rfactory 3 — canonical-source puzzle geometry, pixel-exact by construction.

Mask geometry does NOT hallucinate fragment texture: original pixels are
cut from a single accepted source illustration and restored byte-for-byte.
This module has no AI, network or mutable global state.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Literal

import cv2
import numpy as np

GeometryName = Literal[
    "rectangle", "ellipse", "organic", "jigsaw", "curved_band",
    "hexagon", "ring_sector", "triangle",
]
GEOMETRIES = (
    "rectangle", "ellipse", "organic", "jigsaw",
    "curved_band", "hexagon", "ring_sector", "triangle",
)


@dataclass(frozen=True)
class Fragment:
    source_sha256: str
    geometry: str
    bounds_xywh: tuple[int, int, int, int]
    piece_rgba: np.ndarray
    base_rgba: np.ndarray
    mask: np.ndarray

    def reconstruct(self) -> np.ndarray:
        x, y, w, h = self.bounds_xywh
        result = self.base_rgba.copy()
        area = result[y:y+h, x:x+w]
        area[self.mask > 0] = self.piece_rgba[self.mask > 0]
        return result

    def validate_against(self, source: np.ndarray) -> None:
        if hashlib.sha256(source.tobytes()).hexdigest() != self.source_sha256:
            raise ValueError("Fragment is tied to a different canonical source")
        if not np.array_equal(self.reconstruct(), source):
            raise AssertionError("Puzzle fragment cannot reconstruct canonical art")


def _binary_mask(shape: tuple[int, int], geometry: str, seed: int) -> np.ndarray:
    h, w = shape
    if geometry not in GEOMETRIES:
        raise ValueError(f"Unsupported geometry: {geometry}")
    if h < 18 or w < 18:
        raise ValueError("Puzzle fragment must be at least 18x18")
    m = np.zeros((h, w), np.uint8)
    cx, cy = w // 2, h // 2
    margin = max(3, int(min(w, h) * .06))
    x1, y1, x2, y2 = margin, margin, w - margin - 1, h - margin - 1
    if geometry == "rectangle":
        cv2.rectangle(m, (x1,y1), (x2,y2), 255, -1)
    elif geometry == "ellipse":
        cv2.ellipse(m, (cx,cy), ((x2-x1)//2,(y2-y1)//2), 0, 0, 360, 255, -1)
    elif geometry == "organic":
        rng = np.random.default_rng(seed)
        points = []
        for i in range(72):
            ang = 2 * math.pi * i / 72
            radial = 0.79 + .075 * math.sin(3*ang + seed%13) + .04 * math.sin(7*ang)
            radial += float(rng.uniform(-.015, .015))
            points.append((int(cx + radial*(w*.47)*math.cos(ang)),
                           int(cy + radial*(h*.47)*math.sin(ang))))
        cv2.fillPoly(m, [np.array(points,np.int32)], 255)
    elif geometry == "jigsaw":
        edge = max(6,min(w,h)//10)
        cv2.rectangle(m, (x1+edge,y1+edge), (x2-edge,y2-edge), 255, -1)
        cv2.circle(m,(cx,y1+edge),edge,255,-1)
        cv2.circle(m,(x2-edge,cy),edge,255,-1)
        cv2.circle(m,(cx,y2-edge),edge,0,-1)
        cv2.circle(m,(x1+edge,cy),edge,0,-1)
    elif geometry == "curved_band":
        thickness = max(5, int(h*.38))
        for x in range(x1,x2+1):
            ym = int(cy + .14*h*math.sin(2*math.pi*(x-x1)/max(1,x2-x1)))
            m[max(0,ym-thickness//2):min(h,ym+thickness//2),x] = 255
    elif geometry == "hexagon":
        pts=np.array([
            (cx,y1),(x2,cy-(y2-y1)//4),(x2,cy+(y2-y1)//4),
            (cx,y2),(x1,cy+(y2-y1)//4),(x1,cy-(y2-y1)//4)
        ],np.int32)
        cv2.fillPoly(m,[pts],255)
    elif geometry == "ring_sector":
        rx=max(7,(x2-x1)//2);ry=max(7,(y2-y1)//2)
        cv2.ellipse(m,(cx,cy),(rx,ry),0,25,300,255,-1)
        cv2.ellipse(m,(cx,cy),(max(1,int(rx*.55)),max(1,int(ry*.55))),0,0,360,0,-1)
    elif geometry == "triangle":
        cv2.fillPoly(m,[np.array([(cx,y1),(x2,y2),(x1,y2)],np.int32)],255)
    if int(cv2.countNonZero(m)) < 10:
        raise ValueError("Generated mask is empty")
    return m


def cut_exact_fragment(
    source_rgba: np.ndarray,
    bounds_xywh: tuple[int,int,int,int],
    geometry: str = "organic",
    seed: int = 0,
) -> Fragment:
    """Extract a positive fragment and its *same-source* negative hole.

    Pixel-perfect here means exact RGBA bytes restored at the identity pose.
    It does not imply H.264 decoding is pixel-lossless.
    """
    if source_rgba.dtype != np.uint8 or source_rgba.ndim != 3 or source_rgba.shape[2] != 4:
        raise ValueError("Canonical source must be uint8 RGBA")
    x,y,w,h = bounds_xywh
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x+w > source_rgba.shape[1] or y+h > source_rgba.shape[0]:
        raise ValueError("Fragment bounds outside canonical source")
    mask = _binary_mask((h,w),geometry,seed)
    crop = source_rgba[y:y+h,x:x+w].copy()
    piece = crop.copy()
    piece[mask==0] = (0,0,0,0)
    base = source_rgba.copy()
    base[y:y+h,x:x+w][mask>0] = (0,0,0,0)
    fragment=Fragment(
        source_sha256=hashlib.sha256(source_rgba.tobytes()).hexdigest(),
        geometry=geometry,
        bounds_xywh=bounds_xywh,
        piece_rgba=piece,
        base_rgba=base,
        mask=mask,
    )
    fragment.validate_against(source_rgba)
    return fragment


def cut_multiple_fragments(
    source_rgba: np.ndarray,
    specs: list[tuple[tuple[int,int,int,int],str,int]],
) -> tuple[np.ndarray, list[Fragment]]:
    """Prepare 2-5 independent nonoverlapping puzzle pieces.

    Overlapping positive masks are forbidden; the target still derives from
    exactly one canonical image, without regenerated or interpolated pixels.
    """
    if not 2 <= len(specs) <= 5:
        raise ValueError("Multi-piece puzzles require 2 to 5 fragments")
    coverage = np.zeros(source_rgba.shape[:2], np.uint8)
    pieces = []
    base = source_rgba.copy()
    for bounds, geometry, seed in specs:
        fragment=cut_exact_fragment(source_rgba,bounds,geometry,seed)
        x,y,w,h=bounds
        view=coverage[y:y+h,x:x+w]
        if np.any((view>0)&(fragment.mask>0)):
            raise ValueError("Puzzle pieces overlap")
        view[fragment.mask>0]=1
        base[y:y+h,x:x+w][fragment.mask>0]=(0,0,0,0)
        pieces.append(fragment)
    reconstructed=base.copy()
    for item in pieces:
        x,y,w,h=item.bounds_xywh
        reconstructed[y:y+h,x:x+w][item.mask>0]=item.piece_rgba[item.mask>0]
    if not np.array_equal(reconstructed,source_rgba):
        raise AssertionError("Multi-piece reconstruction failed")
    return base,pieces
