"""Regression tests for the real mobile/web motion preview and diversity API."""
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.server import app
from services.engine.motion_profiles import MOTION_PROFILES


class CreativeMotionAPITests(unittest.TestCase):
    def setUp(self):
        self.token=patch.dict(os.environ,{"RFACTORY_API_TOKEN":"test-motion-token"})
        self.token.start()
        self.addCleanup(self.token.stop)
        self.client=TestClient(app)
        self.addCleanup(self.client.close)
        self.headers={"Authorization":"Bearer test-motion-token"}

    def test_does_not_leak_unprotected_mobile_endpoints(self):
        unauthorized=self.client.get("/api/v1/creative/capabilities")
        self.assertEqual(unauthorized.status_code,401)
        authorized=self.client.get("/api/v1/creative/capabilities",headers=self.headers)
        self.assertEqual(authorized.status_code,200)
        self.assertGreaterEqual(len(authorized.json()["motion_profiles"]),16)
        self.assertEqual(len(authorized.json()["puzzle_geometries"]),8)

    def test_preview_matches_real_seeded_frame_indices(self):
        data={
            "profile":"bezier_sweep","fps":30,"duration_sec":12,
            "crossing_count":5,"seed":11452,"samples":240
        }
        a=self.client.post("/api/v1/creative/motion/preview",json=data,headers=self.headers)
        b=self.client.post("/api/v1/creative/motion/preview",json=data,headers=self.headers)
        self.assertEqual(a.status_code,200,a.text)
        self.assertEqual(a.json(),b.json())
        payload=a.json()
        self.assertEqual(payload["crossing_count"],5)
        self.assertEqual(payload["total_frames"],360)
        self.assertEqual(len(payload["crossing_frames"]),5)
        self.assertEqual(sum(bool(p["exact_fit"]) for p in payload["samples"]),5)
        self.assertEqual(payload["paused_frames_per_fit"],0)
        for p in payload["samples"]:
            if p["exact_fit"]:
                self.assertEqual((p["x"],p["y"],p["rotation"],p["scale_x"],p["scale_y"]),
                                 (0,0,0.0,1.0,1.0))

    def test_rejects_unknown_profile_and_out_of_bounds(self):
        a=self.client.post("/api/v1/creative/motion/preview",json={
            "profile":"invented", "duration_sec":12
        },headers=self.headers)
        self.assertEqual(a.status_code,422)
        b=self.client.post("/api/v1/creative/motion/preview",json={
            "profile":"helix","duration_sec":2,"crossing_count":12
        },headers=self.headers)
        self.assertEqual(b.status_code,422)

    def test_diversity_flags_identical_paths(self):
        item={"profile":"orbit_lock","fps":30,"duration_sec":12,"seed":42}
        result=self.client.post("/api/v1/creative/motion/diversity",
                                json=[item,item],headers=self.headers)
        self.assertEqual(result.status_code,200,result.text)
        self.assertFalse(result.json()["pass"])
        self.assertEqual(result.json()["near_duplicates"][0]["distance"],0.0)

    def test_diversity_does_not_flag_all_distinct_trajectories(self):
        a={"profile":"spiral","fps":30,"duration_sec":12,"seed":42}
        b={"profile":"slide","fps":30,"duration_sec":12,"seed":42}
        result=self.client.post("/api/v1/creative/motion/diversity",
                                json=[a,b],headers=self.headers)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()["compared"],2)


if __name__=="__main__":
    unittest.main()
