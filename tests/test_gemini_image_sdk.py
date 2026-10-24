"""SDK-compatible image-generation and editing contract; never substitute mocks as real art."""
import io
import unittest
from types import SimpleNamespace
from PIL import Image

from services.ai.studio import GeminiCreativeStudio, ImageBrief, ProviderError


def png_bytes():
    image=Image.new("RGBA",(900,900),(0,0,0,0))
    from PIL import ImageDraw
    ImageDraw.Draw(image).ellipse((120,100,780,800),fill=(100,160,200,255))
    mem=io.BytesIO()
    image.save(mem,format="PNG")
    return mem.getvalue()


class FakeModels:
    def __init__(self, image=None):
        self.image=image
        self.calls=[]
    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.image is None:
            return SimpleNamespace(parts=[SimpleNamespace(text="Sorry, no image")])
        return SimpleNamespace(parts=[
            SimpleNamespace(inline_data=SimpleNamespace(
                mime_type="image/png", data=self.image
            ))
        ])


class RealImageSDKContractTests(unittest.TestCase):
    def test_generator_calls_image_modalities_with_real_bytes(self):
        models=FakeModels(png_bytes())
        provider=GeminiCreativeStudio(client=SimpleNamespace(models=models))
        art,prompt=provider.image(ImageBrief(
            prompt="Original professional snow leopard, isolated on plain white background",
            model="gemini-3.1-flash-lite-image",
        ))
        self.assertEqual(art,png_bytes())
        self.assertIn("snow leopard",prompt)
        self.assertEqual(len(models.calls),1)
        self.assertEqual(models.calls[0]["model"],"gemini-3.1-flash-lite-image")
        self.assertIn("IMAGE",str(models.calls[0]["config"]))

    def test_real_image_edit_uses_reference_bytes(self):
        original=png_bytes()
        models=FakeModels(original)
        provider=GeminiCreativeStudio(client=SimpleNamespace(models=models))
        edited,prompt=provider.edit_image(original,ImageBrief(
            prompt="Keep this same animal, upgrade texture and natural lighting",
            model="gemini-3.1-flash-lite-image",
        ))
        self.assertEqual(edited,original)
        self.assertIn("Maintain the same single subject",prompt)
        self.assertEqual(len(models.calls),1)
        self.assertEqual(len(models.calls[0]["contents"]),2)

    def test_provider_never_fabricates_missing_image(self):
        models=FakeModels(None)
        provider=GeminiCreativeStudio(client=SimpleNamespace(models=models))
        with self.assertRaises(ProviderError):
            provider.image(ImageBrief(prompt="Cinematic astronaut portrait, original clean silhouette"))
        with self.assertRaises(ProviderError):
            provider.edit_image(png_bytes(),ImageBrief(prompt="Improve the original astronaut illustration"))
