#!/usr/bin/env python3
"""backend/key_vault.py 测试 — BYOK 加密存储与 Key 验证

覆盖：
- Fernet 加解密 roundtrip / 篡改检测
- mask_key 掩码格式
- APP_ENCRYPTION_KEY 缺失 fail-fast
- validate_api_key 三家 provider 的验证调用（mock requests）
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 测试用固定加密密钥（Fernet 要求 32 字节 urlsafe base64）
TEST_ENC_KEY = "t3stk3y_" + "a" * 35 + "="


@pytest.fixture(autouse=True)
def _enc_key_env(monkeypatch):
    """默认注入合法 APP_ENCRYPTION_KEY；fail-fast 测试内部自行删除"""
    from cryptography.fernet import Fernet
    monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    # key_vault 若做模块级缓存，需要每次重置
    import importlib
    import backend.key_vault as kv
    importlib.reload(kv)
    yield


# ─── 加解密 ─────────────────────────────────────────────


class TestEncryptDecrypt:
    def test_roundtrip(self):
        from backend.key_vault import encrypt_key, decrypt_key
        plain = "sk-abcdef1234567890"
        token = encrypt_key(plain)
        assert token != plain
        assert decrypt_key(token) == plain

    def test_different_plaintexts_different_ciphertexts(self):
        from backend.key_vault import encrypt_key
        assert encrypt_key("sk-aaa") != encrypt_key("sk-bbb")

    def test_tampered_ciphertext_raises(self):
        from backend.key_vault import encrypt_key, decrypt_key, KeyVaultError
        token = encrypt_key("sk-abcdef1234567890")
        tampered = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
        with pytest.raises(KeyVaultError):
            decrypt_key(tampered)

    def test_decrypt_with_wrong_key_raises(self, monkeypatch):
        """APP_ENCRYPTION_KEY 轮换后旧密文解不开 → KeyVaultError（上层视为无 Key）"""
        from cryptography.fernet import Fernet
        import importlib
        import backend.key_vault as kv

        token = kv.encrypt_key("sk-abcdef1234567890")
        monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
        importlib.reload(kv)
        with pytest.raises(kv.KeyVaultError):
            kv.decrypt_key(token)


# ─── 掩码 ───────────────────────────────────────────────


class TestMaskKey:
    def test_mask_shows_only_last4(self):
        from backend.key_vault import mask_key
        masked = mask_key("sk-abcdef1234567890ab12")
        assert masked.endswith("ab12")
        assert "abcdef" not in masked
        assert "***" in masked

    def test_short_key_fully_masked(self):
        """短于 8 位的 key 不能露任何字符"""
        from backend.key_vault import mask_key
        masked = mask_key("sk-ab")
        assert "sk-ab"[-2:] not in masked or masked == "***"
        assert "ab" not in masked.replace("***", "")

    def test_empty_key(self):
        from backend.key_vault import mask_key
        assert mask_key("") == "***"


# ─── fail-fast ──────────────────────────────────────────


class TestEncryptionKeyMissing:
    def test_missing_env_raises(self, monkeypatch):
        monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
        import importlib
        import backend.key_vault as kv
        importlib.reload(kv)
        with pytest.raises(kv.KeyVaultError):
            kv.encrypt_key("sk-xxx")

    def test_invalid_format_raises(self, monkeypatch):
        """APP_ENCRYPTION_KEY 不是合法 Fernet key → 明确报错而非隐晦崩溃"""
        monkeypatch.setenv("APP_ENCRYPTION_KEY", "not-a-valid-fernet-key")
        import importlib
        import backend.key_vault as kv
        importlib.reload(kv)
        with pytest.raises(kv.KeyVaultError):
            kv.encrypt_key("sk-xxx")


# ─── Key 验证调用 ────────────────────────────────────────


class TestValidateApiKey:
    def _mock_response(self, status_code):
        resp = MagicMock()
        resp.status_code = status_code
        return resp

    def test_deepseek_valid(self):
        from backend.key_vault import validate_api_key
        with patch("backend.key_vault.requests.get") as mget:
            mget.return_value = self._mock_response(200)
            assert validate_api_key("deepseek", "sk-valid") is True
            url = mget.call_args[0][0]
            assert "api.deepseek.com" in url
            headers = mget.call_args[1]["headers"]
            assert headers.get("Authorization") == "Bearer sk-valid"

    def test_gpt_valid(self):
        from backend.key_vault import validate_api_key
        with patch("backend.key_vault.requests.get") as mget:
            mget.return_value = self._mock_response(200)
            assert validate_api_key("gpt", "sk-valid") is True
            assert "api.openai.com" in mget.call_args[0][0]

    def test_claude_uses_x_api_key_header(self):
        from backend.key_vault import validate_api_key
        with patch("backend.key_vault.requests.get") as mget:
            mget.return_value = self._mock_response(200)
            assert validate_api_key("claude", "sk-ant-valid") is True
            assert "api.anthropic.com" in mget.call_args[0][0]
            headers = mget.call_args[1]["headers"]
            assert headers.get("x-api-key") == "sk-ant-valid"
            assert "anthropic-version" in headers

    def test_invalid_key_401(self):
        from backend.key_vault import validate_api_key
        with patch("backend.key_vault.requests.get") as mget:
            mget.return_value = self._mock_response(401)
            assert validate_api_key("deepseek", "sk-bad") is False

    def test_timeout_returns_false(self):
        import requests as _requests
        from backend.key_vault import validate_api_key
        with patch("backend.key_vault.requests.get",
                   side_effect=_requests.exceptions.Timeout):
            assert validate_api_key("deepseek", "sk-any") is False

    def test_network_error_returns_false(self):
        import requests as _requests
        from backend.key_vault import validate_api_key
        with patch("backend.key_vault.requests.get",
                   side_effect=_requests.exceptions.ConnectionError):
            assert validate_api_key("deepseek", "sk-any") is False

    def test_unknown_provider_raises(self):
        from backend.key_vault import validate_api_key
        with pytest.raises(ValueError):
            validate_api_key("gemini", "sk-any")

    def test_timeout_param_set(self):
        """验证调用必须带超时（防挂死任务线程）"""
        from backend.key_vault import validate_api_key
        with patch("backend.key_vault.requests.get") as mget:
            mget.return_value = self._mock_response(200)
            validate_api_key("deepseek", "sk-valid")
            assert mget.call_args[1].get("timeout") is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
