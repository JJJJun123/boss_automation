#!/usr/bin/env python3
"""画像锚定分析（spec 阶段 D5）"""

import json as _json
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

JOB = {"title": "买方量化风控经理", "company": "某基金",
       "job_description": "负责量化风控模型", "salary": "30-50K"}

PROFILE = {"target_directions": ["买方量化风控", "市场风险管理"],
           "transition": {"is_transition": True, "from": "券商风控",
                          "to": "买方量化风控"},
           "cities": ["shanghai"], "salary_floor": None,
           "hard_avoids": ["外包"], "seniority": None, "notes": ""}


def _analyzer(screening_mode=True):
    from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer
    return EnhancedJobAnalyzer(
        extraction_provider="deepseek", analysis_provider="deepseek",
        extraction_model_name="deepseek-v4-flash", screening_mode=screening_mode)


def _capture_ai(analyzer):
    """假 AI：记录所有 prompt，粗筛回'是'，精配回合法 JSON"""
    prompts = []

    def _dispatch(prompt, **kwargs):
        prompts.append({"prompt": prompt, "kwargs": kwargs})
        if kwargs.get("max_tokens", 0) <= 200:
            return "是"
        return _json.dumps({"score": 7, "reason": "ok",
                            "final_decision": "apply"}, ensure_ascii=False)

    fake = MagicMock()
    fake.call_api_simple.side_effect = _dispatch
    analyzer.job_analyzer.ai_client = fake
    analyzer.extraction_service = fake
    return prompts


class TestNoProfileRegression:
    def test_none_profile_behaves_as_today(self):
        analyzer = _analyzer()
        prompts = _capture_ai(analyzer)
        out = analyzer.analyze_jobs([dict(JOB)], resume_text="简历",
                                    keyword="风控", career_profile=None)
        assert out and out[0]["score"] == 7
        # 无画像时任何 prompt 都不应包含画像专有词
        assert all("target_directions" not in p["prompt"] for p in prompts)


class TestHardAvoidsRuleLayer:
    def test_hard_avoids_discard_before_ai(self):
        analyzer = _analyzer(screening_mode=False)
        _capture_ai(analyzer)
        bad_job = dict(JOB, title="风控专员（外包驻场）")
        analyzer.analyze_jobs([bad_job], resume_text="简历", keyword="风控",
                              career_profile=dict(PROFILE))
        assert any(e["stage"] == "hard_filter" for e in analyzer.discarded_jobs), \
            f"hard_avoids 未进规则层: {analyzer.discarded_jobs}"


class TestScreeningAnchor:
    def test_screening_prompt_contains_directions(self):
        analyzer = _analyzer(screening_mode=True)
        prompts = _capture_ai(analyzer)
        analyzer.analyze_jobs([dict(JOB)], resume_text="简历", keyword="风控",
                              career_profile=dict(PROFILE))
        screening_prompts = [p["prompt"] for p in prompts
                             if p["kwargs"].get("max_tokens", 0) <= 200]
        assert screening_prompts, "未发生粗筛调用"
        assert any("买方量化风控" in p for p in screening_prompts), \
            "粗筛 prompt 未包含画像目标方向"


class TestMatchingAnchor:
    def test_transition_prompt_uses_springboard_anchor(self):
        analyzer = _analyzer(screening_mode=False)
        prompts = _capture_ai(analyzer)
        analyzer.analyze_jobs([dict(JOB)], resume_text="简历", keyword="风控",
                              career_profile=dict(PROFILE))
        match_prompts = [p["prompt"] for p in prompts
                         if p["kwargs"].get("max_tokens", 0) > 200]
        assert match_prompts, "未发生精配调用"
        text = match_prompts[0]
        assert "买方量化风控" in text, "匹配 prompt 未包含转型目标"
        assert ("跳板" in text or "可迁移" in text), \
            "转型场景未切换评分锚（应含 跳板/可迁移 表述）"

    def test_non_transition_profile_no_springboard(self):
        analyzer = _analyzer(screening_mode=False)
        prompts = _capture_ai(analyzer)
        plain = dict(PROFILE, transition=None)
        analyzer.analyze_jobs([dict(JOB)], resume_text="简历", keyword="风控",
                              career_profile=plain)
        match_prompts = [p["prompt"] for p in prompts
                         if p["kwargs"].get("max_tokens", 0) > 200]
        assert match_prompts
        assert "跳板" not in match_prompts[0], "非转型不应用跳板锚"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
