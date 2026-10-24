"""Normalize pristine original artwork for Rfactory face-puzzle assets.

Requires operator confirmation of clean, uncut source. Baked-in fake jigsaw
or collage detection cannot be guaranteed algorithmically and is NOT claimed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError


@dataclass(frozen=True)
class CanonicalImage:
    rgba: np.ndarray
    sha256: str
    width: int
    height: int
    subject_bbox_xywh: tuple[int,int,int,int]
    provenance: str
    clean_source_confirmed: bool
    segmentation_method: str


def canonicalize_image(
    image_bytes: bytes,
    *,
    provenance: str,
    clean_source_confirmed: bool,
    minimum_side: int = 512,
) -> CanonicalImage:
    if not clean_source_confirmed:
        raise ValueError("Operator must confirm source contains no baked-in puzzle pieces")
    if not 3 <= len(provenance) <= 180:
        raise ValueError("Source provenance is required")
    if not 0 < len(image_bytes) <= 16*1024*1024:
        raise ValueError("Source image must be 1 byte to 16MB")
    try:
        with Image.open(io.BytesIO(image_bytes)) as pil:
            pil.load()
            if pil.format not in {"PNG","JPEG","WEBP"}:
                raise ValueError("Source must be PNG, JPEG or WebP")
            if pil.width * pil.height > 24_000_000 or min(pil.size) < minimum_side:
                raise ValueError("Source image resolution below configured quality threshold")
            rgba = np.asarray(pil.convert("RGBA"),dtype=np.uint8).copy()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Not a valid image") from exc
    h,w=rgba.shape[:2]
    visible = (rgba[:,:,3] > 16).astype(np.uint8)
    nz=cv2.findNonZero(visible)
    if nz is None:
        raise ValueError("Image contains no visible subject")
    x,y,bw,bh=cv2.boundingRect(nz)
    if bw*bh < .02*w*h:
        raise ValueError("Source subject covers less than two percent of canvas")
    return CanonicalImage(
        rgba=rgba,sha256=hashlib.sha256(rgba.tobytes()).hexdigest(),
        width=w,height=h,subject_bbox_xywh=(x,y,bw,bh),
        provenance=provenance,clean_source_confirmed=True,
        segmentation_method="alpha_channel" if (visible==0).any() else "opaque_source",
    )
