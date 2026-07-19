#!/usr/bin/env python3
"""Machine Summary 结构化产物（spec 阶段 P2）

阶段二输出从自由 JSON 升级为固定 schema：
final_decision（四枚举）/ hard_stops / soft_gaps / discard_reasons（slug 枚举）/
advertised_comp（逐字薪资）。normalize 兜住 AI 输出的不稳定性。
"""

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

JOB = {"title": "风险经理", "company": "X公司", "salary": "20-35K·14薪",
       "job_description": "负责市场风险计量"}


# ─── normalize_machine_summary ──────────────────────────


class TestNormalize:
    def _norm(self, raw, job=None):
        from analyzer.machine_summary import normalize_machine_summary
        return normalize_machine_summary(raw, job if job is not None else dict(JOB))

    def test_valid_passthrough(self):
        raw = {"final_decision": "apply",
               "hard_stops": [],
               "soft_gaps": ["未做过期货"],
               "discard_reasons": [],
               "advertised_comp": "20-35K·14薪"}
        out = self._norm(raw)
        assert out["final_decision"] == "apply"
        assert out["soft_gaps"] == ["未做过期货"]
        assert out["advertised_comp"] == "20-35K·14薪"

    def test_invalid_decision_falls_back_to_consider(self):
        out = self._norm({"final_decision": "立即投递！"})
        assert out["final_decision"] == "consider"

    def test_missing_decision_falls_back_to_consider(self):
        out = self._norm({})
        assert out["final_decision"] == "consider"

    def test_unknown_discard_slug_becomes_other(self):
        out = self._norm({"final_decision": "skip",
                          "discard_reasons": ["salary_too_low", "自造理由"]})
        assert "salary_too_low" in out["discard_reasons"]
        assert "other" in out["discard_reasons"]
        assert "自造理由" not in out["discard_reasons"]

    def test_list_fields_default_empty(self):
        out = self._norm({"final_decision": "apply",
                          "hard_stops": "不是列表", "soft_gaps": None})
        assert out["hard_stops"] == []
        assert out["soft_gaps"] == []

    def test_advertised_comp_falls_back_to_job_salary(self):
        out = self._norm({"final_decision": "apply"})
        assert out["advertised_comp"] == "20-35K·14薪"

    def test_advertised_comp_empty_when_no_salary_anywhere(self):
        out = self._norm({"final_decision": "apply"}, job={"title": "x"})
        assert out["advertised_comp"] == ""

    def test_output_has_exactly_five_keys(self):
        out = self._norm({"final_decision": "apply"})
        assert set(out.keys()) == {"final_decision", "hard_stops", "soft_gaps",
                                   "discard_reasons", "advertised_comp"}

    def test_enums_exported(self):
        from analyzer.machine_summary import VALID_DECISIONS, VALID_DISCARD_REASONS
        assert VALID_DECISIONS == {"apply", "consider", "research", "skip"}
        assert "salary_too_low" in VALID_DISCARD_REASONS
        assert "other" in VALID_DISCARD_REASONS


# ─── prompt 模板包含 schema 键 ──────────────────────────


class TestPromptSchema:
    def test_match_prompt_mentions_all_keys(self):
        from analyzer.prompts.job_match_prompts import JobMatchPrompts
        # 取任意一个生成匹配 prompt 的方法输出做包含性检查
        candidates = [m for m in dir(JobMatchPrompts) if "match" in m.lower()]
        assert candidates, "JobMatchPrompts 无匹配 prompt 方法"
        text = ""
        for name in candidates:
            fn = getattr(JobMatchPrompts, name)
            try:
                text += str(fn.__doc__ or "")
                import inspect
                text += inspect.getsource(fn)
            except Exception:
                continue
        for key in ("final_decision", "hard_stops", "soft_gaps",
                    "discard_reasons", "advertised_comp"):
            assert key in text, f"匹配 prompt 未包含 schema 键 {key}"


# ─── analyzer 集成：分析产物并入 5 字段 ──────────────────


class TestAnalyzerIntegration:
    def _analyzer_with_fake_ai(self, ai_response: str):
        from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer
        analyzer = EnhancedJobAnalyzer(
            extraction_provider="deepseek", analysis_provider="deepseek",
            extraction_model_name="deepseek-v4-flash", screening_mode=False)
        fake = MagicMock()
        fake.call_api_simple.return_value = ai_response
        analyzer.job_analyzer.ai_client = fake
        analyzer.extraction_service = fake
        return analyzer

    def test_analyzed_job_carries_machine_summary_fields(self):
        response = json.dumps({
            "score": 7, "reason": "匹配较好",
            "final_decision": "apply", "hard_stops": [],
            "soft_gaps": ["缺期货经验"], "discard_reasons": [],
            "advertised_comp": "20-35K·14薪",
        }, ensure_ascii=False)
        analyzer = self._analyzer_with_fake_ai(response)
        out = analyzer.analyze_jobs([dict(JOB)], resume_text="简历", keyword="风险")
        assert out, "分析结果为空"
        job = out[0]
        for key in ("final_decision", "hard_stops", "soft_gaps",
                    "discard_reasons", "advertised_comp"):
            assert key in job, f"分析产物缺少 {key}"
        assert job["final_decision"] == "apply"

    def test_bad_decision_normalized_in_pipeline(self):
        response = json.dumps({
            "score": 3, "reason": "一般",
            "final_decision": "乱写的决策",
        }, ensure_ascii=False)
        analyzer = self._analyzer_with_fake_ai(response)
        out = analyzer.analyze_jobs([dict(JOB)], resume_text="简历", keyword="风险")
        assert out[0]["final_decision"] == "consider"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
