"""Mobile-ready v1 creative-studio endpoints.

All cloud provider credentials stay server-side. These routes are protected by
the existing API token middleware and use explicit validation and stable IDs.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.ai.studio import (
    CreativeBrief, ImageBrief, VoiceBrief, GeminiCreativeStudio,
    ConfigurationError, ProviderError, MODELS, VOICES, enabled,
)
from services.ai.workflow import (
    StudioStore, StudioWorkflow, BudgetExceeded, ApprovalRequired, NotFoundError,
)

from pathlib import Path

STORAGE_ROOT = Path(__file__).resolve().parents[2] / "storage"
router = APIRouter(prefix="/api/v1/ai", tags=["AI Creative Studio"])


def get_store() -> StudioStore:
    return StudioStore(STORAGE_ROOT)


def get_workflow(store: StudioStore = Depends(get_store)) -> StudioWorkflow:
    return StudioWorkflow(store, GeminiCreativeStudio())


class PlanRequest(BaseModel):
    brief: CreativeBrief
    model: str = MODELS["planning"][0]


class ImageRequest(ImageBrief):
    plan_id: str | None = None
    source_image_id: str | None = None


class VoiceRequest(VoiceBrief):
    plan_id: str | None = None


class RenderRequest(BaseModel):
    plan_id: str
    image_id: str
    voice_id: str | None = None
    duration_sec: float = Field(default=15.0, ge=8, le=30)
    sfx_enabled: bool = True
    motion_profile: Literal["slide", "spin_snap", "orbit_lock", "pendulum", "spiral", "elastic", "flip_reveal", "zigzag"] | None = None
    motion_intensity: float = Field(default=1.0, ge=0.0, le=2.0)
    snap_count: int = Field(default=0, ge=0, le=12, description="0 uses storyboard cycles; 1-12 chooses number of irregular exact-fit events")


def _run(op):
    try:
        return op()
    except (ConfigurationError, BudgetExceeded) as exc:
        raise HTTPException(status_code=503 if isinstance(exc, ConfigurationError) else 429, detail=str(exc)) from exc
    except (NotFoundError,) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ApprovalRequired,) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    # Other exceptions become internal errors. Never return provider secrets.


@router.get("/capabilities")
def get_capabilities() -> dict:
    import os
    return {
        "api_version": "v1",
        "ai_enabled": enabled(),
        "configured": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "providers": ["gemini"],
        "models": MODELS,
        "voices": list(VOICES),
        "creative_styles": ["storybook", "premium_3d", "editorial", "clay", "hand_painted", "neon"],
        "supported_languages": ["en", "es", "fr", "ar"],
        "review_required": True,
        "auto_publish_enabled": False,
        "auth": "backend bearer token (replace with OAuth/JWT before mobile public launch)",
    }


@router.post("/plans", status_code=201)
def generate_plan(req: PlanRequest, workflow: StudioWorkflow = Depends(get_workflow)):
    return _run(lambda: workflow.plan(req.brief, model=req.model))


@router.post("/images", status_code=201)
def generate_image(req: ImageRequest, workflow: StudioWorkflow = Depends(get_workflow)):
    return _run(lambda: workflow.image(ImageBrief.model_validate(req.model_dump(exclude={"plan_id", "source_image_id"})), req.plan_id, req.source_image_id))


@router.post("/voices", status_code=201)
def generate_voice(req: VoiceRequest, workflow: StudioWorkflow = Depends(get_workflow)):
    return _run(lambda: workflow.voice(VoiceBrief.model_validate(req.model_dump(exclude={"plan_id"})), req.plan_id))


@router.post("/images/import", status_code=201)
async def import_uploaded_image(
    file: UploadFile = File(...),
    plan_id: str | None = Form(None),
    workflow: StudioWorkflow = Depends(get_workflow),
):
    """Import gallery artwork without a paid image-generation model.

    Strict 10 MB limit, Pillow image validation, no arbitrary file paths.
    User must have rights to imported artwork.
    """
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload PNG, JPEG or WebP")
    blob = await file.read(10 * 1024 * 1024 + 1)
    if len(blob) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds 10 MB limit")
    return _run(lambda: workflow.import_image(blob, plan_id))


@router.post("/images/{image_id}/approve")
def approve_image(image_id: str, store: StudioStore = Depends(get_store)):
    return _run(lambda: store.approve_image(image_id))


@router.post("/renders", status_code=201)
def render_reel(req: RenderRequest, workflow: StudioWorkflow = Depends(get_workflow)):
    return _run(lambda: workflow.render(req.plan_id, req.image_id, req.voice_id,
                                        req.duration_sec, req.sfx_enabled,
                                        req.motion_profile, req.motion_intensity,
                                        req.snap_count))


@router.get("/library")
def list_library(
    kind: Literal["plan", "image", "voice", "render"] = "plan",
    limit: int = 20,
    offset: int = 0,
    store: StudioStore = Depends(get_store),
):
    return _run(lambda: store.list_records(kind, limit=limit, offset=offset))


@router.get("/records/{kind}/{asset_id}")
def record(kind: Literal["plan", "image", "voice", "render"], asset_id: str, store: StudioStore = Depends(get_store)):
    return _run(lambda: store.read_metadata(kind, asset_id))


@router.get("/media/{kind}/{asset_id}")
def media(kind: Literal["image", "voice", "render"], asset_id: str, store: StudioStore = Depends(get_store)):
    path = _run(lambda: store.media_path(kind, asset_id))
    mimetype = {"image": "image/png", "voice": "audio/wav", "render": "video/mp4"}[kind]
    return FileResponse(path, media_type=mimetype, filename=path.name, content_disposition_type="inline")
