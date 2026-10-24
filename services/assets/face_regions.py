"""Face-aware region selection with explicit provenance and review requirements.

Human portraits: OpenCV Haar-cascade assisted discovery if available.
Animals: manually supplied face rectangle preferred. Otherwise an *estimated*
portrait region is produced and flagged for review, never claimed as detected.
All rectangles are integer pixel bounds in the unchanged canonical source.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal
import cv2
import numpy as np

Kind = Literal["animal", "human", "portrait"]
BBox = tuple[int, int, int, int]

@dataclass(frozen=True)
class FaceRegion:
    bbox: BBox
    method: str
    needs_review: bool
    confidence: float
    def manifest(self) -> dict:
        return asdict(self)

def validate_bbox(box: BBox, image_shape: tuple[int, ...]) -> BBox:
    if len(box) != 4 or any(type(v) is not int for v in box):
        raise ValueError("Face bbox must contain four integer pixel coordinates")
    x,y,w,h=box
    height,width=image_shape[:2]
    if x < 0 or y < 0 or w < 18 or h < 18 or x+w>width or y+h>height:
        raise ValueError("Face bbox is outside source or too small")
    return box

def find_face(image_rgba: np.ndarray, kind: Kind, bbox: BBox | None = None) -> FaceRegion:
    if image_rgba.dtype != np.uint8 or image_rgba.ndim != 3 or image_rgba.shape[2] not in (3,4):
        raise ValueError("Expected a real uint8 RGB/RGBA source")
    if kind not in ("animal", "human", "portrait"):
        raise ValueError("Unknown subject kind")
    h,w=image_rgba.shape[:2]
    if bbox is not None:
        return FaceRegion(validate_bbox(bbox, image_rgba.shape),"operator_annotated",False,1.0)
    if kind in ("human","portrait"):
        try:
            gray=cv2.cvtColor(image_rgba, cv2.COLOR_RGBA2GRAY if image_rgba.shape[2]==4 else cv2.COLOR_RGB2GRAY)
            classifier=cv2.CascadeClassifier(cv2.data.haarcascades+"haarcascade_frontalface_default.xml")
            faces=classifier.detectMultiScale(gray,scaleFactor=1.08,minNeighbors=5,minSize=(max(25,w//9),max(25,h//9)))
            if len(faces):
                candidate=sorted(faces,key=lambda f:int(f[2])*int(f[3]),reverse=True)[0]
                box=tuple(int(v) for v in candidate)
                return FaceRegion(validate_bbox(box,image_rgba.shape),"opencv_frontal_face",True,0.75)
        except (AttributeError,cv2.error,ValueError):
            pass
    # Estimate for UX preview only. Approval requires operator confirmation;
    # face detection is NOT reliably solved for arbitrary animal species.
    box=(int(w*.24),int(h*.14),int(w*.52),int(h*.43))
    box=validate_bbox(box,image_rgba.shape)
    return FaceRegion(box,"unverified_composition_heuristic",True,0.0)

def normalized_bbox(box: BBox, width: int, height: int) -> tuple[float,float,float,float]:
    x,y,w,h=box
    return (round(x/width,6),round(y/height,6),round(w/width,6),round(h/height,6))

def source_bbox(ratios: tuple[float,float,float,float], width:int,height:int) -> BBox:
    if len(ratios)!=4 or any(not isinstance(v,(float,int)) for v in ratios):
        raise ValueError("Face ratios must contain four numbers")
    x,y,w,h=ratios
    if any(not np.isfinite(v) for v in ratios) or min(x,y,w,h)<0 or x+w>1.000001 or y+h>1.000001:
        raise ValueError("Face ratios must fit within source bounds")
    return validate_bbox((round(x*width),round(y*height),round(w*width),round(h*height)),(height,width,4))
