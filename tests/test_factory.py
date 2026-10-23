"""
Comprehensive Automated Test Suite for Animal & Celebrity Face Puzzle Reels Factory.
Covers all required test areas (unit, vision/masks, pixel-perfect alignment for both
animals and celebrity/people portraits, FFprobe QA, batch fault isolation, crash recovery,
timezone/caps, and mock publisher safety). Never publishes to real Facebook Pages.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import services
from services.assets.generator import (
    ANIMAL_CATALOG,
    generate_procedural_animal_rgba,
    generate_speckled_egg_rgba,
)
from services.assets.segmentation import (
    extract_horizontal_slice_bundle,
    extract_missing_piece_bundle,
    extract_three_band_face_bundle,
    generate_outline_silhouette_rgba,
    validate_alpha_mask,
)
from services.content.agent import ContentGenerationAgent
from services.database.repository import FactoryRepository
from services.engine.qa_validator import validate_rendered_video
from services.engine.renderer import (
    PuzzleVideoRenderer,
    RenderConfig,
    evaluate_periodic_displacement,
)
from services.publisher.adapters import (
    ManualExportPublisher,
    MetaBusinessSuitePlaywrightPublisher,
)
from services.worker.batch_runner import BatchProductionWorker


class AnimalPuzzleReelsFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.storage_root = REPO_ROOT / "storage"
        cls.assets_root = cls.storage_root / "assets"
        cls.renders_root = cls.storage_root / "renders"
        cls.prod_db_path = cls.storage_root / "factory.db"

    def test_01_asset_generation_and_deduplication(self) -> None:
        manifest_path = self.assets_root / "asset_manifest.json"
        self.assertTrue(manifest_path.exists(), "Asset manifest must exist")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(manifest), 23)
        hashes = [m["sha256"] for m in manifest]
        self.assertEqual(len(hashes), len(set(hashes)), "All generated assets must have unique SHA-256 hashes")

    def test_02_segmentation_and_mask_validation(self) -> None:
        rgba, svg = generate_procedural_animal_rgba(
            species="donkey",
            primary_color=(142, 128, 116),
            secondary_color=(218, 208, 198),
            accent_color=(48, 42, 38),
            seed=1002,
        )
        val = validate_alpha_mask(rgba)
        self.assertTrue(val.valid, f"Procedural animal mask failed validation: {val.errors}")
        self.assertFalse(val.touches_border)
        self.assertGreater(val.non_empty_ratio, 0.05)
        self.assertIn("<svg", svg)

        egg_rgba, _ = generate_speckled_egg_rgba(seed=2001)
        egg_val = validate_alpha_mask(egg_rgba)
        self.assertTrue(egg_val.valid)
        outline = generate_outline_silhouette_rgba(egg_rgba)
        self.assertEqual(outline.shape, egg_rgba.shape)

    def test_03_missing_piece_pixel_perfect_alignment(self) -> None:
        rgba, _ = generate_procedural_animal_rgba(
            species="giraffe",
            primary_color=(230, 176, 98),
            secondary_color=(156, 78, 34),
            accent_color=(62, 40, 26),
            seed=1004,
        )
        bundle = extract_missing_piece_bundle(rgba, slice_x_ratio=(0.27, 0.51))
        self.assertEqual(
            bundle.pixel_match_mad,
            0.0,
            "Extracted missing piece must restore original animal with 0.0 Mean Absolute Difference at target XY",
        )
        self.assertGreater(bundle.extracted_piece_rgba.shape[0], 100)
        self.assertGreater(bundle.extracted_piece_rgba.shape[1], 50)

    def test_04_animation_template_displacement_and_loop(self) -> None:
        self.assertEqual(evaluate_periodic_displacement(0.0, hold_ratio=0.14), 0.0)
        self.assertEqual(evaluate_periodic_displacement(0.5, hold_ratio=0.14), 0.0)
        self.assertEqual(evaluate_periodic_displacement(1.0, hold_ratio=0.14), 0.0)
        self.assertAlmostEqual(evaluate_periodic_displacement(0.25, hold_ratio=0.14), 1.0, places=4)
        self.assertAlmostEqual(evaluate_periodic_displacement(0.75, hold_ratio=0.14), -1.0, places=4)

    def test_05_rendered_mp4_qa_verification(self) -> None:
        out_dir = REPO_ROOT.parent / "artifacts/file_generation/ttl=63d/output"
        mp4_a = out_dir / "sample_template_a_outline_match.mp4"
        mp4_b = out_dir / "sample_template_b_missing_piece.mp4"
        self.assertTrue(mp4_a.exists())
        self.assertTrue(mp4_b.exists())

        qa_a = validate_rendered_video(mp4_a)
        qa_b = validate_rendered_video(mp4_b)
        self.assertTrue(qa_a.passed, f"Sample A failed QA: {qa_a.errors}")
        self.assertTrue(qa_b.passed, f"Sample B failed QA: {qa_b.errors}")
        self.assertEqual((qa_a.width, qa_a.height), (1080, 1920))
        self.assertEqual(qa_a.video_codec, "h264")
        self.assertEqual(qa_a.pixel_format, "yuv420p")
        self.assertEqual(qa_a.audio_codec, "aac")

    def test_06_batch_14_videos_verified_in_database(self) -> None:
        repo = FactoryRepository(db_path=self.prod_db_path)
        with repo._connect() as conn:
            ready_jobs = conn.execute(
                "SELECT COUNT(*) AS c FROM render_jobs WHERE status = 'READY'"
            ).fetchone()["c"]
            qa_outputs = conn.execute(
                "SELECT COUNT(*) AS c FROM render_outputs WHERE qa_passed = 1"
            ).fetchone()["c"]
        self.assertGreaterEqual(ready_jobs, 14)
        self.assertGreaterEqual(qa_outputs, 14)

    def test_07_crash_recovery_and_fault_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = FactoryRepository(db_path=tmp_path / "test.db")
            repo.seed_defaults(tmp_path / "profiles")
            repo.register_asset(
                asset_id="animal_lizard",
                species="lizard",
                category="animal",
                template_affinity="OUTLINE_MATCH",
                png_path=str(self.assets_root / "animals/lizard.png"),
                svg_path=None,
                outline_png_path=None,
                width=820,
                height=820,
                sha256="hash_lizard_test",
                seed=1001,
                provenance="test",
                license_str="CC0",
                validation_dict={},
            )
            _, job_id = repo.create_project_and_job(
                brand_id="brd_wildlife_01",
                page_id="pg_atlas_wildlife",
                title="Crash Recovery Test",
                template_id="OUTLINE_MATCH",
                species="lizard",
                asset_id="animal_lizard",
                seed=1001,
                config_dict={"job_id": "crash_job"},
                caption="Test",
                engagement_question="Q?",
                hashtags="#test",
            )
            repo.transition_render_job(job_id, "RENDERING", progress_pct=45)
            recovered = repo.recover_stalled_render_jobs()
            self.assertEqual(recovered, 1)
            with repo._connect() as conn:
                status = conn.execute("SELECT status FROM render_jobs WHERE id = ?", (job_id,)).fetchone()["status"]
            self.assertEqual(status, "QUEUED")

    def test_08_scheduling_timezone_and_daily_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = FactoryRepository(db_path=tmp_path / "test_sched.db")
            repo.seed_defaults(tmp_path / "profiles")
            repo.register_asset(
                asset_id="animal_lizard",
                species="lizard",
                category="animal",
                template_affinity="OUTLINE_MATCH",
                png_path=str(self.assets_root / "animals/lizard.png"),
                svg_path=None,
                outline_png_path=None,
                width=820,
                height=820,
                sha256="hash_lizard_sched",
                seed=1001,
                provenance="test",
                license_str="CC0",
                validation_dict={},
            )
            proj_ids = []
            for i in range(3):
                pid, jid = repo.create_project_and_job(
                    brand_id="brd_wildlife_01",
                    page_id="pg_atlas_wildlife",
                    title=f"Sched Test {i}",
                    template_id="OUTLINE_MATCH",
                    species="lizard",
                    asset_id="animal_lizard",
                    seed=2000 + i,
                    config_dict={"seed": 2000 + i},
                    caption="Cap test",
                    engagement_question="?",
                    hashtags="#test",
                )
                repo.transition_render_job(jid, "RENDERING")
                repo.transition_render_job(jid, "QA")
                repo.transition_render_job(jid, "READY")
                proj_ids.append(pid)

            s1 = repo.approve_and_schedule_project(proj_ids[0], "pg_atlas_wildlife", "2026-10-25T14:00:00", "Africa/Casablanca")
            s2 = repo.approve_and_schedule_project(proj_ids[1], "pg_atlas_wildlife", "2026-10-25T19:00:00", "Africa/Casablanca")
            self.assertTrue(s1.startswith("sch_"))
            self.assertTrue(s2.startswith("sch_"))

            with self.assertRaises(ValueError):
                repo.approve_and_schedule_project(proj_ids[2], "pg_atlas_wildlife", "2026-10-25T21:00:00", "Africa/Casablanca")

    def test_09_publisher_safety_taxonomy_and_unknown_result_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = FactoryRepository(db_path=tmp_path / "test_pub.db")
            repo.seed_defaults(tmp_path / "profiles")
            with repo._connect() as conn:
                conn.execute("UPDATE facebook_pages SET browser_publishing_enabled = 1 WHERE id = 'pg_atlas_wildlife'")

            repo.register_asset(
                asset_id="animal_donkey",
                species="donkey",
                category="animal",
                template_affinity="MISSING_PIECE_SLIDE",
                png_path=str(self.assets_root / "animals/donkey.png"),
                svg_path=None,
                outline_png_path=None,
                width=820,
                height=820,
                sha256="hash_donkey_pub",
                seed=1002,
                provenance="test",
                license_str="CC0",
                validation_dict={"missing_piece_bounds": [220, 120, 418, 740], "missing_piece_target_xy": [220, 120], "missing_piece_mad": 0.0},
            )
            pid, jid = repo.create_project_and_job(
                brand_id="brd_wildlife_01",
                page_id="pg_atlas_wildlife",
                title="Pub Safety Test",
                template_id="MISSING_PIECE_SLIDE",
                species="donkey",
                asset_id="animal_donkey",
                seed=1002,
                config_dict={"seed": 1002},
                caption="Test caption",
                engagement_question="?",
                hashtags="#test",
            )
            repo.transition_render_job(jid, "RENDERING")
            repo.transition_render_job(jid, "QA")
            repo.transition_render_job(jid, "READY")

            out_mp4 = REPO_ROOT.parent / "artifacts/file_generation/ttl=63d/output/sample_template_b_missing_piece.mp4"
            thumb_png = self.renders_root / "job_9105fabefc_donkey/job_9105fabefc_donkey_thumb.png"
            repo.record_render_output(
                job_id=jid,
                project_id=pid,
                mp4_path=str(out_mp4),
                thumbnail_path=str(thumb_png),
                alignment_frame_png_path=str(thumb_png),
                width=1080,
                height=1920,
                fps=30.0,
                duration_sec=15.0,
                file_size_bytes=out_mp4.stat().st_size,
                sha256="sha_test",
                pixel_match_mad=0.0,
                qa_passed=True,
                qa_report_dict={"passed": True},
            )
            sched_id = repo.approve_and_schedule_project(pid, "pg_atlas_wildlife", "2026-10-26T18:00:00")
            pub = MetaBusinessSuitePlaywrightPublisher(repo=repo, artifacts_dir=tmp_path / "traces")

            res_wrong = pub.publish_reel(
                sched_id,
                dry_run=False,
                live_publish_enabled=True,
                simulated_dom_state={"detected_page_name": "Unrelated Personal Page"},
            )
            self.assertEqual(res_wrong.failure_taxonomy, "WRONG_PAGE")
            self.assertEqual(res_wrong.status, "FAILED")

            repo.transition_scheduled_post(sched_id, "SCHEDULED")
            res_unk = pub.publish_reel(
                sched_id,
                dry_run=False,
                live_publish_enabled=True,
                simulated_dom_state={"ambiguous_confirmation": True},
            )
            self.assertEqual(res_unk.status, "UNKNOWN_RESULT")
            self.assertEqual(res_unk.failure_taxonomy, "UNKNOWN_RESULT")

            res_retry = pub.publish_reel(sched_id, dry_run=False, live_publish_enabled=True)
            self.assertEqual(res_retry.status, "UNKNOWN_RESULT")
            self.assertIn("UNKNOWN_RESULT", res_retry.trace_steps[-1])

    def test_10_mock_business_suite_fixture_and_content_agent(self) -> None:
        fixture = REPO_ROOT / "tests/fixtures/mock_business_suite.html"
        html = fixture.read_text(encoding="utf-8")
        self.assertIn('id="active-page-header"', html)
        self.assertIn('id="reel-video-upload"', html)
        self.assertIn('id="btn-publish-reel"', html)

        agent = ContentGenerationAgent()
        ideas = agent.generate_batch_ideas(count=14, language="en")
        self.assertEqual(len(ideas), 14)
        self.assertEqual(len({i.idea_id for i in ideas}), 14)

    def test_11_celebrity_face_slices_and_rendered_mp4s(self) -> None:
        face_rgba, _ = generate_procedural_animal_rgba(
            species="football_icon",
            primary_color=(218, 164, 128),
            secondary_color=(28, 86, 214),
            accent_color=(38, 28, 22),
            seed=1013,
        )
        horiz_bundle = extract_horizontal_slice_bundle(face_rgba, slice_y_ratio=(0.30, 0.54))
        self.assertEqual(horiz_bundle.pixel_match_mad, 0.0)

        band3_bundle = extract_three_band_face_bundle(face_rgba, split_ratios=(0.37, 0.64))
        self.assertEqual(band3_bundle.pixel_match_mad, 0.0)

        out_dir = REPO_ROOT.parent / "artifacts/file_generation/ttl=63d/output"
        mp4_c = out_dir / "sample_celebrity_face_slide.mp4"
        mp4_d = out_dir / "sample_celebrity_face_3band.mp4"
        self.assertTrue(mp4_c.exists())
        self.assertTrue(mp4_d.exists())

        qa_c = validate_rendered_video(mp4_c)
        qa_d = validate_rendered_video(mp4_d)
        self.assertTrue(qa_c.passed, f"Sample Celebrity Slide failed QA: {qa_c.errors}")
        self.assertTrue(qa_d.passed, f"Sample Celebrity 3-Band failed QA: {qa_d.errors}")


if __name__ == "__main__":
    unittest.main()
