#!/usr/bin/env python3
"""画像存储（spec 阶段 D1）"""

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.state_store import StateStore, resume_fingerprint


@pytest.fixture
def store(tmp_path):
    s = StateStore(db_path=str(tmp_path / "profile.db"))
    s.init_schema()
    return s


@pytest.fixture
def user_id(store):
    code = store.create_invite()
    uid, _ = store.consume_invite(code)
    return uid


PROFILE = {"target_directions": ["市场风险管理"], "transition": None,
           "cities": ["shanghai"], "salary_floor": "25K",
           "hard_avoids": ["外包"], "seniority": "3-5年", "notes": ""}


class TestCareerProfileStore:
    def test_get_before_set_none(self, store, user_id):
        assert store.get_career_profile(user_id) is None

    def test_roundtrip(self, store, user_id):
        fp = resume_fingerprint("简历A")
        store.set_career_profile(user_id, json.dumps(PROFILE, ensure_ascii=False), fp)
        out = store.get_career_profile(user_id)
        assert out["profile"]["target_directions"] == ["市场风险管理"]
        assert out["resume_hash"] == fp
        assert out["updated_at"] > 0

    def test_upsert_updates(self, store, user_id):
        fp = resume_fingerprint("简历A")
        store.set_career_profile(user_id, json.dumps(PROFILE), fp)
        first = store.get_career_profile(user_id)
        time.sleep(0.02)
        newp = dict(PROFILE, salary_floor="30K")
        store.set_career_profile(user_id, json.dumps(newp), fp)
        second = store.get_career_profile(user_id)
        assert second["profile"]["salary_floor"] == "30K"
        assert second["updated_at"] > first["updated_at"]

    def test_isolated_between_users(self, store):
        c1, c2 = store.create_invite(), store.create_invite()
        u1, _ = store.consume_invite(c1)
        u2, _ = store.consume_invite(c2)
        store.set_career_profile(u1, json.dumps(PROFILE), resume_fingerprint("A"))
        assert store.get_career_profile(u2) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
