"""Versioned deterministic creative-preview API for Studio and future Android.

Produces trajectories, geometry registries, seeded match times, and
normalized motion fingerprints without spending any Gemini tokens or rendering
a video. All routes inherit the existing /api/ bearer middleware.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.engine.motion_profiles import (
    MOTION_PROFILES, continuous_motion_pose,
)
from services.engine.puzzle_geometry import GEOMETRIES
from services.engine.snap_timeline import build_crossing_timeline

router = APIRouter(prefix="/api/v1/creative", tags=["Deterministic Motion Director"])


class MotionPreviewRequest(BaseModel):
    profile: str = "orbit_lock"
    fps: int = Field(default=30, ge=12, le=60)
    duration_sec: float = Field(default=12, ge=2, le=30)
    crossing_count: int = Field(default=5, ge=1, le=12)
    seed: int = Field(default=1001, ge=0, le=2**31 - 1)
    travel_px: float = Field(default=180.0, ge=1, le=1200)
    intensity: float = Field(default=1.0, gt=0, le=2)
    samples: int = Field(default=180, ge=12, le=900)


def _trajectory(req: MotionPreviewRequest) -> dict[str, Any]:
    if req.profile not in MOTION_PROFILES:
        raise ValueError(f"Unknown profile: {req.profile}")
    frame_count = int(round(req.duration_sec * req.fps))
    timeline = build_crossing_timeline(
        total_frames=frame_count, fps=req.fps,
        count=req.crossing_count, seed=req.seed,
    )
    # Samples use real integer frames, not a made-up generic interpolation.
    positions = sorted({int(round(i*(frame_count-1)/max(1,req.samples-1))) for i in range(req.samples)})
    positions.extend(p.first_locked_frame for p in timeline.passes)
    positions = sorted(set(positions))
    frames = []
    for frame in positions:
        pose = continuous_motion_pose(
            req.profile, timeline.phase(frame),
            travel_px=req.travel_px, seed=req.seed, intensity=req.intensity,
        )
        frames.append({
            "frame": frame,
            "time_sec": round(frame/req.fps, 4),
            "x": pose.dx, "y": pose.dy,
            "rotation": pose.angle_deg,
            "scale_x": pose.scale_x, "scale_y": pose.scale_y,
            "exact_fit": timeline.is_locked(frame),
        })
    crossings = [p.first_locked_frame for p in timeline.passes]
    return {
        "profile": req.profile,
        "seed": req.seed,
        "fps": req.fps,
        "duration_sec": round(frame_count/req.fps, 4),
        "total_frames": frame_count,
        "crossing_count": len(crossings),
        "crossing_frames": crossings,
        "crossing_times_sec": [round(f/req.fps,4) for f in crossings],
        "paused_frames_per_fit": 0,
        "single_frame_per_crossing": True,
        "no_visual_indicator": True,
        "samples": frames,
    }


@router.get("/capabilities")
def creative_capabilities() -> dict[str,Any]:
    return {
        "api_version": "1",
        "motion_profiles": list(MOTION_PROFILES),
        "puzzle_geometries": list(GEOMETRIES),
        "continuous_motion": True,
        "exact_fit_frames_per_crossing": 1,
        "maximum_puzzle_fragments": 5,
        "maximum_crossings": 12,
        "renderer_provenance": "deterministic",
        "future_mobile_support": "versioned REST; server-side rendering",
    }


@router.post("/motion/preview")
def motion_preview(request: MotionPreviewRequest) -> dict[str, Any]:
    try:
        return _trajectory(request)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.post("/motion/diversity")
def diversity_test(requests: list[MotionPreviewRequest]) -> dict[str,Any]:
    """Identify identical or near-identical motion plans before expensive renders."""
    if not 2 <= len(requests) <= 20:
        raise HTTPException(status_code=422, detail="Compare 2 to 20 motion plans")
    plans = []
    try:
        for req in requests:
            timeline=build_crossing_timeline(int(round(req.duration_sec*req.fps)),
                                             req.fps,req.crossing_count,req.seed)
            # Fixed phase samples abstract away differences caused only by
            # random crossing timings. Distinct geometric paths should differ.
            sequence=[]
            for k in range(64):
                pose=continuous_motion_pose(req.profile,k/63,req.travel_px,seed=req.seed,
                                            intensity=req.intensity)
                sequence.extend((
                    pose.dx/max(req.travel_px,.01),
                    pose.dy/max(req.travel_px,.01),
                    pose.angle_deg/360,
                    pose.scale_x-1, pose.scale_y-1,
                ))
            plans.append((req,sequence))
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    candidates=[]
    for i in range(len(plans)):
        for j in range(i+1,len(plans)):
            a,b=plans[i][1],plans[j][1]
            distance=math.sqrt(sum((x-y)**2 for x,y in zip(a,b))/len(a))
            if distance < .13:
                candidates.append({
                    "first_index":i,"second_index":j,
                    "distance":round(distance,5),
                    "warning":"Motion trajectories are visually similar; vary geometry or motion profile."
                })
    return {
        "compared":len(requests),
        "near_duplicates":candidates,
        "pass":not candidates,
        "threshold":.13,
        "method":"normalized sampled pose RMS; heuristic, not a visual proof",
    }
