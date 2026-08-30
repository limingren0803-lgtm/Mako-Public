"""Shared ChromaDB connection policy for Mako storage components."""
import logging
from typing import Any

import chromadb

logger = logging.getLogger(__name__)


def connect_chroma(
    *,
    host: str,
    port: int,
    local_path: str,
    allow_local_fallback: bool,
) -> tuple[Any, bool]:
    """Connect to the configured server without silently splitting persistent data."""
    try:
        client = chromadb.HttpClient(
            host=host,
            port=port,
            settings=chromadb.Settings(anonymized_telemetry=False),
        )
        client.heartbeat()
        logger.info("ChromaDB 已连接: %s:%s", host, port)
        return client, True
    except Exception as exc:
        if not allow_local_fallback:
            raise RuntimeError(
                "ChromaDB 服务不可用，已阻止本地降级以避免持久化数据分叉"
            ) from exc
        logger.warning(
            "ChromaDB 服务不可用，显式降级到本地目录: error_type=%s path=%s",
            type(exc).__name__,
            local_path,
        )
        return chromadb.PersistentClient(
            path=local_path,
            settings=chromadb.Settings(anonymized_telemetry=False),
        ), False
