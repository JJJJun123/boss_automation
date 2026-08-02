#!/usr/bin/env python3
"""阶段 S-G：邀请码管理 CLI 契约测试。"""

import os
import re
import sqlite3
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "invite.py")
WRAPPER = os.path.join(os.path.dirname(__file__), "..", "scripts", "invite")


def _run(db_path, *args):
    """运行邀请 CLI；参数为数据库路径和命令参数，返回 CompletedProcess。"""
    return subprocess.run(
        [sys.executable, SCRIPT, "--db", str(db_path), *args],
        capture_output=True,
        text=True,
    )


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "state.db"


def test_generate_creates_one_unused_code(db_path):
    result = _run(db_path, "generate")
    assert result.returncode == 0, result.stderr
    code = result.stdout.strip()
    assert re.fullmatch(r"[A-Za-z0-9_-]{8}", code)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT code, status FROM invites WHERE code = ?", (code,)
        ).fetchone()
    assert row == (code, "unused")


def test_server_command_wrapper_is_executable(db_path):
    assert os.path.isfile(WRAPPER)
    assert os.access(WRAPPER, os.X_OK)
    result = subprocess.run(
        [WRAPPER, "--db", str(db_path), "generate"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert re.fullmatch(r"[A-Za-z0-9_-]{8}", result.stdout.strip())


def test_generate_count_outputs_distinct_codes(db_path):
    result = _run(db_path, "generate", "--count", "3")
    assert result.returncode == 0, result.stderr
    codes = result.stdout.splitlines()
    assert len(codes) == 3
    assert len(set(codes)) == 3


def test_list_can_filter_by_status(db_path):
    generated = _run(db_path, "generate", "--count", "2")
    assert generated.returncode == 0
    codes = generated.stdout.splitlines()
    result = _run(db_path, "list", "--status", "unused")
    assert result.returncode == 0, result.stderr
    assert "STATUS" in result.stdout
    assert all(code in result.stdout for code in codes)
    assert "unused" in result.stdout


def test_revoke_marks_unused_code_revoked(db_path):
    generated = _run(db_path, "generate")
    assert generated.returncode == 0, generated.stderr
    code = generated.stdout.strip()
    result = _run(db_path, "revoke", code)
    assert result.returncode == 0, result.stderr
    assert code in result.stdout
    listed = _run(db_path, "list", "--status", "revoked")
    assert code in listed.stdout


def test_revoke_refuses_used_or_unknown_code(db_path):
    from utils.state_store import StateStore

    store = StateStore(str(db_path))
    store.init_schema()
    used_code = store.create_invite()
    assert store.consume_invite(used_code)

    used_result = _run(db_path, "revoke", used_code)
    missing_result = _run(db_path, "revoke", "notfound")
    assert used_result.returncode != 0
    assert missing_result.returncode != 0
    assert store.list_invites(status="used")[0]["code"] == used_code


def test_revoke_accepts_urlsafe_code_starting_with_dash(db_path):
    from utils.state_store import StateStore

    store = StateStore(str(db_path))
    store.init_schema()
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO invites (code, status, created_at) "
            "VALUES (?, 'unused', 1)",
            ("-abc1234",),
        )
        conn.commit()

    result = _run(db_path, "revoke", "-abc1234")
    assert result.returncode == 0, result.stderr
    assert store.list_invites(status="revoked")[0]["code"] == "-abc1234"
