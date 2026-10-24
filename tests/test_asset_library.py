"""Generated/fallback image library tests; no external providers needed."""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from services.assets.library import AssetLibrary, LibraryError
from services.api.server import app
from services.api.library_routes import get_library


def png_bytes(size=(900, 900)) -> bytes:
    image=Image.new("RGBA",size,(0,0,0,0))
    painter=ImageDraw.Draw(image)
    painter.ellipse((size[0]*.12,size[1]*.12,size[0]*.88,size[1]*.88),fill=(125,210,87,255))
    buffer=io.BytesIO()
    image.save(buffer,format="PNG")
    return buffer.getvalue()


def metadata_for(blob: bytes, tier="production_generated", subject="Snow leopard") -> dict:
    with Image.open(io.BytesIO(blob)) as art:
        width,height=art.size
    return {
        "file":"production_generated/asset.png",
        "subject":subject,
        "category":"animals",
        "tier":tier,
        "provenance":"openai_generated",
        "source_description":"Original separately generated image, not Gemini",
        "source_dimensions":[width,height],
        "sha256":hashlib.sha256(blob).hexdigest(),
    }


def pack_bytes(blob,meta):
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json",json.dumps({"schema_version":1,"assets":[meta]}))
        z.writestr(meta["file"],blob)
    return out.getvalue()


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="rfactory_hd_lib_")
        self.addCleanup(self.temp.cleanup)
        self.library=AssetLibrary(Path(self.temp.name)/"storage")

    def add(self,tier="production_generated",size=(900,900),subject="Snow leopard"):
        return self.library.add_image(
            png_bytes(size),subject,"animals",tier,
            "openai_generated","Original AI art without Gemini API",
        )

    def test_derived_fallback_not_mislabeled_as_new_ai_image(self):
        art=self.add("fallback")
        self.assertTrue(art["production_eligible"])
        self.assertTrue(art["is_fallback"])
        self.assertFalse(art["approved"])
        self.assertEqual(art["review_status"],"AWAITING_REVIEW")
        with self.assertRaises(LibraryError):
            self.library.select("animals",allow_fallback=True)
        self.library.approve(art["id"])
        with self.assertRaises(LibraryError):
            self.library.select("animals",allow_fallback=False)
        chosen=self.library.select("animals",allow_fallback=True)
        self.assertTrue(chosen["selected_as_fallback"])
        self.assertFalse(chosen["generation_attempted"])
        self.assertIn("EXPLICIT FALLBACK",chosen["selection_note"])

    def test_primary_outranks_fallback_and_original_asset_path_is_bounded(self):
        fallback=self.add("fallback",subject="Snow leopard fallback")
        primary=self.add("production_generated",subject="Snow leopard primary")
        self.library.approve(fallback["id"])
        self.library.approve(primary["id"])
        selected=self.library.select("animals",allow_fallback=True)
        self.assertEqual(selected["id"],primary["id"])
        self.assertFalse(selected["selected_as_fallback"])
        self.assertTrue(self.library.path(primary["id"]).is_file())
        with self.assertRaises(LibraryError):
            self.library.path("../etc/passwd")

    def test_reference_only_thumbnails_cannot_become_hd_by_upscaling(self):
        ref=self.add("reference_only",size=(100,140))
        self.assertFalse(ref["production_eligible"])
        with self.assertRaises(LibraryError):
            self.library.approve(ref["id"])
        upscale=png_bytes((900,900))
        forged=self.library.add_image(
            upscale,"Fake HD animal","animals","fallback","openai_generated",
            "User supplied source metadata",original_dimensions=(100,140)
        )
        self.assertEqual(forged["tier"],"reference_only")
        self.assertFalse(forged["production_eligible"])

    def test_bundle_import_checks_sha_and_preserves_original_dimensions(self):
        blob=png_bytes()
        manifest=metadata_for(blob)
        result=self.library.import_pack(pack_bytes(blob,manifest))
        self.assertEqual(result["imported"],1)
        self.assertEqual(result["production_candidates"],1)
        self.assertEqual(result["reference_only"],0)
        self.assertFalse(result["assets"][0]["approved"])
        corrupt=dict(manifest); corrupt["sha256"]="0"*64
        with self.assertRaises(LibraryError):
            self.library.import_pack(pack_bytes(blob,corrupt))
        self.assertEqual(len(self.library.list_assets()),1)

    def test_bundle_rejects_traversal_or_unsafe_name(self):
        blob=png_bytes()
        meta=metadata_for(blob)
        meta["file"]="../sneaky.png"
        with self.assertRaises(LibraryError):
            self.library.import_pack(pack_bytes(blob,meta))

    def test_invalid_image_and_filter_rejected(self):
        with self.assertRaises(LibraryError):
            self.library.add_image(b"not an image","panda","animals","fallback",
                                   "openai_generated","invalid image")
        with self.assertRaises(LibraryError):
            self.library.list_assets(category="unknown")
        self.assertEqual(self.library.list_assets(production_only=True),[])


class LibraryAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="rfactory_lib_api_")
        self.addCleanup(self.temp.cleanup)
        self.library=AssetLibrary(Path(self.temp.name)/"storage")
        app.dependency_overrides[get_library]=lambda:self.library
        self.addCleanup(lambda:app.dependency_overrides.clear())
        self.environment=patch.dict(os.environ,{"RFACTORY_API_TOKEN":"library-secret-token"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client=TestClient(app)
        self.addCleanup(self.client.close)
        self.auth={"Authorization":"Bearer library-secret-token"}

    def test_routes_require_auth_and_upload_preserves_provenance(self):
        self.assertEqual(self.client.get("/api/v1/library/assets").status_code,401)
        image=png_bytes()
        response=self.client.post("/api/v1/library/assets/import",headers=self.auth,
                                  data={"subject":"Red Panda","category":"animals",
                                        "tier":"fallback","provenance":"openai_generated_derivative",
                                        "source_description":"Approved operator-supplied generated artwork"},
                                  files={"file":("panda.png",image,"image/png")})
        self.assertEqual(response.status_code,201,response.text)
        item=response.json()
        listing=self.client.get("/api/v1/library/assets?category=animals",headers=self.auth)
        self.assertEqual(len(listing.json()["items"]),1)
        path=f"/api/v1/library/assets/{item['id']}/approve"
        approved=self.client.post(path,headers=self.auth)
        self.assertEqual(approved.status_code,200,approved.text)
        self.assertTrue(approved.json()["approved"])
        denied=self.client.post("/api/v1/library/select",headers=self.auth,json={
            "category":"animals","allow_fallback":False,
        })
        self.assertEqual(denied.status_code,422)
        selected=self.client.post("/api/v1/library/select",headers=self.auth,json={
            "category":"animals","allow_fallback":True,
        })
        self.assertTrue(selected.json()["selected_as_fallback"])
        stage=self.client.post(
            f"/api/v1/library/assets/{item['id']}/stage",
            headers=self.auth,json={"acknowledge_source_license":False},
        )
        self.assertEqual(stage.status_code,409)
        preview=self.client.get(f"/api/v1/library/media/{item['id']}",headers=self.auth)
        self.assertEqual(preview.status_code,200)
        self.assertEqual(preview.headers["content-type"],"image/png")

    def test_zip_pack_endpoint_never_autoapproves_import(self):
        blob=png_bytes()
        bundle=pack_bytes(blob,metadata_for(blob))
        result=self.client.post("/api/v1/library/import-pack",headers=self.auth,
                                files={"file":("library.zip",bundle,"application/zip")})
        self.assertEqual(result.status_code,201,result.text)
        self.assertEqual(result.json()["imported"],1)
        self.assertFalse(result.json()["assets"][0]["approved"])


if __name__=="__main__":
    unittest.main()
