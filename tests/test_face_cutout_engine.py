"""Face-source canonicalization, semantic multi-cutout and real MP4 tests."""
from __future__ import annotations
import io
import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from services.assets.canonical_builder import canonicalize_image
from services.assets.face_cutout_engine import FACE_MODES, face_cutout, estimate_face_bbox
from services.assets.asset_packager import package_face_bundle, create_puzzle_zip
from services.assets.fit_validator import validate_face_bundle
from services.engine.renderer import RenderConfig, PuzzleVideoRenderer


def clean_portrait(size=(820,920)) -> bytes:
    """One original intact source fixture, NO jigsaw effects at all."""
    image=Image.new("RGBA",size,(0,0,0,0))
    p=ImageDraw.Draw(image)
    w,h=size
    p.ellipse((w*.11,h*.13,w*.89,h*.92),fill=(203,125,67,255))
    p.ellipse((w*.28,h*.41,w*.44,h*.49),fill=(45,35,25,255))
    p.ellipse((w*.56,h*.41,w*.72,h*.49),fill=(45,35,25,255))
    p.ellipse((w*.43,h*.67,w*.57,h*.74),fill=(240,190,160,255))
    out=io.BytesIO();image.save(out,format="PNG")
    return out.getvalue()


class FaceCutoutTests(unittest.TestCase):
    def setUp(self):
        self.clean=clean_portrait()
        self.source=canonicalize_image(
            self.clean,provenance="test_pristine_art",
            clean_source_confirmed=True,
        )

    def test_pristine_confirmation_required(self):
        with self.assertRaises(ValueError):
            canonicalize_image(self.clean,provenance="generated",clean_source_confirmed=False)
        self.assertEqual(self.source.width,820)
        self.assertEqual(self.source.height,920)
        self.assertTrue(self.source.clean_source_confirmed)

    def test_all_modes_reconstruct_byte_identical_canonical(self):
        for mode in FACE_MODES:
            with self.subTest(mode=mode):
                typ="animal" if mode.startswith("animal_") else "human" if mode.startswith("human_") else "portrait"
                pack=face_cutout(self.source.rgba,mode,subject_type=typ,
                                seed=1995,face_bbox_norm=(.18,.17,.64,.64))
                qa=validate_face_bundle(pack)
                self.assertEqual(qa["exact_raw_rgba_mad"],0.0)
                self.assertEqual(qa["source_pixel_sha256"],qa["restored_pixel_sha256"])
                self.assertTrue(qa["no_mask_overlaps"])
                self.assertTrue(np.array_equal(pack.restored_rgba(),self.source.rgba))
                expected=3 if mode in {"human_three_slice_face","human_triangle_face_puzzle","human_feature_fragments"} else 1
                self.assertEqual(len(pack.pieces),expected)

    def test_invalid_bbox_and_cross_species_misuse_fails(self):
        for bbox in ((-.1,.2,.5,.4),(.3,.5,.9,.4),(.3,.2,0,.4)):
            with self.assertRaises(ValueError):
                estimate_face_bbox(self.source.rgba,"animal",bbox)
        with self.assertRaises(ValueError):
            face_cutout(self.source.rgba,"human_eye_band",subject_type="animal")

    def test_packager_outputs_source_mask_hole_and_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            pack=face_cutout(self.source.rgba,"human_three_slice_face",
                             subject_type="human",face_bbox_norm=(.18,.17,.64,.64))
            d=Path(temp)
            data=package_face_bundle(pack,d,provenance="test_source")
            self.assertEqual(data["status"],"AWAITING_CUTOUT_APPROVAL")
            self.assertEqual(data["piece_count"],3)
            self.assertEqual(data["qa"]["exact_raw_rgba_mad"],0.0)
            for expected in (
                "source.png","hole_plate.png","overlay_preview.png","cutout_debug.png",
                "piece_01.png","piece_02.png","piece_03.png",
                "piece_01_mask.png","piece_02_mask.png","piece_03_mask.png",
                "puzzle_manifest.json",
            ):
                self.assertTrue((d/expected).is_file(),expected)
            zipfile=create_puzzle_zip(d,d/"assets.zip")
            self.assertGreater(zipfile.stat().st_size,1000)

    def test_actual_human_three_slice_render_creates_full_frame_qa(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            animal=root/"assets"/"faces";animal.mkdir(parents=True)
            (animal/"pristine.png").write_bytes(self.clean)
            renderer=PuzzleVideoRenderer(root/"assets",root/"renders")
            config=RenderConfig(
                job_id="face_human_three_test",
                template_id="CANONICAL_FACE",species="pristine",
                asset_path="faces/pristine.png",
                face_mode="human_three_slice_face",subject_type="human",
                face_bbox_norm=(.18,.17,.64,.64),
                motion_profile="spiral",
                fps=30,duration_sec=2.0,snap_count=2,cycles=2,
                continuous_motion=True,enable_audio=False,
            )
            art=renderer.render_video(config)
            self.assertEqual(art.pixel_match_mad,0.0)
            self.assertEqual(len(art.alignment_frames),2)
            self.assertTrue(Path(art.mp4_path).is_file())
            pack_manifest=Path(art.mp4_path).parent/"cutout_assets"/"puzzle_manifest.json"
            meta=json.loads(pack_manifest.read_text())
            self.assertEqual(meta["piece_count"],3)
            self.assertTrue(json.loads(Path(art.mp4_path).with_suffix(".frameqa.json").read_text())["passed"])

if __name__=="__main__":
    unittest.main()
