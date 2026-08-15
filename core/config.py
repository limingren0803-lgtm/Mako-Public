"""Configuration helpers for Mako environment variables."""
import os


def env_value(name: str, default: str) -> str:
    """Read a non-blank Mako environment variable or use its default."""
    return os.getenv(name, "").strip() or default


def env_int(name: str, default: int) -> int:
    """Read an integer Mako environment variable or use its default."""
    return int(env_value(name, str(default)))
