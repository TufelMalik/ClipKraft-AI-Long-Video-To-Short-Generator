from backend.services.gemini_worker import editing_requirements_guidance


def test_editing_requirements_are_absent_by_default(monkeypatch):
    monkeypatch.delenv("USER_EDITING_REQUIREMENTS", raising=False)

    assert editing_requirements_guidance() == ""


def test_editing_requirements_are_added_as_bounded_preferences(monkeypatch):
    monkeypatch.setenv("USER_EDITING_REQUIREMENTS", "Prefer practical Hindi tips")

    guidance = editing_requirements_guidance()
    assert "Prefer practical Hindi tips" in guidance
    assert "Do not invent events, claims" in guidance
    assert "JSON schema must still be followed" in guidance
