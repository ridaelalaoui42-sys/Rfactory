"""Actual MP4 production using approved HD artwork, without any AI API."""
import tempfile
import unittest
from pathlib import Path

from services.assets.library import AssetLibrary, LibraryError
from scripts.render_from_library import render_approved_asset
from PIL import Image, ImageDraw
import io


def png_bytes():
    image = Image.new("RGBA", (900, 900), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((140, 140, 760, 760), fill=(205, 160, 60, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class OriginalArtworkRenderingTests(unittest.TestCase):
    def test_explicit_fallback_gate_blocks_unapproved_substitutes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/"storage"
            library=AssetLibrary(root)
            item=library.add_image(
                png_bytes(),"Snow leopard variant","animals","fallback",
                "openai_generated_derivative","Generated original source derivative"
            )
            arguments=dict(
                storage_root=root,geometry="organic",motion="orbit_lock",
                duration=2.0,crossings=2,seed=18,enable_sfx=False,
            )
            with self.assertRaises(LibraryError):
                render_approved_asset(item["id"],allow_fallback=True,**arguments)
            library.approve(item["id"])
            with self.assertRaises(LibraryError):
                render_approved_asset(item["id"],allow_fallback=False,**arguments)

    def test_approved_original_produces_verified_mp4_and_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/"storage"
            library=AssetLibrary(root)
            item=library.add_image(
                png_bytes(),"Golden creature","animals","production_generated",
                "openai_generated","Original generated image"
            )
            library.approve(item["id"])
            output=render_approved_asset(
                item["id"],storage_root=root,allow_fallback=False,
                geometry="jigsaw",motion="helix",
                duration=2.0,crossings=2,seed=281,
                enable_sfx=False,
            )
            self.assertTrue(Path(output["video"]).is_file())
            self.assertTrue(output["qa_passed"])
            self.assertFalse(output["published"])
            self.assertFalse(output["generated_with_gemini_during_this_render"])
            self.assertEqual(output["raw_alignment_mad"],0.0)
            self.assertEqual(output["all_frames_checked"],60)
            self.assertEqual(len(output["exact_fit_times_sec"]),2)
            self.assertEqual(output["source_sha256"],item["sha256"])
