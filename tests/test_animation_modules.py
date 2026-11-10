import pytest
from fastapi.testclient import TestClient
from clipforge.animation_modules import AnimationBrief, MODULES, catalog, select
from clipforge.api import app


def test_catalog_covers_separate_modules():
    assert {"bang_motion", "vox_director", "huashu_art_motion", "claude_drawing",
            "stickman_director", "clipforge_compositor"}.issubset(set(MODULES))
    assert all(entry["source"].startswith("https://") for entry in catalog())


def test_tech_caption_free_routes_to_bang():
    plan = select(AnimationBrief(topic="A cinematic tech launch reel for a mobile app",
                                 captions=False, voiceover=False, duration_seconds=15))
    assert plan["primary_module"] == "bang_motion"
    assert plan["min_resolution"] == "1080x1920"
    assert not plan["can_render_now"]
    assert any(r["id"] == "vox_director" and
               "no_captionless_export" in r["blockers"] for r in plan["shortlist"])


def test_art_nature_routes_to_huashu_with_drawing_assets():
    plan = select(AnimationBrief(topic="Painterly nature story with a tree",
                                 genre="nature", blend_modules=True))
    assert plan["primary_module"] == "huashu_art_motion"
    assert any(item["id"] == "claude_drawing" for item in plan["support_modules"])


def test_captioned_documentary_selects_vox_when_api_allowed():
    plan = select(AnimationBrief(topic="Evidence-led documentary about history",
                                 genre="documentary", voiceover=True, captions=True,
                                 budget="api_allowed"))
    assert plan["primary_module"] == "vox_director"


def test_user_preference_cannot_override_capability_hard_gate():
    plan = select(AnimationBrief(topic="An editorial documentary",
                                 preferred_module="vox_director", voiceover=False,
                                 captions=False, budget="local_only"))
    assert plan["primary_module"] != "vox_director"


def test_asset_skill_is_not_misrepresented_as_full_video_engine():
    plan = select(AnimationBrief(topic="Artistic drawing of a forest",
                                 preferred_module="claude_drawing"))
    assert plan["primary_module"] != "claude_drawing"
    assert any("asset_provider_only" in r["blockers"] for r in plan["shortlist"]
               if r["id"] == "claude_drawing")


def test_no_silent_unknown_genre_or_module():
    with pytest.raises(ValueError):
        AnimationBrief(topic="Short video about physics", genre="fake_genre")
    with pytest.raises(ValueError):
        AnimationBrief(topic="Short video about physics", preferred_module="missing")


def test_routes_are_authenticated(monkeypatch):
    monkeypatch.setenv("CLIPFORGE_API_TOKEN", "test-animation-token")
    client = TestClient(app)
    assert client.get("/v1/animation/modules").status_code == 401
    headers = {"Authorization": "Bearer test-animation-token"}
    modules = client.get("/v1/animation/modules", headers=headers)
    assert modules.status_code == 200
    assert len(modules.json()["modules"]) == 6
    plan = client.post("/v1/animation/select", headers=headers,
                       json={"topic": "How does a volcano erupt?",
                             "captions": False, "voiceover": False})
    assert plan.status_code == 200
    assert plan.json()["primary_module"]
    assert plan.json()["min_resolution"] == "1080x1920"
