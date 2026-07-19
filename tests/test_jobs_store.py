#!/usr/bin/env python3
"""岗位落库 + 双层缓存 store 层（spec 阶段 P3）

jobs 表：全局事实缓存（key = Boss job_id，跨用户共享）
job_analyses 表：判断缓存（key = user + job + 简历指纹，任一变即失效）
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.state_store import StateStore, resume_fingerprint


@pytest.fixture
def store(tmp_path):
    s = StateStore(db_path=str(tmp_path / "jobs.db"))
    s.init_schema()
    return s


JOB = {"job_id": "abc123XYZ", "title": "风险经理", "company": "X公司",
       "salary": "20-35K·14薪", "city": "shanghai",
       "url": "https://www.zhipin.com/job_detail/abc123XYZ.html",
       "jd": "负责市场风险计量与压力测试"}


# ─── resume_fingerprint ─────────────────────────────────


class TestResumeFingerprint:
    def test_deterministic(self):
        assert resume_fingerprint("简历A") == resume_fingerprint("简历A")

    def test_different_text_different_hash(self):
        assert resume_fingerprint("简历A") != resume_fingerprint("简历B")

    def test_is_hex_sha256(self):
        fp = resume_fingerprint("任意文本")
        assert len(fp) == 64
        int(fp, 16)  # 合法十六进制


# ─── jobs 表 ────────────────────────────────────────────


class TestJobsUpsert:
    def test_first_seen_and_get(self, store):
        store.upsert_job(dict(JOB))
        row = store.get_fresh_job("abc123XYZ", max_age_seconds=60)
        assert row is not None
        assert row["title"] == "风险经理"
        assert row["jd"].startswith("负责市场风险")
        assert row["first_seen"] > 0
        assert row["last_seen"] >= row["first_seen"]

    def test_reupsert_updates_last_seen_keeps_first_seen(self, store):
        store.upsert_job(dict(JOB))
        row1 = store.get_fresh_job("abc123XYZ", 60)
        time.sleep(0.02)
        updated = dict(JOB, salary="25-40K·15薪")
        store.upsert_job(updated)
        row2 = store.get_fresh_job("abc123XYZ", 60)
        assert row2["first_seen"] == row1["first_seen"], "first_seen 不应被覆盖"
        assert row2["last_seen"] > row1["last_seen"], "last_seen 应更新"
        assert row2["salary"] == "25-40K·15薪", "字段应覆盖为最新"

    def test_missing_job_id_silently_skipped(self, store):
        store.upsert_job({"title": "无ID岗位"})  # 不抛即过

    def test_stale_job_not_returned(self, store):
        store.upsert_job(dict(JOB))
        # 手动把 last_seen 拨回 3 天前
        with store._connect() as conn:
            conn.execute("UPDATE jobs SET last_seen = ? WHERE job_id = ?",
                         (time.time() - 3 * 86400, "abc123XYZ"))
            conn.commit()
        assert store.get_fresh_job("abc123XYZ", max_age_seconds=48 * 3600) is None

    def test_unknown_job_none(self, store):
        assert store.get_fresh_job("nope", 60) is None


# ─── job_analyses 缓存 ──────────────────────────────────


class TestAnalysisCache:
    def _uid(self, store):
        code = store.create_invite()
        uid, _ = store.consume_invite(code)
        return uid

    def test_roundtrip(self, store):
        uid = self._uid(store)
        fp = resume_fingerprint("简历A")
        store.set_cached_analysis(uid, "job1", fp,
                                  '{"score": 7, "final_decision": "apply"}')
        cached = store.get_cached_analysis(uid, "job1", fp)
        assert cached["score"] == 7
        assert cached["final_decision"] == "apply"

    def test_upsert_overwrites(self, store):
        uid = self._uid(store)
        fp = resume_fingerprint("简历A")
        store.set_cached_analysis(uid, "job1", fp, '{"score": 5}')
        store.set_cached_analysis(uid, "job1", fp, '{"score": 8}')
        assert store.get_cached_analysis(uid, "job1", fp)["score"] == 8

    def test_miss_on_different_resume(self, store):
        uid = self._uid(store)
        store.set_cached_analysis(uid, "job1", resume_fingerprint("旧简历"),
                                  '{"score": 7}')
        assert store.get_cached_analysis(
            uid, "job1", resume_fingerprint("新简历")) is None

    def test_miss_on_different_user(self, store):
        uid_a, uid_b = self._uid(store), self._uid(store)
        fp = resume_fingerprint("简历A")
        store.set_cached_analysis(uid_a, "job1", fp, '{"score": 7}')
        assert store.get_cached_analysis(uid_b, "job1", fp) is None

    def test_miss_on_different_job(self, store):
        uid = self._uid(store)
        fp = resume_fingerprint("简历A")
        store.set_cached_analysis(uid, "job1", fp, '{"score": 7}')
        assert store.get_cached_analysis(uid, "job2", fp) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
