"""One canonical face canvas for BOTH asset review and final video output.

Never resize a reviewed mask independently of its original image. Use this
letterboxed canvas for all preview/cutout generation and rendered face puzzles.
This prevents preview-to-MP4 shifts, nonuniform facial stretching and mask
resampling.
"""
from __future__ import annotations

import cv2
import numpy as np

FACE_CANVAS_WH = (860, 860)


def prepare_face_canvas(
    original: np.ndarray,
    face_bbox_norm: tuple[float, float, float, float] | None = None,
    canvas_wh: tuple[int, int] = FACE_CANVAS_WH,
) -> tuple[np.ndarray, tuple[float,float,float,float] | None]:
    if original.ndim != 3 or original.shape[2] != 4 or original.dtype != np.uint8:
        raise ValueError("Original image must be uint8 RGBA")
    target_w, target_h = canvas_wh
    if min(target_w,target_h) < 96:
        raise ValueError("Canvas is too small for a face")
    orig_h,orig_w=original.shape[:2]
    scale=min(target_w/orig_w,target_h/orig_h)
    new_w=max(1,round(orig_w*scale))
    new_h=max(1,round(orig_h*scale))
    resized=cv2.resize(original,(new_w,new_h),interpolation=cv2.INTER_LANCZOS4)
    canvas=np.zeros((target_h,target_w,4),dtype=np.uint8)
    pad_x=(target_w-new_w)//2
    pad_y=(target_h-new_h)//2
    canvas[pad_y:pad_y+new_h,pad_x:pad_x+new_w]=resized
    mapped=None
    if face_bbox_norm is not None:
        if len(face_bbox_norm)!=4 or not all(np.isfinite(x) for x in face_bbox_norm):
            raise ValueError("Invalid original face bounding box")
        x,y,w,h=face_bbox_norm
        if x<0 or y<0 or w<=0 or h<=0 or x+w>1 or y+h>1:
            raise ValueError("Face coordinates outside original image")
        mapped=(
            (pad_x+x*new_w)/target_w,
            (pad_y+y*new_h)/target_h,
            w*new_w/target_w,
            h*new_h/target_h,
        )
    return canvas,mapped
