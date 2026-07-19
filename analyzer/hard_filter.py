#!/usr/bin/env python3
"""
Hard filter — AI 评分前的硬性过滤

对应 IMPLEMENTATION_PLAN 阶段 1.8 + design.md F2「Hard filters」。

在两阶段 AI 之前过滤掉用户明确不要的岗位，节省 API 成本：
- 最低薪资门槛（月薪 K）
- 排除标签（外包 / 培训 / 中介猎头 / 销售 等）命中标题/JD
- 期望年限范围（可选）

核心原则：**信息不足时不排除**（宁可送 AI 也不误杀）。
薪资"面议"无法判定下限 → 保留；标签未命中 → 保留。
"""

import re
from typing import Any, Dict, List, Optional, Tuple


# 匹配 "20-40K" / "15K-30K" / "30K" / "1-2万" / "1.5万" 这类月薪
_RANGE_K = re.compile(r"(\d+(?:\.\d+)?)\s*[Kk]?\s*[-~到]\s*(\d+(?:\.\d+)?)\s*[Kk]")
_SINGLE_K = re.compile(r"(\d+(?:\.\d+)?)\s*[Kk]")
_RANGE_WAN = re.compile(r"(\d+(?:\.\d+)?)\s*[-~到]\s*(\d+(?:\.\d+)?)\s*万")
_SINGLE_WAN = re.compile(r"(\d+(?:\.\d+)?)\s*万")
# 日薪/时薪等非月薪 → 不强行换算
_NON_MONTHLY = re.compile(r"/\s*(天|日|时|小时|周)")

# 经验年限：匹配 "3-5年" "5年以上" "3年" "经验3年"
_EXP_RANGE = re.compile(r"(\d+)\s*[-~到]\s*(\d+)\s*年")
_EXP_MIN = re.compile(r"(\d+)\s*年(?:以上|\+)")
_EXP_SINGLE = re.compile(r"(\d+)\s*年")
# "经验不限" / "应届" / "1年以下" 视为低门槛
_EXP_UNLIMITED = re.compile(r"经验不限|不限经验|应届|实习")

# 学历等级（数字越大要求越高）
_EDU_LEVELS = {
    "高中": 1, "中专": 1, "技校": 1,
    "大专": 2, "专科": 2,
    "本科": 3, "学士": 3,
    "硕士": 4, "研究生": 4,
    "博士": 5,
}
_EDU_UNLIMITED = re.compile(r"学历不限|不限学历")

# 销售岗别名（绕过"销售"字面的常见马甲）
SALES_ALIASES = (
    "销售", "客户经理", "业务代表", "业务经理", "渠道经理",
    "BD", "商务拓展", "电话销售", "客户代表", "大客户",
)
# 猎头/中介别名
HEADHUNTER_ALIASES = (
    "猎头", "中介", "人力资源服务", "招聘顾问", "RPO", "人才顾问", "劳务派遣",
)


def parse_salary_floor_k(salary: Optional[str]) -> Optional[float]:
    """解析薪资文本，返回月薪下限（单位 K）

    支持："20-40K" "15K-30K" "30K" "20-40K·14薪" "1-2万" "1.5万"
    返回 None：面议 / 空 / 日薪时薪等无法判定月薪下限的格式

    参数：salary - Boss 薪资文本
    返回：float 月薪下限（K）；无法判定返回 None
    """
    if not salary:
        return None
    text = salary.strip()
    # 日薪/时薪等不强行换算
    if _NON_MONTHLY.search(text):
        return None

    # K 区间优先（取低值）
    m = _RANGE_K.search(text)
    if m:
        return float(m.group(1))
    # 万区间（转 K）
    m = _RANGE_WAN.search(text)
    if m:
        return float(m.group(1)) * 10
    # 单值 K
    m = _SINGLE_K.search(text)
    if m:
        return float(m.group(1))
    # 单值万
    m = _SINGLE_WAN.search(text)
    if m:
        return float(m.group(1)) * 10
    # 面议 / 其它无法解析 → None
    return None


def parse_required_years(job: Dict[str, Any]) -> Optional[float]:
    """从 JD/要求 解析岗位要求的最低经验年限

    返回：float 年限下限；信息不足（无年限描述）返回 None
    "经验不限/应届" → 0
    """
    text = " ".join([
        str(job.get("job_requirements", "")),
        str(job.get("job_description", "")),
        str(job.get("title", "")),
    ])
    if _EXP_UNLIMITED.search(text):
        return 0.0
    m = _EXP_RANGE.search(text)
    if m:
        return float(m.group(1))
    m = _EXP_MIN.search(text)
    if m:
        return float(m.group(1))
    m = _EXP_SINGLE.search(text)
    if m:
        return float(m.group(1))
    return None


def parse_required_edu(job: Dict[str, Any]) -> Optional[int]:
    """从 JD/要求 解析岗位要求的学历等级（数字越大越高）

    返回：int 学历等级（见 _EDU_LEVELS）；信息不足/不限 → None
    """
    text = " ".join([
        str(job.get("job_requirements", "")),
        str(job.get("job_description", "")),
    ])
    if _EDU_UNLIMITED.search(text):
        return None
    # 取文本中出现的最高学历要求（"本科及以上" → 本科）
    found = [level for kw, level in _EDU_LEVELS.items() if kw in text]
    return max(found) if found else None


def job_passes_hard_filters(job: Dict[str, Any],
                            hard_filters: Dict[str, Any]) -> Tuple[bool, str]:
    """判断单个岗位是否通过 hard filters

    参数：
        job          - 岗位 dict（title / salary / job_description / job_requirements）
        hard_filters - {min_salary_k, exclude_tags[], year_min, year_max,
                        edu_max_level, exclude_sales, exclude_headhunter}
    返回：
        (passed, reason) - passed=False 时 reason 说明被哪条过滤

    原则：信息不足（薪资面议 / 无年限描述 / 学历不限）一律**不排除**，宁送 AI 不误杀。
    """
    if not hard_filters:
        return True, ""

    haystack = " ".join([
        str(job.get("title", "")),
        str(job.get("job_description", "")),
        str(job.get("job_requirements", "")),
    ])

    # 1. 薪资下限：能解析出下限且低于门槛才排除
    min_salary = hard_filters.get("min_salary_k")
    if min_salary:
        floor = parse_salary_floor_k(job.get("salary"))
        if floor is not None and floor < float(min_salary):
            return False, f"薪资下限 {floor}K < 门槛 {min_salary}K"

    # 2. 年限：岗位要求年限 > 用户上限才排除（信息不足不排除）
    year_max = hard_filters.get("year_max")
    if year_max is not None:
        req_years = parse_required_years(job)
        if req_years is not None and req_years > float(year_max):
            return False, f"要求经验 {req_years}年 > 上限 {year_max}年"

    # 3. 学历：岗位要求学历 > 用户可达上限才排除（信息不足不排除）
    edu_max = hard_filters.get("edu_max_level")
    if edu_max is not None:
        req_edu = parse_required_edu(job)
        if req_edu is not None and req_edu > int(edu_max):
            return False, f"要求学历等级 {req_edu} > 用户上限 {edu_max}"

    # 4. 自定义排除标签
    for tag in (hard_filters.get("exclude_tags") or []):
        if tag and tag in haystack:
            return False, f"命中排除标签「{tag}」"

    # 5. 排除销售岗（含别名）
    if hard_filters.get("exclude_sales"):
        for alias in SALES_ALIASES:
            if alias in haystack:
                return False, f"命中销售岗别名「{alias}」"

    # 6. 排除猎头/中介
    if hard_filters.get("exclude_headhunter"):
        for alias in HEADHUNTER_ALIASES:
            if alias in haystack:
                return False, f"命中猎头/中介别名「{alias}」"

    return True, ""


def apply_hard_filters(jobs: List[Dict[str, Any]],
                       hard_filters: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """对岗位列表批量应用 hard filters

    参数：
        jobs         - 岗位列表
        hard_filters - 过滤条件
    返回：
        (kept, dropped) - kept 是通过的岗位；dropped 每项 = 原 job + {"reason": ...}
                          dropped 带原因便于日志记录与前端"被过滤数"展示
    """
    if not hard_filters:
        return list(jobs), []

    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    for job in jobs:
        passed, reason = job_passes_hard_filters(job, hard_filters)
        if passed:
            kept.append(job)
        else:
            dropped.append({**job, "reason": reason})
    return kept, dropped
