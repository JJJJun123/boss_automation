#!/usr/bin/env python3
"""BYOK API Key 加密、掩码与有效性验证。"""

import os
from typing import Dict, Tuple

import requests
from cryptography.fernet import Fernet, InvalidToken


class KeyVaultError(RuntimeError):
    """加密密钥缺失、格式错误或密文无法解密。"""


class KeyValidationTimeout(TimeoutError):
    """Provider 验证端点未在时限内响应；不代表 API Key 无效。"""


_PROVIDER_ENDPOINTS: Dict[str, Tuple[str, str]] = {
    "deepseek": ("https://api.deepseek.com/models", "bearer"),
    "gpt": ("https://api.openai.com/v1/models", "bearer"),
    "claude": ("https://api.anthropic.com/v1/models", "anthropic"),
}


def load_encryption_key() -> bytes:
    """每次从环境变量加载 Fernet key，不缓存，支持安全轮换。"""
    raw = os.environ.get("APP_ENCRYPTION_KEY", "").strip()
    if not raw:
        raise KeyVaultError("APP_ENCRYPTION_KEY 环境变量未设置")
    try:
        key = raw.encode("ascii")
        Fernet(key)
        return key
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise KeyVaultError("APP_ENCRYPTION_KEY 不是合法的 Fernet key") from exc


def encrypt_key(plain: str) -> str:
    """加密 API Key，返回可安全写入 SQLite 的文本 token。"""
    try:
        return Fernet(load_encryption_key()).encrypt(plain.encode("utf-8")).decode("ascii")
    except KeyVaultError:
        raise
    except Exception as exc:
        raise KeyVaultError("API Key 加密失败") from exc


def decrypt_key(token: str) -> str:
    """解密 API Key；密钥轮换、数据损坏或篡改统一抛 KeyVaultError。"""
    try:
        return Fernet(load_encryption_key()).decrypt(token.encode("ascii")).decode("utf-8")
    except KeyVaultError:
        raise
    except (InvalidToken, ValueError, TypeError, UnicodeError) as exc:
        raise KeyVaultError("API Key 密文无法解密") from exc


def mask_key(plain: str) -> str:
    """只显示足够长 Key 的前缀类别和最后四位；短 Key 完全隐藏。"""
    if not plain or len(plain) < 8:
        return "***"
    prefix = "sk-" if plain.startswith("sk-") else ""
    return f"{prefix}***{plain[-4:]}"


def validate_api_key(provider: str, key: str, *, raise_on_timeout: bool = False) -> bool:
    """调用 provider 的 models 端点验证 Key。

    默认保持原有布尔契约：超时和网络错误都返回 False。交互式保存接口可传
    ``raise_on_timeout=True``，从而给用户明确的可重试提示，而不是误报 Key 无效。
    """
    normalized = (provider or "").strip().lower()
    if normalized not in _PROVIDER_ENDPOINTS:
        raise ValueError(f"不支持的 AI provider: {provider}")

    url, auth_type = _PROVIDER_ENDPOINTS[normalized]
    if auth_type == "anthropic":
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        }
    else:
        headers = {"Authorization": f"Bearer {key}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.status_code == 200
    except requests.exceptions.Timeout as exc:
        if raise_on_timeout:
            raise KeyValidationTimeout("API Key 验证请求超时") from exc
        return False
    except requests.exceptions.RequestException:
        return False
