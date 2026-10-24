"""Protected, no-Gemini HD artwork rendering endpoint contracts."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.server import app
from services.api.library_routes import get_library
from services.assets.library import AssetLibrary


class OfflineLibraryRenderRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rfactory_offline_render_route_")
        self.addCleanup(self.temp.cleanup)
        self.storage = Path(self.temp.name) / "storage"
        self.lib = AssetLibrary(self.storage)
        app.dependency_overrides[get_library] = lambda: self.lib
        self.addCleanup(lambda: app.dependency_overrides.clear())
        self.settings = patch.dict(os.environ, {"RFACTORY_API_TOKEN": "route-test-secret"})
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.header = {"Authorization": "Bearer route-test-secret"}

    def test_render_is_authenticated_and_does_not_claim_publication(self):
        endpoint = "/api/v1/library/renders"
        body = {
            "asset_id": "a" * 32,
            "allow_fallback": False,
            "geometry": "organic",
            "motion_profile": "orbit_lock",
            "duration_sec": 10,
            "exact_fit_count": 5,
            "seed": 41,
            "enable_sfx": True,
        }
        self.assertEqual(self.client.post(endpoint, json=body).status_code, 401)
        with patch("services.api.library_routes.render_approved_asset") as render:
            render.return_value = {
                "video": str(self.storage / "renders" / "library_1234567890abcd" / "library_1234567890abcd.mp4"),
                "exact_fit_times_sec": [1.0, 3.0, 5.0, 7.0, 9.0],
                "all_frames_checked": 300,
                "raw_alignment_mad": 0.0,
                "source_provenance": "openai_generated",
                "explicit_fallback": False,
            }
            result = self.client.post(endpoint, headers=self.header, json=body)
            self.assertEqual(result.status_code, 201, result.text)
            payload = result.json()
            self.assertEqual(payload["status"], "READY_FOR_REVIEW")
            self.assertFalse(payload["published"])
            self.assertEqual(len(payload["exact_fit_times_sec"]), 5)
            self.assertIn("library_1234567890abcd/video", payload["video_url"])
            self.assertEqual(render.call_count, 1)
            self.assertEqual(render.call_args.kwargs["storage_root"], self.storage)

    def test_unsupported_trajectory_and_path_traversal_are_blocked(self):
        invalid = {
            "asset_id": "c" * 32, "motion_profile": "teleport",
            "geometry": "organic", "duration_sec": 10,
        }
        self.assertEqual(self.client.post("/api/v1/library/renders", headers=self.header, json=invalid).status_code, 422)
        result = self.client.get("/api/v1/library/renders/../../etc/passwd/video", headers=self.header)
        self.assertNotEqual(result.status_code, 200)
        self.assertEqual(self.client.get(
            "/api/v1/library/renders/library_notavalidid/video",
            headers=self.header,
        ).status_code, 404)

    def test_report_is_protected_and_does_not_leak_server_path(self):
        target = self.storage / "renders" / "library_1234567890abcd"
        target.mkdir(parents=True, exist_ok=True)
        private_path = str(target / "library_1234567890abcd.mp4")
        (target / "library_1234567890abcd.provenance.json").write_text(
            json.dumps({"video": private_path, "qa_passed": True})
        )
        route = "/api/v1/library/renders/library_1234567890abcd/report"
        self.assertEqual(self.client.get(route).status_code, 401)
        response = self.client.get(route, headers=self.header)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"qa_passed": True})
