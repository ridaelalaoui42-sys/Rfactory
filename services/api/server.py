"""
FastAPI REST API Server for Animal Puzzle Reels Factory.
Exposes endpoints for Overview stats, Video Studio rendering, Batch campaigns,
Asset Library, Video Library approval/scheduling, Page Connections, and Audit Logs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import services
from services.content.agent import ContentGenerationAgent
from services.database.repository import FactoryRepository
from services.engine.renderer import PuzzleVideoRenderer, RenderConfig
from services.publisher.adapters import (
    ManualExportPublisher,
    MetaBusinessSuitePlaywrightPublisher,
)
from services.worker.batch_runner import BatchProductionWorker

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STORAGE_ROOT = REPO_ROOT / "storage"

app = FastAPI(title="Animal Puzzle Reels Factory API", version="1.0.0")


def get_repo() -> FactoryRepository:
    return FactoryRepository(db_path=STORAGE_ROOT / "factory.db")


class EnqueueBatchRequest(BaseModel):
    name: str = "Custom Puzzle Campaign"
    count: int = 10
    template_filter: str = "BOTH"
    language: str = "en"
    duration_sec: float = 15.0
    enable_audio: bool = True
    base_seed: int = 2001


class SchedulePostRequest(BaseModel):
    project_id: str
    page_id: str = "pg_atlas_wildlife"
    scheduled_for_local_iso: str = "2026-10-25T18:00:00"
    timezone_name: str = "Africa/Casablanca"
    publisher_mode: str = "MANUAL_EXPORT"


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    repo = get_repo()
    with repo._connect() as conn:
        ready = conn.execute("SELECT COUNT(*) AS c FROM render_jobs WHERE status = 'READY'").fetchone()["c"]
        pages = conn.execute("SELECT COUNT(*) AS c FROM facebook_pages").fetchone()["c"]
    return {"status": "ok", "ready_videos": ready, "configured_pages": pages, "default_timezone": "Africa/Casablanca"}


@app.get("/api/overview")
def get_overview() -> Dict[str, Any]:
    repo = get_repo()
    with repo._connect() as conn:
        jobs = [dict(r) for r in conn.execute("SELECT * FROM render_jobs ORDER BY created_at DESC").fetchall()]
        projects = [dict(r) for r in conn.execute("SELECT * FROM video_projects ORDER BY created_at DESC").fetchall()]
        outputs = [dict(r) for r in conn.execute("SELECT * FROM render_outputs ORDER BY created_at DESC").fetchall()]
        pages = [dict(r) for r in conn.execute("SELECT * FROM facebook_pages").fetchall()]
        scheduled = [dict(r) for r in conn.execute("SELECT * FROM scheduled_posts ORDER BY scheduled_for_utc ASC").fetchall()]
        audits = [dict(r) for r in conn.execute("SELECT * FROM audit_events ORDER BY created_at DESC LIMIT 50").fetchall()]
    return {
        "jobs": jobs,
        "projects": projects,
        "outputs": outputs,
        "pages": pages,
        "scheduled": scheduled,
        "audits": audits,
    }


@app.post("/api/batches")
def create_and_run_batch(req: EnqueueBatchRequest) -> Dict[str, Any]:
    repo = get_repo()
    renderer = PuzzleVideoRenderer(assets_root=STORAGE_ROOT / "assets", outputs_root=STORAGE_ROOT / "renders")
    worker = BatchProductionWorker(repo=repo, renderer=renderer, content_agent=ContentGenerationAgent())
    batch_id, job_ids = worker.enqueue_batch_campaign(
        name=req.name,
        count=req.count,
        template_filter=req.template_filter,
        language=req.language,
        duration_sec=req.duration_sec,
        enable_audio=req.enable_audio,
        base_seed=req.base_seed,
    )
    return {"batch_id": batch_id, "job_ids": job_ids}


@app.post("/api/schedule")
def schedule_video(req: SchedulePostRequest) -> Dict[str, Any]:
    repo = get_repo()
    try:
        sched_id = repo.approve_and_schedule_project(
            project_id=req.project_id,
            page_id=req.page_id,
            scheduled_for_local_iso=req.scheduled_for_local_iso,
            timezone_name=req.timezone_name,
            publisher_mode=req.publisher_mode,
        )
        return {"scheduled_post_id": sched_id, "status": "SCHEDULED"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
