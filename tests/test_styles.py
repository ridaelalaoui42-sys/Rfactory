"""Atlas-inspired metadata contracts, independent of optional cinematic renderer."""
import json
import pytest
from pydantic import ValidationError
from clipforge.core import EditPlan, ClipRange
from clipforge.editorv1 import brief
from clipforge.style_atlas import list_styles, get_style, style_brief, make_prompt, FAMILY_COUNTS


def make_plan(style=None, fmt="vertical"):
    return EditPlan(source_id=1, ranges=[ClipRange(start=1, end=9)],
                    format=fmt, output_name="sample.mp4", style_preset=style)


def test_catalog_has_eighteen_verified_presets_and_fourteen_families():
    styles = list_styles()
    assert len(styles) == 18
    assert len({style["id"] for style in styles}) == 18
    assert len(FAMILY_COUNTS) == 14
    assert sum(FAMILY_COUNTS.values()) == 86
    for style in styles:
        info = get_style(style["id"])
        assert info["motion_ops"] and info["sound_cues"]
        assert info["visual_direction"] and info["motion_direction"]


def test_unknown_style_rejected_before_render():
    with pytest.raises(ValueError, match="Unknown style"):
        get_style("../evil")
    with pytest.raises(ValidationError, match="Unknown style"):
        make_plan("../evil")


def test_copy_prevents_mutation_of_shared_presets():
    info = get_style("whiteboard_explainer")
    info["motion_ops"].append("malicious_effect")
    assert "malicious_effect" not in get_style("whiteboard_explainer")["motion_ops"]


@pytest.mark.parametrize("fmt,expected", [
    ("horizontal", "16:9"), ("vertical", "9:16"), ("square", "1:1"),
])
def test_style_brief_has_output_specific_direction(fmt, expected):
    info = style_brief("editorial_essay_collage", fmt)
    assert expected in info["format_guidance"]
    assert info["render_status"] == "creative-brief-only"
    assert info["story_beats"][-1]["end_pct"] == 100
    assert "motion_ops" in info and "production_rules" in info


def test_unsupported_layout_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        style_brief("whiteboard_explainer", "portraitish")


def test_editor_handoff_includes_optional_style(tmp_path):
    src = {"title": "Original owned clip", "local_file": "/authorized/clip.mp4",
           "rights": "owned", "evidence": "Creator release"}
    output = tmp_path / "sample.editor-v1.json"
    brief(make_plan("whiteboard_explainer"), src, output)
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["visual_style"]["id"] == "whiteboard_explainer"
    assert data["visual_style"]["render_status"] == "creative-brief-only"
    assert data["format"] == "vertical"
    assert data["rights_evidence"] == "Creator release"
    brief(make_plan(), src, output)
    assert "visual_style" not in json.loads(output.read_text(encoding="utf-8"))

def test_original_prompt_compilation():
    prompt = make_prompt("tech_glow_explainer", "horizontal",
                         "How robots learn", "Robots compare examples.", 30)
    assert "Tech Glow Explainer" in prompt
    assert "16:9" in prompt
    assert "Robots compare examples." in prompt
    assert "not executable instructions" in prompt
    with pytest.raises(ValueError, match="Topic"):
        make_prompt("tech_glow_explainer", "horizontal", "")
    with pytest.raises(ValueError, match="Duration"):
        make_prompt("tech_glow_explainer", "horizontal", "A topic", duration_seconds=0)
