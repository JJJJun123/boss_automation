#!/usr/bin/env python3
"""AIClientFactory per-user api_key 透传测试

覆盖：
- create_pure_client(api_key=...) 覆盖 env
- 不传 api_key 回落 env（现状行为不变）
- 多实例不同 key 互不污染（并发安全最小闭环）
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzer.ai_client_factory import AIClientFactory


class TestDeepSeekKeyOverride:
    def test_explicit_key_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-key")
        client = AIClientFactory.create_pure_client(
            "deepseek", "deepseek-v4-flash", api_key="sk-user-key")
        assert client.api_key == "sk-user-key"

    def test_no_key_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-key")
        client = AIClientFactory.create_pure_client("deepseek", "deepseek-v4-flash")
        assert client.api_key == "sk-env-key"

    def test_two_instances_hold_independent_keys(self, monkeypatch):
        """并发场景基础保证：实例各持各的 key，互不覆盖"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-key")
        a = AIClientFactory.create_pure_client(
            "deepseek", "deepseek-v4-flash", api_key="sk-user-a")
        b = AIClientFactory.create_pure_client(
            "deepseek", "deepseek-v4-flash", api_key="sk-user-b")
        assert a.api_key == "sk-user-a"
        assert b.api_key == "sk-user-b"

    def test_override_does_not_mutate_env(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-key")
        AIClientFactory.create_pure_client(
            "deepseek", "deepseek-v4-flash", api_key="sk-user-key")
        assert os.environ["DEEPSEEK_API_KEY"] == "sk-env-key"


class TestHttpClientsKeyOverride:
    """HTTP 客户端（非 SDK）路径的 key 透传"""

    def test_claude_http_client(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_API_KEY", "sk-env-key")
        client = AIClientFactory.create_pure_client(
            "claude", None, use_sdk=False, api_key="sk-user-key")
        assert client.api_key == "sk-user-key"

    def test_gpt_http_client(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
        client = AIClientFactory.create_pure_client(
            "gpt", None, use_sdk=False, api_key="sk-user-key")
        assert client.api_key == "sk-user-key"


class TestAnalyzerKeyThreading:
    """EnhancedJobAnalyzer 把 api_key 一路传到两阶段 client"""

    def test_analyzer_passes_key_to_extraction_client(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-key")
        from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer
        analyzer = EnhancedJobAnalyzer(
            extraction_provider="deepseek",
            analysis_provider="deepseek",
            extraction_model_name="deepseek-v4-flash",
            api_key="sk-user-key",
        )
        assert analyzer.extraction_service.api_key == "sk-user-key"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
