#!/usr/bin/env python3
"""阶段 D/C review 中可静态验证的前端安全与交互契约。"""

from pathlib import Path


MAIN_JS = (
    Path(__file__).resolve().parents[1] / "backend" / "static" / "js" / "main.js"
)
INDEX_HTML = (
    Path(__file__).resolve().parents[1] / "backend" / "templates" / "index.html"
)
STYLE_CSS = (
    Path(__file__).resolve().parents[1] / "backend" / "static" / "css" / "style.css"
)


def _source() -> str:
    return MAIN_JS.read_text(encoding="utf-8")


def test_job_description_never_uses_inner_html():
    source = _source()
    assert "element.innerHTML = cleanedText" not in source
    assert "element.innerHTML = truncatedText" not in source
    assert "${displayText}${isLong" not in source
    assert "descriptionElement.textContent" in source


def test_search_plan_deduplicates_case_insensitively():
    source = _source()
    assert "value.toLowerCase()" in source
    assert "seenKeywords" in source


def test_profile_editor_loads_missing_profile_before_opening():
    source = _source()
    assert "async function populateProfileEditor()" in source
    assert 'await axios.get("/api/career-profile")' in source


def test_key_configuration_lives_in_settings_drawer():
    html = INDEX_HTML.read_text(encoding="utf-8")
    drawer_start = html.index('id="settings-drawer"')
    key_input = html.index('id="api-key-input"')
    assert 'id="btn-open-settings"' in html
    assert 'id="btn-close-settings"' in html
    assert drawer_start < key_input
    assert 'id="btn-test-api-key"' in html
    assert "Invitation management" in html


def test_settings_drawer_has_open_close_and_byok_bridge():
    source = _source()
    assert "function openSettingsDrawer()" in source
    assert "function closeSettingsDrawer()" in source
    assert 'fetch("/api/user-key/test"' in source
    assert 'apiKeyForm?.addEventListener("submit"' in source
    assert "event.preventDefault();" in source
    assert 'getElementById("byok-go-settings")' in source
    assert "openSettingsDrawer();" in source


def test_settings_drawer_uses_existing_editorial_design_tokens():
    css = STYLE_CSS.read_text(encoding="utf-8")
    assert ".settings-drawer.open" in css
    assert "background: var(--cream)" in css
    assert "font-family: var(--font-display)" in css
