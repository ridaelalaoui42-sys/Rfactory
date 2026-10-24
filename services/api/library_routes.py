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
from services.engine.puzzle_geometry import GEOMETRIES
from services.engine.motion_profiles import MOTION_PROFILES
from scripts.render_from_library import render_approved_asset
import re

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


@router.post("/import-pack", status_code=201)
async def import_generated_artpack(
    file: UploadFile = File(...),
    library: AssetLibrary = Depends(get_library),
):
    """Install a ZIP asset pack; leave all files unapproved pending review."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=415, detail="Provide an Rfactory asset ZIP")
    contents = await file.read(60 * 1024 * 1024 + 1)
    if len(contents) > 60 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Asset pack ZIP exceeds 60 MB")
    return _safe(lambda: library.import_pack(contents))


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


class OfflineRenderRequest(BaseModel):
    asset_id: str
    allow_fallback: bool = False
    geometry: str = "organic"
    motion_profile: str = "orbit_lock"
    duration_sec: float = Field(default=10.0, ge=2, le=30)
    exact_fit_count: int = Field(default=5, ge=1, le=12)
    seed: int = Field(default=42041, ge=0, le=2**31 - 1)
    enable_sfx: bool = True
    cutout_id: str | None = None


@router.post("/renders", status_code=201)
def render_curated_artwork(
    request: OfflineRenderRequest,
    library: AssetLibrary = Depends(get_library),
):
    """Produce a real 9:16 puzzle Reel using approved HD source image.

    Works without Gemini text/image/TTS access. The endpoint is synchronous
    and is intended for private, single-user local/VM deployments; a durable
    queue should replace this for high-concurrency multi-user operation.
    """
    if request.geometry not in GEOMETRIES or request.motion_profile not in MOTION_PROFILES:
        raise HTTPException(status_code=422, detail="Unsupported geometry or motion")
    face_kwargs = {}
    if request.cutout_id is not None:
        if not re.fullmatch(r"face_[a-f0-9]{24}", request.cutout_id):
            raise HTTPException(status_code=422, detail="Malformed face cutout ID")
        pack_manifest = library.root.parent.parent / "cutout_packs" / request.cutout_id / "puzzle_manifest.json"
        if not pack_manifest.is_file():
            raise HTTPException(status_code=404, detail="Cutout pack not found")
        import json
        cut = json.loads(pack_manifest.read_text(encoding="utf8"))
        if not cut.get("approved") or cut.get("status") != "APPROVED":
            raise HTTPException(status_code=409, detail="Cutout pack must be approved")
        if cut.get("library_asset_id") != request.asset_id:
            raise HTTPException(status_code=409, detail="Cutout belongs to a different source image")
        library_asset = library.get(request.asset_id)
        if cut.get("original_image_sha256") != library_asset["sha256"]:
            raise HTTPException(status_code=409, detail="Canonical source changed; regenerate cutout")
        face_kwargs = {
            "face_mode": cut["mode"],
            "subject_type":cut["subject_type"],
            "face_bbox_norm":tuple(cut["face_bbox_norm"]) if cut.get("face_bbox_norm") else None,
            "face_asset_seed":int(cut["seed"]),
        }
    try:
        result = render_approved_asset(
            request.asset_id, storage_root=library.root.parent.parent,
            allow_fallback=request.allow_fallback,
            geometry=request.geometry,
            motion=request.motion_profile,
            duration=request.duration_sec,
            crossings=request.exact_fit_count,
            seed=request.seed,
            enable_sfx=request.enable_sfx,
            **face_kwargs,
        )
        # Expose an authenticated opaque video ID, not the VM's local paths.
        video_id = Path(result["video"]).parent.name
        if not re.fullmatch(r"library_[a-f0-9]{14}", video_id):
            raise RuntimeError("Unexpected render ID")
        return {
            "id": video_id,
            "status": "READY_FOR_REVIEW",
            "video_url": f"/api/v1/library/renders/{video_id}/video",
            "report_url": f"/api/v1/library/renders/{video_id}/report",
            "exact_fit_times_sec": result["exact_fit_times_sec"],
            "decoded_frames_checked": result["all_frames_checked"],
            "raw_alignment_mad": result["raw_alignment_mad"],
            "provenance": result["source_provenance"],
            "fallback_used": result["explicit_fallback"],
            "face_cutout_id":request.cutout_id,
            "face_mode":result.get("face_mode"),
            "published": False,
        }
    except (LibraryError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Source image missing") from exc


def _validated_render_path(library: AssetLibrary, video_id: str, ext: str) -> Path:
    if not re.fullmatch(r"library_[a-f0-9]{14}", video_id):
        raise HTTPException(status_code=404, detail="Unknown render")
    path = library.root.parent.parent / "renders" / video_id / (video_id + ext)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Render file not found")
    return path


@router.get("/renders/{video_id}/video")
def curated_video(video_id: str, library: AssetLibrary = Depends(get_library)):
    path = _validated_render_path(library, video_id, ".mp4")
    return FileResponse(path, media_type="video/mp4", filename=path.name, content_disposition_type="inline")


@router.get("/renders/{video_id}/report")
def curated_report(video_id: str, library: AssetLibrary = Depends(get_library)):
    path = _validated_render_path(library, video_id, ".provenance.json")
    import json
    record = json.loads(path.read_text(encoding="utf-8"))
    # Never send server filesystem paths to web and Android clients.
    record.pop("video", None)
    return record


@router.get("/media/{asset_id}")
def media(asset_id: str, library: AssetLibrary = Depends(get_library)):
    path = _safe(lambda: library.path(asset_id))
    return FileResponse(path, media_type="image/png", content_disposition_type="inline")
