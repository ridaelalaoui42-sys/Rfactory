"""Live Gemini model discovery, never a claim about billing or free-tier status.

Uses Google Gen AI's official models.list API. This boundary accepts an
injected fake client for tests. API keys never leave the backend, and provider
exceptions are masked to avoid leaking sensitive request metadata.
"""
from __future__ import annotations

from typing import Any


class ProviderCatalogError(RuntimeError):
    pass


def discover_gemini_models(client: Any, limit: int = 200) -> dict:
    if not 1 <= limit <= 300:
        raise ValueError("Model discovery limit must be 1-300")
    records = []
    try:
        for item in client.models.list():
            name = str(getattr(item, "name", "") or "")
            if not name or len(name) > 180:
                continue
            actions = getattr(item, "supported_actions", None)
            if actions is None:
                actions = getattr(item, "supported_generation_methods", None)
            actions = list(actions or [])
            records.append({
                "name": name.removeprefix("models/"),
                "display_name": str(getattr(item, "display_name", "") or "")[:150],
                "supported_actions": [str(a) for a in actions[:15]],
                "input_token_limit": getattr(item, "input_token_limit", None),
                "output_token_limit": getattr(item, "output_token_limit", None),
            })
            if len(records) >= limit:
                break
    except Exception as exc:
        # Provider exceptions may include request query strings and credentials.
        raise ProviderCatalogError(
            "Gemini model discovery failed. Check server key, project access and network."
        ) from None
    records.sort(key=lambda item:item["name"])
    return {
        "provider":"gemini",
        "verified_with_provider":True,
        "model_count":len(records),
        "models":records,
        "pricing_tier":"NOT_VERIFIED",
        "availability_note":(
            "Model listing does not prove free-tier quota, generation permission, "
            "billing availability, or a successful text/image/speech generation."
        ),
    }
