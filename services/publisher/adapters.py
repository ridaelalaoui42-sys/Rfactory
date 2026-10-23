"""
Facebook Publishing Adapters for Animal Puzzle Reels Factory (Playwright / Browser + Manual Export).
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.database.repository import FactoryRepository, utc_now_iso


@dataclass
class PublishResult:
    attempt_id: str
    scheduled_post_id: str
    adapter_name: str
    status: str
    failure_taxonomy: Optional[str]
    dry_run: bool
    external_permalink: Optional[str]
    export_bundle_path: Optional[str]
    sanitized_screenshot_path: Optional[str]
    trace_steps: List[str]


class ManualExportPublisher:
    adapter_name = "ManualExportPublisher"

    def __init__(self, repo: FactoryRepository, exports_root: Path) -> None:
        self.repo = repo
        self.exports_root = Path(exports_root)
        self.exports_root.mkdir(parents=True, exist_ok=True)

    def export_scheduled_post(self, scheduled_post_id: str) -> PublishResult:
        attempt_id = f"att_{uuid.uuid4().hex[:10]}"
        started_at = utc_now_iso()
        trace: List[str] = ["Initialized ManualExportPublisher"]

        with self.repo._connect() as conn:
            row = conn.execute(
                """
                SELECT s.id AS sched_id, s.project_id, s.page_id, s.scheduled_for_utc, s.timezone, s.idempotency_key,
                       p.title, p.caption, p.engagement_question, p.hashtags, p.species, p.template_id, p.seed,
                       pg.page_name, pg.page_external_id, pg.page_url,
                       o.mp4_path, o.thumbnail_path, o.sha256, o.duration_sec
                FROM scheduled_posts s
                JOIN video_projects p ON p.id = s.project_id
                JOIN facebook_pages pg ON pg.id = s.page_id
                JOIN render_outputs o ON o.project_id = p.id
                WHERE s.id = ?
                ORDER BY o.created_at DESC LIMIT 1
                """,
                (scheduled_post_id,),
            ).fetchone()
            if not row:
                raise KeyError(f"Scheduled post or render output not found for {scheduled_post_id}")

        bundle_dir = self.exports_root / f"{scheduled_post_id}_{row['species']}"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        mp4_dest = bundle_dir / "reel_1080x1920.mp4"
        cover_dest = bundle_dir / "cover_1080x1920.png"
        caption_dest = bundle_dir / "caption.txt"
        manifest_dest = bundle_dir / "manifest.json"
        instructions_dest = bundle_dir / "POSTING_INSTRUCTIONS.md"

        shutil.copy2(str(row["mp4_path"]), mp4_dest)
        trace.append(f"Copied verified H.264 MP4 to {mp4_dest.name}")
        shutil.copy2(str(row["thumbnail_path"]), cover_dest)
        trace.append(f"Copied cover frame PNG to {cover_dest.name}")

        caption_text = str(row["caption"])
        caption_dest.write_text(caption_text, encoding="utf-8")

        manifest_data = {
            "scheduled_post_id": scheduled_post_id,
            "project_id": str(row["project_id"]),
            "idempotency_key": str(row["idempotency_key"]),
            "target_page_name": str(row["page_name"]),
            "target_page_external_id": str(row["page_external_id"]),
            "scheduled_for_utc": str(row["scheduled_for_utc"]),
            "timezone": str(row["timezone"]),
            "template_id": str(row["template_id"]),
            "species": str(row["species"]),
            "seed": int(row["seed"]),
            "video_sha256": str(row["sha256"]),
            "duration_sec": float(row["duration_sec"]),
            "exported_at_utc": utc_now_iso(),
        }
        manifest_dest.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

        instructions_md = f"""# Manual Meta Business Suite Reel Publishing Package

- **Target Facebook Page**: {row['page_name']} (`{row['page_external_id']}`)
- **Meta Business Suite URL**: {row['page_url']}
- **Scheduled Time ({row['timezone']})**: `{row['scheduled_for_utc']}`
- **Video File**: `reel_1080x1920.mp4` (1080×1920, 30fps, H.264 yuv420p)
- **Cover Thumbnail**: `cover_1080x1920.png`
"""
        instructions_dest.write_text(instructions_md, encoding="utf-8")
        trace.append("Wrote manifest.json and POSTING_INSTRUCTIONS.md")

        with self.repo._connect() as conn:
            conn.execute(
                "UPDATE scheduled_posts SET export_bundle_path = ?, updated_at = ? WHERE id = ?",
                (str(bundle_dir), utc_now_iso(), scheduled_post_id),
            )
            conn.execute(
                """
                INSERT INTO publish_attempts (
                    id, scheduled_post_id, page_id, adapter_name, dry_run,
                    status, failure_taxonomy, trace_log_json, sanitized_screenshot_path,
                    started_at, finished_at
                ) VALUES (?, ?, ?, ?, 1, 'SCHEDULED', NULL, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    scheduled_post_id,
                    str(row["page_id"]),
                    self.adapter_name,
                    json.dumps(trace),
                    str(cover_dest),
                    started_at,
                    utc_now_iso(),
                ),
            )
            self.repo.log_audit(
                conn,
                "scheduled_post",
                scheduled_post_id,
                "MANUAL_EXPORT_GENERATED",
                "publisher",
                {"bundle_dir": str(bundle_dir)},
            )

        return PublishResult(
            attempt_id=attempt_id,
            scheduled_post_id=scheduled_post_id,
            adapter_name=self.adapter_name,
            status="SCHEDULED",
            failure_taxonomy=None,
            dry_run=True,
            external_permalink=None,
            export_bundle_path=str(bundle_dir),
            sanitized_screenshot_path=str(cover_dest),
            trace_steps=trace,
        )


class MetaBusinessSuitePlaywrightPublisher:
    adapter_name = "MetaBusinessSuitePlaywrightPublisher"

    def __init__(self, repo: FactoryRepository, artifacts_dir: Path) -> None:
        self.repo = repo
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def publish_reel(
        self,
        scheduled_post_id: str,
        dry_run: bool = True,
        live_publish_enabled: bool = False,
        composer_override_url: Optional[str] = None,
        simulated_dom_state: Optional[Dict[str, Any]] = None,
    ) -> PublishResult:
        attempt_id = f"att_{uuid.uuid4().hex[:10]}"
        started_at = utc_now_iso()
        trace: List[str] = [f"Starting {self.adapter_name} (dry_run={dry_run})"]

        with self.repo._connect() as conn:
            row = conn.execute(
                """
                SELECT s.id AS sched_id, s.project_id, s.page_id, s.status AS sched_status,
                       p.caption, p.render_status,
                       pg.page_name, pg.page_external_id, pg.page_url, pg.session_profile_dir,
                       pg.session_status, pg.browser_publishing_enabled,
                       o.mp4_path, o.thumbnail_path
                FROM scheduled_posts s
                JOIN video_projects p ON p.id = s.project_id
                JOIN facebook_pages pg ON pg.id = s.page_id
                LEFT JOIN render_outputs o ON o.project_id = p.id
                WHERE s.id = ?
                ORDER BY o.created_at DESC LIMIT 1
                """,
                (scheduled_post_id,),
            ).fetchone()
            if not row:
                raise KeyError(f"Scheduled post not found: {scheduled_post_id}")

        page_id = str(row["page_id"])
        cur_sched_status = str(row["sched_status"])

        if cur_sched_status == "UNKNOWN_RESULT":
            trace.append("ABORT: Scheduled post is in UNKNOWN_RESULT state; human verification required.")
            return self._record_attempt(
                attempt_id=attempt_id,
                scheduled_post_id=scheduled_post_id,
                page_id=page_id,
                dry_run=dry_run,
                status="UNKNOWN_RESULT",
                taxonomy="UNKNOWN_RESULT",
                trace=trace,
                started_at=started_at,
                screenshot_path=None,
                permalink=None,
            )

        # SAFETY: This release contains a DOM-state simulator, not a real Playwright
        # browser integration. Never treat its trace messages as evidence of a
        # Facebook upload or publication. In normal operation fail closed.
        if simulated_dom_state is None:
            trace.append(
                "BROWSER_WORKFLOW_UNIMPLEMENTED: No browser was opened, no upload "
                "occurred, and no publish action was performed. Use manual export."
            )
            return self._record_attempt(
                attempt_id=attempt_id,
                scheduled_post_id=scheduled_post_id,
                page_id=page_id,
                dry_run=True,
                status="BLOCKED",
                taxonomy="BROWSER_WORKFLOW_UNIMPLEMENTED",
                trace=trace,
                started_at=started_at,
                screenshot_path=None,
                permalink=None,
            )
        if os.environ.get("RFACTORY_ALLOW_TEST_SIMULATION") != "1":
            trace.append("SIMULATION_DISABLED: Test DOM input rejected outside isolated tests.")
            return self._record_attempt(
                attempt_id=attempt_id,
                scheduled_post_id=scheduled_post_id,
                page_id=page_id,
                dry_run=True,
                status="BLOCKED",
                taxonomy="SIMULATION_DISABLED",
                trace=trace,
                started_at=started_at,
                screenshot_path=None,
                permalink=None,
            )

        if int(row["browser_publishing_enabled"]) == 0:
            trace.append("ABORT: Browser automation is disabled on this Page (browser_publishing_enabled=0).")
            self.repo.transition_scheduled_post(scheduled_post_id, "BLOCKED")
            return self._record_attempt(
                attempt_id=attempt_id,
                scheduled_post_id=scheduled_post_id,
                page_id=page_id,
                dry_run=dry_run,
                status="BLOCKED",
                taxonomy="POLICY_BLOCKED",
                trace=trace,
                started_at=started_at,
                screenshot_path=None,
                permalink=None,
            )

        if not self.repo.acquire_page_lock(page_id, scheduled_post_id):
            trace.append(f"ABORT: Page {page_id} is currently locked by another active publishing job.")
            return self._record_attempt(
                attempt_id=attempt_id,
                scheduled_post_id=scheduled_post_id,
                page_id=page_id,
                dry_run=dry_run,
                status="BLOCKED",
                taxonomy="POLICY_BLOCKED",
                trace=trace,
                started_at=started_at,
                screenshot_path=None,
                permalink=None,
            )

        try:
            dom = simulated_dom_state or {}
            if str(row["session_status"]) != "CONNECTED" or dom.get("login_wall", False):
                trace.append("Detected expired or unauthenticated Facebook session; pausing for human login.")
                self.repo.transition_scheduled_post(scheduled_post_id, "NEEDS_LOGIN")
                return self._record_attempt(
                    attempt_id=attempt_id,
                    scheduled_post_id=scheduled_post_id,
                    page_id=page_id,
                    dry_run=dry_run,
                    status="NEEDS_LOGIN",
                    taxonomy="SESSION_EXPIRED",
                    trace=trace,
                    started_at=started_at,
                    screenshot_path=None,
                    permalink=None,
                )

            if dom.get("captcha_present", False):
                trace.append("Detected security/CAPTCHA checkpoint; halting immediately without bypass.")
                self.repo.transition_scheduled_post(scheduled_post_id, "BLOCKED")
                return self._record_attempt(
                    attempt_id=attempt_id,
                    scheduled_post_id=scheduled_post_id,
                    page_id=page_id,
                    dry_run=dry_run,
                    status="BLOCKED",
                    taxonomy="CAPTCHA_REQUIRED",
                    trace=trace,
                    started_at=started_at,
                    screenshot_path=None,
                    permalink=None,
                )

            mp4_path = Path(str(row["mp4_path"])) if row["mp4_path"] else None
            if not mp4_path or not mp4_path.exists():
                trace.append("MP4 file missing or unreadable before upload.")
                self.repo.transition_scheduled_post(scheduled_post_id, "UPLOADING")
                self.repo.transition_scheduled_post(scheduled_post_id, "FAILED")
                return self._record_attempt(
                    attempt_id=attempt_id,
                    scheduled_post_id=scheduled_post_id,
                    page_id=page_id,
                    dry_run=dry_run,
                    status="FAILED",
                    taxonomy="UPLOAD_FAILED",
                    trace=trace,
                    started_at=started_at,
                    screenshot_path=None,
                    permalink=None,
                )

            expected_page_name = str(row["page_name"])
            detected_page_name = str(dom.get("detected_page_name", expected_page_name))
            if detected_page_name != expected_page_name:
                trace.append(
                    f"CRITICAL SAFETY HALT: Composer active Page '{detected_page_name}' != intended Page '{expected_page_name}'."
                )
                self.repo.transition_scheduled_post(scheduled_post_id, "UPLOADING")
                self.repo.transition_scheduled_post(scheduled_post_id, "FAILED")
                return self._record_attempt(
                    attempt_id=attempt_id,
                    scheduled_post_id=scheduled_post_id,
                    page_id=page_id,
                    dry_run=dry_run,
                    status="FAILED",
                    taxonomy="WRONG_PAGE",
                    trace=trace,
                    started_at=started_at,
                    screenshot_path=None,
                    permalink=None,
                )

            if dom.get("ui_selector_missing", False):
                trace.append("Reel composer upload/caption locator not found; Meta Business Suite UI changed.")
                self.repo.transition_scheduled_post(scheduled_post_id, "UPLOADING")
                self.repo.transition_scheduled_post(scheduled_post_id, "FAILED")
                return self._record_attempt(
                    attempt_id=attempt_id,
                    scheduled_post_id=scheduled_post_id,
                    page_id=page_id,
                    dry_run=dry_run,
                    status="FAILED",
                    taxonomy="UI_CHANGED",
                    trace=trace,
                    started_at=started_at,
                    screenshot_path=None,
                    permalink=None,
                )

            self.repo.transition_scheduled_post(scheduled_post_id, "UPLOADING")
            trace.append(f"Verified active Page header: '{expected_page_name}'")
            trace.append(f"Attached MP4 file ({mp4_path.name}) to Reel file input and waited for 100% upload processing")
            trace.append(f"Populated Reel description ({len(str(row['caption']))} chars)")

            if dry_run or not live_publish_enabled:
                trace.append("DRY-RUN COMPLETE: Stopped safely before clicking final Publish/Schedule button.")
                with self.repo._connect() as conn:
                    conn.execute(
                        "UPDATE scheduled_posts SET status = 'SCHEDULED', updated_at = ? WHERE id = ?",
                        (utc_now_iso(), scheduled_post_id),
                    )
                    conn.execute(
                        "UPDATE video_projects SET publish_status = 'SCHEDULED', updated_at = ? WHERE id = ?",
                        (utc_now_iso(), str(row["project_id"])),
                    )
                return self._record_attempt(
                    attempt_id=attempt_id,
                    scheduled_post_id=scheduled_post_id,
                    page_id=page_id,
                    dry_run=True,
                    status="SCHEDULED",
                    taxonomy=None,
                    trace=trace,
                    started_at=started_at,
                    screenshot_path=str(row["thumbnail_path"]),
                    permalink=None,
                )

            self.repo.transition_scheduled_post(scheduled_post_id, "SUBMITTING")
            trace.append("Clicked final Publish button in Meta Business Suite composer.")
            self.repo.transition_scheduled_post(scheduled_post_id, "VERIFYING")

            if dom.get("ambiguous_confirmation", False):
                trace.append(
                    "WARNING: Submission completed but confirmation toast/permalink timed out. "
                    "Flagging UNKNOWN_RESULT to prevent duplicate re-submission."
                )
                self.repo.transition_scheduled_post(scheduled_post_id, "UNKNOWN_RESULT")
                return self._record_attempt(
                    attempt_id=attempt_id,
                    scheduled_post_id=scheduled_post_id,
                    page_id=page_id,
                    dry_run=False,
                    status="UNKNOWN_RESULT",
                    taxonomy="UNKNOWN_RESULT",
                    trace=trace,
                    started_at=started_at,
                    screenshot_path=str(row["thumbnail_path"]),
                    permalink=None,
                )

            permalink = str(
                dom.get("permalink")
                or f"https://www.facebook.com/{row['page_external_id']}/videos/{uuid.uuid4().hex[:12]}"
            )
            trace.append(f"Verified visible publish confirmation and captured permalink: {permalink}")
            self.repo.transition_scheduled_post(scheduled_post_id, "PUBLISHED")

            with self.repo._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO published_posts (
                        id, scheduled_post_id, page_id, project_id,
                        external_permalink, confirmation_method, published_at_utc
                    ) VALUES (?, ?, ?, ?, ?, 'DOM_TOAST_AND_PERMALINK', ?)
                    """,
                    (
                        f"pub_{uuid.uuid4().hex[:10]}",
                        scheduled_post_id,
                        page_id,
                        str(row["project_id"]),
                        permalink,
                        utc_now_iso(),
                    ),
                )

            return self._record_attempt(
                attempt_id=attempt_id,
                scheduled_post_id=scheduled_post_id,
                page_id=page_id,
                dry_run=False,
                status="PUBLISHED",
                taxonomy="PUBLISHED",
                trace=trace,
                started_at=started_at,
                screenshot_path=str(row["thumbnail_path"]),
                permalink=permalink,
            )

        finally:
            self.repo.release_page_lock(page_id, scheduled_post_id)

    def _record_attempt(
        self,
        attempt_id: str,
        scheduled_post_id: str,
        page_id: str,
        dry_run: bool,
        status: str,
        taxonomy: Optional[str],
        trace: List[str],
        started_at: str,
        screenshot_path: Optional[str],
        permalink: Optional[str],
    ) -> PublishResult:
        with self.repo._connect() as conn:
            conn.execute(
                """
                INSERT INTO publish_attempts (
                    id, scheduled_post_id, page_id, adapter_name, dry_run,
                    status, failure_taxonomy, trace_log_json, sanitized_screenshot_path,
                    started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    scheduled_post_id,
                    page_id,
                    self.adapter_name,
                    1 if dry_run else 0,
                    status,
                    taxonomy,
                    json.dumps(trace),
                    screenshot_path,
                    started_at,
                    utc_now_iso(),
                ),
            )
        return PublishResult(
            attempt_id=attempt_id,
            scheduled_post_id=scheduled_post_id,
            adapter_name=self.adapter_name,
            status=status,
            failure_taxonomy=taxonomy,
            dry_run=dry_run,
            external_permalink=permalink,
            export_bundle_path=None,
            sanitized_screenshot_path=screenshot_path,
            trace_steps=trace,
        )
