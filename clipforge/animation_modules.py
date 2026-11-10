"""Rfactory Creative Director: multi-module animation planning and routing.

The router is a declarative planning layer. External Skill repositories are
not executable integrations merely because their paths exist. A module must
have a tested adapter and its dependencies installed before jobs can render.
"""
import os
import shutil
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, model_validator

# Source repositories are third-party MIT-licensed upstream projects.
MODULES = {
    "bang_motion": {
        "name": "Bang Motion", "source": "https://github.com/bangtutorial/bang-motion",
        "focus": "Browser choreography, kinetic graphics, moving cameras, live UI",
        "genres": ("technology", "promo", "product", "business", "science", "abstract", "education"),
        "modes": ("animated", "captionless", "sfx_only", "voiceover"),
        "setup": "CLIPFORGE_BANG_MOTION_ROOT", "marker": "SKILL.md",
        "adapter": "planned", "cost": "local", "can_render_solo": True,
        "weight": 9,
    },
    "vox_director": {
        "name": "Vox Director", "source": "https://github.com/Alisa0808/vox-director",
        "focus": "Editorial paper collage, documentary evidence, reported explainers",
        "genres": ("documentary", "history", "news", "politics", "economics", "education", "culture"),
        "modes": ("animated", "voiceover", "captions", "collage"),
        "setup": "CLIPFORGE_VOX_DIRECTOR_ROOT", "marker": "SKILL.md",
        "adapter": "planned", "cost": "api", "can_render_solo": True,
        "weight": 8,
    },
    "huashu_art_motion": {
        "name": "Huashu Art Motion", "source": "https://github.com/alchaincyf/huashu-art-motion",
        "focus": "Painterly art animation, whiteboard, visual metaphor, playful storytelling",
        "genres": ("art", "education", "science", "history", "culture", "story", "nature"),
        "modes": ("animated", "captionless", "sfx_only", "voiceover", "illustration"),
        "setup": "CLIPFORGE_HUASHU_ART_MOTION_ROOT", "marker": "SKILL.md",
        "adapter": "planned", "cost": "local", "can_render_solo": True,
        "weight": 8,
    },
    "claude_drawing": {
        "name": "Claude Drawing", "source": "https://github.com/cloveric/claude-drawing-skill",
        "focus": "Original painted scene assets and staged drawing reveals",
        "genres": ("art", "nature", "history", "story", "culture", "education"),
        "modes": ("illustration", "assets", "captionless", "sfx_only"),
        "setup": "CLIPFORGE_CLAUDE_DRAWING_ROOT", "marker": "SKILL.md",
        "adapter": "planned", "cost": "local", "can_render_solo": False,
        "weight": 6,
    },
    "stickman_director": {
        "name": "Stickman Video Director", "source": "https://github.com/kaomei/stickman-video-director",
        "focus": "Character-led animated explainers with authored narration and captions",
        "genres": ("education", "story", "psychology", "science", "business"),
        "modes": ("animated", "voiceover", "captions", "character"),
        "setup": "CLIPFORGE_STICKMAN_SKILL_ROOT", "marker": "scripts/autopilot.mjs",
        "adapter": "separate_pr", "cost": "local", "can_render_solo": True,
        "weight": 7,
    },
    "clipforge_compositor": {
        "name": "ClipForge / FFmpeg", "source": "https://github.com/ridaelalaoui42-sys/Rfactory",
        "focus": "Existing rights-aware rough cuts, sound mixing and final MP4 assembly",
        "genres": ("all",),
        "modes": ("compositing", "captions_optional", "sfx_only"),
        "setup": None, "marker": None,
        "adapter": "implemented", "cost": "local", "can_render_solo": False,
        "weight": 1,
    },
}
GENRE_KEYWORDS = {
    "technology": ("ai", "robot", "app", "tech", "computer", "phone", "software", "machine", "cyber", "internet"),
    "promo": ("launch", "promo", "teaser", "trailer", "brand", "announcement"),
    "product": ("product", "store", "device", "dashboard", "website", "saas"),
    "business": ("business", "startup", "market", "entrepreneur", "sales"),
    "science": ("science", "physics", "space", "moon", "planet", "volcano", "chemistry", "engineering"),
    "documentary": ("documentary", "investigation", "evidence", "how it happened", "explained"),
    "history": ("history", "ancient", "historical", "dynasty", "archaeology", "past"),
    "news": ("news", "latest", "headline", "current events", "journalism"),
    "politics": ("election", "government", "policy", "politics", "parliament"),
    "economics": ("economy", "inflation", "tax", "finance", "investment"),
    "education": ("teach", "student", "classroom", "lesson", "educational", "explain"),
    "culture": ("tradition", "culture", "music", "community", "film", "language"),
    "art": ("art", "paint", "drawing", "artistic", "illustration", "gallery"),
    "story": ("story", "character", "fairy tale", "adventure", "animated short"),
    "nature": ("nature", "tree", "forest", "mountain", "river", "animal", "ocean"),
    "psychology": ("psychology", "mind", "behavior", "emotion", "habit"),
    "abstract": ("concept", "abstract", "geometric", "motion graphics"),
}


class AnimationBrief(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    format: Literal["vertical", "horizontal"] = "vertical"
    duration_seconds: int = Field(default=15, ge=3, le=3600)
    captions: bool = False
    voiceover: bool = False
    sound_effects: bool = True
    budget: Literal["local_only", "api_allowed"] = "local_only"
    genre: str | None = None
    preferred_module: str | None = None
    blend_modules: bool = False

    @model_validator(mode="after")
    def valid_genre(self):
        if self.genre is not None and self.genre not in GENRE_KEYWORDS:
            raise ValueError("Unknown genre")
        if self.preferred_module is not None and self.preferred_module not in MODULES:
            raise ValueError("Unknown preferred module")
        return self


def catalog() -> list[dict]:
    rows = []
    for key, value in MODULES.items():
        setup = value["setup"]
        configured = bool(
            setup is None and shutil.which("ffmpeg") or
            setup and os.environ.get(setup) and
            (Path(os.environ[setup]).expanduser() / value["marker"]).is_file()
        )
        rows.append({
            "id": key, "name": value["name"], "source": value["source"],
            "focus": value["focus"], "capabilities": list(value["modes"]),
            "genres": list(value["genres"]), "integration": value["adapter"],
            "configured": configured, "cost": value["cost"],
            "can_render_solo": value["can_render_solo"],
            "note": "Configured refers to local files only, not verified runtime readiness.",
        })
    return rows


def _genres(brief: AnimationBrief) -> set[str]:
    result = {brief.genre} if brief.genre else set()
    text = brief.topic.lower()
    for genre, words in GENRE_KEYWORDS.items():
        if any(word in text for word in words):
            result.add(genre)
    if not result:
        result.add("abstract")
    return result


def _score(brief: AnimationBrief, key: str, genres: set[str]) -> tuple[float, list[str], list[str]]:
    module = MODULES[key]
    modes = set(module["modes"])
    reasons = []
    blockers = []
    if key == "clipforge_compositor":
        blockers.append("compositing_only")
    elif key == "claude_drawing":
        blockers.append("asset_provider_only")
    match = sorted(genres.intersection(module["genres"]))
    score = float(module["weight"] + len(match) * 7)
    if match:
        reasons.append("Topic fit: " + ", ".join(match))
    else:
        score -= 8
    if brief.captions and "captions" not in modes and "captions_optional" not in modes:
        blockers.append("captions_not_verified")
    if not brief.captions and "captionless" not in modes and "captions_optional" not in modes:
        blockers.append("no_captionless_export")
    if brief.voiceover and "voiceover" not in modes:
        blockers.append("voiceover_not_verified")
    if not brief.voiceover and "sfx_only" not in modes:
        blockers.append("no_voiceover_free_export")
    if brief.budget == "local_only" and module["cost"] == "api":
        blockers.append("requires_paid_model_api")
    if brief.preferred_module == key:
        score += 30
        reasons.append("User-preferred module")
    if brief.duration_seconds <= 40 and key == "bang_motion":
        score += 3
        reasons.append("Good fit for short-form continuous motion")
    if "documentary" in genres and key == "vox_director":
        score += 5
    if blockers:
        score -= 200
    return score, reasons, blockers


def select(brief: AnimationBrief) -> dict:
    genres = _genres(brief)
    recommendations = []
    for key in MODULES:
        score, reasons, blockers = _score(brief, key, genres)
        recommendations.append({
            "id": key, "name": MODULES[key]["name"],
            "score": score, "reasons": reasons, "blockers": blockers,
            "candidate": not blockers,
            "integration": MODULES[key]["adapter"],
        })
    recommendations.sort(key=lambda r: (-r["score"], r["id"]))
    executable_choices = [r for r in recommendations if r["candidate"]]
    primary = executable_choices[0]["id"] if executable_choices else None
    attachments = []
    if primary and brief.blend_modules:
        if primary != "claude_drawing" and genres.intersection({"art", "story", "nature", "history"}):
            attachments.append({"id": "claude_drawing", "role": "style-consistent painted assets"})
    if primary:
        attachments.append({"id": "clipforge_compositor", "role": "approved asset assembly, SFX and final encode"})
    return {
        "format": brief.format, "min_resolution": "1080x1920" if brief.format == "vertical" else "1920x1080",
        "duration_seconds": brief.duration_seconds, "captions": brief.captions,
        "voiceover": brief.voiceover, "sound_effects": brief.sound_effects,
        "detected_genres": sorted(genres), "primary_module": primary,
        "support_modules": attachments, "shortlist": recommendations,
        "can_render_now": False,
        "next_step": "Configure and test the selected module's executable adapter; this API only returns a plan.",
        "selection_policy": "hard exclusions for unsupported output; then topic fit, duration, preference and production cost",
    }
