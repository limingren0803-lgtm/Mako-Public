"""Configuration helpers for Mako environment-variable migrations."""
import os
from typing import Optional


def env_with_legacy(primary: str, legacy: Optional[str], default: str) -> str:
    """Read the Mako variable first, then an optional legacy alias."""
    primary_value = os.getenv(primary, "").strip()
    if primary_value:
        return primary_value
    if legacy:
        legacy_value = os.getenv(legacy, "").strip()
        if legacy_value:
            return legacy_value
    return default


def env_int_with_legacy(primary: str, legacy: Optional[str], default: int) -> int:
    """Read an integer environment variable with a compatibility fallback."""
    return int(env_with_legacy(primary, legacy, str(default)))
