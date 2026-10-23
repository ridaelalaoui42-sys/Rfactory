"""
Durable Relational Repository & State Machine for Animal & Celebrity Face Puzzle Reels Factory.
Implements all 16 tables, append-only audit trail, crash recovery, per-Page mutex locks,
timezone-aware scheduling (`Africa/Casablanca` default), daily post caps, and strict
render & publishing state transitions including `UNKNOWN_RESULT` quarantine.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

VALID_RENDER_TRANSITIONS: Dict[str, set[str]] = {
    "DRAFT": {"QUEUED", "CANCELLED"},
    "QUEUED": {"RENDERING", "CANCELLED"},
    "RENDERING": {"QA", "FAILED", "CANCELLED", "QUEUED"},
    "QA": {"READY", "FAILED"},
    "FAILED": {"QUEUED", "CANCELLED"},
    "READY": {"QUEUED"},
    "CANCELLED": {"QUEUED"},
}

VALID_PUBLISH_TRANSITIONS: Dict[str, set[str]] = {
    "DRAFT": {"APPROVED"},
    "APPROVED": {"SCHEDULED", "DRAFT"},
    "SCHEDULED": {"UPLOADING", "APPROVED", "BLOCKED", "NEEDS_LOGIN"},
    "UPLOADING": {"SUBMITTING", "FAILED", "NEEDS_LOGIN", "BLOCKED"},
    "SUBMITTING": {"VERIFYING", "UNKNOWN_RESULT", "FAILED", "BLOCKED"},
    "VERIFYING": {"PUBLISHED", "UNKNOWN_RESULT", "FAILED"},
    "UNKNOWN_RESULT": set(),
    "NEEDS_LOGIN": {"SCHEDULED"},
    "BLOCKED": {"SCHEDULED"},
    "FAILED": {"SCHEDULED"},
    "PUBLISHED": set(),
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class FactoryRepository:
    def __init__(self, db_path: Path | str, schema_sql_path: Optional[Path | str] = None) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.schema_sql_path = (
            Path(schema_sql_path)
            if schema_sql_path
            else Path(__file__).parent / "schema.sql"
        )
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        # WAL + NORMAL preserve committed data across process crashes while
        # allowing concurrent readers. MEMORY/OFF could silently lose jobs.
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        sql = self.schema_sql_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(sql)

    def log_audit(
        self,
        conn: sqlite3.Connection,
        entity_type: str,
        entity_id: str,
        event_type: str,
        actor: str = "system",
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """
            INSERT INTO audit_events (id, entity_type, entity_id, event_type, actor, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                entity_type,
                entity_id,
                event_type,
                actor,
                json.dumps(details or {}),
                utc_now_iso(),
            ),
        )
        return event_id

    def seed_defaults(self, worker_profiles_root: Path) -> Dict[str, str]:
        now = utc_now_iso()
        worker_profiles_root.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO users (id, email, display_name, role, timezone, created_at)
                VALUES ('usr_admin_01', 'operator@animalpuzzle.local', 'Puzzle Factory Operator', 'ADMIN', 'Africa/Casablanca', ?)
                """,
                (now,),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO brands (id, name, slug, default_language, primary_color_hex, default_bg_hex, watermark_enabled, created_at)
                VALUES ('brd_wildlife_01', 'Wild & Celebrity Puzzle Reels', 'wild-celebrity-puzzle-reels', 'en', '#183AF5', '#F2FAFF', 0, ?)
                """,
                (now,),
            )
            pages = [
                (
                    "pg_atlas_wildlife",
                    "brd_wildlife_01",
                    "Atlas Wildlife & Celebrity Puzzles",
                    "fb_page_1092837465",
                    "https://business.facebook.com/latest/home?asset_id=1092837465",
                    str(worker_profiles_root / "pg_atlas_wildlife"),
                    "CONNECTED",
                    0,
                    2,
                    "23:00",
                    "07:00",
                    "Africa/Casablanca",
                ),
                (
                    "pg_safari_brainteasers",
                    "brd_wildlife_01",
                    "Safari & Star Brain Teasers Daily",
                    "fb_page_2093847561",
                    "https://business.facebook.com/latest/home?asset_id=2093847561",
                    str(worker_profiles_root / "pg_safari_brainteasers"),
                    "NEEDS_LOGIN",
                    0,
                    2,
                    "23:00",
                    "07:00",
                    "Africa/Casablanca",
                ),
            ]
            for p in pages:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO facebook_pages (
                        id, brand_id, page_name, page_external_id, page_url,
                        session_profile_dir, session_status, browser_publishing_enabled,
                        daily_post_cap, quiet_hours_start, quiet_hours_end, timezone, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*p, now),
                )

            default_settings = {
                "default_timezone": "Africa/Casablanca",
                "live_publish_enabled": False,
                "browser_automation_enabled": False,
                "max_daily_posts_per_page": 2,
                "worker_concurrency": 2,
                "default_resolution": "1080x1920",
                "default_fps": 30,
                "default_duration_sec": 15.0,
                "storage_cleanup_retention_days": 30,
            }
            for k, v in default_settings.items():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO system_settings (key, value_json, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (k, json.dumps(v), now),
                )
            self.log_audit(conn, "system", "seed", "SEED_INITIALIZED", "system", {"pages": 2})
        return {"user_id": "usr_admin_01", "brand_id": "brd_wildlife_01", "primary_page_id": "pg_atlas_wildlife"}

    def register_asset(
        self,
        asset_id: str,
        species: str,
        category: str,
        template_affinity: str,
        png_path: str,
        svg_path: Optional[str],
        outline_png_path: Optional[str],
        width: int,
        height: int,
        sha256: str,
        seed: int,
        provenance: str,
        license_str: str,
        validation_dict: Dict[str, Any],
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO assets (
                    id, species, category, template_affinity, png_path, svg_path,
                    outline_png_path, width, height, sha256, seed, provenance,
                    license, validation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    species,
                    category,
                    template_affinity,
                    png_path,
                    svg_path,
                    outline_png_path,
                    width,
                    height,
                    sha256,
                    seed,
                    provenance,
                    license_str,
                    json.dumps(validation_dict),
                    now,
                ),
            )
            if category in ("animal", "celebrity_face") and "missing_piece_bounds" in validation_dict:
                mask_id = f"msk_{species}_slice"
                conn.execute(
                    """
                    INSERT OR REPLACE INTO asset_masks (
                        id, asset_id, mask_type, base_png_path, piece_png_path,
                        slice_bounds_json, alignment_target_xy_json, pixel_match_mad, created_at
                    ) VALUES (?, ?, 'MISSING_SLICE', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        mask_id,
                        asset_id,
                        str(Path(png_path).parent.parent / "masks" / f"{species}_missing_base.png"),
                        str(Path(png_path).parent.parent / "masks" / f"{species}_missing_piece.png"),
                        json.dumps(validation_dict.get("missing_piece_bounds", [])),
                        json.dumps(validation_dict.get("missing_piece_target_xy", [])),
                        float(validation_dict.get("missing_piece_mad", 0.0)),
                        now,
                    ),
                )
            if category in ("animal", "celebrity_face") and "horizontal_slice_bounds" in validation_dict:
                h_mask_id = f"msk_{species}_horiz_slice"
                conn.execute(
                    """
                    INSERT OR REPLACE INTO asset_masks (
                        id, asset_id, mask_type, base_png_path, piece_png_path,
                        slice_bounds_json, alignment_target_xy_json, pixel_match_mad, created_at
                    ) VALUES (?, ?, 'FACE_HORIZ_SLICE', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        h_mask_id,
                        asset_id,
                        str(Path(png_path).parent.parent / "masks" / f"{species}_horiz_base.png"),
                        str(Path(png_path).parent.parent / "masks" / f"{species}_horiz_piece.png"),
                        json.dumps(validation_dict.get("horizontal_slice_bounds", [])),
                        json.dumps(validation_dict.get("horizontal_slice_target_xy", [])),
                        float(validation_dict.get("horizontal_slice_mad", 0.0)),
                        now,
                    ),
                )

    def create_batch(
        self,
        brand_id: str,
        name: str,
        requested_count: int,
        template_filter: str = "ALL",
        language: str = "en",
        target_duration_sec: float = 15.0,
        enable_audio: bool = True,
    ) -> str:
        batch_id = f"bat_{uuid.uuid4().hex[:10]}"
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO batches (
                    id, brand_id, name, requested_count, completed_count, failed_count,
                    template_filter, language, target_duration_sec, enable_audio,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?, ?, 'QUEUED', ?, ?)
                """,
                (
                    batch_id,
                    brand_id,
                    name,
                    requested_count,
                    template_filter,
                    language,
                    target_duration_sec,
                    1 if enable_audio else 0,
                    now,
                    now,
                ),
            )
            self.log_audit(
                conn,
                "batch",
                batch_id,
                "BATCH_CREATED",
                "operator",
                {"requested_count": requested_count, "template_filter": template_filter},
            )
        return batch_id

    def create_project_and_job(
        self,
        brand_id: str,
        page_id: Optional[str],
        title: str,
        template_id: str,
        species: str,
        asset_id: str,
        seed: int,
        config_dict: Dict[str, Any],
        caption: str,
        engagement_question: str,
        hashtags: str,
        language: str = "en",
        batch_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        now = utc_now_iso()
        config_str = json.dumps(config_dict, sort_keys=True)
        content_hash = hashlib.sha256(f"{template_id}:{species}:{seed}:{config_str}".encode()).hexdigest()

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM video_projects WHERE content_hash = ?",
                (content_hash,),
            ).fetchone()
            if existing:
                proj_id = str(existing["id"])
                job_row = conn.execute(
                    "SELECT id FROM render_jobs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                    (proj_id,),
                ).fetchone()
                return proj_id, str(job_row["id"]) if job_row else f"job_{uuid.uuid4().hex[:10]}"

            # Resolve asset_id dynamically if needed
            asset_row = conn.execute("SELECT id FROM assets WHERE species = ? LIMIT 1", (species,)).fetchone()
            resolved_asset_id = str(asset_row["id"]) if asset_row else asset_id

            proj_id = f"prj_{uuid.uuid4().hex[:10]}"
            job_id = f"job_{uuid.uuid4().hex[:10]}"
            if template_id == "MISSING_PIECE_SLIDE":
                mask_id = f"msk_{species}_slice"
            elif template_id == "FACE_FEATURE_SLIDE":
                mask_id = f"msk_{species}_horiz_slice"
            else:
                mask_id = None

            conn.execute(
                """
                INSERT INTO video_projects (
                    id, brand_id, page_id, idea_id, title, template_id, template_version,
                    species, asset_id, mask_id, seed, config_json, caption,
                    engagement_question, hashtags, language, render_status, publish_status,
                    content_hash, created_at, updated_at
                ) VALUES (?, ?, ?, NULL, ?, ?, '1.0.0', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'QUEUED', 'DRAFT', ?, ?, ?)
                """,
                (
                    proj_id,
                    brand_id,
                    page_id,
                    title,
                    template_id,
                    species,
                    resolved_asset_id,
                    mask_id,
                    seed,
                    config_str,
                    caption,
                    engagement_question,
                    hashtags,
                    language,
                    content_hash,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO render_jobs (
                    id, project_id, batch_id, status, progress_pct, attempt_count,
                    max_attempts, created_at
                ) VALUES (?, ?, ?, 'QUEUED', 0, 0, 3, ?)
                """,
                (job_id, proj_id, batch_id, now),
            )
            self.log_audit(
                conn,
                "video_project",
                proj_id,
                "PROJECT_QUEUED",
                "system",
                {"job_id": job_id, "template_id": template_id, "species": species, "seed": seed},
            )
        return proj_id, job_id

    def transition_render_job(
        self,
        job_id: str,
        new_status: str,
        progress_pct: Optional[int] = None,
        error_log: Optional[str] = None,
        worker_id: str = "worker_local_01",
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT project_id, status, attempt_count, progress_pct FROM render_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if not row:
                raise KeyError(f"Render job not found: {job_id}")
            cur_status = str(row["status"])
            if new_status != cur_status and new_status not in VALID_RENDER_TRANSITIONS.get(cur_status, set()):
                raise ValueError(f"Invalid render transition: {cur_status} -> {new_status}")

            attempt = int(row["attempt_count"]) + (1 if (new_status == "RENDERING" and cur_status != "RENDERING") else 0)
            prog = progress_pct if progress_pct is not None else int(row["progress_pct"])
            started_at = now if (new_status == "RENDERING" and cur_status != "RENDERING") else None
            completed_at = now if new_status in ("READY", "FAILED", "CANCELLED") else None

            conn.execute(
                """
                UPDATE render_jobs
                SET status = ?,
                    progress_pct = ?,
                    attempt_count = ?,
                    worker_id = ?,
                    error_log = COALESCE(?, error_log),
                    started_at = COALESCE(?, started_at),
                    completed_at = COALESCE(?, completed_at)
                WHERE id = ?
                """,
                (new_status, prog, attempt, worker_id, error_log, started_at, completed_at, job_id),
            )
            conn.execute(
                "UPDATE video_projects SET render_status = ?, updated_at = ? WHERE id = ?",
                (new_status, now, str(row["project_id"])),
            )

    def record_render_output(
        self,
        job_id: str,
        project_id: str,
        mp4_path: str,
        thumbnail_path: str,
        alignment_frame_png_path: str,
        width: int,
        height: int,
        fps: float,
        duration_sec: float,
        file_size_bytes: int,
        sha256: str,
        pixel_match_mad: float,
        qa_passed: bool,
        qa_report_dict: Dict[str, Any],
    ) -> str:
        out_id = f"out_{uuid.uuid4().hex[:10]}"
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO render_outputs (
                    id, job_id, project_id, mp4_path, thumbnail_path,
                    alignment_frame_png_path, width, height, fps, duration_sec,
                    file_size_bytes, sha256, pixel_match_mad, qa_passed,
                    qa_report_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    out_id,
                    job_id,
                    project_id,
                    mp4_path,
                    thumbnail_path,
                    alignment_frame_png_path,
                    width,
                    height,
                    fps,
                    duration_sec,
                    file_size_bytes,
                    sha256,
                    pixel_match_mad,
                    1 if qa_passed else 0,
                    json.dumps(qa_report_dict),
                    now,
                ),
            )
            self.log_audit(
                conn,
                "render_output",
                out_id,
                "RENDER_QA_COMPLETED",
                "worker",
                {"job_id": job_id, "qa_passed": qa_passed, "pixel_match_mad": pixel_match_mad},
            )
        return out_id

    def recover_stalled_render_jobs(self) -> int:
        now = utc_now_iso()
        recovered = 0
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, project_id, attempt_count, max_attempts FROM render_jobs WHERE status = 'RENDERING'"
            ).fetchall()
            for r in rows:
                if int(r["attempt_count"]) < int(r["max_attempts"]):
                    conn.execute(
                        "UPDATE render_jobs SET status = 'QUEUED', error_log = 'Recovered after worker restart' WHERE id = ?",
                        (str(r["id"]),),
                    )
                    conn.execute(
                        "UPDATE video_projects SET render_status = 'QUEUED', updated_at = ? WHERE id = ?",
                        (now, str(r["project_id"])),
                    )
                    self.log_audit(conn, "render_job", str(r["id"]), "CRASH_RECOVERED_TO_QUEUE", "worker", {})
                    recovered += 1
                else:
                    conn.execute(
                        "UPDATE render_jobs SET status = 'FAILED', error_log = 'Exceeded max attempts after crash' WHERE id = ?",
                        (str(r["id"]),),
                    )
                    conn.execute(
                        "UPDATE video_projects SET render_status = 'FAILED', updated_at = ? WHERE id = ?",
                        (now, str(r["project_id"])),
                    )
        return recovered

    def approve_and_schedule_project(
        self,
        project_id: str,
        page_id: str,
        scheduled_for_local_iso: str,
        timezone_name: str = "Africa/Casablanca",
        publisher_mode: str = "MANUAL_EXPORT",
    ) -> str:
        tz = ZoneInfo(timezone_name)
        dt_local = datetime.fromisoformat(scheduled_for_local_iso)
        if dt_local.tzinfo is None:
            dt_local = dt_local.replace(tzinfo=tz)
        dt_utc = dt_local.astimezone(timezone.utc)
        utc_iso = dt_utc.replace(microsecond=0).isoformat()
        day_prefix = dt_utc.strftime("%Y-%m-%d")

        now = utc_now_iso()
        with self._connect() as conn:
            proj = conn.execute(
                "SELECT render_status, content_hash FROM video_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if not proj:
                raise KeyError(f"Project {project_id} not found")
            if str(proj["render_status"]) != "READY":
                raise ValueError(f"Cannot approve/schedule project unless render_status is READY (got {proj['render_status']})")

            page = conn.execute(
                "SELECT daily_post_cap FROM facebook_pages WHERE id = ?",
                (page_id,),
            ).fetchone()
            if not page:
                raise KeyError(f"Facebook Page {page_id} not found")

            daily_cap = int(page["daily_post_cap"])
            scheduled_today = conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM scheduled_posts
                WHERE page_id = ? AND substr(scheduled_for_utc, 1, 10) = ?
                  AND status NOT IN ('FAILED', 'BLOCKED')
                """,
                (page_id, day_prefix),
            ).fetchone()
            if int(scheduled_today["cnt"]) >= daily_cap:
                raise ValueError(f"Daily post cap ({daily_cap}/day) reached for Page {page_id} on {day_prefix}")

            idem_key = hashlib.sha256(f"{page_id}:{project_id}:{proj['content_hash']}".encode()).hexdigest()[:24]
            sched_id = f"sch_{uuid.uuid4().hex[:10]}"

            conn.execute(
                "UPDATE video_projects SET publish_status = 'SCHEDULED', page_id = ?, updated_at = ? WHERE id = ?",
                (page_id, now, project_id),
            )
            conn.execute(
                """
                INSERT INTO scheduled_posts (
                    id, project_id, page_id, scheduled_for_utc, timezone,
                    publisher_mode, status, idempotency_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'SCHEDULED', ?, ?, ?)
                """,
                (sched_id, project_id, page_id, utc_iso, timezone_name, publisher_mode, idem_key, now, now),
            )
            self.log_audit(
                conn,
                "scheduled_post",
                sched_id,
                "POST_APPROVED_AND_SCHEDULED",
                "operator",
                {
                    "project_id": project_id,
                    "page_id": page_id,
                    "scheduled_for_utc": utc_iso,
                    "timezone": timezone_name,
                    "publisher_mode": publisher_mode,
                },
            )
        return sched_id

    def acquire_page_lock(self, page_id: str, lock_owner_id: str) -> bool:
        now = utc_now_iso()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT active_lock_job_id FROM facebook_pages WHERE id = ?",
                (page_id,),
            ).fetchone()
            if not row:
                raise KeyError(f"Page not found: {page_id}")
            if row["active_lock_job_id"] is not None and str(row["active_lock_job_id"]) != lock_owner_id:
                return False
            conn.execute(
                "UPDATE facebook_pages SET active_lock_job_id = ?, last_heartbeat_at = ? WHERE id = ?",
                (lock_owner_id, now, page_id),
            )
            return True

    def release_page_lock(self, page_id: str, lock_owner_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE facebook_pages SET active_lock_job_id = NULL WHERE id = ? AND active_lock_job_id = ?",
                (page_id, lock_owner_id),
            )

    def transition_scheduled_post(
        self,
        scheduled_post_id: str,
        new_status: str,
        export_bundle_path: Optional[str] = None,
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT project_id, status FROM scheduled_posts WHERE id = ?",
                (scheduled_post_id,),
            ).fetchone()
            if not row:
                raise KeyError(f"Scheduled post not found: {scheduled_post_id}")
            cur_status = str(row["status"])
            if new_status != cur_status and new_status not in VALID_PUBLISH_TRANSITIONS.get(cur_status, set()):
                raise ValueError(
                    f"Illegal publish state transition {cur_status} -> {new_status} "
                    f"(Note: UNKNOWN_RESULT requires manual operator resolution to prevent duplicate posts)"
                )

            conn.execute(
                """
                UPDATE scheduled_posts
                SET status = ?,
                    export_bundle_path = COALESCE(?, export_bundle_path),
                    updated_at = ?
                WHERE id = ?
                """,
                (new_status, export_bundle_path, now, scheduled_post_id),
            )
            conn.execute(
                "UPDATE video_projects SET publish_status = ?, updated_at = ? WHERE id = ?",
                (new_status, now, str(row["project_id"])),
            )
            self.log_audit(
                conn,
                "scheduled_post",
                scheduled_post_id,
                f"PUBLISH_STATUS_{new_status}",
                "publisher",
                {"from": cur_status, "to": new_status},
            )
