"""Persistent queued Reel execution: state, leases, idempotency and real MP4."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image,ImageDraw

from services.assets.library import AssetLibrary
from services.api.library_routes import get_library
from services.api.server import app
from services.worker.art_render_queue import RenderQueue


def png()->bytes:
    im=Image.new("RGBA",(820,900),(0,0,0,0))
    d=ImageDraw.Draw(im)
    d.ellipse((100,70,720,830),fill=(230,160,95,255))
    d.ellipse((280,310,370,355),fill=(23,45,77,255))
    d.ellipse((470,310,560,355),fill=(23,45,77,255))
    b=io.BytesIO();im.save(b,format="PNG");return b.getvalue()


class QueueCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="rfactory_queue_")
        self.addCleanup(self.tmp.cleanup)
        self.storage=Path(self.tmp.name)/"storage"
        self.queue=RenderQueue(self.storage)

    @staticmethod
    def spec(seed=77):
        return {"asset_id":"a"*32,"seed":seed,"duration_sec":2.0}

    def test_persistence_atomic_claim_and_idempotency(self):
        first=self.queue.enqueue(self.spec(),idempotency_key="render-2026-001")
        same=RenderQueue(self.storage).enqueue(self.spec(),idempotency_key="render-2026-001")
        self.assertEqual(first["id"],same["id"])
        with self.assertRaises(ValueError):
            self.queue.enqueue(self.spec(78),idempotency_key="render-2026-001")
        claimed=self.queue.claim("worker_alpha")
        self.assertEqual(claimed[0],first["id"])
        self.assertIsNone(RenderQueue(self.storage).claim("worker_beta"))
        self.queue.progress(first["id"],"worker_alpha",33)
        self.assertEqual(RenderQueue(self.storage).get(first["id"])["progress_pct"],33)
        self.assertEqual(self.queue.get(first["id"])["status"],"RUNNING")

    def test_cancel_retry_crash_recovery_and_timeout_cap(self):
        job=self.queue.enqueue(self.spec())
        cancelled=self.queue.cancel(job["id"])
        self.assertEqual(cancelled["status"],"CANCELLED")
        self.assertIsNone(self.queue.claim("worker_beta"))
        self.queue.retry(job["id"])
        self.queue.claim("worker_alpha")
        with self.assertRaises(ValueError):
            self.queue.cancel(job["id"])
        old=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        with self.queue._conn() as c:
            c.execute("UPDATE art_render_jobs SET lease_until=? WHERE id=?",(old,job["id"]))
        self.assertEqual(self.queue.recover_expired()["requeued"],1)
        self.queue.claim("worker_alpha")
        with self.queue._conn() as c:
            c.execute("UPDATE art_render_jobs SET lease_until=? WHERE id=?",(old,job["id"]))
        self.assertEqual(self.queue.recover_expired()["failed"],1)
        self.assertEqual(self.queue.get(job["id"])["status"],"FAILED")
        self.queue.retry(job["id"])
        self.assertEqual(self.queue.get(job["id"])["attempts"],0)

    def test_result_never_discloses_worker_filesystem_path(self):
        job=self.queue.enqueue(self.spec())
        self.queue.claim("worker_alpha")
        result={
          "video":str(self.storage/"renders"/"library_1234567890abcd"/"library_1234567890abcd.mp4"),
          "exact_fit_times_sec":[0.63,1.53],
          "all_frames_checked":60,"raw_alignment_mad":0.0,
          "source_provenance":"user_uploaded",
          "explicit_fallback":False,
        }
        self.queue.complete(job["id"],"worker_alpha",result)
        ready=RenderQueue(self.storage).get(job["id"])
        self.assertEqual(ready["status"],"READY")
        self.assertEqual(ready["progress_pct"],100)
        self.assertFalse(ready["result"]["published"])
        self.assertNotIn(str(self.storage),str(ready))
        self.assertEqual(ready["result"]["id"],"library_1234567890abcd")


class QueueAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="rfactory_queue_api_")
        self.addCleanup(self.tmp.cleanup)
        self.storage=Path(self.tmp.name)/"storage"
        self.library=AssetLibrary(self.storage)
        app.dependency_overrides[get_library]=lambda:self.library
        self.addCleanup(lambda:app.dependency_overrides.clear())
        self.env=patch.dict(os.environ,{"RFACTORY_API_TOKEN":"render-queue-unit"})
        self.env.start();self.addCleanup(self.env.stop)
        self.client=TestClient(app);self.addCleanup(self.client.close)
        self.headers={"Authorization":"Bearer render-queue-unit"}
        self.image=self.library.add_image(
            png(),"Original wolf","animals","production_generated",
            "test_generated","Original uncut image")
        self.library.approve(self.image["id"])

    def payload(self):
        return {
          "asset_id":self.image["id"],"duration_sec":2.0,
          "exact_fit_count":2,"geometry":"organic",
          "motion_profile":"figure_eight","seed":209,
          "enable_sfx":False,
        }

    def test_public_api_queues_without_rendering_inside_request(self):
        self.assertEqual(self.client.post("/api/v1/library/render-jobs",json=self.payload()).status_code,401)
        with patch("services.worker.art_render_queue.render_approved_asset") as renderer:
            request=self.client.post(
                "/api/v1/library/render-jobs",json=self.payload(),headers=self.headers)
            self.assertEqual(request.status_code,202,request.text)
            self.assertEqual(renderer.call_count,0)
            job=request.json()
            self.assertEqual(job["status"],"QUEUED")
            self.assertEqual(self.client.get(job["status_url"],headers=self.headers).json()["status"],"QUEUED")
            self.assertEqual(len(self.client.get(
                "/api/v1/library/render-jobs",headers=self.headers
            ).json()["items"]),1)
            self.assertEqual(self.client.post(job["status_url"]+"/cancel",headers=self.headers).json()["status"],"CANCELLED")
            self.assertEqual(self.client.post(job["status_url"]+"/retry",headers=self.headers).json()["status"],"QUEUED")

    def test_real_full_hd_video_generated_by_persistent_job_worker(self):
        response=self.client.post("/api/v1/library/render-jobs",json=self.payload(),headers=self.headers)
        self.assertEqual(response.status_code,202,response.text)
        job_id=response.json()["id"]
        result=RenderQueue(self.storage).process_one("worker_test_real")
        self.assertEqual(result["status"],"READY",result)
        self.assertEqual(result["progress_pct"],100)
        self.assertEqual(result["result"]["decoded_frames_checked"],60)
        self.assertEqual(result["result"]["raw_alignment_mad"],0.0)
        self.assertEqual(len(result["result"]["exact_fit_times_sec"]),2)
        media=self.client.get(result["result"]["video_url"],headers=self.headers)
        self.assertEqual(media.status_code,200)
        self.assertGreater(len(media.content),10000)
        self.assertEqual(media.headers["content-type"],"video/mp4")
        self.assertFalse(result["result"]["published"])

if __name__=="__main__":
    unittest.main()
