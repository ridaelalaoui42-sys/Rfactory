"""Pure source-pixel validation of face-cutout bundles, including multi-piece."""
from __future__ import annotations

import hashlib

import cv2
import numpy as np

from services.assets.face_cutout_engine import FaceAssetBundle


def validate_face_bundle(bundle: FaceAssetBundle) -> dict:
    source=bundle.source_rgba
    height,width=source.shape[:2]
    if not 1 <= len(bundle.pieces) <= 5:
        raise AssertionError("Expected 1-5 pieces")
    coverage=np.zeros((height,width),dtype=np.uint8)
    bad_alpha=0
    pixels_moved=0
    for i,part in enumerate(bundle.pieces):
        x,y,w,h=part.bounds_xywh
        if not (0<=x and 0<=y and x+w<=width and y+h<=height):
            raise AssertionError(f"Piece {i} outside source")
        if part.piece_rgba.shape[:2]!=(h,w) or part.mask.shape!=(h,w):
            raise AssertionError("Piece geometry dimension mismatch")
        if part.mask.dtype!=np.uint8 or not np.all(np.isin(part.mask,(0,255))):
            raise AssertionError("Nonbinary mask")
        coverage_roi=coverage[y:y+h,x:x+w]
        if np.any((coverage_roi>0)&(part.mask>0)):
            raise AssertionError("Overlapping fragments")
        coverage_roi[part.mask>0]=1
        if not np.array_equal(part.piece_rgba[part.mask>0],source[y:y+h,x:x+w][part.mask>0]):
            raise AssertionError("Source-color mismatch in extracted piece")
        if not np.all(part.piece_rgba[part.mask==0]==0):
            raise AssertionError("Nontransparent outside piece mask")
        # The negative plate must have an ACTUAL transparent hole. Otherwise
        # an overpainted fake cutout can reconstruct while still displaying
        # the complete face underneath the moving piece.
        if not np.all(bundle.hole_plate_rgba[y:y+h,x:x+w][part.mask>0] == 0):
            raise AssertionError("Hole plate retains pixels inside removed fragment")
        pixels_moved+=int(cv2.countNonZero(part.mask))
        if pixels_moved==0:
            raise AssertionError("Empty face fragment")
    restored=bundle.restored_rgba()
    different=np.abs(restored.astype(np.int16)-source.astype(np.int16))
    mad=float(different.mean())
    if mad!=0 or not np.array_equal(restored,source):
        raise AssertionError(f"RGBA reconstruction failed with MAD {mad}")
    return {
        "valid":True,"piece_count":len(bundle.pieces),
        "source_pixel_sha256":hashlib.sha256(source.tobytes()).hexdigest(),
        "restored_pixel_sha256":hashlib.sha256(restored.tobytes()).hexdigest(),
        "exact_raw_rgba_mad":mad,
        "source_dimensions":[width,height],
        "face_bbox_xywh":list(bundle.face_bbox_xywh),
        "detector":bundle.detection_method,
        "masked_pixel_count":pixels_moved,
        "no_mask_overlaps":True,
        "edge_policy":"hard_binary_alpha; no inverse-resampling at solved pose",
    }
