"""
Durable Batch & Queue Worker for Animal & Celebrity Face Puzzle Reels Factory.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from services.content.agent import ContentGenerationAgent
from services.database.repository import FactoryRepository, utc_now_iso
from services.engine.qa_validator import validate_rendered_video
from services.engine.renderer import PuzzleVideoRenderer, RenderConfig


class BatchProductionWorker:
    def __init__(
        self,
        repo: FactoryRepository,
        renderer: PuzzleVideoRenderer,
        content_agent: ContentGenerationAgent,
        worker_id: str = "worker_local_01",
    ) -> None:
        self.repo = repo
        self.renderer = renderer
        self.content_agent = content_agent
        self.worker_id = worker_id

    def enqueue_batch_campaign(
        self,
        brand_id: str = "brd_wildlife_01",
        page_id: Optional[str] = "pg_atlas_wildlife",
        name: str = "Weekly Wildlife & Celebrity Puzzle Batch",
        count: int = 10,
        template_filter: str = "ALL",
        language: str = "en",
        duration_sec: float = 15.0,
        enable_audio: bool = True,
        base_seed: int = 1001,
    ) -> Tuple[str, List[str]]:
        batch_id = self.repo.create_batch(
            brand_id=brand_id,
            name=name,
            requested_count=count,
            template_filter=template_filter,
            language=language,
            target_duration_sec=duration_sec,
            enable_audio=enable_audio,
        )
        ideas = self.content_agent.generate_batch_ideas(
            count=count,
            template_filter=template_filter,
            language=language,
            base_seed=base_seed,
        )
        job_ids: List[str] = []
        for idx, idea in enumerate(ideas):
            cfg = RenderConfig(
                job_id=f"batch_{batch_id}_{idx+1:02d}_{idea.species}",
                template_id=idea.template_id,
                species=idea.species,
                seed=idea.seed,
                width=1080,
                height=1920,
                fps=30,
                duration_sec=duration_sec,
                background_hex=idea.background_hex,
                object_count=idea.object_count,
                offset_distance_px=idea.offset_distance_px,
                cycles=idea.cycles,
                hold_ratio=idea.hold_ratio,
                slice_x_ratio=idea.slice_x_ratio,
                enable_audio=enable_audio,
            )
            asset_prefix = (
                "celebrity_face"
                if idea.species in ("football_icon", "pop_diva", "cinema_star", "genius_scientist", "astronaut_hero", "chef_maestro")
                else "animal"
            )
            _, job_id = self.repo.create_project_and_job(
                brand_id=brand_id,
                page_id=page_id,
                title=idea.title,
                template_id=idea.template_id,
                species=idea.species,
                asset_id=f"{asset_prefix}_{idea.species}",
                seed=idea.seed,
                config_dict=asdict(cfg),
                caption=idea.caption,
                engagement_question=idea.hook_question,
                hashtags=idea.hashtags,
                language=idea.language,
                batch_id=batch_id,
            )
            job_ids.append(job_id)
        return batch_id, job_ids

    def process_single_job(self, job_id: str) -> Dict[str, Any]:
        with self.repo._connect() as conn:
            row = conn.execute(
                """
                SELECT j.id AS job_id, j.project_id, j.batch_id, j.status,
                       p.config_json, p.template_id, p.species, p.seed
                FROM render_jobs j
                JOIN video_projects p ON p.id = j.project_id
                WHERE j.id = ?
                """,
                (job_id,),
            ).fetchone()
            if not row:
                raise KeyError(f"Job {job_id} not found")

        project_id = str(row["project_id"])
        batch_id = str(row["batch_id"]) if row["batch_id"] else None
        cfg_dict = json.loads(str(row["config_json"]))
        cfg_dict["slice_x_ratio"] = tuple(cfg_dict.get("slice_x_ratio", (0.27, 0.51)))
        cfg_dict["slice_y_ratio"] = tuple(cfg_dict.get("slice_y_ratio", (0.30, 0.54)))
        cfg_dict["outline_color_rgba"] = tuple(cfg_dict.get("outline_color_rgba", (24, 58, 245, 255)))
        cfg_dict["placeholder_color_rgba"] = tuple(cfg_dict.get("placeholder_color_rgba", (255, 232, 0, 255)))
        cfg_dict["job_id"] = f"{job_id}_{row['species']}"
        cfg = RenderConfig(**cfg_dict)

        try:
            self.repo.transition_render_job(job_id, "RENDERING", progress_pct=10, worker_id=self.worker_id)

            artifact = self.renderer.render_video(cfg, progress_callback=None)

            self.repo.transition_render_job(job_id, "QA", progress_pct=95, worker_id=self.worker_id)
            qa_report = validate_rendered_video(
                artifact.mp4_path,
                expected_width=cfg.width,
                expected_height=cfg.height,
                expected_fps=float(cfg.fps),
                expected_duration_sec=cfg.duration_sec,
                require_audio=cfg.enable_audio,
                missing_piece_mad=artifact.pixel_match_mad,
            )

            self.repo.record_render_output(
                job_id=job_id,
                project_id=project_id,
                mp4_path=artifact.mp4_path,
                thumbnail_path=artifact.thumbnail_path,
                alignment_frame_png_path=artifact.alignment_frame_png_path,
                width=artifact.width,
                height=artifact.height,
                fps=float(artifact.fps),
                duration_sec=artifact.duration_sec,
                file_size_bytes=qa_report.file_size_bytes,
                sha256=artifact.sha256,
                pixel_match_mad=artifact.pixel_match_mad,
                qa_passed=qa_report.passed,
                qa_report_dict=asdict(qa_report),
            )

            if qa_report.passed:
                self.repo.transition_render_job(job_id, "READY", progress_pct=100, worker_id=self.worker_id)
                if batch_id:
                    with self.repo._connect() as conn:
                        conn.execute(
                            "UPDATE batches SET completed_count = completed_count + 1, updated_at = ? WHERE id = ?",
                            (utc_now_iso(), batch_id),
                        )
                return {"job_id": job_id, "status": "READY", "artifact": asdict(artifact), "qa": asdict(qa_report)}
            else:
                err_msg = "; ".join(qa_report.errors)
                self.repo.transition_render_job(
                    job_id, "FAILED", progress_pct=100, error_log=f"QA Failed: {err_msg}", worker_id=self.worker_id
                )
                if batch_id:
                    with self.repo._connect() as conn:
                        conn.execute(
                            "UPDATE batches SET failed_count = failed_count + 1, updated_at = ? WHERE id = ?",
                            (utc_now_iso(), batch_id),
                        )
                return {"job_id": job_id, "status": "FAILED", "error": err_msg}

        except Exception as exc:
            err_str = f"{type(exc).__name__}: {exc}"
            self.repo.transition_render_job(
                job_id, "FAILED", progress_pct=100, error_log=err_str, worker_id=self.worker_id
            )
            if batch_id:
                with self.repo._connect() as conn:
                    conn.execute(
                        "UPDATE batches SET failed_count = failed_count + 1, updated_at = ? WHERE id = ?",
                        (utc_now_iso(), batch_id),
                    )
            return {"job_id": job_id, "status": "FAILED", "error": err_str}

    def process_all_queued_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        self.repo.recover_stalled_render_jobs()
        with self.repo._connect() as conn:
            rows = conn.execute(
                "SELECT id, batch_id FROM render_jobs WHERE status = 'QUEUED' ORDER BY created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()

        results: List[Dict[str, Any]] = []
        touched_batches: set[str] = set()
        for r in rows:
            jid = str(r["id"])
            if r["batch_id"]:
                touched_batches.add(str(r["batch_id"]))
            res = self.process_single_job(jid)
            results.append(res)

        for bid in touched_batches:
            with self.repo._connect() as conn:
                b_row = conn.execute(
                    "SELECT requested_count, completed_count, failed_count FROM batches WHERE id = ?",
                    (bid,),
                ).fetchone()
                if b_row:
                    comp = int(b_row["completed_count"])
                    fail = int(b_row["failed_count"])
                    req = int(b_row["requested_count"])
                    if comp + fail >= req:
                        b_status = "COMPLETED" if fail == 0 else "PARTIAL_FAILURE"
                    else:
                        b_status = "RUNNING"
                    conn.execute(
                        "UPDATE batches SET status = ?, updated_at = ? WHERE id = ?",
                        (b_status, utc_now_iso(), bid),
                    )
        return results
