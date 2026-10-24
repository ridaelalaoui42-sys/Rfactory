"""Authenticated face-aware cutout factory API.

Approved HD library image -> operator-confirmed clean canonical source ->
real masks + hole plates + exact pieces -> review -> approved pack ->
video renderer. No AI-generated puzzle seam is ever accepted as geometry.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.api.library_routes import get_library
from services.assets.library import AssetLibrary, LibraryError
from services.assets.canonical_builder import canonicalize_image
from services.assets.face_canvas import prepare_face_canvas
from services.assets.approved_face_pack import load_reviewed_face_pack, manifest_and_files, file_hashes, CutoutIntegrityError
from services.assets.face_cutout_engine import FACE_MODES, face_cutout
from services.assets.asset_packager import package_face_bundle, create_puzzle_zip

router=APIRouter(prefix="/api/v1/assets",tags=["Canonical Face Cutout Factory"])
PACK_ID=re.compile(r"^face_[a-f0-9]{24}$")
MEDIA={"source.png","hole_plate.png","overlay_preview.png","cutout_debug.png",
       "piece_01.png","piece_02.png","piece_03.png",
       "piece_01_mask.png","piece_02_mask.png","piece_03_mask.png"}


class FaceCutoutRequest(BaseModel):
    asset_id: str = Field(min_length=32,max_length=32)
    mode: str
    subject_type: Literal["animal","human","portrait"]
    clean_source_confirmed: bool = False
    acknowledge_source_license: bool = False
    face_bbox_norm: tuple[float,float,float,float] | None = None
    seed: int = Field(default=7103,ge=0,le=2**31-1)


def _pack_path(library: AssetLibrary, face_id: str) -> Path:
    if not PACK_ID.fullmatch(face_id):
        raise HTTPException(404,"Unknown cutout pack")
    return library.root.parent.parent/"cutout_packs"/face_id


def _manifest(library: AssetLibrary,face_id: str) -> dict:
    path=_pack_path(library,face_id)/"puzzle_manifest.json"
    if not path.is_file():
        raise HTTPException(404,"Cutout not found")
    return json.loads(path.read_text(encoding="utf8"))


@router.get("/face-modes")
def face_modes():
    return {
        "modes":list(FACE_MODES),
        "supported_subjects":["animal","human","portrait"],
        "clean_source_required":True,
        "max_pieces":3,
        "geometry_authority":"deterministic source-pixel cutout",
        "manual_face_bbox_recommended_for_animals":True,
    }


@router.post("/cutout",status_code=201)
def create_face_cutout(
    request: FaceCutoutRequest,
    library: AssetLibrary=Depends(get_library),
):
    if request.mode not in FACE_MODES:
        raise HTTPException(422,"Unknown face cutout mode")
    if not request.clean_source_confirmed or not request.acknowledge_source_license:
        raise HTTPException(409,"Confirm pristine image and artwork rights")
    try:
        asset=library.get(request.asset_id)
        if not asset["approved"] or not asset["production_eligible"]:
            raise HTTPException(409,"Approve the full-resolution source image first")
        source_data=library.path(request.asset_id).read_bytes()
        canonical=canonicalize_image(
            source_data,provenance=asset["provenance"],
            clean_source_confirmed=request.clean_source_confirmed,
            minimum_side=768,
        )
        # Cut and review on the SAME aspect-preserving canvas as the
        # final renderer. Never resize a reviewed cutout again.
        canvas,mapped_face=prepare_face_canvas(canonical.rgba,request.face_bbox_norm)
        bundle=face_cutout(canvas,request.mode,
                           subject_type=request.subject_type,
                           seed=request.seed,
                           face_bbox_norm=mapped_face)
    except (LibraryError,ValueError,FileNotFoundError) as exc:
        raise HTTPException(422,str(exc)) from exc
    face_id="face_"+secrets.token_hex(12)
    path=_pack_path(library,face_id)
    metadata=package_face_bundle(
        bundle,path,provenance=canonical.provenance,
        original_image_sha256=asset["sha256"],
        approved=False,
    )
    metadata.update({
        "id":face_id,"library_asset_id":request.asset_id,
        "seed":request.seed,
        "face_bbox_norm":list(request.face_bbox_norm) if request.face_bbox_norm else [
            round(bundle.face_bbox_xywh[0] / canvas.shape[1], 8),
            round(bundle.face_bbox_xywh[1] / canvas.shape[0], 8),
            round(bundle.face_bbox_xywh[2] / canvas.shape[1], 8),
            round(bundle.face_bbox_xywh[3] / canvas.shape[0], 8),
        ],
        "bbox_review_origin": "operator_annotated" if request.face_bbox_norm else "detector_or_estimate_pending_review",
        "clean_source_review":"operator_confirmed_not_computer_vision_proven",
        "download_url":f"/api/v1/assets/{face_id}/download",
    })
    (path/"puzzle_manifest.json").write_text(
        json.dumps(metadata,indent=2),encoding="utf8"
    )
    return {
        "id":face_id,"status":metadata["status"],
        "mode":request.mode,"subject_type":request.subject_type,
        "face_bbox_xywh":metadata["face_bbox_xywh"],
        "detection_method":metadata["detection_method"],
        "piece_count":metadata["piece_count"],
        "qa":metadata["qa"],
        "images":{
            "source":f"/api/v1/assets/{face_id}/media/source.png",
            "hole_plate":f"/api/v1/assets/{face_id}/media/hole_plate.png",
            "overlay":f"/api/v1/assets/{face_id}/media/overlay_preview.png",
            "debug":f"/api/v1/assets/{face_id}/media/cutout_debug.png",
            "pieces":[f"/api/v1/assets/{face_id}/media/{p['file']}" for p in metadata["pieces"]],
            "masks":[f"/api/v1/assets/{face_id}/media/{p['mask']}" for p in metadata["pieces"]],
        },
    }


@router.get("/{face_id}/manifest")
def get_face_manifest(face_id: str,library: AssetLibrary=Depends(get_library)):
    return _manifest(library,face_id)


@router.post("/{face_id}/approve")
def approve_face_cutout(face_id: str,library: AssetLibrary=Depends(get_library)):
    data=_manifest(library,face_id)
    if not data["qa"]["valid"] or data["qa"]["exact_raw_rgba_mad"]!=0.0:
        raise HTTPException(409,"Cutout exact-fit validation failed")
    # Approve only if the original library record remains approved.
    asset=library.get(data["library_asset_id"])
    if not asset["approved"] or not asset["production_eligible"]:
        raise HTTPException(409,"Source is no longer approved")
    # Verify the actual PNGs being approved. Manifest QA is insufficient:
    # an artist may have edited the mask or plate after generation.
    try:
        root,_,members=manifest_and_files(library.root.parent.parent,face_id)
        original=canonicalize_image(
            library.path(data["library_asset_id"]).read_bytes(),
            provenance=asset["provenance"],clean_source_confirmed=True,
            minimum_side=768,
        )
        canvas,_=prepare_face_canvas(original.rgba)
        load_reviewed_face_pack(
            library.root.parent.parent,face_id,
            expected_canonical_rgba=canvas,
            expected_original_sha256=asset["sha256"],
            require_approved=False,
        )
        hashes=file_hashes(root,members)
    except (CutoutIntegrityError,ValueError,FileNotFoundError) as exc:
        raise HTTPException(409, "Cutout source, geometry or media validation failed") from exc
    data.update({
        "approved":True,"status":"APPROVED",
        "approved_media_sha256":hashes,
        "approved_pixel_source_sha256":data["normalized_source_pixel_sha256"],
    })
    (_pack_path(library,face_id)/"puzzle_manifest.json").write_text(
        json.dumps(data,indent=2),encoding="utf8"
    )
    return {"id":face_id,"approved":True,"status":"APPROVED","mode":data["mode"]}


@router.get("/{face_id}/media/{file_name}")
def media(face_id: str,file_name: str,library: AssetLibrary=Depends(get_library)):
    if file_name not in MEDIA:
        raise HTTPException(404,"Not an allowed cutout artifact")
    path=_pack_path(library,face_id)/file_name
    if not path.is_file():
        raise HTTPException(404,"Cutout media is missing")
    return FileResponse(path,media_type="image/png",filename=file_name,content_disposition_type="inline")


@router.get("/{face_id}/download")
def download_pack(face_id: str,library: AssetLibrary=Depends(get_library)):
    directory=_pack_path(library,face_id)
    if not (directory/"puzzle_manifest.json").is_file():
        raise HTTPException(404,"Cutout pack not found")
    zip_path=directory/"face_assets.zip"
    create_puzzle_zip(directory,zip_path)
    return FileResponse(zip_path,media_type="application/zip",filename=face_id+".zip")
