"""Network-free model-discovery contract with a fake official SDK client."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.ai.provider_catalog import discover_gemini_models, ProviderCatalogError
from services.api.server import app


class FakeModelList:
    def list(self):
        return [
            SimpleNamespace(name="models/gemini-3.8-flash",display_name="Gemini Flash",
                            supported_actions=["generateContent"],input_token_limit=1000000,
                            output_token_limit=32000),
            SimpleNamespace(name="models/gemini-3.8-flash-lite-tts",display_name="Gemini TTS",
                            supported_actions=["generateContent"],input_token_limit=8192,
                            output_token_limit=4096),
        ]


class ModelDiscoveryTests(unittest.TestCase):
    def test_live_catalog_contract_no_key_or_free_claim(self):
        result=discover_gemini_models(SimpleNamespace(models=FakeModelList()))
        self.assertTrue(result["verified_with_provider"])
        self.assertEqual(result["model_count"],2)
        self.assertEqual(result["pricing_tier"],"NOT_VERIFIED")
        self.assertEqual(result["models"][0]["name"],"gemini-3.8-flash")
        self.assertNotIn("api_key",str(result).lower())

    def test_limit_and_provider_errors(self):
        with self.assertRaises(ValueError):
            discover_gemini_models(SimpleNamespace(models=FakeModelList()),limit=0)
        class ErrorList:
            def list(self):
                raise RuntimeError("api_key=SHOULD_NOT_APPEAR")
        with self.assertRaises(ProviderCatalogError) as err:
            discover_gemini_models(SimpleNamespace(models=ErrorList()))
        self.assertNotIn("SHOULD_NOT_APPEAR",str(err.exception))

    def test_route_requires_auth_and_explicit_provider_opt_in(self):
        with patch.dict(os.environ,{"RFACTORY_API_TOKEN":"private-unit-token",
                                     "RFACTORY_AI_ENABLED":"false"}):
            with TestClient(app) as client:
                denied=client.get("/api/v1/ai/provider-models")
                self.assertEqual(denied.status_code,401)
                disabled=client.get("/api/v1/ai/provider-models",
                                    headers={"Authorization":"Bearer private-unit-token"})
                self.assertEqual(disabled.status_code,503)


if __name__=="__main__":
    unittest.main()
