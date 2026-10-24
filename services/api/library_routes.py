"""Authenticated asset-library REST routes for web Studio and future Android."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.assets.library import AssetLibrary, LibraryError
from services.ai.workflow import StudioWorkflow
from services.api.ai_routes import get_workflow

ROOT = Path(__file__).resolve().parents[2]
router = APIRouter(prefix="/api/v1/library", tags=["AI Artwork Library"])


def get_library() -> AssetLibrary:
    return AssetLibrary(ROOT / "storage")


class SelectRequest(BaseModel):
    category: str = Field(min_length=3, max_length=40)
    subject: str | None = Field(default=None, max_length=100)
    allow_fallback: bool = False
    seed: int = Field(default=0, ge=0, le=2**31 - 1)


class StageRequest(BaseModel):
    plan_id: str | None = None
    acknowledge_source_license: bool = False


def _safe(operation):
    try:
        return operation()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Artwork not found") from exc
    except LibraryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/capabilities")
def capabilities():
    return {
        "version": 1,
        "asset_types": ["production_generated", "fallback", "reference_only", "user_uploaded"],
        "min_original_resolution": 768,
        "fallback_selection": "explicit_opt_in_only",
        "auto_publish": False,
        "all_artwork_requires_approval": True,
    }


@router.get("/assets")
def list_assets(
    category: str | None = None,
    production_only: bool = False,
    limit: int = 100,
    library: AssetLibrary = Depends(get_library),
):
    return {"items": _safe(lambda: library.list_assets(category, production_only, limit))}


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str, library: AssetLibrary = Depends(get_library)):
    return _safe(lambda: library.get(asset_id))


@router.post("/assets/import", status_code=201)
async def import_asset(
    file: UploadFile = File(...),
    subject: str = Form(...),
    category: str = Form(...),
    tier: Literal["production_generated", "fallback", "reference_only", "user_uploaded"] = Form("user_uploaded"),
    provenance: str = Form("operator_uploaded"),
    source_description: str = Form("Uploaded by operator; rights and origin require review"),
    library: AssetLibrary = Depends(get_library),
):
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload PNG, JPEG, or WebP")
    blob = await file.read(16 * 1024 * 1024 + 1)
    if len(blob) > 16 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Maximum artwork size is 16 MB")
    return _safe(lambda: library.add_image(
        blob, subject=subject, category=category, tier=tier,
        provenance=provenance, source_description=source_description,
    ))


@router.post("/assets/{asset_id}/approve")
def approve_asset(asset_id: str, library: AssetLibrary = Depends(get_library)):
    return _safe(lambda: library.approve(asset_id))


@router.post("/select")
def select_asset(request: SelectRequest, library: AssetLibrary = Depends(get_library)):
    return _safe(lambda: library.select(
        request.category,
        subject=request.subject,
        allow_fallback=request.allow_fallback,
        seed=request.seed,
    ))


@router.post("/assets/{asset_id}/stage")
def stage_asset(
    asset_id: str,
    request: StageRequest,
    library: AssetLibrary = Depends(get_library),
    workflow: StudioWorkflow = Depends(get_workflow),
):
    """Create a Studio image from approved library art; still requires review.

    Importing a pre-approved library asset does not override the downstream
    Studio image-level approval gate. The client must explicitly acknowledge
    media rights; no silent fallback staging.
    """
    metadata = _safe(lambda: library.get(asset_id))
    if not metadata["approved"] or not metadata["production_eligible"]:
        raise HTTPException(status_code=409, detail="Artwork must pass human review and resolution QA")
    if not request.acknowledge_source_license:
        raise HTTPException(status_code=409, detail="Confirm permission to use this source artwork")
    data = _safe(lambda: library.path(asset_id).read_bytes())
    image = workflow.import_image(data, request.plan_id)
    image["provider"] = "curated_asset_library"
    image["library_asset_id"] = asset_id
    image["library_provenance"] = metadata["provenance"]
    image["fallback_used"] = metadata["is_fallback"]
    image["generation_attempted"] = False
    workflow.store.write_metadata("image", image["id"], image)
    return image


@router.get("/media/{asset_id}")
def media(asset_id: str, library: AssetLibrary = Depends(get_library)):
    path = _safe(lambda: library.path(asset_id))
    return FileResponse(path, media_type="image/png", content_disposition_type="inline")
