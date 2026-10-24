"""Nonblocking, authenticated approved-artwork render queue API.

The previous /api/v1/library/renders endpoint remains backwards-compatible
for private CLI integrations, but Studio defaults to these durable endpoints.
All FFmpeg and QA work happens in the separate persistent worker process.
"""
from __future__ import annotations

import json
import hashlib
from PIL import Image
from pathlib import Path
import re

from fastapi import APIRouter, Depends, Header, HTTPException, status

from services.api.library_routes import OfflineRenderRequest, get_library
from services.assets.library import AssetLibrary, LibraryError
from services.engine.motion_profiles import MOTION_PROFILES
from services.engine.puzzle_geometry import GEOMETRIES
from services.worker.art_render_queue import RenderQueue

router=APIRouter(prefix="/api/v1/library/render-jobs",tags=["Durable Reel Queue"])


def get_queue(library: AssetLibrary=Depends(get_library))->RenderQueue:
    return RenderQueue(library.root.parent.parent)


def validated_spec(request:OfflineRenderRequest,library:AssetLibrary)->dict:
    if request.geometry not in GEOMETRIES or request.motion_profile not in MOTION_PROFILES:
        raise HTTPException(status_code=422,detail="Unsupported geometry/motion family")
    try:
        asset=library.get(request.asset_id)
    except (LibraryError,FileNotFoundError) as exc:
        raise HTTPException(status_code=404,detail="Source artwork does not exist") from exc
    if not asset["approved"] or not asset["production_eligible"]:
        raise HTTPException(status_code=409,detail="Approve HD source artwork first")
    if asset["is_fallback"] and not request.allow_fallback:
        raise HTTPException(status_code=409,detail="Fallback requires explicit approval")
    # Pin the exact decoded source pixel hash at submission. If source
    # artwork changes before the worker picks up the job, the job fails closed.
    try:
        with Image.open(library.path(request.asset_id)) as photo:
            source_pixel_sha256=hashlib.sha256(photo.convert("RGBA").tobytes()).hexdigest()
    except (OSError,ValueError) as exc:
        raise HTTPException(status_code=409,detail="Unable to verify original artwork pixels") from exc
    if source_pixel_sha256 != asset.get("pixel_sha256"):
        raise HTTPException(status_code=409,detail="Original source changed after approval")
    props={
        "expected_source_pixel_sha256": source_pixel_sha256,
        "asset_id":request.asset_id,
        "allow_fallback":request.allow_fallback,
        "geometry":request.geometry,
        "motion_profile":request.motion_profile,
        "duration_sec":request.duration_sec,
        "exact_fit_count":request.exact_fit_count,
        "seed":request.seed,
        "enable_sfx":request.enable_sfx,
    }
    if request.cutout_id is not None:
        if not re.fullmatch(r"face_[a-f0-9]{24}",request.cutout_id):
            raise HTTPException(status_code=422,detail="Invalid cutout ID")
        path=library.root.parent.parent/"cutout_packs"/request.cutout_id/"puzzle_manifest.json"
        if not path.is_file():
            raise HTTPException(status_code=404,detail="Cutout pack missing")
        try:
            cut=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError) as exc:
            raise HTTPException(status_code=409,detail="Invalid saved cutout manifest") from exc
        if not cut.get("approved") or cut.get("status")!="APPROVED":
            raise HTTPException(status_code=409,detail="Approve cutout before submitting a job")
        if cut.get("library_asset_id")!=request.asset_id or cut.get("original_image_sha256")!=asset["sha256"]:
            raise HTTPException(status_code=409,detail="Cutout source hash does not match approved artwork")
        if not cut.get("approved_media_sha256"):
            raise HTTPException(status_code=409,detail="Regenerate and reapprove legacy face cutout")
        props.update({
            "face_mode":cut["mode"],
            "subject_type":cut["subject_type"],
            "face_bbox_norm":cut.get("face_bbox_norm"),
            "face_asset_seed":int(cut["seed"]),
            "face_pack_id":request.cutout_id,
        })
    return props


@router.post("",status_code=202)
def enqueue_reel(
    request:OfflineRenderRequest,
    idempotency_key:str|None=Header(default=None,alias="Idempotency-Key"),
    library:AssetLibrary=Depends(get_library),
    queue:RenderQueue=Depends(get_queue),
):
    params=validated_spec(request,library)
    try:
        job=queue.enqueue(params,idempotency_key=idempotency_key)
    except ValueError as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    job["status_url"]=f"/api/v1/library/render-jobs/{job['id']}"
    return job


@router.get("")
def list_render_jobs(limit:int=25,queue:RenderQueue=Depends(get_queue)):
    try:
        return {"items":queue.list(limit)}
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.get("/{job_id}")
def get_render_job(job_id:str,queue:RenderQueue=Depends(get_queue)):
    try:
        return queue.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404,detail="Render job not found") from exc


@router.post("/{job_id}/cancel")
def cancel_render_job(job_id:str,queue:RenderQueue=Depends(get_queue)):
    try:
        return queue.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404,detail="Render job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post("/{job_id}/retry")
def retry_render_job(job_id:str,queue:RenderQueue=Depends(get_queue)):
    try:
        return queue.retry(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404,detail="Render job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc
