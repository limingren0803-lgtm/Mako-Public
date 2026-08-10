"""Deterministic lexical ranking for locally stored official job postings."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping


_ASCII_WORD = re.compile(r"[a-z0-9+#.]{2,}", re.IGNORECASE)
_CJK_RUN = re.compile(r"[\u3400-\u9fff]+")
_QUERY_STOP_TOKENS = {
    "哪些",
    "什么",
    "岗位",
    "职位",
    "招聘",
    "推荐",
    "现在",
    "目前",
    "有没有",
}


def _tokens(value: Any) -> set[str]:
    text = str(value or "").casefold()
    result = set(_ASCII_WORD.findall(text))
    for run in _CJK_RUN.findall(text):
        if 2 <= len(run) <= 6:
            result.add(run)
        result.update(run[index : index + 2] for index in range(len(run) - 1))
    return {token for token in result if token not in _QUERY_STOP_TOKENS}


def _flatten(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item) for item in value)
    return str(value or "")


def _not_expired(job: Mapping[str, Any], now: datetime) -> bool:
    value = job.get("expires_at")
    if not value:
        payload = job.get("payload")
        if isinstance(payload, dict):
            value = payload.get("valid_through")
    if not value:
        return True
    try:
        expires_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > now


def rank_job_postings(
    query: str,
    jobs: Iterable[Mapping[str, Any]],
    *,
    limit: int = 5,
    now: datetime | None = None,
) -> List[Dict[str, Any]]:
    """Rank active, non-expired postings without calling an external model."""
    query_tokens = _tokens(query)
    if not query_tokens:
        return []
    now = now or datetime.now(timezone.utc)
    ranked: List[tuple[float, str, Dict[str, Any]]] = []
    for raw_job in jobs:
        job = dict(raw_job)
        if job.get("status") != "active" or not _not_expired(job, now):
            continue
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        fields = (
            (payload.get("company_name") or job.get("company_name"), 6.0),
            (payload.get("title") or job.get("title"), 5.0),
            (payload.get("job_category"), 3.0),
            (payload.get("department"), 2.5),
            (_flatten(payload.get("locations")), 3.0),
            (_flatten(payload.get("responsibilities")), 1.2),
            (_flatten(payload.get("requirements")), 1.0),
        )
        score = 0.0
        for value, weight in fields:
            score += len(query_tokens.intersection(_tokens(value))) * weight
        company = str(payload.get("company_name") or job.get("company_name") or "")
        title = str(payload.get("title") or job.get("title") or "")
        if company and company.casefold() in query.casefold():
            score += 8.0
        if title and title.casefold() in query.casefold():
            score += 10.0
        if score <= 0:
            continue
        freshness = str(
            payload.get("source_updated_at")
            or payload.get("published_at")
            or job.get("last_seen_at")
            or ""
        )
        job["match_score"] = round(score, 3)
        ranked.append((score, freshness, job))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in ranked[: min(max(limit, 1), 20)]]
