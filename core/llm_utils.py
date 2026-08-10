"""LLM response helpers shared by Anthropic-compatible providers."""
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Tuple


TOKEN_LIMIT_REASONS = {"max_tokens", "length"}
INCOMPLETE_ENDINGS = ("，", "、", "：", "；", ":", ";", ",", "-", "/", "(", "[", "{")


@dataclass(frozen=True)
class TextCompletion:
    """Normalized text plus provider-independent completion metadata."""

    text: str
    stop_reason: Optional[str]
    complete: bool
    quality_flags: Tuple[str, ...] = ()
    continuation_used: bool = False


def extract_text_content(content: Iterable[Any]) -> str:
    """Return text blocks from Anthropic-style response content."""
    texts: List[str] = []
    for block in content or []:
        if isinstance(block, str):
            texts.append(block)
            continue

        block_type = getattr(block, "type", None)
        text = getattr(block, "text", None)
        if isinstance(block, dict):
            block_type = block.get("type", block_type)
            text = block.get("text", text)

        if isinstance(text, str) and (block_type in (None, "text")):
            texts.append(text)

    return "\n".join(t for t in texts if t)


def inspect_text_completion(text: str, stop_reason: Optional[str]) -> TextCompletion:
    """Detect strong signs that an LLM response ended before it was complete."""
    normalized_reason = str(stop_reason).strip().lower() if stop_reason else None
    stripped = text.rstrip()
    flags: List[str] = []

    if not stripped:
        flags.append("empty_response")
    if normalized_reason in TOKEN_LIMIT_REASONS:
        flags.append("token_limit")
    if stripped.count("```") % 2:
        flags.append("unclosed_code_fence")
    if stripped and stripped.endswith(INCOMPLETE_ENDINGS):
        flags.append("incomplete_ending")

    return TextCompletion(
        text=text,
        stop_reason=normalized_reason,
        complete=not flags,
        quality_flags=tuple(dict.fromkeys(flags)),
    )


def join_continuation(initial: str, continuation: str) -> str:
    """Join a continuation without changing the generated wording."""
    first = initial.rstrip()
    second = continuation.lstrip()
    if not first:
        return second
    if not second:
        return first
    separator = "" if first.endswith(("\n", " ")) else "\n"
    return f"{first}{separator}{second}"
