#!/usr/bin/env python3
"""Claude 客户端不得发送采样参数（temperature/top_p/top_k）

背景：Claude 5 家族（claude-sonnet-5 等）与 Opus 4.7+ 已移除采样参数，
非默认值请求直接 400（实测报错：`temperature` is deprecated for this model）。
官方迁移指引：彻底省略采样参数（对旧 Claude 模型省略 = 用默认值，同样安全）。

覆盖：
- HTTP 客户端 call_api / call_api_simple 请求体无 temperature/top_p/top_k
- SDK 客户端 messages.create 调用 kwargs 无 temperature/top_p/top_k
- 显式传入 temperature 也被忽略（防上游 analyzer 旧代码路径复发）
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SAMPLING_KEYS = ("temperature", "top_p", "top_k")


class TestClaudeHttpClientNoSampling:
    def _capture_payload(self, call, **kwargs):
        from analyzer.clients.claude_client import ClaudeClient
        client = ClaudeClient("claude-sonnet-5")
        client.api_key = "sk-test"
        captured = {}

        def _fake_post(url, headers=None, json=None, timeout=None, **kw):
            captured.update(json or {})
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"content": [{"text": "ok"}]}
            return resp

        with patch("analyzer.clients.claude_client.requests.post",
                   side_effect=_fake_post):
            if call == "simple":
                client.call_api_simple("提示词", **kwargs)
            else:
                client.call_api("system", "user", **kwargs)
        return captured

    def test_call_api_simple_omits_sampling(self):
        payload = self._capture_payload("simple")
        for key in SAMPLING_KEYS:
            assert key not in payload, f"请求体不应含 {key}"

    def test_call_api_omits_sampling(self):
        payload = self._capture_payload("full")
        for key in SAMPLING_KEYS:
            assert key not in payload, f"请求体不应含 {key}"

    def test_explicit_temperature_kwarg_ignored(self):
        """上游旧代码显式传 temperature=0.1 也不能进请求体"""
        payload = self._capture_payload("simple", temperature=0.1)
        assert "temperature" not in payload


class TestClaudeSdkClientNoSampling:
    def test_sdk_call_api_simple_omits_sampling(self):
        from analyzer.clients import claude_client_sdk as mod
        if not mod.ANTHROPIC_SDK_AVAILABLE:
            pytest.skip("anthropic SDK 未安装")
        client = mod.ClaudeClientSDK("claude-sonnet-5", api_key="sk-test")
        fake_msg = MagicMock()
        fake_msg.content = [MagicMock(text="ok")]
        client.client = MagicMock()
        client.client.messages.create.return_value = fake_msg

        client.call_api_simple("提示词", temperature=0.1)

        kwargs = client.client.messages.create.call_args.kwargs
        for key in SAMPLING_KEYS:
            assert key not in kwargs, f"SDK 调用不应含 {key}"

    def test_sdk_call_api_omits_sampling(self):
        from analyzer.clients import claude_client_sdk as mod
        if not mod.ANTHROPIC_SDK_AVAILABLE:
            pytest.skip("anthropic SDK 未安装")
        client = mod.ClaudeClientSDK("claude-sonnet-5", api_key="sk-test")
        fake_msg = MagicMock()
        fake_msg.content = [MagicMock(text="ok")]
        client.client = MagicMock()
        client.client.messages.create.return_value = fake_msg

        client.call_api("system", "user")

        kwargs = client.client.messages.create.call_args.kwargs
        for key in SAMPLING_KEYS:
            assert key not in kwargs, f"SDK 调用不应含 {key}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
