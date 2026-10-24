"""Prove final MP4 uses EXACT artwork fragments approved in the Studio.

No Gemini/API credits needed. Full render follows the same authenticated
cutout -> approval -> production endpoint as a real operator.
"""
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from services.assets.library import AssetLibrary
from services.api.library_routes import get_library
from services.api.server import app


def intact_portrait_png():
    image=Image.new("RGBA",(820,950),(0,0,0,0))
    paint=ImageDraw.Draw(image)
    paint.ellipse((100,80,720,840),fill="#cc884e")
    paint.ellipse((250,390,335,440),fill="#181d25")
    paint.ellipse((488,390,575,440),fill="#181d25")
    paint.ellipse((364,615,455,660),fill="#7a352b")
    result=io.BytesIO()
    image.save(result,format="PNG")
    return result.getvalue()


class ApprovedCutoutProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="rfactory_pack_qa_")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"storage"
        self.library=AssetLibrary(self.root)
        app.dependency_overrides[get_library]=lambda: self.library
        self.addCleanup(lambda: app.dependency_overrides.clear())
        self.patch=patch.dict(os.environ,{"RFACTORY_API_TOKEN":"face-integrity-test"})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.client=TestClient(app)
        self.addCleanup(self.client.close)
        self.headers={"Authorization":"Bearer face-integrity-test"}
        self.source=self.library.add_image(
            intact_portrait_png(),"Original human","characters","user_uploaded",
            "test_generated_clean_original","Uncut original source image",
        )
        self.library.approve(self.source["id"])

    def new_pack(self):
        response=self.client.post("/api/v1/assets/cutout",json={
            "asset_id":self.source["id"],"mode":"human_three_slice_face",
            "subject_type":"human", "clean_source_confirmed":True,
            "acknowledge_source_license":True,
            "face_bbox_norm":[.15,.11,.7,.73],"seed":4217,
        },headers=self.headers)
        self.assertEqual(response.status_code,201,response.text)
        return response.json()["id"]

    def approve(self,pack_id):
        response=self.client.post(
            f"/api/v1/assets/{pack_id}/approve",headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        manifest=json.loads((self.root/"cutout_packs"/pack_id/"puzzle_manifest.json").read_text())
        self.assertEqual(len(manifest["approved_media_sha256"]),8)
        return manifest

    def video_request(self,pack_id):
        return {
            "asset_id":self.source["id"],"cutout_id":pack_id,
            "geometry":"organic","motion_profile":"orbit_lock",
            "duration_sec":2.0,"exact_fit_count":2,
            "enable_sfx":False, "seed":1859,
        }

    def test_full_studio_approval_to_video_exact_artwork(self):
        pack=self.new_pack()
        manifest=self.approve(pack)
        reply=self.client.post("/api/v1/library/renders",
                               json=self.video_request(pack),headers=self.headers)
        self.assertEqual(reply.status_code,201,reply.text)
        info=reply.json()
        self.assertEqual(info["status"],"READY_FOR_REVIEW")
        self.assertEqual(info["face_cutout_id"],pack)
        self.assertEqual(info["raw_alignment_mad"],0.0)
        self.assertEqual(info["decoded_frames_checked"],60)
        self.assertEqual(len(info["exact_fit_times_sec"]),2)
        self.assertFalse(info["published"])

        job=info["id"]
        frameqa=json.loads((
            self.root/"renders"/job/(job+".frameqa.json")).read_text())
        self.assertTrue(frameqa["reviewed_cutout_pixels_used_directly"])
        self.assertTrue(frameqa["solved_scene_raw_pixel_exact"])
        profiles=frameqa["face_piece_motion_profiles"]
        self.assertEqual(len(profiles),3)
        self.assertEqual(len(set(profiles)),3)
        video=self.client.get(info["video_url"],headers=self.headers)
        self.assertEqual(video.status_code,200)
        self.assertEqual(video.headers["content-type"],"video/mp4")
        self.assertGreater(len(video.content),10000)
        # The final frame uses the approved input pack. No second cutout
        # is generated within the render job directory.
        self.assertFalse((self.root/"renders"/job/"cutout_assets").exists())
        self.assertEqual(manifest["normalized_source_pixel_sha256"],
            json.loads((self.root/"cutout_packs"/pack/"puzzle_manifest.json").read_text())[
                "normalized_source_pixel_sha256"])

    def test_mutated_approved_mask_blocks_video_and_reapproval(self):
        pack=self.new_pack()
        self.approve(pack)
        mask=self.root/"cutout_packs"/pack/"piece_01_mask.png"
        with Image.open(mask) as im:
            edited=im.copy()
        edited.putpixel((0,0),127)
        edited.save(mask)
        reply=self.client.post("/api/v1/library/renders",
                               json=self.video_request(pack),headers=self.headers)
        self.assertEqual(reply.status_code,422,reply.text)
        self.assertIn("changed",reply.text.lower())
        self.assertFalse(list((self.root/"renders").rglob("*.mp4")) if
                         (self.root/"renders").exists() else True)

    def test_changed_original_is_rejected(self):
        pack=self.new_pack()
        self.approve(pack)
        asset_png=self.library.path(self.source["id"])
        with Image.open(asset_png) as im:
            edited=im.convert("RGBA")
        edited.putpixel((0,0),(0,255,0,255))
        edited.save(asset_png)
        reply=self.client.post("/api/v1/library/renders",
                               json=self.video_request(pack),headers=self.headers)
        self.assertEqual(reply.status_code,422,reply.text)


if __name__=="__main__":
    unittest.main()
