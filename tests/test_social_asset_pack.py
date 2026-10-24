"""Archive-level QA: canonical bundled stickers and backgrounds are complete."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "assets/social/rfactory_social_assets_compact_v1.zip"


class SocialAssetPackTest(unittest.TestCase):
    def test_pack_is_complete_and_source_resolution_only(self):
        self.assertTrue(PACK.is_file(), "Compact asset ZIP must be checked into Git")
        self.assertLess(PACK.stat().st_size, 10 * 1024 * 1024, "Do not commit upscaled variants")
        with ZipFile(PACK) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(len([n for n in names if n.startswith("assets/webp/")]), 182)
            self.assertEqual(len([n for n in names if n.startswith("backgrounds/")]), 16)
            catalog = json.loads(archive.read("asset-catalog.json"))
            self.assertEqual(len(catalog["entries"]), 182)
            for entry in catalog["entries"]:
                self.assertEqual(entry["tier"], "reference_only")
                path = entry["webp"]
                self.assertTrue(path.startswith("assets/webp/"))
                self.assertEqual(hashlib.sha256(archive.read(path)).hexdigest(), entry["sha256"])
                self.assertGreater(entry["width"], 0)
                self.assertGreater(entry["height"], 0)


if __name__ == "__main__":
    unittest.main()
