"""Schemas and security gates for video production."""
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, model_validator

FORMATS = {"vertical":(1080,1920),"horizontal":(1920,1080),"square":(1080,1080)}
APPROVED_RIGHTS = {"owned","licensed","permission","public_domain"}

class SourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    youtube_id: str | None = None
    local_file: str | None = None
    rights: Literal["owned","licensed","permission","public_domain","unknown","fair_use_review"] = "unknown"
    evidence: str = ""
    attribution: str = ""

class TranscriptItem(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str = Field(min_length=1)
    language: str = "und"
    @model_validator(mode="after")
    def interval(self):
        if self.end <= self.start: raise ValueError("End must exceed start")
        return self

class ClipRange(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    @model_validator(mode="after")
    def interval(self):
        if self.end <= self.start: raise ValueError("End must exceed start")
        return self

class EditPlan(BaseModel):
    source_id: int = Field(gt=0)
    ranges: list[ClipRange] = Field(min_length=1,max_length=200)
    format: Literal["vertical","horizontal","square"]
    output_name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\.mp4$")
    title: str = ""
    @model_validator(mode="after")
    def max_duration(self):
        if sum(r.end-r.start for r in self.ranges)>14400: raise ValueError("Four-hour output limit")
        return self

def safe_local(path: str, root: Path) -> Path:
    root=root.expanduser().resolve()
    p=Path(path).expanduser().resolve()
    if not p.is_relative_to(root) or not p.is_file():
        raise ValueError("Source file must exist inside CLIPFORGE_MEDIA_ROOT")
    return p

def render_allowed(source: dict) -> bool:
    return bool(source["rights"] in APPROVED_RIGHTS and str(source["evidence"]).strip() and source["local_file"])
