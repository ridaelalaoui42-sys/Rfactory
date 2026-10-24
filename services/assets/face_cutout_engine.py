"""Face-aware original-source puzzle slicing.

Never request an AI model to draw cutouts. First approve one clean source,
then extract all pieces/masks from its actual pixels. Detection is best-effort:
human OpenCV face cascade if installed, otherwise explicitly labelled
proportional face estimate; caller can supply a reviewed normalized bbox.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from services.engine.puzzle_geometry import Fragment, cut_exact_fragment, cut_multiple_fragments

FaceMode = Literal[
    "animal_face_core", "animal_eye_band", "animal_muzzle_patch",
    "animal_forehead_patch", "human_eye_band", "human_nose_mouth_patch",
    "human_three_slice_face", "human_triangle_face_puzzle",
    "human_feature_fragments", "portrait_center_mask", "portrait_ring_segment",
    "portrait_cheek_patch",
]
FACE_MODES = (
    "animal_face_core", "animal_eye_band", "animal_muzzle_patch",
    "animal_forehead_patch", "human_eye_band", "human_nose_mouth_patch",
    "human_three_slice_face", "human_triangle_face_puzzle",
    "human_feature_fragments", "portrait_center_mask", "portrait_ring_segment",
    "portrait_cheek_patch",
)
ANIMAL_MODES = set(FACE_MODES[:4])
HUMAN_MODES = set(FACE_MODES[4:9])
MULTI_MODES = {"human_three_slice_face", "human_triangle_face_puzzle", "human_feature_fragments"}


@dataclass
class FaceAssetBundle:
    mode: str
    subject_type: str
    face_bbox_xywh: tuple[int, int, int, int]
    detection_method: str
    source_rgba: np.ndarray
    hole_plate_rgba: np.ndarray
    pieces: list[Fragment]
    pixel_match_mad: float

    def restored_rgba(self) -> np.ndarray:
        out = self.hole_plate_rgba.copy()
        for p in self.pieces:
            x, y, w, h = p.bounds_xywh
            region = out[y:y+h, x:x+w]
            region[p.mask > 0] = p.piece_rgba[p.mask > 0]
        return out


def estimate_face_bbox(
    rgba: np.ndarray,
    subject_type: str,
    manual_face_bbox: tuple[float, float, float, float] | None = None,
) -> tuple[tuple[int, int, int, int], str]:
    """Find face region, reporting whether coordinates were inferred or reviewed.

    Normalized manual bbox is (x,y,w,h). No animal face detector is claimed.
    Human Haar detection can fail, especially on illustration; manual override
    is expected for professional output.
    """
    if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("Expected original uint8 RGBA canonical artwork")
    if subject_type not in {"animal", "human", "portrait"}:
        raise ValueError("subject_type must be animal, human or portrait")
    height, width = rgba.shape[:2]
    if min(height, width) < 96:
        raise ValueError("Source image too small for meaningful face cutout")
    if manual_face_bbox is not None:
        if len(manual_face_bbox) != 4 or not all(np.isfinite(v) for v in manual_face_bbox):
            raise ValueError("Invalid normalized face coordinates")
        a,b,c,d = manual_face_bbox
        if a < 0 or b < 0 or c <= 0 or d <= 0 or a+c > 1 or b+d > 1:
            raise ValueError("Face coordinates exceed original image")
        return (
            round(a * width), round(b * height),
            round(c * width), round(d * height)
        ), "operator_bbox"
    if subject_type == "human":
        # Optional OpenCV face classifier (bundled with opencv-python) does not
        # require model downloads and doesn't modify source image.
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        clf = cv2.CascadeClassifier(cascade_path)
        if not clf.empty():
            rgb = cv2.cvtColor(rgba, cv2.COLOR_RGBA2RGB)
            gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            detected = clf.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                            minSize=(max(50,width//9),max(50,height//9)))
            if len(detected):
                x,y,w,h = max(detected, key=lambda box: int(box[2]*box[3]))
                pad_w, pad_h = round(w*.12), round(h*.16)
                x2 = min(width, x+w+pad_w)
                y2 = min(height, y+h+pad_h)
                x, y = max(0,x-pad_w),max(0,y-pad_h)
                return (int(x),int(y),int(x2-x),int(y2-y)), "opencv_haar_face"
    # Proportional estimate is visibly disclosed, never marketed as
    # ML-detected or artist-reviewed. Isolated close portraits work best.
    if subject_type == "animal":
        bbox = (.24, .12, .52, .48)
    else:
        bbox = (.22, .11, .56, .65)
    x,y,w,h = bbox
    return (
        round(x*width),round(y*height),round(w*width),round(h*height)
    ), "unverified_proportional_estimate"


def _region(
    face: tuple[int,int,int,int],
    fx: float, fy: float, fw: float, fh: float,
    source_wh: tuple[int,int],
) -> tuple[int,int,int,int]:
    x,y,w,h = face
    sw, sh = source_wh
    rx = max(0,min(sw-18,round(x+fx*w)))
    ry = max(0,min(sh-18,round(y+fy*h)))
    rw = max(18,min(sw-rx,round(fw*w)))
    rh = max(18,min(sh-ry,round(fh*h)))
    return (rx,ry,rw,rh)


def face_cutout(
    source_rgba: np.ndarray,
    mode: str,
    *,
    subject_type: str,
    seed: int = 0,
    face_bbox_norm: tuple[float,float,float,float] | None = None,
) -> FaceAssetBundle:
    """Generate 1–3 face-centered, exactly reconstructable source pieces."""
    if mode not in FACE_MODES:
        raise ValueError(f"Unsupported face cutout mode: {mode}")
    if mode in ANIMAL_MODES and subject_type != "animal":
        raise ValueError("Animal mode requires animal subject type")
    if mode in HUMAN_MODES and subject_type != "human":
        raise ValueError("Human mode requires human subject type")
    source = source_rgba.copy()
    height,width=source.shape[:2]
    face, method = estimate_face_bbox(source, subject_type, face_bbox_norm)
    shape = {
        "animal_face_core": [(.13,.16,.74,.69,"organic")],
        "animal_eye_band": [(.06,.27,.88,.26,"curved_band")],
        "animal_muzzle_patch": [(.20,.54,.60,.33,"organic")],
        "animal_forehead_patch": [(.22,.05,.56,.31,"organic")],
        "human_eye_band": [(.06,.28,.88,.24,"curved_band")],
        "human_nose_mouth_patch": [(.23,.46,.54,.40,"organic")],
        "human_three_slice_face": [
            (.10,.18,.80,.18,"curved_band"),
            (.10,.42,.80,.18,"curved_band"),
            (.10,.68,.80,.19,"curved_band"),
        ],
        "human_triangle_face_puzzle": [
            (.16,.18,.35,.30,"triangle"),
            (.54,.18,.32,.30,"triangle"),
            (.32,.53,.38,.34,"triangle"),
        ],
        "human_feature_fragments": [
            (.10,.28,.80,.20,"curved_band"),
            (.34,.53,.32,.17,"organic"),
            (.22,.75,.56,.14,"organic"),
        ],
        "portrait_center_mask": [(.20,.21,.62,.56,"ellipse")],
        "portrait_ring_segment": [(.08,.12,.84,.74,"ring_sector")],
        "portrait_cheek_patch": [(.52,.44,.35,.33,"organic")],
    }[mode]
    specs=[
        (_region(face, fx,fy,fw,fh,(width,height)),geom,seed+i*23)
        for i,(fx,fy,fw,fh,geom) in enumerate(shape)
    ]
    if mode in MULTI_MODES:
        base, parts = cut_multiple_fragments(source,specs)
    else:
        part = cut_exact_fragment(source,*specs[0])
        base, parts = part.base_rgba,[part]
    bundle=FaceAssetBundle(
        mode=mode, subject_type=subject_type, face_bbox_xywh=face,
        detection_method=method, source_rgba=source,
        hole_plate_rgba=base, pieces=parts, pixel_match_mad=0.0,
    )
    if not np.array_equal(bundle.restored_rgba(),source):
        raise AssertionError("Face puzzle does not reconstruct original source")
    if not np.all(np.isin(np.unique(np.concatenate([p.mask.ravel() for p in parts])),[0,255])):
        raise AssertionError("Masks must be hard binary")
    return bundle
