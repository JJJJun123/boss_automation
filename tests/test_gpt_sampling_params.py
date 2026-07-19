#!/usr/bin/env python3
"""GPT 客户端参数契约（spec 阶段 R1/R2）

GPT-5 推理系列（gpt-5-mini / gpt-5.2）：
- 拒收非默认采样参数（temperature/top_p/top_k）——与 Claude 5 同款雷
- token 上限参数是 max_completion_tokens，旧 max_tokens 被拒；
  max_completion_tokens 兼容旧 chat 模型，可无条件使用

契约：两个 GPT 客户端对外签名不变（仍收 max_tokens= kwarg），内部
不发采样参数、payload/kwargs 用 max_completion_tokens。
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SAMPLING_KEYS = ("temperature", "top_p", "top_k")


class TestGptHttpClient:
    def _capture_payload(self, call, **kwargs):
        from analyzer.clients.gpt_client import GPTClient
        client = GPTClient("gpt-5.2")
        client.api_key = "sk-test"
        captured = {}

        def _fake_post(url, headers=None, json=None, timeout=None, **kw):
            captured.update(json or {})
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": "ok"}}]}
            return resp

        with patch("analyzer.clients.gpt_client.requests.post",
                   side_effect=_fake_post):
            if call == "simple":
                result = client.call_api_simple("提示词", **kwargs)
            else:
                result = client.call_api("system", "user", **kwargs)
        return captured, result

    def test_call_api_simple_omits_sampling(self):
        payload, _ = self._capture_payload("simple")
        for key in SAMPLING_KEYS:
            assert key not in payload, f"请求体不应含 {key}"

    def test_call_api_omits_sampling(self):
        payload, _ = self._capture_payload("full")
        for key in SAMPLING_KEYS:
            assert key not in payload, f"请求体不应含 {key}"

    def test_explicit_temperature_kwarg_ignored(self):
        payload, _ = self._capture_payload("simple", temperature=0.1)
        assert "temperature" not in payload

    def test_uses_max_completion_tokens(self):
        """GPT-5 推理系拒收 max_tokens，必须用 max_completion_tokens"""
        payload, _ = self._capture_payload("simple", max_tokens=6000)
        assert "max_tokens" not in payload, "旧参数 max_tokens 不应出现"
        assert payload.get("max_completion_tokens") == 6000

    def test_call_api_uses_max_completion_tokens(self):
        payload, _ = self._capture_payload("full", max_tokens=1234)
        assert "max_tokens" not in payload
        assert payload.get("max_completion_tokens") == 1234

    def test_response_parsing_unchanged(self):
        """choices[0].message.content 解析回归"""
        _, result = self._capture_payload("simple")
        assert result == "ok"


class TestGptSdkClient:
    def _client_with_capture(self):
        from analyzer.clients import gpt_client_sdk as mod
        if not getattr(mod, "OPENAI_SDK_AVAILABLE", True):
            pytest.skip("openai SDK 未安装")
        client = mod.GPTClientSDK("gpt-5.2", api_key="sk-test")
        fake_choice = MagicMock()
        fake_choice.message.content = "ok"
        fake_resp = MagicMock()
        fake_resp.choices = [fake_choice]
        client.client = MagicMock()
        client.client.chat.completions.create.return_value = fake_resp
        return client

    def _create_kwargs(self, client):
        return client.client.chat.completions.create.call_args.kwargs

    def test_sdk_simple_omits_sampling(self):
        client = self._client_with_capture()
        client.call_api_simple("提示词", temperature=0.1)
        kwargs = self._create_kwargs(client)
        for key in SAMPLING_KEYS:
            assert key not in kwargs, f"SDK 调用不应含 {key}"

    def test_sdk_call_api_omits_sampling(self):
        client = self._client_with_capture()
        client.call_api("system", "user")
        kwargs = self._create_kwargs(client)
        for key in SAMPLING_KEYS:
            assert key not in kwargs, f"SDK 调用不应含 {key}"

    def test_sdk_uses_max_completion_tokens(self):
        client = self._client_with_capture()
        client.call_api_simple("提示词", max_tokens=6000)
        kwargs = self._create_kwargs(client)
        assert "max_tokens" not in kwargs
        assert kwargs.get("max_completion_tokens") == 6000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
