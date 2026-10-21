import pytest

from selection_quality import selection_quality_guidance


@pytest.mark.parametrize("setting", [None, "", "legacy", "0", "true", "v2"])
@pytest.mark.parametrize("mode", ["score", "detail", "visual"])
def test_default_and_unknown_settings_preserve_original_prompt(mode, setting):
    original = "Existing formatted prompt"
    assert original + selection_quality_guidance(mode, setting) == original


def test_enabled_guidance_is_limited_to_transcript_stages():
    assert "Score every window" in selection_quality_guidance("score", "v1")
    assert "continuous source interval" in selection_quality_guidance("detail", " V1 ")
    assert selection_quality_guidance("visual", "v1") == ""
