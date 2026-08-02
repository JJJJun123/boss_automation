#!/usr/bin/env python3
"""阶段 S-B/C：可提交、可审查的 systemd 与 cron 配置契约。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_systemd_unit_uses_single_gthread_worker():
    unit = (ROOT / "deploy" / "boss-automation.service").read_text("utf-8")
    assert "--worker-class gthread" in unit
    assert "--workers 1" in unit
    assert "--threads 16" in unit
    assert "--timeout 120" in unit
    assert "backend.app:create_app_for_gunicorn()" in unit
    assert "run_web.py" not in unit


def test_daily_backup_cron_runs_at_four_and_keeps_fourteen():
    cron = (ROOT / "deploy" / "boss-state-backup.cron").read_text("utf-8")
    assert cron.startswith("0 4 * * * root ")
    assert "scripts/backup_state.sh" in cron
    assert "data/state.db" in cron
    assert "/root/backups 14" in cron


def test_gunicorn_is_a_runtime_dependency():
    requirements = (ROOT / "requirements.txt").read_text("utf-8")
    assert "gunicorn" in requirements
