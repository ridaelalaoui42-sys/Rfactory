"""Portable release checks: no archived database, videos, or Facebook session required."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.server import app
from services.database.repository import FactoryRepository


class ReleaseSafetyTests(unittest.TestCase):
    def test_sqlite_is_crash_resilient(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = FactoryRepository(Path(tmp) / "test.db")
            with db._connect() as connection:
                self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                self.assertEqual(connection.execute("PRAGMA synchronous").fetchone()[0], 1)

    def test_api_denies_missing_bearer_token(self):
        with patch.dict(os.environ, {"RFACTORY_API_TOKEN": "local-test-secret"}):
            with TestClient(app) as client:
                res = client.get("/api/overview")
                self.assertEqual(res.status_code, 401)

    def test_api_rejects_wrong_token(self):
        with patch.dict(os.environ, {"RFACTORY_API_TOKEN": "local-test-secret"}):
            with TestClient(app) as client:
                res = client.get("/api/overview", headers={"Authorization": "Bearer incorrect"})
                self.assertEqual(res.status_code, 401)

    def test_api_accepts_correct_token(self):
        with patch.dict(os.environ, {"RFACTORY_API_TOKEN": "local-test-secret"}):
            with TestClient(app) as client:
                res = client.get("/api/overview", headers={"Authorization": "Bearer local-test-secret"})
                self.assertEqual(res.status_code, 200)
                self.assertIn("jobs", res.json())


if __name__ == "__main__":
    unittest.main()
