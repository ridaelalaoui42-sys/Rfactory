"""Load the EXACT reviewed cutout PNGs into the renderer, never recut them.

All assets are read under a private generated pack ID. Approval hashes pin
source, hole plate, mask and piece bytes. The source is compared against the
image currently selected from the approved artwork library. A changed pixel,
incorrect mask or mismatched source blocks rendering.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image

from services.assets.face_cutout_engine import FaceAssetBundle
from services.assets.fit_validator import validate_face_bundle
from services.engine.puzzle_geometry import Fragment

_ID = re.compile(r"^face_[a-f0-9]{24}$")
_FILE = re.compile(r"^piece_0[1-5](?:_mask)?\.png$")
_FIXED = {"source.png", "hole_plate.png"}


class CutoutIntegrityError(ValueError):
    pass


def _directory(storage_root: Path, pack_id: str) -> Path:
    if not _ID.fullmatch(pack_id):
        raise CutoutIntegrityError("Invalid reviewed cutout identifier")
    return Path(storage_root) / "cutout_packs" / pack_id


def manifest_and_files(storage_root: Path, pack_id: str) -> tuple[Path,dict,list[str]]:
    root = _directory(storage_root,pack_id)
    path = root / "puzzle_manifest.json"
    if not path.is_file():
        raise CutoutIntegrityError("Reviewed cutout pack does not exist")
    manifest=json.loads(path.read_text(encoding="utf-8"))
    pieces=manifest.get("pieces", [])
    if not isinstance(pieces,list) or not 1 <= len(pieces) <= 5:
        raise CutoutIntegrityError("Cutout pack requires 1–5 fragments")
    members=["source.png","hole_plate.png"]
    for item in pieces:
        for key in ("file","mask"):
            name=item.get(key)
            if not isinstance(name,str) or not _FILE.fullmatch(name):
                raise CutoutIntegrityError("Invalid cutout media filename")
            members.append(name)
    if len(set(members))!=len(members):
        raise CutoutIntegrityError("Duplicated media filenames")
    return root,manifest,members


def file_hashes(root: Path, members: list[str]) -> dict[str,str]:
    result={}
    for name in members:
        media=(root/name).resolve()
        if not media.is_relative_to(root.resolve()) or not media.is_file():
            raise CutoutIntegrityError("A cutout PNG is missing or outside its pack")
        if media.stat().st_size > 16*1024*1024:
            raise CutoutIntegrityError("Oversized reviewed cutout PNG")
        result[name]=hashlib.sha256(media.read_bytes()).hexdigest()
    return result


def load_reviewed_face_pack(
    storage_root: Path,
    pack_id: str,
    *,
    expected_canonical_rgba: np.ndarray,
    expected_original_sha256: str,
    require_approved: bool = True,
) -> FaceAssetBundle:
    root,manifest,members=manifest_and_files(storage_root,pack_id)
    if require_approved and (
        not manifest.get("approved") or manifest.get("status")!="APPROVED"
    ):
        raise CutoutIntegrityError("Face cutout is not approved")
    if manifest.get("original_image_sha256") != expected_original_sha256:
        raise CutoutIntegrityError("Face pack belongs to a different original image")
    expected_hashes=manifest.get("approved_media_sha256")
    actual_hashes=file_hashes(root,members)
    if require_approved and expected_hashes != actual_hashes:
        raise CutoutIntegrityError("Reviewed PNGs changed after approval")

    def rgba(name:str)->np.ndarray:
        with Image.open(root/name) as img:
            return np.asarray(img.convert("RGBA"),dtype=np.uint8).copy()

    source=rgba("source.png")
    if source.shape!=expected_canonical_rgba.shape or not np.array_equal(source,expected_canonical_rgba):
        raise CutoutIntegrityError("Approved cutout uses different normalized source pixels")
    plate=rgba("hole_plate.png")
    if plate.shape!=source.shape:
        raise CutoutIntegrityError("Hole plate dimensions do not match source")
    source_sha=hashlib.sha256(source.tobytes()).hexdigest()
    if source_sha!=manifest.get("normalized_source_pixel_sha256"):
        raise CutoutIntegrityError("Approved canonical source pixel hash differs")

    fragments=[]
    for info in manifest["pieces"]:
        box=info.get("bounds_xywh")
        if not isinstance(box,list) or len(box)!=4 or not all(isinstance(n,int) for n in box):
            raise CutoutIntegrityError("Invalid fragment bounding box")
        x,y,w,h=box
        if x<0 or y<0 or w<1 or h<1 or x+w>source.shape[1] or y+h>source.shape[0]:
            raise CutoutIntegrityError("Fragment is outside canonical canvas")
        piece=rgba(info["file"])
        with Image.open(root/info["mask"]) as mask_image:
            if mask_image.mode != "L":
                raise CutoutIntegrityError("Fragment mask is not a binary greyscale PNG")
            mask=np.asarray(mask_image,dtype=np.uint8).copy()
        if piece.shape[:2]!=(h,w) or mask.shape!=(h,w):
            raise CutoutIntegrityError("Fragment geometry differs from reviewed mask")
        fragments.append(Fragment(
            source_sha256=source_sha,geometry="reviewed_face",
            bounds_xywh=(x,y,w,h),piece_rgba=piece,
            base_rgba=plate,mask=mask,
        ))
    box=manifest.get("face_bbox_xywh")
    if not isinstance(box,list) or len(box)!=4:
        raise CutoutIntegrityError("Face detection coordinates missing")
    bundle=FaceAssetBundle(
        mode=manifest["mode"],subject_type=manifest["subject_type"],
        face_bbox_xywh=tuple(box),
        detection_method=manifest.get("detection_method","reviewed_pack"),
        source_rgba=source,hole_plate_rgba=plate,
        pieces=fragments,pixel_match_mad=0.0,
    )
    try:
        result=validate_face_bundle(bundle)
    except (AssertionError,ValueError) as exc:
        raise CutoutIntegrityError("Reviewed cutout failed exact-pixel validation") from exc
    if result["exact_raw_rgba_mad"]!=0:
        raise CutoutIntegrityError("Exact restoration must be lossless")
    return bundle
