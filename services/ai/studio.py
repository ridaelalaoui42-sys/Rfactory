"""Gemini-powered creative studio, isolated from rendering and future Android clients.

Gemini calls are optional and explicitly enabled. Each generated result has a
validated Pydantic contract, model provenance, and stable media identifiers.
No silent replacement with procedural art is permitted for Gemini failures.
"""
from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image
from pydantic import BaseModel, Field, ConfigDict

from services.assets.segmentation import (
    remove_white_background_to_rgba,
    validate_alpha_mask,
)

Style = Literal["storybook", "premium_3d", "editorial", "clay", "hand_painted", "neon"]
Template = Literal["OUTLINE_MATCH", "MISSING_PIECE_SLIDE", "FACE_FEATURE_SLIDE", "FACE_SPLIT_3BAND"]
Language = Literal["en", "es", "fr", "ar"]

MODELS = {
    "planning": ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"],
    "image": ["gemini-nano-banana-2.1", "gemini-3.1-flash-image", "gemini-3.1-flash-lite-image", "gemini-3-pro-image"],
    "tts": ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"],
}
DEFAULT_MODELS = {kind: models[0] for kind, models in MODELS.items()}
VOICES = ("Kore", "Puck", "Charon", "Fenrir", "Aoede")


class CreativeBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=5, max_length=250)
    audience: str = Field(default="Family-friendly puzzle fans", max_length=160)
    language: Language = "en"
    style: Style = "premium_3d"
    template: Template = "MISSING_PIECE_SLIDE"
    brand: str = Field(default="Animal Puzzle Factory", max_length=100)
    twist: str = Field(default="A delightful visual surprise", max_length=250)
    duration_sec: float = Field(default=15, ge=8, le=30)


class CreativePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=4, max_length=120)
    subject: str = Field(min_length=2, max_length=100)
    image_prompt: str = Field(min_length=35, max_length=1800)
    narration: str = Field(min_length=5, max_length=350)
    hook: str = Field(min_length=4, max_length=160)
    caption: str = Field(min_length=8, max_length=600)
    hashtags: list[str] = Field(min_length=1, max_length=8)
    background_hex: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    audio_style: str = Field(min_length=3, max_length=160)
    motion_note: str = Field(min_length=5, max_length=350)
    # Gemini may customize the actual compositor timing rather than merely
    # write a motion description; bounded values protect renderer stability.
    cycles: int = Field(default=5, ge=2, le=9)
    offset_distance_px: int = Field(default=165, ge=80, le=340)
    hold_ratio: float = Field(default=0.14, ge=0.05, le=0.28)
    object_count: int = Field(default=5, ge=3, le=8)
    template: Template


class ImageBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=20, max_length=1800)
    style: Style = "premium_3d"
    model: str = DEFAULT_MODELS["image"]
    transparent_subject: bool = True


class VoiceBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=3, max_length=700)
    style: str = Field(default="bright, playful, clear and inviting", max_length=160)
    voice: str = "Kore"
    model: str = DEFAULT_MODELS["tts"]
    language: Language = "en"


class ConfigurationError(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


def enabled() -> bool:
    return os.getenv("RFACTORY_AI_ENABLED", "false").lower() == "true"


def check_enabled() -> None:
    if not enabled():
        raise ConfigurationError("AI features disabled. Set RFACTORY_AI_ENABLED=true explicitly.")
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        raise ConfigurationError("Gemini API key is not configured on the server.")


def allowed_model(category: str, name: str) -> None:
    if name not in MODELS[category]:
        raise ValueError(f"Unsupported {category} model. Allowed: {MODELS[category]}")


def _decode_payload(encoded: str | bytes, limit: int) -> bytes:
    try:
        blob = base64.b64decode(encoded, validate=True) if isinstance(encoded, str) else encoded
    except Exception as exc:
        raise ProviderError("Invalid base64 data from image/audio provider") from exc
    if not blob or len(blob) > limit:
        raise ProviderError("Empty or oversized generated media")
    return blob


def provider_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Use the portable Gemini JSON-Schema subset; validate full rules locally.

    Pydantic emits minLength, pattern, defaults and other validation keywords
    that can vary across provider model versions. Removing them here prevents
    avoidable schema-level API rejection while keeping strict model validation
    on every returned JSON document.
    """
    safe = {"type", "properties", "required", "items", "description", "enum", "anyOf"}
    def walk(obj):
        if isinstance(obj, list):
            return [walk(v) for v in obj]
        if isinstance(obj, dict):
            return {key: walk(value) for key, value in obj.items() if key in safe}
        return obj
    return walk(schema)


class GeminiCreativeStudio:
    """Stable provider boundary for backend and future Android REST consumers.

    Inject a fake .interactions.create client for isolated tests. Importing this
    module never initializes a cloud client or spends tokens.
    """

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            check_enabled()
            try:
                from google import genai
            except ImportError as exc:
                raise ConfigurationError("Install the optional requirements-ai.txt dependencies.") from exc
            self._client = genai.Client(
                api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            )
        return self._client

    def plan(self, brief: CreativeBrief, model: str = DEFAULT_MODELS["planning"]) -> CreativePlan:
        allowed_model("planning", model)
        instruction = (
            "You are a professional visual-puzzle creative director. Design ONE original, "
            "high-retention vertical Reel with a real visual challenge, elegant art direction, "
            "and natural, brief narration. Avoid generic stock-vector style. "
            "Only original fictional/cartoon subjects unless permission for real people is verified. "
            "For slicing puzzles use one single, isolated complete subject, centered, "
            "with natural anatomy, plain white surrounding canvas, without labels, words, "
            "watermarks, multiple subjects or clipping. Color/style consistency matters. "
            "Provide a precise image_prompt to feed into a separate image-generation call. "
            "Don't make unsupported claims or fabricated statistics. "
            "Make narrator instructions friendly and understandable. "
            "Set bounded cycles, hold_ratio, object_count and offset_distance_px "
            "to art-direct a distinctive animation rhythm for this puzzle. "
            "Respond exactly to the supplied structured output schema. "
            "Do not include script stage directions in narration.\n"
            f"Creative brief: {brief.model_dump_json()}"
        )
        response = self.client.interactions.create(
            model=model,
            input=instruction,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": provider_json_schema(CreativePlan.model_json_schema()),
            },
        )
        raw = getattr(response, "output_text", None)
        if not raw:
            raise ProviderError("Gemini did not return a structured storyboard")
        try:
            plan = CreativePlan.model_validate_json(raw)
        except Exception as exc:
            raise ProviderError("Gemini storyboard failed schema validation") from exc
        if plan.template != brief.template:
            raise ProviderError("Model changed the requested puzzle template")
        return plan

    def image(self, brief: ImageBrief) -> tuple[bytes, str]:
        allowed_model("image", brief.model)
        prompt = (
            f"{brief.prompt}\nArt direction: {brief.style}. "
            "Original distinctive high-end illustration, professionally shaded, "
            "clear realistic anatomy, sharp silhouette, subject occupies roughly 75% of the frame. "
            "One complete isolated subject on PURE WHITE (#FFFFFF), evenly lit, "
            "no text, no watermark, no border, no collage, no extra subjects, "
            "no contact shadows. Keep generous whitespace on every edge."
            if brief.transparent_subject
            else brief.prompt + f"\nArt direction: {brief.style}."
        )
        response = self.client.interactions.create(
            model=brief.model,
            input=prompt,
            response_format={"type": "image", "mime_type": "image/png", "aspect_ratio": "1:1"},
        )
        payload = getattr(getattr(response, "output_image", None), "data", None)
        if not payload:
            raise ProviderError("Gemini returned no image; no procedural fallback was substituted")
        blob = _decode_payload(payload, 15 * 1024 * 1024)
        try:
            with Image.open(io.BytesIO(blob)) as image:
                image.verify()
        except Exception as exc:
            raise ProviderError("AI image content is not decodable") from exc
        return blob, prompt

    def edit_image(self, source: bytes, brief: ImageBrief) -> tuple[bytes, str]:
        """Edit AI-owned artwork through Gemini text+image input, no fake redraws."""
        allowed_model("image", brief.model)
        if not source or len(source) > 15 * 1024 * 1024:
            raise ValueError("Image reference must be nonempty and under 15 MB")
        prompt = (
            "Edit the supplied image according to this request: " + brief.prompt
            + ". Maintain the same single subject, coherent character identity, "
              "excellent anatomical consistency, complete limbs and edges, "
              "isolated pure-white/transparent background with 10% padding, "
              "no captions, no watermarks. Style: " + brief.style
        )
        response = self.client.interactions.create(
            model=brief.model,
            input=[
                {"type": "text", "text": prompt},
                {"type": "image", "data": base64.b64encode(source).decode("ascii"), "mime_type": "image/png"},
            ],
        )
        encoded = getattr(getattr(response, "output_image", None), "data", None)
        if not encoded:
            raise ProviderError("Gemini returned no edited image")
        blob = _decode_payload(encoded, 15 * 1024 * 1024)
        try:
            with Image.open(io.BytesIO(blob)) as image:
                image.verify()
        except Exception as exc:
            raise ProviderError("Edited image is not decodable") from exc
        return blob, prompt

    def voice(self, brief: VoiceBrief) -> bytes:
        allowed_model("tts", brief.model)
        if brief.voice not in VOICES:
            raise ValueError("Unknown prebuilt voice; voice cloning is not supported in this release")
        response = self.client.interactions.create(
            model=brief.model,
            input=[{
                "type": "user_input",
                "content": [{
                    "type": "text",
                    "text": brief.text,
                    "annotations": [{"type": "speech_metadata", "style": brief.style}],
                }],
            }],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": brief.voice}]},
        )
        payload = getattr(getattr(response, "output_audio", None), "data", None)
        if not payload:
            raise ProviderError("Gemini returned no speech audio")
        blob = _decode_payload(payload, 20 * 1024 * 1024)
        import wave
        try:
            with wave.open(io.BytesIO(blob), "rb") as wav:
                if wav.getnframes() < 1 or wav.getnchannels() < 1:
                    raise ValueError("No audio frames")
        except Exception as exc:
            raise ProviderError("TTS response did not contain a valid WAV") from exc
        return blob


def prepare_subject(source_bytes: bytes, output_path: Path) -> dict[str, Any]:
    """Segment isolated AI art for exact-fit video puzzles; reject bad silhouettes."""
    with Image.open(io.BytesIO(source_bytes)) as source:
        source.load()
        if source.width > 8192 or source.height > 8192 or source.width * source.height > 20_000_000:
            raise ProviderError("Image dimensions exceed safety limits")
        rgba = source.convert("RGBA")
        has_alpha = np.count_nonzero(np.array(rgba)[:, :, 3] < 230) > (rgba.width * rgba.height // 5)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if has_alpha:
            img = rgba.copy()
            img.thumbnail((740, 740), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (820, 820), (0, 0, 0, 0))
            canvas.alpha_composite(img, ((820 - img.width)//2, (820 - img.height)//2))
            arr = np.asarray(canvas)
        else:
            # Background removal relies on a high-key white canvas; human
            # review is still needed when the subject itself contains white.
            raw = output_path.parent / (output_path.stem + "_source.png")
            rgba.save(raw)
            try:
                arr = remove_white_background_to_rgba(
                    raw, target_size=(820, 820), add_crisp_border=False
                )
            finally:
                raw.unlink(missing_ok=True)
    quality = validate_alpha_mask(arr)
    if not quality.valid or quality.touches_border or quality.non_empty_ratio < 0.04:
        raise ProviderError(
            "Generated subject did not pass mask QA; revise prompt or supply a better image"
        )
    Image.fromarray(arr).save(output_path)
    return {
        "width": 820,
        "height": 820,
        "mask_sha256": quality.sha256,
        "subject_coverage": quality.non_empty_ratio,
        "qa_passed": True,
    }
