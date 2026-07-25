#!/usr/bin/env python3
"""搜索词生成（spec 阶段 D3）：解析约束 + /api/search-plan 路由"""

import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ORIGIN = {"Origin": "http://localhost:3001"}


class TestParseSearchKeywords:
    def _parse(self, text):
        from analyzer.profile_interview import parse_search_keywords
        return parse_search_keywords(text)

    def test_basic(self):
        assert self._parse('["市场风险管理", "风险计量"]') == ["市场风险管理", "风险计量"]

    def test_trimmed_to_three(self):
        out = self._parse('["a", "b", "c", "d"]')
        assert len(out) == 3

    def test_dedup_and_strip(self):
        out = self._parse('[" 风控 ", "风控", "计量"]')
        assert out == ["风控", "计量"]

    def test_fence_tolerated(self):
        assert self._parse('```json\n["风控"]\n```') == ["风控"]

    def test_malformed_empty(self):
        assert self._parse("不是列表") == []


# ─── /api/search-plan 路由 ──────────────────────────────


@pytest.fixture(autouse=True)
def _reset_invite_limiter():
    from backend.rate_limiter import invite_limiter
    invite_limiter._failures.clear()
    invite_limiter._blacklist.clear()
    yield


@pytest.fixture
def store(tmp_path):
    from utils.state_store import StateStore
    s = StateStore(db_path=str(tmp_path / "plan.db"))
    s.init_schema()
    return s


@pytest.fixture
def app(store, monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-12345678-aaaaaaaa")
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from backend.app import create_app
    application = create_app(store=store)
    application.config["TESTING"] = True
    return application


def _authed(app, store, with_profile=True):
    from utils.state_store import resume_fingerprint
    code = store.create_invite()
    uid, token = store.consume_invite(code)
    store.set_resume(uid, "四年市场风险经验", filename="r.pdf")
    if with_profile:
        profile = {"target_directions": ["市场风险管理", "风险计量"],
                   "transition": None, "cities": ["shanghai"],
                   "salary_floor": None, "hard_avoids": [], "seniority": None,
                   "notes": ""}
        store.set_career_profile(uid, json.dumps(profile, ensure_ascii=False),
                                 resume_fingerprint("四年市场风险经验"))
    client = app.test_client()
    client.set_cookie("boss_session", token, domain="localhost")
    return client, uid


class TestSearchPlanRoute:
    def test_no_profile_404(self, app, store):
        client, _ = _authed(app, store, with_profile=False)
        r = client.post("/api/search-plan", json={}, headers=ORIGIN)
        assert r.status_code == 404

    def test_returns_keywords(self, app, store, monkeypatch):
        client, _ = _authed(app, store)
        fake = MagicMock()
        fake.call_api_simple.return_value = '["市场风险管理", "FRM 风控"]'
        monkeypatch.setattr(
            "backend.app.AIClientFactory",
            MagicMock(create_pure_client=MagicMock(return_value=fake)))
        r = client.post("/api/search-plan", json={}, headers=ORIGIN)
        assert r.status_code == 200
        body = r.get_json()
        assert body["keywords"] == ["市场风险管理", "FRM 风控"]
        assert body["profile"]["target_directions"]

    def test_ai_failure_falls_back_to_directions(self, app, store, monkeypatch):
        client, _ = _authed(app, store)
        fake = MagicMock()
        fake.call_api_simple.side_effect = Exception("AI down")
        monkeypatch.setattr(
            "backend.app.AIClientFactory",
            MagicMock(create_pure_client=MagicMock(return_value=fake)))
        r = client.post("/api/search-plan", json={}, headers=ORIGIN)
        assert r.status_code == 200
        assert r.get_json()["keywords"] == ["市场风险管理", "风险计量"]

    def test_unauthenticated_401(self, app):
        c = app.test_client()
        r = c.post("/api/search-plan", json={}, headers=ORIGIN)
        assert r.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
