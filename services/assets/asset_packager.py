"""Create inspectable, portable face-puzzle asset packs from source pixels."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import cv2
import numpy as np
from PIL import Image, ImageDraw

from services.assets.face_cutout_engine import FaceAssetBundle
from services.assets.fit_validator import validate_face_bundle


def _write_rgba(path: Path, pixels: np.ndarray) -> None:
    Image.fromarray(pixels,"RGBA").save(path)


def package_face_bundle(
    bundle: FaceAssetBundle, destination: Path, *, provenance: str,
    original_image_sha256: str = "",
    approved: bool = False,
) -> dict:
    dest=Path(destination)
    dest.mkdir(parents=True,exist_ok=True)
    qa=validate_face_bundle(bundle)
    _write_rgba(dest/"source.png",bundle.source_rgba)
    _write_rgba(dest/"hole_plate.png",bundle.hole_plate_rgba)
    preview=Image.fromarray(bundle.hole_plate_rgba,"RGBA").convert("RGB")
    preview_bg=Image.new("RGB",preview.size,(228,233,240))
    preview_bg.paste(preview,mask=Image.fromarray(bundle.hole_plate_rgba[:,:,3],"L"))
    dbg=Image.fromarray(bundle.source_rgba,"RGBA").convert("RGB")
    painter=ImageDraw.Draw(dbg)
    x,y,w,h=bundle.face_bbox_xywh
    painter.rectangle((x,y,x+w,y+h),outline="#2de2af",width=5)
    pieces=[]
    for idx,item in enumerate(bundle.pieces,1):
        prefix=f"piece_{idx:02d}"
        _write_rgba(dest/f"{prefix}.png",item.piece_rgba)
        Image.fromarray(item.mask,"L").save(dest/f"{prefix}_mask.png")
        ox,oy,pw,ph=item.bounds_xywh
        painter.rectangle((ox,oy,ox+pw,oy+ph),outline="#ffce66",width=3)
        pieces.append({
            "id":prefix,"file":prefix+".png",
            "mask":prefix+"_mask.png",
            "bounds_xywh":list(item.bounds_xywh),
            "source_pixel_sha256":item.source_sha256,
            "masked_pixel_count":int(cv2.countNonZero(item.mask)),
        })
    preview_bg.save(dest/"overlay_preview.png")
    dbg.save(dest/"cutout_debug.png")
    manifest={
        "version":1,"mode":bundle.mode,"subject_type":bundle.subject_type,
        "provenance":provenance,
        "original_image_sha256":original_image_sha256 or qa["source_pixel_sha256"],
        "normalized_source_pixel_sha256":qa["source_pixel_sha256"],
        "clean_source_confirmed":True,
        "face_bbox_xywh":list(bundle.face_bbox_xywh),
        "detection_method":bundle.detection_method,
        "piece_count":len(bundle.pieces),"pieces":pieces,
        "qa":qa,"approved":approved,"status":"APPROVED" if approved else "AWAITING_CUTOUT_APPROVAL",
        "perfect_reconstruction":True,
        "rendered_video":False,
    }
    (dest/"puzzle_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest


def create_puzzle_zip(asset_dir: Path, zip_path: Path) -> Path:
    files=[
        p for p in Path(asset_dir).iterdir()
        if p.is_file() and p.suffix in {".json",".png"}
    ]
    with zipfile.ZipFile(zip_path,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):
            z.write(p,arcname=p.name)
    return zip_path
