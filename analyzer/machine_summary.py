#!/usr/bin/env python3
"""阶段二分析结果的稳定、机器可读摘要。"""

import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)

VALID_DECISIONS = {"apply", "consider", "research", "skip"}
VALID_DISCARD_REASONS = {
    "salary_too_low",
    "seniority_mismatch",
    "domain_mismatch",
    "location_mismatch",
    "company_type_mismatch",
    "workload_mismatch",
    "other",
}


def normalize_machine_summary(raw: Any, job: Any) -> Dict[str, Any]:
    """把模型的不稳定输出收敛为固定五字段 schema。

    这里刻意不抛出校验异常：单个模型字段写坏时，岗位分析的其余旧字段
    仍然有价值。无效决策回落到 ``consider``，避免误导用户直接投递或跳过。
    """
    raw = raw if isinstance(raw, dict) else {}
    job = job if isinstance(job, dict) else {}

    decision = raw.get("final_decision")
    decision = decision.strip().lower() if isinstance(decision, str) else ""
    if decision not in VALID_DECISIONS:
        logger.warning("模型返回了无效 final_decision=%r，已回落为 consider", decision)
        decision = "consider"

    hard_stops = raw.get("hard_stops")
    if not isinstance(hard_stops, list):
        hard_stops = []

    soft_gaps = raw.get("soft_gaps")
    if not isinstance(soft_gaps, list):
        soft_gaps = []

    raw_reasons = raw.get("discard_reasons")
    discard_reasons = []
    if isinstance(raw_reasons, list):
        for reason in raw_reasons:
            normalized = (reason if isinstance(reason, str)
                          and reason in VALID_DISCARD_REASONS else "other")
            if normalized not in discard_reasons:
                discard_reasons.append(normalized)

    advertised_comp = raw.get("advertised_comp")
    if not isinstance(advertised_comp, str) or not advertised_comp.strip():
        advertised_comp = job.get("salary") or ""

    return {
        "final_decision": decision,
        "hard_stops": hard_stops,
        "soft_gaps": soft_gaps,
        "discard_reasons": discard_reasons,
        "advertised_comp": advertised_comp,
    }
