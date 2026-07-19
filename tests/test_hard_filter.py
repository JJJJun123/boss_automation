#!/usr/bin/env python3
"""
Hard filter 测试（IMPLEMENTATION_PLAN 阶段 1.8 + design.md F2）

Hard filters 在 AI 评分前过滤岗位，节省 API 成本：
- 最低薪资门槛（月薪 K）
- 排除标签（外包 / 培训 / 中介猎头 / 销售）命中 title/JD → 排除
- 期望年限范围

设计原则：
- 信息不足时（薪资"面议"）**不排除**——宁可送 AI 也不误杀
- 每个 filter 命中/边界/不确定三类用例
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer.hard_filter import (
    parse_salary_floor_k,
    parse_required_years,
    parse_required_edu,
    job_passes_hard_filters,
    apply_hard_filters,
)


# ─── 薪资下限解析 ──────────────────────────────────────────

def test_parse_salary_range():
    assert parse_salary_floor_k("20-40K") == 20
    assert parse_salary_floor_k("15K-30K") == 15
    assert parse_salary_floor_k("20-40K·14薪") == 20


def test_parse_salary_single():
    assert parse_salary_floor_k("30K") == 30


def test_parse_salary_wan():
    """万/月 → 转 K"""
    assert parse_salary_floor_k("1-2万") == 10
    assert parse_salary_floor_k("1.5万") == 15


def test_parse_salary_negotiable_returns_none():
    """面议 / 薪资面议 / 空 → None（信息不足）"""
    assert parse_salary_floor_k("薪资面议") is None
    assert parse_salary_floor_k("面议") is None
    assert parse_salary_floor_k("") is None
    assert parse_salary_floor_k(None) is None


def test_parse_salary_daily_returns_none():
    """日薪/时薪等非月薪格式 → None（不强行换算）"""
    assert parse_salary_floor_k("200元/天") is None


# ─── 单岗位 hard filter 判定 ───────────────────────────────

def _job(title="AI算法工程师", salary="20-40K", desc="", req=""):
    return {"title": title, "salary": salary, "job_description": desc, "job_requirements": req}


# ─── 年限解析 + 过滤（命中/边界/不确定）─────────────────────

def test_parse_years_range():
    assert parse_required_years(_job(req="要求 3-5年 经验")) == 3
    assert parse_required_years(_job(req="5年以上经验")) == 5
    assert parse_required_years(_job(req="3年工作经验")) == 3


def test_parse_years_unlimited():
    assert parse_required_years(_job(req="经验不限")) == 0
    assert parse_required_years(_job(req="应届毕业生")) == 0


def test_parse_years_unknown_returns_none():
    """无年限描述 → None（不确定）"""
    assert parse_required_years(_job(req="负责大模型研发")) is None


def test_year_filter_hit():
    """要求 5 年 > 用户上限 2 年 → 排除（命中）"""
    job = _job(req="要求 5年以上 经验")
    ok, reason = job_passes_hard_filters(job, {"year_max": 2})
    assert ok is False
    assert "经验" in reason


def test_year_filter_boundary():
    """要求正好等于上限 → 通过（边界）"""
    job = _job(req="3年经验")
    ok, _r = job_passes_hard_filters(job, {"year_max": 3})
    assert ok is True


def test_year_filter_unknown_not_rejected():
    """无年限信息 → 不排除（不确定）"""
    job = _job(req="负责算法研发")
    ok, _r = job_passes_hard_filters(job, {"year_max": 2})
    assert ok is True


# ─── 学历解析 + 过滤（命中/边界/不确定）─────────────────────

def test_parse_edu_levels():
    assert parse_required_edu(_job(req="本科及以上")) == 3
    assert parse_required_edu(_job(req="硕士学历")) == 4
    assert parse_required_edu(_job(req="博士")) == 5


def test_parse_edu_unlimited_returns_none():
    assert parse_required_edu(_job(req="学历不限")) is None


def test_parse_edu_unknown_returns_none():
    assert parse_required_edu(_job(req="熟悉 Python")) is None


def test_edu_filter_hit():
    """要求博士(5) > 用户上限本科(3) → 排除（命中）"""
    job = _job(req="要求 博士 学历")
    ok, reason = job_passes_hard_filters(job, {"edu_max_level": 3})
    assert ok is False
    assert "学历" in reason


def test_edu_filter_boundary():
    """要求正好等于用户上限 → 通过（边界）"""
    job = _job(req="本科及以上")
    ok, _r = job_passes_hard_filters(job, {"edu_max_level": 3})
    assert ok is True


def test_edu_filter_unknown_not_rejected():
    """无学历要求 → 不排除（不确定）"""
    job = _job(req="熟悉机器学习")
    ok, _r = job_passes_hard_filters(job, {"edu_max_level": 2})
    assert ok is True


# ─── 销售岗别名（命中/边界/不确定）─────────────────────────

def test_sales_alias_hit_direct():
    """直接"销售"字面（命中）"""
    ok, reason = job_passes_hard_filters(_job(title="销售代表"), {"exclude_sales": True})
    assert ok is False
    assert "销售" in reason


def test_sales_alias_hit_disguised():
    """别名"客户经理"/"业务代表"绕过字面（命中别名）"""
    ok, _r = job_passes_hard_filters(_job(title="大客户经理"), {"exclude_sales": True})
    assert ok is False
    ok2, _r2 = job_passes_hard_filters(_job(title="业务代表"), {"exclude_sales": True})
    assert ok2 is False


def test_sales_alias_no_hit():
    """算法岗不含销售别名 → 通过（不确定边界：算法工程师不该误伤）"""
    ok, _r = job_passes_hard_filters(_job(title="AI算法工程师", desc="大模型 RAG"), {"exclude_sales": True})
    assert ok is True


# ─── 猎头/中介（命中/边界/不确定）──────────────────────────

def test_headhunter_hit():
    ok, reason = job_passes_hard_filters(_job(desc="某猎头公司代招"), {"exclude_headhunter": True})
    assert ok is False
    assert "猎头" in reason or "中介" in reason


def test_headhunter_alias_hit():
    ok, _r = job_passes_hard_filters(_job(desc="招聘顾问 RPO 服务"), {"exclude_headhunter": True})
    assert ok is False


def test_headhunter_no_hit():
    """普通甲方岗位 → 通过"""
    ok, _r = job_passes_hard_filters(_job(title="算法工程师", desc="字节跳动直招"), {"exclude_headhunter": True})
    assert ok is True


def test_passes_when_no_filters():
    """无 filter → 全通过"""
    assert job_passes_hard_filters(_job(), {})[0] is True


def test_salary_floor_pass():
    job = _job(salary="30-50K")
    ok, reason = job_passes_hard_filters(job, {"min_salary_k": 25})
    assert ok is True


def test_salary_floor_reject():
    job = _job(salary="10-15K")
    ok, reason = job_passes_hard_filters(job, {"min_salary_k": 25})
    assert ok is False
    assert "薪资" in reason


def test_salary_floor_boundary():
    """正好等于门槛 → 通过"""
    job = _job(salary="25-40K")
    ok, _ = job_passes_hard_filters(job, {"min_salary_k": 25})
    assert ok is True


def test_salary_negotiable_not_rejected():
    """面议信息不足 → 不排除（宁送 AI 不误杀）"""
    job = _job(salary="薪资面议")
    ok, _ = job_passes_hard_filters(job, {"min_salary_k": 25})
    assert ok is True


def test_exclude_tag_in_title():
    job = _job(title="销售代表（高薪急招）")
    ok, reason = job_passes_hard_filters(job, {"exclude_tags": ["销售"]})
    assert ok is False
    assert "销售" in reason


def test_exclude_tag_in_jd():
    job = _job(title="算法工程师", desc="本岗位为外包派遣至甲方")
    ok, reason = job_passes_hard_filters(job, {"exclude_tags": ["外包"]})
    assert ok is False


def test_exclude_tag_in_requirements():
    job = _job(req="培训机构讲师方向")
    ok, _ = job_passes_hard_filters(job, {"exclude_tags": ["培训"]})
    assert ok is False


def test_exclude_tag_no_hit():
    job = _job(title="AI算法工程师", desc="大模型 RAG 方向")
    ok, _ = job_passes_hard_filters(job, {"exclude_tags": ["外包", "销售"]})
    assert ok is True


def test_multiple_filters_all_must_pass():
    """薪资过但命中排除标签 → 仍排除"""
    job = _job(title="销售经理", salary="30-50K")
    ok, _ = job_passes_hard_filters(job, {"min_salary_k": 20, "exclude_tags": ["销售"]})
    assert ok is False


# ─── 批量过滤 ──────────────────────────────────────────────

def test_apply_hard_filters_splits():
    jobs = [
        _job(title="AI算法工程师", salary="30-50K"),
        _job(title="销售代表", salary="30-50K"),
        _job(title="数据分析师", salary="8-12K"),
    ]
    filters = {"min_salary_k": 20, "exclude_tags": ["销售"]}
    kept, dropped = apply_hard_filters(jobs, filters)
    assert len(kept) == 1
    assert kept[0]["title"] == "AI算法工程师"
    assert len(dropped) == 2


def test_apply_hard_filters_empty_filters_keeps_all():
    jobs = [_job(), _job(title="销售")]
    kept, dropped = apply_hard_filters(jobs, {})
    assert len(kept) == 2
    assert len(dropped) == 0


def test_apply_hard_filters_records_drop_reason():
    jobs = [_job(title="销售代表")]
    kept, dropped = apply_hard_filters(jobs, {"exclude_tags": ["销售"]})
    assert len(dropped) == 1
    # dropped 项带原因便于日志/前端"被过滤数"展示
    assert "reason" in dropped[0]
    assert "销售" in dropped[0]["reason"]
