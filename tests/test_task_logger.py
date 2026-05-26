#!/usr/bin/env python3
"""
任务日志（JSONL + journald 双写）测试

按 IMPLEMENTATION_PLAN.md 阶段 0.6：
- 任务/阶段/错误/评分 4 级日志统一接口
- 日期分文件 logs/tasks/YYYY-MM-DD.jsonl
- 敏感字段（简历正文 / Boss cookie）自动 hash + 长度
- 多线程并发写安全
- 输出 JSONL 一行一对象，jq 可解析
"""

import json
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.task_logger import TaskLogger, mask_sensitive


@pytest.fixture
def logger(tmp_path):
    """每个测试独立的日志目录"""
    return TaskLogger(log_dir=str(tmp_path / "logs"))


# ─── 基础写入与读回 ───────────────────────────────────────

def test_log_creates_jsonl_file_for_today(logger):
    logger.log({"task_id": "t1", "kind": "task_start", "keyword": "AI"})
    today_file = logger._file_path_for(time.time())
    assert os.path.exists(today_file)


def test_each_log_is_one_jsonl_line(logger):
    logger.log({"task_id": "t1", "kind": "task_start"})
    logger.log({"task_id": "t1", "kind": "task_end", "status": "success"})

    path = logger._file_path_for(time.time())
    with open(path) as f:
        lines = f.readlines()
    assert len(lines) == 2
    for line in lines:
        # 每行必须是合法 JSON
        obj = json.loads(line)
        assert "task_id" in obj
        assert "kind" in obj


def test_log_auto_adds_timestamp(logger):
    logger.log({"task_id": "t1", "kind": "task_start"})
    path = logger._file_path_for(time.time())
    with open(path) as f:
        obj = json.loads(f.readline())
    assert "ts" in obj
    assert isinstance(obj["ts"], (int, float))


# ─── 日期分文件 ───────────────────────────────────────────

def test_logs_split_by_date(logger):
    """同一 logger 写两天的数据应写到两个文件"""
    day1_ts = 1714000000.0  # 某天
    day2_ts = day1_ts + 86400 + 100  # 第二天
    logger.log({"task_id": "t1", "kind": "x"}, now=day1_ts)
    logger.log({"task_id": "t2", "kind": "y"}, now=day2_ts)

    file1 = logger._file_path_for(day1_ts)
    file2 = logger._file_path_for(day2_ts)
    assert file1 != file2
    assert os.path.exists(file1)
    assert os.path.exists(file2)


# ─── 敏感字段脱敏 ─────────────────────────────────────────

def test_mask_sensitive_resume_text():
    """简历正文必须被替换为 hash + 长度，正文绝不出现"""
    raw = {
        "task_id": "t1",
        "resume_text": "我是张三，5 年 Python 经验，曾在阿里...",
        "keyword": "AI",
    }
    masked = mask_sensitive(raw)
    assert "我是张三" not in str(masked)
    assert "阿里" not in str(masked)
    assert masked["resume_text"] != raw["resume_text"]
    # 应该是 dict {hash, length}
    assert "hash" in masked["resume_text"]
    assert "length" in masked["resume_text"]


def test_mask_sensitive_cookie():
    raw = {"task_id": "t1", "cookie": "__zp_stoken__=abc123secret"}
    masked = mask_sensitive(raw)
    assert "abc123secret" not in str(masked)


def test_mask_sensitive_api_key():
    raw = {"task_id": "t1", "api_key": "sk-xxx-secret-token-12345"}
    masked = mask_sensitive(raw)
    assert "sk-xxx" not in str(masked)


def test_mask_preserves_non_sensitive_fields():
    """非敏感字段原样保留"""
    raw = {"task_id": "t1", "keyword": "AI", "city": "shanghai", "score": 8}
    masked = mask_sensitive(raw)
    assert masked["keyword"] == "AI"
    assert masked["score"] == 8


def test_log_auto_masks_sensitive_fields(logger):
    """logger.log 自动调用 mask_sensitive"""
    logger.log({"task_id": "t1", "resume_text": "真实简历正文"})
    path = logger._file_path_for(time.time())
    with open(path) as f:
        content = f.read()
    assert "真实简历正文" not in content


# ─── 并发写入安全 ─────────────────────────────────────────

def test_concurrent_writes_no_corruption(logger):
    """10 个线程各写 100 条，最终 1000 条全部 JSON 合法"""
    def worker(tid):
        for i in range(100):
            logger.log({"task_id": f"t{tid}-{i}", "kind": "x"})

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    path = logger._file_path_for(time.time())
    with open(path) as f:
        lines = f.readlines()
    assert len(lines) == 1000
    for line in lines:
        json.loads(line)  # 每行都合法 = 没串行 corrupt


# ─── kind 级别字段 ────────────────────────────────────────

def test_log_task_event_helper(logger):
    """log_task_event(task_id, kind, **kwargs) 便捷接口"""
    logger.log_task_event("t1", "task_start", keyword="AI", city="shanghai")
    path = logger._file_path_for(time.time())
    with open(path) as f:
        obj = json.loads(f.readline())
    assert obj["task_id"] == "t1"
    assert obj["kind"] == "task_start"
    assert obj["keyword"] == "AI"
