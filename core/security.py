"""HTTP 边界使用的安全配置与校验工具。"""

import os
import secrets
import threading
import time
import unicodedata
from collections import deque
from typing import Optional
from urllib.parse import urlparse

from fastapi import Header, HTTPException


# 简单的 in-process 速率限制（按 IP 对管理接口做保护）
_admin_attempts_lock = threading.Lock()
_admin_attempts: deque = deque()  # 时间戳队列
_ADMIN_RATE_LIMIT = {"window_s": 60, "max_attempts": 10}


DEFAULT_CORS_ORIGINS = (
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def env_bool(name: str, default: bool = False) -> bool:
    """读取常见布尔环境变量写法。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def cors_origins() -> list[str]:
    """返回允许跨域访问 API 的显式来源列表。

    校验每个 origin 的协议必须是 http 或 https，防止
    MAKO_CORS_ALLOW_ORIGINS 中混入 file://、data:// 等危险协议。
    """
    raw = os.getenv("MAKO_CORS_ALLOW_ORIGINS", "").strip()
    if not raw:
        return list(DEFAULT_CORS_ORIGINS)
    result = []
    for origin in raw.split(","):
        origin = origin.strip()
        if not origin:
            continue
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        result.append(origin)
    return result or list(DEFAULT_CORS_ORIGINS)


def validate_identifier(value: str, field_name: str) -> str:
    """拒绝可能污染存储键、路径或日志的空白及控制字符标识。"""
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} 不能为空")
    if len(value) > 128:
        raise ValueError(f"{field_name} 不能超过 128 个字符")
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError(f"{field_name} 不能包含控制字符")
    return value


async def require_admin_key(
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> None:
    """保护调试、管理和高成本接口；未配置时保持关闭。"""
    now = time.time()
    with _admin_attempts_lock:
        cutoff = now - _ADMIN_RATE_LIMIT["window_s"]
        while _admin_attempts and _admin_attempts[0] < cutoff:
            _admin_attempts.popleft()
        if len(_admin_attempts) >= _ADMIN_RATE_LIMIT["max_attempts"]:
            raise HTTPException(status_code=429, detail="管理接口请求过于频繁")
        _admin_attempts.append(now)
    expected = os.getenv("MAKO_ADMIN_API_KEY", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="管理接口未启用，请配置 MAKO_ADMIN_API_KEY",
        )
    if len(expected) < 32:
        raise HTTPException(
            status_code=503,
            detail="MAKO_ADMIN_API_KEY 至少需要 32 个字符",
        )
    if not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(status_code=401, detail="无效的管理密钥")
