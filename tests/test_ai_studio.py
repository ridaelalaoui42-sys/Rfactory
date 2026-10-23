"""Network-free contract tests of Gemini API adapter and Android-ready service."""
import base64
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import wave

from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from services.ai.studio import (
    CreativeBrief, CreativePlan, ImageBrief, VoiceBrief, GeminiCreativeStudio,
    ConfigurationError, ProviderError,
)
from services.ai.workflow import StudioStore, StudioWorkflow, ApprovalRequired, BudgetExceeded
from services.api.server import app
from services.api.ai_routes import get_store, get_workflow


PLAN = CreativePlan(
    title="The Golden Fox Puzzle",
    subject="golden fox",
    image_prompt="A luxurious whimsical golden fox with wonderful fur, clear elegant anatomy and a delightful 3D editorial lighting setup",
    narration="Can you find the perfect moment to complete this beautiful fox?",
    hook="Stop exactly when the fox is complete",
    caption="Can you solve this delightful fox challenge in one try?",
    hashtags=["#FoxPuzzle", "#ReelsPuzzle"],
    background_hex="#EAF5FF",
    audio_style="playful and warm",
    motion_note="Move the middle strip vertically and pause at alignment.",
    template="MISSING_PIECE_SLIDE",
)


def png_subject():
    pic = Image.new("RGBA", (400, 400), (255, 255, 255, 0))
    d = ImageDraw.Draw(pic)
    d.ellipse((85, 60, 325, 342), fill=(195, 120, 36, 255))
    d.ellipse((150, 160, 190, 202), fill=(20, 28, 32, 255))
    with io.BytesIO() as buf:
        pic.save(buf, "PNG")
        return buf.getvalue()


def wav_subject():
    with io.BytesIO() as buf:
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(b"\x00\x00" * 24000)
        return buf.getvalue()


class FakeInteractions:
    def __init__(self):
        self.calls = []
        self.image_bytes = png_subject()
        self.audio_bytes = wav_subject()

    def create(self, **kwargs):
        self.calls.append(kwargs)
        model = kwargs["model"]
        if "tts" in model:
            return SimpleNamespace(
                output_audio=SimpleNamespace(data=base64.b64encode(self.audio_bytes).decode())
            )
        if "image" in model or "banana" in model:
            return SimpleNamespace(
                output_image=SimpleNamespace(data=base64.b64encode(self.image_bytes).decode())
            )
        return SimpleNamespace(output_text=PLAN.model_dump_json())


class AICreativeStudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rfactory_gemini_test_")
        self.addCleanup(self.tmp.cleanup)
        self.store = StudioStore(Path(self.tmp.name) / "storage")
        self.fake = FakeInteractions()
        self.workflow = StudioWorkflow(self.store, GeminiCreativeStudio(
            client=SimpleNamespace(interactions=self.fake)
        ))
        self.env = patch.dict(os.environ, {
            "RFACTORY_AI_ENABLED": "true",
            "GEMINI_API_KEY": "fake-not-sent-to-network",
            "RFACTORY_AI_DAILY_CALL_LIMIT": "20",
            "RFACTORY_API_TOKEN": "test-backend-bearer",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.brief = CreativeBrief(topic="Golden fox missing-piece puzzle")

    def test_plan_json_contract_no_fallback(self):
        result = self.workflow.plan(self.brief)
        self.assertEqual(result["plan"]["subject"], "golden fox")
        self.assertEqual(result["model"], "gemini-3.8-flash")
        self.assertIsNotNone(self.store.read_metadata("plan", result["id"]))
        self.assertEqual(self.fake.calls[-1]["response_format"]["mime_type"], "application/json")

    def test_generate_original_image_and_explicit_approval(self):
        plan = self.workflow.plan(self.brief)
        art = self.workflow.image(ImageBrief(prompt=PLAN.image_prompt), plan["id"])
        self.assertEqual(art["provider"], "gemini")
        self.assertTrue(art["qa"]["qa_passed"])
        self.assertEqual(art["status"], "AWAITING_APPROVAL")
        with self.assertRaises(ApprovalRequired):
            self.workflow.render(plan["id"], art["id"], duration_sec=8)
        approved = self.store.approve_image(art["id"])
        self.assertEqual(approved["status"], "APPROVED")
        self.assertTrue(self.store.media_path("image", art["id"]).is_file())

    def test_edit_image_with_reference_keeps_provenance_and_reapproval(self):
        plan = self.workflow.plan(self.brief)
        original = self.workflow.image(ImageBrief(prompt=PLAN.image_prompt), plan["id"])
        self.store.approve_image(original["id"])
        modified = self.workflow.image(
            ImageBrief(prompt="Enhance the rich golden fur and subtle premium highlights"),
            plan["id"], source_image_id=original["id"]
        )
        self.assertNotEqual(original["id"], modified["id"])
        self.assertEqual(modified["source_image_id"], original["id"])
        self.assertEqual(modified["status"], "AWAITING_APPROVAL")
        parts = self.fake.calls[-1]["input"]
        self.assertEqual(parts[1]["type"], "image")
        self.assertEqual(parts[1]["mime_type"], "image/png")

    def test_free_tier_upload_from_device_requires_approval(self):
        plan = self.workflow.plan(self.brief)
        with TestClient(app) as client:
            app.dependency_overrides[get_store] = lambda: self.store
            app.dependency_overrides[get_workflow] = lambda: self.workflow
            self.addCleanup(app.dependency_overrides.clear)
            headers = {"Authorization": "Bearer test-backend-bearer"}
            res = client.post("/api/v1/ai/images/import",
                              headers=headers,
                              data={"plan_id": plan["id"]},
                              files={"file": ("original-fox.png", png_subject(), "image/png")})
            self.assertEqual(res.status_code, 201, res.text)
            uploaded = res.json()
            self.assertEqual(uploaded["provider"], "user_upload")
            self.assertEqual(uploaded["status"], "AWAITING_APPROVAL")
            self.assertTrue(uploaded["qa"]["qa_passed"])
            bad = client.post("/api/v1/ai/images/import", headers=headers,
                              files={"file": ("document.txt", b"not an image", "text/plain")})
            self.assertEqual(bad.status_code, 415)
            approved = client.post("/api/v1/ai/images/" + uploaded["id"] + "/approve",
                                   headers=headers)
            self.assertEqual(approved.status_code, 200)

    def test_tts_wav_and_real_voice_video(self):
        plan = self.workflow.plan(self.brief)
        art = self.workflow.image(ImageBrief(prompt=PLAN.image_prompt), plan["id"])
        self.store.approve_image(art["id"])
        voice = self.workflow.voice(VoiceBrief(text=PLAN.narration), plan["id"])
        self.assertEqual(voice["provider"], "gemini")
        with wave.open(str(self.store.media_path("voice", voice["id"])), "rb") as wf:
            self.assertEqual(wf.getframerate(), 24000)
        video = self.workflow.render(plan["id"], art["id"], voice_id=voice["id"], duration_sec=8.0)
        self.assertEqual(video["qa"]["codec"], "h264")
        self.assertEqual(video["publishing"], "NOT_PUBLISHED")
        self.assertTrue(self.store.media_path("render", video["id"]).is_file())

    def test_rejects_bad_models_and_missing_ai_configuration(self):
        with self.assertRaises(ValueError):
            self.workflow.image(ImageBrief(prompt=PLAN.image_prompt, model="arbitrary-model"))
        with patch.dict(os.environ, {"RFACTORY_AI_ENABLED": "false"}):
            with self.assertRaises(ConfigurationError):
                self.workflow.plan(self.brief)

    def test_daily_budget_counts_calls_even_after_failure(self):
        with patch.dict(os.environ, {"RFACTORY_AI_DAILY_CALL_LIMIT": "1"}):
            self.workflow.plan(self.brief)
            with self.assertRaises(BudgetExceeded):
                self.workflow.plan(self.brief)

    def test_mobile_studio_static_page_is_served(self):
        with TestClient(app) as client:
            res = client.get("/studio")
            self.assertEqual(res.status_code, 200)
            self.assertIn("AI Creative Studio", res.text)
            res2 = client.get("/studio-static/app.js")
            self.assertEqual(res2.status_code, 200)
            self.assertIn("/api/v1/ai", res2.text)

    def test_versioned_api_requires_token_and_preserves_contract(self):
        app.dependency_overrides[get_store] = lambda: self.store
        app.dependency_overrides[get_workflow] = lambda: self.workflow
        self.addCleanup(app.dependency_overrides.clear)
        with TestClient(app) as client:
            response = client.get("/api/v1/ai/capabilities")
            self.assertEqual(response.status_code, 401)
            headers = {"Authorization": "Bearer test-backend-bearer"}
            response = client.get("/api/v1/ai/capabilities", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["ai_enabled"])
            response = client.post("/api/v1/ai/plans", headers=headers, json={
                "brief": self.brief.model_dump(),
            })
            self.assertEqual(response.status_code, 201, response.text)
            plan_id = response.json()["id"]
            detail = client.get(f"/api/v1/ai/records/plan/{plan_id}", headers=headers)
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["plan"]["title"], PLAN.title)


if __name__ == "__main__":
    unittest.main()
