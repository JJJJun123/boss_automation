#!/usr/bin/env python3
"""阶段 D/C review 中可静态验证的前端安全与交互契约。"""

from pathlib import Path


MAIN_JS = (
    Path(__file__).resolve().parents[1] / "backend" / "static" / "js" / "main.js"
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
