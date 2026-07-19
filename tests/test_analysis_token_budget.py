#!/usr/bin/env python3
"""阶段二分析预算按 provider 区分（spec 阶段 R3）

Claude sonnet-5 / GPT-5 推理系的 thinking token 计入 max_tokens，
6000 会截断 JSON；DeepSeek 维持 6000（已调优 + 输出上限更低）。

契约：EnhancedJobAnalyzer._analysis_max_tokens() -> int；
_call_ai_for_matching 用它取代硬编码。
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer

JOB = {"title": "风险经理", "company": "X", "job_description": "做风控"}
RESUME = "四年市场风险经验"


def _analyzer_with_provider(provider):
    """构造 analyzer 并把匹配阶段 provider/client 换成假件

    真实构造走 deepseek（无 key 也能建），再覆写 job_analyzer 的
    provider 标识与 ai_client——只考察预算传参，不打真 API。
    """
    analyzer = EnhancedJobAnalyzer(
        extraction_provider="deepseek",
        analysis_provider="deepseek",
        extraction_model_name="deepseek-v4-flash",
    )
    fake_client = MagicMock()
    fake_client.call_api_simple.return_value = '{"score": 5, "reason": "r"}'
    analyzer.job_analyzer.ai_provider = provider
    analyzer.job_analyzer.ai_client = fake_client
    return analyzer, fake_client


class TestAnalysisMaxTokens:
    def test_contract_method_exists(self):
        analyzer, _ = _analyzer_with_provider("deepseek")
        assert callable(getattr(analyzer, "_analysis_max_tokens", None)), \
            "缺少 _analysis_max_tokens() 契约方法"

    @pytest.mark.parametrize("provider,expected", [
        ("claude", 16000),
        ("gpt", 16000),
        ("deepseek", 6000),
    ])
    def test_budget_by_provider(self, provider, expected):
        analyzer, fake_client = _analyzer_with_provider(provider)
        analyzer._call_ai_for_matching(JOB, RESUME)
        assert fake_client.call_api_simple.called, "匹配阶段未调用 AI"
        kwargs = fake_client.call_api_simple.call_args.kwargs
        assert kwargs.get("max_tokens") == expected, \
            f"{provider} 阶段二预算应为 {expected}，实际 {kwargs.get('max_tokens')}"

    def test_thinking_still_enabled(self):
        """预算改造不能弄丢 thinking=True（阶段二靠它做链式推理）"""
        analyzer, fake_client = _analyzer_with_provider("deepseek")
        analyzer._call_ai_for_matching(JOB, RESUME)
        kwargs = fake_client.call_api_simple.call_args.kwargs
        assert kwargs.get("thinking") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
