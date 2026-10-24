"""Production campaign API: 2–24 distinct motion variants over real HD images.

A campaign is a group of existing atomic SQLite render-queue jobs. This
endpoint never creates artwork, fakes Gemini success or posts to social media.
"""
from __future__ import annotations

from typing import Any

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
