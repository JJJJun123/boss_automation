#!/usr/bin/env python3
"""阶段 S-C：state.db 每日备份脚本

契约：scripts/backup_state.sh <db_path> <backup_dir> [retention_days]
- sqlite3 .backup 在线原子快照（不锁写库）→ gzip 到 backup_dir/state-YYYY-MM-DD.db.gz
- 超过 retention_days（默认 14）份数的最旧备份被删除
- db 不存在 → 非零退出
- 幂等：同日重跑覆盖当日份
"""

import gzip
import os
import sqlite3
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "backup_state.sh")


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO users VALUES ('u1', '陈俊旭')")
    conn.commit()
    conn.close()


def _run(db, out, retention=None):
    cmd = ["bash", SCRIPT, str(db), str(out)]
    if retention is not None:
        cmd.append(str(retention))
    return subprocess.run(cmd, capture_output=True, text=True)


class TestBackupScript:
    def test_script_exists_and_executable(self):
        assert os.path.isfile(SCRIPT), "scripts/backup_state.sh 不存在"

    def test_backup_created_and_openable(self, tmp_path):
        db = tmp_path / "state.db"
        out = tmp_path / "backups"
        _make_db(db)
        result = _run(db, out)
        assert result.returncode == 0, result.stderr
        backups = list(out.glob("state-*.db.gz"))
        assert len(backups) == 1, f"应产出 1 份 gz 备份，实际 {backups}"
        raw = tmp_path / "restored.db"
        raw.write_bytes(gzip.decompress(backups[0].read_bytes()))
        conn = sqlite3.connect(raw)
        rows = conn.execute("SELECT name FROM users").fetchall()
        conn.close()
        assert rows == [("陈俊旭",)], "备份内容不完整"

    def test_missing_db_nonzero_exit(self, tmp_path):
        result = _run(tmp_path / "nope.db", tmp_path / "backups")
        assert result.returncode != 0, "库不存在必须报错退出（否则 cron 静默空转）"

    def test_retention_prunes_oldest(self, tmp_path):
        db = tmp_path / "state.db"
        out = tmp_path / "backups"
        out.mkdir()
        _make_db(db)
        for day in ("2026-07-01", "2026-07-02", "2026-07-03"):
            (out / f"state-{day}.db.gz").write_bytes(b"old")
        result = _run(db, out, retention=3)
        assert result.returncode == 0, result.stderr
        backups = sorted(p.name for p in out.glob("state-*.db.gz"))
        assert len(backups) == 3, f"retention=3 应只留 3 份，实际 {backups}"
        assert "state-2026-07-01.db.gz" not in backups, "最旧一份应被删除"

    def test_same_day_rerun_idempotent(self, tmp_path):
        db = tmp_path / "state.db"
        out = tmp_path / "backups"
        _make_db(db)
        assert _run(db, out).returncode == 0
        assert _run(db, out).returncode == 0, "同日重跑必须成功（覆盖当日份）"
        assert len(list(out.glob("state-*.db.gz"))) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
