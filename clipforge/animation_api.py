"""Authenticated Creative Director routing API.

Planning endpoints never execute third-party Skills or billable generation.
"""
from fastapi import APIRouter
from .animation_modules import AnimationBrief, catalog, select

router = APIRouter(prefix="/v1/animation", tags=["animation"])

@router.get("/modules")
def modules():
    return {"modules": catalog()}

@router.post("/select")
def choose(body: AnimationBrief):
    return select(body)
