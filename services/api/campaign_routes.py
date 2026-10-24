"""Production campaign API: 2–24 distinct motion variants over real HD images.

A campaign is a group of existing atomic SQLite render-queue jobs. This
endpoint never creates artwork, fakes Gemini success or posts to social media.
"""
from __future__ import annotations

from typing import Any
import json
from pathlib import Path
import re
import tempfile
import os
import zipfile

from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from services.api.art_queue_routes import get_queue, validated_spec
from services.api.library_routes import OfflineRenderRequest, get_library
from services.assets.library import AssetLibrary
from services.worker.art_render_queue import RenderQueue
from services.worker.campaign_manager import CampaignManager
from services.worker.campaign_planner import make_campaign_plan

router=APIRouter(prefix="/api/v1/library/campaigns",tags=["Approved Artwork Campaign Factory"])


class CampaignRequest(BaseModel):
    name: str = Field(default="Original Face Puzzle Collection",min_length=2,max_length=90)
    asset_ids: list[str] = Field(min_length=1,max_length=8)
    count: int = Field(default=6,ge=2,le=24)
    base_seed: int = Field(default=32021,ge=0,lt=2**31)
    duration_sec: float = Field(default=10,ge=2,le=30)
    exact_fit_count: int = Field(default=5,ge=1,le=12)
    enable_sfx: bool = True
    allow_fallback: bool = False
    cutout_ids: dict[str,str] = Field(default_factory=dict)


def get_manager(queue:RenderQueue=Depends(get_queue))->CampaignManager:
    return CampaignManager(queue)


@router.post("",status_code=202)
def create_campaign(
    request:CampaignRequest,
    idempotency_key:str|None=Header(default=None,alias="Idempotency-Key"),
    library:AssetLibrary=Depends(get_library),
    manager:CampaignManager=Depends(get_manager),
)->dict[str,Any]:
    try:
        plan=make_campaign_plan(
            request.asset_ids,count=request.count,base_seed=request.base_seed,
            duration_sec=request.duration_sec,exact_fit_count=request.exact_fit_count,
            enable_sfx=request.enable_sfx,allow_fallback=request.allow_fallback,
            cutout_ids=request.cutout_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    validated=[]
    # Strict approval checks happen before ALL jobs are committed. They are
    # repeated by the worker at render time in case the source was edited.
    for entry in plan:
        checked=validated_spec(OfflineRenderRequest(**entry),library)
        validated.append(checked)
    try:
        return manager.create(
            request.name,request.model_dump(),
            validated,idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.get("")
def list_campaigns(
    limit:int=12,
    manager:CampaignManager=Depends(get_manager),
):
    try:
        return {"items":manager.list(limit)}
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.get("/{campaign_id}/export")
def export_ready_campaign(
    campaign_id:str,
    manager:CampaignManager=Depends(get_manager),
):
    """Download only QA-READY MP4s in one portable archive.

    Never exports failed/in-progress output, local VM filesystem paths,
    private provider data or unapproved assets. Archive is cleaned up after
    the response is transmitted. No content is automatically published.
    """
    try:
        data=manager.get(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404,detail="Campaign not found") from exc
    ready=[
        (i,j) for i,j in enumerate(data["jobs"],1)
        if j["status"]=="READY" and isinstance(j.get("result"),dict)
    ]
    if not ready:
        raise HTTPException(status_code=409,detail="No verified Reel is ready for export")
    output_root=(manager.queue.storage/"renders").resolve()
    media=[]
    size=0
    for position,job in ready:
        video_id=job["result"].get("id")
        if not isinstance(video_id,str) or not re.fullmatch(r"library_[a-f0-9]{14}",video_id):
            raise HTTPException(status_code=409,detail="Invalid encoded Reel identifier")
        video=(output_root/video_id/(video_id+".mp4")).resolve()
        if not video.is_relative_to(output_root) or not video.is_file():
            raise HTTPException(status_code=409,detail="A ready MP4 is missing from storage")
        size+=video.stat().st_size
        if size>1_073_741_824:
            raise HTTPException(status_code=413,detail="Campaign archive exceeds 1GB")
        media.append((position,job,video))
    export_root=manager.queue.storage/"runtime"/"exports"
    export_root.mkdir(parents=True,exist_ok=True)
    destination=None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".zip",prefix="rfactory_campaign_",dir=export_root,delete=False,
        ) as handle:
            destination=Path(handle.name)
        manifest={
            "campaign_id":data["id"],"name":data["name"],
            "campaign_status":data["status"],
            "total_videos":data["total"],
            "exported_verified_videos":len(media),
            "still_pending_or_failed":data["total"]-len(media),
            "published":False,
            "videos":[],
        }
        with zipfile.ZipFile(destination,"w",compression=zipfile.ZIP_STORED) as zip_out:
            for position,job,video in media:
                archive_name=f"reels/{position:03d}_{video.name}"
                zip_out.write(video,arcname=archive_name)
                manifest["videos"].append({
                    "file":archive_name,"status":job["status"],
                    "frame_qa_checked":job["result"].get("decoded_frames_checked"),
                    "fit_timestamps_sec":job["result"].get("exact_fit_times_sec"),
                    "raw_alignment_mad":job["result"].get("raw_alignment_mad"),
                    "source_provenance":job["result"].get("source_provenance"),
                    "published":False,
                })
            zip_out.writestr("manifest.json",json.dumps(manifest,indent=2))
    except Exception:
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise
    return FileResponse(
        destination,filename=f"{campaign_id}_verified_reels.zip",
        media_type="application/zip",
        background=BackgroundTask(lambda:destination.unlink(missing_ok=True)),
    )


@router.get("/{campaign_id}")
def get_campaign(campaign_id:str,manager:CampaignManager=Depends(get_manager)):
    try:
        return manager.get(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404,detail="Campaign not found") from exc


@router.post("/{campaign_id}/cancel-pending")
def cancel_pending(campaign_id:str,manager:CampaignManager=Depends(get_manager)):
    try:
        return manager.cancel_pending(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404,detail="Campaign not found") from exc
