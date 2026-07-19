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
            resp.json.return_value = {
                "content": [{"type": "text", "text": "ok"}]}
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
        ok_block = MagicMock()
        ok_block.type = "text"
        ok_block.text = "ok"
        fake_msg.content = [ok_block]
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
        ok_block = MagicMock()
        ok_block.type = "text"
        ok_block.text = "ok"
        fake_msg.content = [ok_block]
        client.client = MagicMock()
        client.client.messages.create.return_value = fake_msg

        client.call_api("system", "user")

        kwargs = client.client.messages.create.call_args.kwargs
        for key in SAMPLING_KEYS:
            assert key not in kwargs, f"SDK 调用不应含 {key}"


class TestClaudeThinkingBlockParsing:
    """claude-sonnet-5 默认自适应思考：content[0] 可能是 thinking 块，
    文本在后续 type=text 块。客户端必须按类型取块，不能写死 content[0]。"""

    def _http_client_with_response(self, content_blocks):
        from analyzer.clients.claude_client import ClaudeClient
        client = ClaudeClient("claude-sonnet-5")
        client.api_key = "sk-test"
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"content": content_blocks}
        return client, resp

    def test_http_client_skips_thinking_block(self):
        client, resp = self._http_client_with_response([
            {"type": "thinking", "thinking": "推理过程…"},
            {"type": "text", "text": "最终答案"},
        ])
        with patch("analyzer.clients.claude_client.requests.post",
                   return_value=resp):
            assert client.call_api_simple("提示词") == "最终答案"

    def test_http_client_plain_text_still_works(self):
        client, resp = self._http_client_with_response([
            {"type": "text", "text": "普通回答"},
        ])
        with patch("analyzer.clients.claude_client.requests.post",
                   return_value=resp):
            assert client.call_api("system", "user") == "普通回答"

    def test_http_client_no_text_block_raises_clear_error(self):
        client, resp = self._http_client_with_response([
            {"type": "thinking", "thinking": "只有思考没有文本"},
        ])
        with patch("analyzer.clients.claude_client.requests.post",
                   return_value=resp):
            with pytest.raises(Exception):
                client.call_api_simple("提示词")

    def test_sdk_client_skips_thinking_block(self):
        from analyzer.clients import claude_client_sdk as mod
        if not mod.ANTHROPIC_SDK_AVAILABLE:
            pytest.skip("anthropic SDK 未安装")
        client = mod.ClaudeClientSDK("claude-sonnet-5", api_key="sk-test")
        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        del thinking_block.text  # thinking 块没有 text 属性
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "最终答案"
        fake_msg = MagicMock()
        fake_msg.content = [thinking_block, text_block]
        client.client = MagicMock()
        client.client.messages.create.return_value = fake_msg
        assert client.call_api_simple("提示词") == "最终答案"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
