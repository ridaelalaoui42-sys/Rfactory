"""Versioned AI asset/workflow storage and budget-guarded orchestration.

Every Gemini request consumes one explicitly reserved daily request slot.
Metadata and media remain server-side. The Android client should only receive
opaque IDs and authenticated media URLs, never provider API keys or local paths.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
import uuid
from typing import Any

from services.ai.studio import (
    CreativeBrief, ImageBrief, VoiceBrief, GeminiCreativeStudio,
    ProviderError, DEFAULT_MODELS, check_enabled, prepare_subject,
)

ID_RE = re.compile(r"^[0-9a-f]{32}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BudgetExceeded(RuntimeError):
    pass


class NotFoundError(LookupError):
    pass


class ApprovalRequired(RuntimeError):
    pass


class StudioStore:
    def __init__(self, storage_root: Path) -> None:
        self.root = Path(storage_root).resolve()
        self.private = self.root / "ai"
        self.plans = self.private / "plans"
        self.voices = self.private / "voices"
        self.renders = self.root / "renders"
        self.images = self.root / "assets" / "ai"
        for dir_path in (self.private, self.plans, self.voices, self.images, self.renders):
            dir_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.private / "studio.sqlite3"
        with self._connect() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_calls (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                detail TEXT
            )""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=15.0)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        return db

    def reserve(self, kind: str, model: str) -> str:
        check_enabled()
        limit = min(200, max(1, int(os.getenv("RFACTORY_AI_DAILY_CALL_LIMIT", "20"))))
        today = datetime.now(timezone.utc).date().isoformat()
        token = uuid.uuid4().hex
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            used = db.execute(
                "SELECT COUNT(*) FROM ai_calls WHERE created_at >= ?",
                (today + "T",),
            ).fetchone()[0]
            if used >= limit:
                raise BudgetExceeded(f"AI daily request limit reached ({limit})")
            db.execute(
                "INSERT INTO ai_calls(id,kind,model,status,created_at) VALUES (?,?,?,?,?)",
                (token, kind, model, "RESERVED", utc_now()),
            )
        return token

    def finish(self, token: str, success: bool) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE ai_calls SET status=? WHERE id=?",
                ("SUCCEEDED" if success else "FAILED", token),
            )

    @staticmethod
    def _validate_id(key: str) -> str:
        if not ID_RE.fullmatch(key):
            raise NotFoundError("Invalid media identifier")
        return key

    def _path(self, kind: str, key: str) -> Path:
        self._validate_id(key)
        folders = {
            "plan": (self.plans, ".json"),
            "image": (self.images, ".png"),
            "voice": (self.voices, ".wav"),
            "render": (self.renders / key, ".mp4"),
        }
        if kind not in folders:
            raise NotFoundError("Unknown media kind")
        folder, ext = folders[kind]
        filename = key + ext
        if kind == "render":
            filename = key + ext
        return folder / filename

    def meta_path(self, kind: str, key: str) -> Path:
        p = self._path(kind, key)
        return p.with_suffix(".json")

    def write_metadata(self, kind: str, key: str, obj: dict[str, Any]) -> None:
        target = self.meta_path(kind, key)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(target)

    def read_metadata(self, kind: str, key: str) -> dict[str, Any]:
        path = self._path(kind, key) if kind == "plan" else self.meta_path(kind, key)
        if not path.is_file():
            raise NotFoundError(f"{kind} asset not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def media_path(self, kind: str, key: str) -> Path:
        if kind not in ("image", "voice", "render"):
            raise NotFoundError("Media not downloadable")
        file = self._path(kind, key)
        if not file.is_file():
            raise NotFoundError("Media file not found")
        return file

    def approve_image(self, image_id: str) -> dict[str, Any]:
        data = self.read_metadata("image", image_id)
        if not data.get("qa", {}).get("qa_passed"):
            raise ApprovalRequired("Image failed mask QA")
        data["status"] = "APPROVED"
        data["approved_at"] = utc_now()
        self.write_metadata("image", image_id, data)
        return data


class StudioWorkflow:
    def __init__(self, store: StudioStore, provider: GeminiCreativeStudio | None = None):
        self.store = store
        self.provider = provider or GeminiCreativeStudio()

    def _call(self, kind: str, model: str, callback):
        token = self.store.reserve(kind, model)
        try:
            result = callback()
        except Exception:
            self.store.finish(token, False)
            raise
        self.store.finish(token, True)
        return result

    def plan(self, brief: CreativeBrief, model: str = DEFAULT_MODELS["planning"]) -> dict[str, Any]:
        plan = self._call("plan", model, lambda: self.provider.plan(brief, model=model))
        key = uuid.uuid4().hex
        meta = {
            "id": key,
            "kind": "plan",
            "status": "DRAFT",
            "provider": "gemini",
            "model": model,
            "created_at": utc_now(),
            "brief": brief.model_dump(),
            "plan": plan.model_dump(),
        }
        self.store.write_metadata("plan", key, meta)
        return meta

    def image(self, brief: ImageBrief, plan_id: str | None = None) -> dict[str, Any]:
        if plan_id:
            self.store.read_metadata("plan", plan_id)
        blob, actual_prompt = self._call("image", brief.model, lambda: self.provider.image(brief))
        key = uuid.uuid4().hex
        path = self.store._path("image", key)
        qa = prepare_subject(blob, path)
        meta = {
            "id": key,
            "kind": "image",
            "plan_id": plan_id,
            "provider": "gemini",
            "model": brief.model,
            "status": "AWAITING_APPROVAL",
            "created_at": utc_now(),
            "prompt": actual_prompt,
            "style": brief.style,
            "qa": qa,
            "provenance": "Generated by Gemini API; commercial use subject to provider terms",
            "media_url": f"/api/v1/ai/media/image/{key}",
        }
        self.store.write_metadata("image", key, meta)
        return meta

    def voice(self, brief: VoiceBrief, plan_id: str | None = None) -> dict[str, Any]:
        if plan_id:
            self.store.read_metadata("plan", plan_id)
        blob = self._call("tts", brief.model, lambda: self.provider.voice(brief))
        key = uuid.uuid4().hex
        self.store._path("voice", key).write_bytes(blob)
        meta = {
            "id": key,
            "kind": "voice",
            "status": "DRAFT",
            "plan_id": plan_id,
            "provider": "gemini",
            "model": brief.model,
            "voice": brief.voice,
            "text": brief.text,
            "language": brief.language,
            "created_at": utc_now(),
            "media_url": f"/api/v1/ai/media/voice/{key}",
        }
        self.store.write_metadata("voice", key, meta)
        return meta

    def render(
        self,
        plan_id: str,
        image_id: str,
        voice_id: str | None = None,
        duration_sec: float = 15.0,
    ) -> dict[str, Any]:
        # Rendering is deterministic and free of further AI calls. An explicit
        # image approval gate prevents automatic publishing of unreviewed art.
        plan = self.store.read_metadata("plan", plan_id)
        image = self.store.read_metadata("image", image_id)
        if image["status"] != "APPROVED":
            raise ApprovalRequired("Approve the AI artwork before rendering")
        if image.get("plan_id") and image["plan_id"] != plan_id:
            raise ApprovalRequired("Image belongs to a different storyboard")
        voice_path = ""
        if voice_id is not None:
            voice = self.store.read_metadata("voice", voice_id)
            if voice.get("plan_id") and voice["plan_id"] != plan_id:
                raise ApprovalRequired("Voice belongs to a different storyboard")
            voice_path = str(self.store.media_path("voice", voice_id))

        from services.engine.renderer import PuzzleVideoRenderer, RenderConfig
        from services.engine.qa_validator import validate_rendered_video

        key = uuid.uuid4().hex
        brief = plan["brief"]
        creative = plan["plan"]
        renderer = PuzzleVideoRenderer(
            assets_root=self.store.root / "assets",
            outputs_root=self.store.root / "renders",
        )
        configuration = RenderConfig(
            job_id=key,
            species=creative["subject"][:80],
            template_id=creative["template"],
            asset_path=f"ai/{image_id}.png",
            narration_wav=voice_path,
            seed=int(key[:8], 16),
            duration_sec=duration_sec,
            background_hex=creative["background_hex"],
            enable_audio=not bool(voice_id),
            cycles=5,
        )
        artifact = renderer.render_video(configuration)
        qa = validate_rendered_video(
            artifact.mp4_path,
            expected_duration_sec=duration_sec,
            require_audio=True,
            missing_piece_mad=artifact.pixel_match_mad,
        )
        if not qa.passed:
            raise ProviderError("Video QA failed: " + "; ".join(qa.errors))
        meta = {
            "id": key,
            "kind": "render",
            "plan_id": plan_id,
            "image_id": image_id,
            "voice_id": voice_id,
            "status": "READY_FOR_REVIEW",
            "created_at": utc_now(),
            "qa": {"passed": qa.passed, "duration_sec": qa.duration_sec, "codec": qa.video_codec},
            "media_url": f"/api/v1/ai/media/render/{key}",
            "publishing": "NOT_PUBLISHED",
        }
        # Renderer writes <job_id>/<job_id>.mp4. Track this canonical file.
        self.store.write_metadata("render", key, meta)
        return meta
