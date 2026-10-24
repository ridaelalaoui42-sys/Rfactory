"""Deterministic multi-video campaign planner, atomic DB and authenticated API."""
from __future__ import annotations

import io
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image,ImageDraw

from services.api.library_routes import get_library
from services.api.server import app
from services.assets.library import AssetLibrary
from services.worker.art_render_queue import RenderQueue
from services.worker.campaign_manager import CampaignManager
from services.worker.campaign_planner import make_campaign_plan


def clean_art(color):
    image=Image.new("RGBA",(820,900),(0,0,0,0))
    d=ImageDraw.Draw(image)
    d.ellipse((125,90,695,800),fill=color)
    d.ellipse((250,310,340,365),fill=(19,20,25,255))
    d.ellipse((490,310,580,365),fill=(19,20,25,255))
    b=io.BytesIO()
    image.save(b,format="PNG")
    return b.getvalue()


class CampaignPlanningTests(unittest.TestCase):
    def test_deterministic_distinct_motion_and_geom_multi_subject(self):
        inputs=dict(asset_ids=["a"*32,"b"*32,"c"*32],
                    count=12,base_seed=12345,duration_sec=12,
                    exact_fit_count=5,enable_sfx=True,allow_fallback=False)
        a=make_campaign_plan(**inputs)
        self.assertEqual(a,make_campaign_plan(**inputs))
        self.assertEqual(len(a),12)
        self.assertEqual(len({item["motion_profile"] for item in a}),12)
        self.assertEqual(len({item["seed"] for item in a}),12)
        self.assertEqual({item["asset_id"] for item in a},set(inputs["asset_ids"]))
        for i in range(1,len(a)):
            self.assertNotEqual(a[i]["motion_profile"],a[i-1]["motion_profile"])
            self.assertNotEqual(a[i]["geometry"],a[i-1]["geometry"])
        self.assertNotEqual(a,make_campaign_plan(**{**inputs,"base_seed":98765}))

    def test_plan_requires_real_unique_sources_and_valid_counts(self):
        kw=dict(asset_ids=["a"*32,"a"*32],count=4,base_seed=88,
                duration_sec=10,exact_fit_count=5,enable_sfx=False,
                allow_fallback=False)
        with self.assertRaises(ValueError):
            make_campaign_plan(**kw)
        with self.assertRaises(ValueError):
            make_campaign_plan(**{**kw,"asset_ids":["a"*32],"count":25})
        with self.assertRaises(ValueError):
            make_campaign_plan(**{**kw,"asset_ids":["a"*32],
                                  "cutout_ids":{"z"*32:"face_"+"a"*24}})


class CampaignDBTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="rfactory_campaign_db_")
        self.addCleanup(self.tmp.cleanup)
        self.queue=RenderQueue(Path(self.tmp.name)/"storage")
        self.campaign=CampaignManager(self.queue)
        self.specs=[
            {"asset_id":"a"*32,"motion_profile":"helix","seed":23},
            {"asset_id":"a"*32,"motion_profile":"spiral","seed":24},
            {"asset_id":"a"*32,"motion_profile":"pendulum","seed":25},
        ]

    def test_atomic_idempotence_and_grouped_progress(self):
        one=self.campaign.create("Wildlife Reels",{"name":"Wildlife Reels"},self.specs,"campaign-2026-seed-01")
        two=self.campaign.create("Wildlife Reels",{"name":"Wildlife Reels"},self.specs,"campaign-2026-seed-01")
        self.assertEqual(one["id"],two["id"])
        self.assertEqual(len(self.queue.list()),3)
        self.assertEqual(one["status"],"QUEUED")
        self.assertFalse(one["published"])
        with self.assertRaises(ValueError):
            self.campaign.create("Other",{"name":"Other"},self.specs,"campaign-2026-seed-01")
        claimed=self.queue.claim("campaign_worker")
        self.queue.progress(claimed[0],"campaign_worker",60)
        running=self.campaign.get(one["id"])
        self.assertEqual(running["status"],"RUNNING")
        self.assertEqual(running["counts"]["RUNNING"],1)
        self.assertEqual(running["counts"]["QUEUED"],2)
        self.assertGreater(running["progress_pct"],0)
        stopped=self.campaign.cancel_pending(one["id"])
        self.assertEqual(stopped["counts"]["CANCELLED"],2)
        self.assertEqual(stopped["counts"]["RUNNING"],1)
        self.assertIsNone(self.queue.claim("other_worker"))
        self.assertEqual(len(self.campaign.list()),1)
        self.assertNotIn(str(self.tmp.name),str(stopped))

    def test_rollback_if_second_job_fails_unique_constraint(self):
        # A defective allocator repeating IDs simulates an insert failure
        # halfway through campaign creation. SQLite must roll back ALL rows.
        fake=SimpleNamespace(hex="a"*32)
        with patch("services.worker.campaign_manager.uuid.uuid4",return_value=fake):
            with self.assertRaises(sqlite3.IntegrityError):
                self.campaign.create("Atomic failure",{"fail":True},self.specs)
        with self.queue._conn() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM art_campaigns").fetchone()[0],0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM art_render_jobs").fetchone()[0],0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM art_campaign_items").fetchone()[0],0)


class CampaignAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="rfactory_campaign_api_")
        self.addCleanup(self.tmp.cleanup)
        self.storage=Path(self.tmp.name)/"storage"
        self.library=AssetLibrary(self.storage)
        self.source_ids=[]
        for name,color in [
            ("Clean fox",(160,70,50,255)),
            ("Clean leopard",(215,175,105,255)),
        ]:
            item=self.library.add_image(
                clean_art(color),name,"animals","production_generated",
                "test_generated_intact","One intact full-resolution image"
            )
            self.library.approve(item["id"])
            self.source_ids.append(item["id"])
        app.dependency_overrides[get_library]=lambda:self.library
        self.addCleanup(lambda:app.dependency_overrides.clear())
        self.env=patch.dict(os.environ,{"RFACTORY_API_TOKEN":"campaign-secret-for-tests"})
        self.env.start();self.addCleanup(self.env.stop)
        self.client=TestClient(app);self.addCleanup(self.client.close)
        self.headers={"Authorization":"Bearer campaign-secret-for-tests",
                      "Idempotency-Key":"rfactory-campaign-fixture-01"}

    def payload(self):
        return {
            "name":"Two Originals Eight Motions",
            "asset_ids":self.source_ids,
            "count":4,"base_seed":44,"duration_sec":2,
            "exact_fit_count":2,"enable_sfx":False,
        }

    def test_authenticated_campaign_create_dedupe_and_cancellation(self):
        route="/api/v1/library/campaigns"
        self.assertEqual(self.client.post(route,json=self.payload()).status_code,401)
        response=self.client.post(route,headers=self.headers,json=self.payload())
        self.assertEqual(response.status_code,202,response.text)
        body=response.json()
        self.assertEqual(body["total"],4)
        self.assertEqual(body["counts"]["QUEUED"],4)
        self.assertEqual(len({j["id"] for j in body["jobs"]}),4)
        repeated=self.client.post(route,headers=self.headers,json=self.payload())
        self.assertEqual(repeated.json()["id"],body["id"])
        changed={**self.payload(),"count":5}
        self.assertEqual(self.client.post(route,headers=self.headers,json=changed).status_code,409)
        listed=self.client.get(route,headers=self.headers)
        self.assertEqual(len(listed.json()["items"]),1)
        cancelled=self.client.post(route+"/"+body["id"]+"/cancel-pending",headers=self.headers)
        self.assertEqual(cancelled.status_code,200)
        self.assertEqual(cancelled.json()["counts"]["CANCELLED"],4)
        self.assertFalse(cancelled.json()["published"])

    def test_rejects_source_approval_or_invalid_asset_before_all_enqueue(self):
        self.assertEqual(self.client.post("/api/v1/library/campaigns",
            headers=self.headers,json={**self.payload(),"asset_ids":["z"*32,self.source_ids[0]]}).status_code,404)
        response=self.client.get("/api/v1/library/campaigns",headers=self.headers)
        self.assertEqual(response.json()["items"],[])

    def test_one_real_video_job_made_by_campaign_worker(self):
        created=self.client.post("/api/v1/library/campaigns",
            headers=self.headers,json={**self.payload(),"count":2})
        self.assertEqual(created.status_code,202,created.text)
        queue=RenderQueue(self.storage)
        output=queue.process_one("campaign_video_worker")
        self.assertEqual(output["status"],"READY",output)
        self.assertEqual(output["result"]["decoded_frames_checked"],60)
        self.assertEqual(output["result"]["raw_alignment_mad"],0.0)
        grouped=self.client.get(
            "/api/v1/library/campaigns/"+created.json()["id"],headers=self.headers
        )
        self.assertEqual(grouped.json()["counts"]["READY"],1)
        self.assertEqual(grouped.json()["counts"]["QUEUED"],1)
        path=output["result"]["video_url"]
        self.assertEqual(self.client.get(path,headers=self.headers).status_code,200)
