#!/usr/bin/env python3
"""
任务日志 — JSONL + journald 双写

按 IMPLEMENTATION_PLAN.md 阶段 0.6 + 设计文档「日志记录」section。

- 日期分文件：`logs/tasks/YYYY-MM-DD.jsonl`，一行一对象，jq 可解析
- 同步落 Python logging（systemd 自动捕获到 journald）
- 敏感字段（简历正文、Boss cookie、API key）自动 hash + 长度替换
- 线程安全：用 threading.Lock 保护文件写入

调用示例：
    from backend.task_logger import task_logger
    task_logger.log_task_event("task-abc", "task_start", keyword="AI", city="shanghai")

每天 0:00 系统 cron 可调 `task_logger.cleanup_old_logs(keep_days=90)` 清旧文件。
"""

import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


# 默认按字段名匹配敏感字段（部分匹配，case insensitive）
_SENSITIVE_KEYS = {
    "resume_text",
    "resume",
    "cookie",
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
}


def mask_sensitive(payload: Dict[str, Any]) -> Dict[str, Any]:
    """把敏感字段替换为 {hash, length}

    输入字段名是否敏感按 _SENSITIVE_KEYS 集合 + 子串包含匹配。
    例如 'resume_text' / 'user_cookie' / 'deepseek_api_key' 都会被识别。

    返回新 dict（不修改原 dict）。
    """
    result = {}
    for key, value in payload.items():
        key_lower = key.lower()
        is_sensitive = any(s in key_lower for s in _SENSITIVE_KEYS)
        if is_sensitive and isinstance(value, str):
            result[key] = {
                "hash": hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16],
                "length": len(value),
                "_masked": True,
            }
        else:
            result[key] = value
    return result


class TaskLogger:
    """JSONL 日志双写"""

    def __init__(self, log_dir: str = "logs/tasks"):
        """
        参数：
            log_dir - 日志根目录；按日期分子文件
        """
        self.log_dir = log_dir
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # ─── 公开 API ────────────────────────────────────────

    def log(self, payload: Dict[str, Any], now: Optional[float] = None) -> None:
        """写一条日志（自动加 ts + mask sensitive）

        参数：
            payload - 任意结构化数据；常见字段 task_id / kind / 其它
            now     - 当前时间戳（测试可注入）
        """
        now = now if now is not None else time.time()
        masked = mask_sensitive(payload)
        masked["ts"] = now

        line = json.dumps(masked, ensure_ascii=False)

        # 双写 1：JSONL 文件（按日期分）
        path = self._file_path_for(now)
        with self._lock:
            # 'a' 追加模式 + UTF-8；多线程 lock 保护避免行交错
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        # 双写 2：Python logging → systemd journald
        logger.info("task_event: %s", line)

    def log_task_event(self, task_id: str, kind: str, **fields) -> None:
        """便捷接口：自动塞 task_id + kind

        kind 推荐枚举：
            task_start / task_end / task_failed
            crawl_start / crawl_end / crawl_failed
            screen_start / screen_end
            match_start / match_end
            ai_call / ai_parse_failed
            error
        """
        payload = {"task_id": task_id, "kind": kind, **fields}
        self.log(payload)

    def cleanup_old_logs(self, keep_days: int = 90, now: Optional[float] = None) -> int:
        """清掉超过 keep_days 的旧日志文件

        返回：清掉的文件数
        """
        now = now if now is not None else time.time()
        cutoff = now - keep_days * 86400
        removed = 0
        for entry in Path(self.log_dir).iterdir():
            if entry.is_file() and entry.suffix == ".jsonl":
                if entry.stat().st_mtime < cutoff:
                    entry.unlink()
                    removed += 1
        return removed

    # ─── 内部 ─────────────────────────────────────────────

    def _file_path_for(self, ts: float) -> str:
        """根据时间戳算出当日 jsonl 文件路径"""
        date_str = time.strftime("%Y-%m-%d", time.gmtime(ts))
        return os.path.join(self.log_dir, f"{date_str}.jsonl")


# 全局单例（供 backend/app.py 复用）
task_logger = TaskLogger()
