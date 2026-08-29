"""Local-browser access boundary for the single-user career workspace."""

from __future__ import annotations

import ipaddress
import secrets
import time
from typing import Dict

from fastapi import Cookie, HTTPException, Request


WORKSPACE_COOKIE = "mako_workspace_session"
SESSION_TTL_SECONDS = 12 * 60 * 60
COMPOSE_NETWORK = ipaddress.ip_network("172.28.0.0/16")
COMPOSE_GATEWAY = COMPOSE_NETWORK.network_address + 1
_sessions: Dict[str, float] = {}


def _is_loopback(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def is_local_workspace_request(request: Request) -> bool:
    """Accept loopback clients and the fixed Compose proxy forwarding loopback."""
    client = request.client.host if request.client else ""
    if _is_loopback(client):
        return True
    try:
        proxy_ip = ipaddress.ip_address(client)
    except ValueError:
        return False
    if proxy_ip not in COMPOSE_NETWORK:
        return False
    forwarded = request.headers.get("x-real-ip", "").strip()
    try:
        forwarded_ip = ipaddress.ip_address(forwarded)
    except ValueError:
        return False
    return forwarded_ip.is_loopback or forwarded_ip == COMPOSE_GATEWAY


def create_workspace_session(request: Request) -> str:
    if not is_local_workspace_request(request):
        raise HTTPException(403, "求职工作区仅允许从本机访问")
    now = time.time()
    for token, expires_at in list(_sessions.items()):
        if expires_at <= now:
            _sessions.pop(token, None)
    token = secrets.token_urlsafe(32)
    _sessions[token] = now + SESSION_TTL_SECONDS
    return token


async def require_workspace_session(
    request: Request,
    mako_workspace_session: str | None = Cookie(default=None),
) -> None:
    if not is_local_workspace_request(request):
        raise HTTPException(403, "求职工作区仅允许从本机访问")
    if not mako_workspace_session:
        raise HTTPException(401, "求职工作区会话不存在")
    expires_at = _sessions.get(mako_workspace_session)
    if expires_at is None or expires_at <= time.time():
        _sessions.pop(mako_workspace_session, None)
        raise HTTPException(401, "求职工作区会话已过期")


def revoke_workspace_session(token: str | None) -> None:
    if token:
        _sessions.pop(token, None)
