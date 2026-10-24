"""Authenticated human and animal face cutout generation, review and render API."""
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image,ImageDraw

from services.assets.library import AssetLibrary
from services.api.server import app
from services.api.library_routes import get_library


def clean_png():
    image=Image.new("RGBA",(820,920),(255,255,255,255))
    pen=ImageDraw.Draw(image)
    pen.ellipse((120,110,690,795),fill=(160,105,65,255))
    pen.ellipse((250,360,315,395),fill=(18,24,35,255))
    pen.ellipse((495,360,560,395),fill=(18,24,35,255))
    out=io.BytesIO()
    image.save(out,format="PNG")
    return out.getvalue()


class FaceCutoutAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="face_builder_api_")
        self.addCleanup(self.temp.cleanup)
        self.lib=AssetLibrary(Path(self.temp.name)/"storage")
        app.dependency_overrides[get_library]=lambda:self.lib
        self.addCleanup(lambda:app.dependency_overrides.clear())
        self.environ=patch.dict(os.environ,{"RFACTORY_API_TOKEN":"face-cutout-test-secret"})
        self.environ.start()
        self.addCleanup(self.environ.stop)
        self.client=TestClient(app)
        self.addCleanup(self.client.close)
        self.headers={"Authorization":"Bearer face-cutout-test-secret"}
        self.asset=self.lib.add_image(
            clean_png(), "Original human portrait","characters",
            "user_uploaded","user_supplied_clean_source",
            "A single intact subject portrait for cutout test"
        )
        self.lib.approve(self.asset["id"])

    def request(self,mode="human_three_slice_face"):
        return {
            "asset_id":self.asset["id"],
            "subject_type":"human",
            "mode":mode,
            "clean_source_confirmed":True,
            "acknowledge_source_license":True,
            "face_bbox_norm":[.19,.17,.64,.64],
            "seed":31,
        }

    def test_cutout_api_requires_authorization_and_review(self):
        path="/api/v1/assets/cutout"
        self.assertEqual(self.client.post(path,json=self.request()).status_code,401)
        req=self.request()
        req["clean_source_confirmed"]=False
        self.assertEqual(self.client.post(path,json=req,headers=self.headers).status_code,409)
        reply=self.client.post(path,json=self.request(),headers=self.headers)
        self.assertEqual(reply.status_code,201,reply.text)
        item=reply.json()
        self.assertEqual(item["piece_count"],3)
        self.assertEqual(item["qa"]["exact_raw_rgba_mad"],0.0)
        self.assertEqual(item["status"],"AWAITING_CUTOUT_APPROVAL")
        mid=item["id"]
        media=self.client.get(f"/api/v1/assets/{mid}/media/piece_01_mask.png",headers=self.headers)
        self.assertEqual(media.status_code,200)
        self.assertEqual(media.headers["content-type"],"image/png")
        self.assertEqual(self.client.get(f"/api/v1/assets/{mid}/media/../../etc/passwd",headers=self.headers).status_code!=200,True)
        zipfile=self.client.get(f"/api/v1/assets/{mid}/download",headers=self.headers)
        self.assertEqual(zipfile.status_code,200)
        self.assertTrue(zipfile.content[:2]==b"PK")
        approval=self.client.post(f"/api/v1/assets/{mid}/approve",headers=self.headers)
        self.assertEqual(approval.status_code,200,approval.text)
        meta=self.client.get(f"/api/v1/assets/{mid}/manifest",headers=self.headers).json()
        self.assertEqual(meta["status"],"APPROVED")

    def test_render_refuses_unapproved_or_foreign_cutout(self):
        response=self.client.post("/api/v1/assets/cutout",headers=self.headers,json=self.request())
        self.assertEqual(response.status_code,201,response.text)
        pack_id=response.json()["id"]
        data={
            "asset_id":self.asset["id"], "cutout_id":pack_id,
            "geometry":"organic","motion_profile":"orbit_lock",
            "duration_sec":2,"exact_fit_count":2,"enable_sfx":False,
        }
        refused=self.client.post("/api/v1/library/renders",headers=self.headers,json=data)
        self.assertEqual(refused.status_code,409,refused.text)
        approved=self.client.post(f"/api/v1/assets/{pack_id}/approve",headers=self.headers)
        self.assertEqual(approved.status_code,200,approved.text)
        with patch("services.api.library_routes.render_approved_asset") as render:
            render.return_value={
                "video":str(Path(self.temp.name)/"storage"/"renders"/"library_1234567890abcd"/"library_1234567890abcd.mp4"),
                "exact_fit_times_sec":[.56,1.46],
                "all_frames_checked":60,
                "raw_alignment_mad":0.0,
                "source_provenance":"user_supplied_clean_source",
                "explicit_fallback":False,
                "face_mode":"human_three_slice_face",
            }
            result=self.client.post("/api/v1/library/renders",headers=self.headers,json=data)
            self.assertEqual(result.status_code,201,result.text)
            self.assertEqual(render.call_args.kwargs["face_mode"],"human_three_slice_face")
            self.assertEqual(render.call_args.kwargs["subject_type"],"human")
            self.assertEqual(render.call_args.kwargs["face_asset_seed"], 31)
            self.assertEqual(render.call_args.kwargs["face_bbox_norm"], (.19,.17,.64,.64))
            self.assertNotEqual(render.call_args.kwargs["seed"], render.call_args.kwargs["face_asset_seed"])

            self.assertEqual(result.json()["face_cutout_id"],pack_id)
            data["asset_id"]="0"*32
            self.assertEqual(self.client.post("/api/v1/library/renders",headers=self.headers,json=data).status_code,409)
