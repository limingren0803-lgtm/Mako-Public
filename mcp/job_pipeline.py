"""Controlled ingestion pipeline for official job postings."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from prometheus_client import Counter

from core.job_posting import JobPosting
from mcp.job_adapters import JobAdapterContext, JobAdapterError, adapter_for_source
from mcp.knowledge_sources import (
    SourceSecurityError,
    fetch_registered_source,
    find_instruction_injection,
    validate_source_url,
)


JOB_REFRESH_TOTAL = Counter(
    "mako_job_refresh_total",
    "Official job refresh attempts",
    ("source_id", "outcome"),
)
JOB_POSTINGS_INGESTED_TOTAL = Counter(
    "mako_job_postings_ingested_total",
    "Normalized official job postings ingested",
    ("source_id", "result"),
)


def ingest_job_html(
    *,
    registry: Any,
    source: Dict[str, Any],
    html: str,
    source_url: str,
    review_status: str = "approved",
) -> Dict[str, Any]:
    """Normalize and version one safely retrieved official page."""
    adapter = adapter_for_source(source["source_id"], allow_generic=True)
    context = JobAdapterContext(
        source_id=source["source_id"],
        company_name=source["company_name"],
        official_domain=source["official_domain"],
        delegated_domains=tuple(source.get("delegated_domains", [])),
    )
    page = adapter.parse_page(
        html=html,
        source_url=source_url,
        context=context,
    )
    if not page.postings and page.total is None:
        raise JobAdapterError("official page did not expose supported structured job data")
    changed = 0
    unchanged = 0
    job_ids: List[str] = []
    for posting in page.postings:
        result = registry.upsert_job_posting(posting, review_status=review_status)
        job_ids.append(result["job_id"])
        if result["changed"]:
            changed += 1
            JOB_POSTINGS_INGESTED_TOTAL.labels(source["source_id"], "changed").inc()
        else:
            unchanged += 1
            JOB_POSTINGS_INGESTED_TOTAL.labels(source["source_id"], "unchanged").inc()
    expired = registry.expire_job_postings()
    return {
        "source_id": source["source_id"],
        "discovered": len(page.postings),
        "changed": changed,
        "unchanged": unchanged,
        "expired": expired,
        "job_ids": job_ids,
        "page_number": page.page_number,
        "page_size": page.page_size,
        "total": page.total,
        "complete_snapshot": page.complete_snapshot,
        "review_status": review_status,
    }


def _active_source(registry: Any, source_id: str) -> Dict[str, Any]:
    source = registry.get_source(source_id)
    if not source:
        raise KeyError(source_id)
    if source["status"] != "active":
        raise SourceSecurityError("job source is not active")
    return source


def _assert_import_enabled(source: Dict[str, Any]) -> None:
    if source.get("support_level") == "official_directory":
        raise SourceSecurityError("job import is not enabled for this directory-only source")


def import_job_posting(
    *,
    registry: Any,
    source_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Store one operator-supplied JD after source and content validation."""
    source = _active_source(registry, source_id)
    _assert_import_enabled(source)
    source_url = str(payload.get("source_url") or "").strip()
    allowed_domains = [source["official_domain"], *source.get("delegated_domains", [])]
    validate_source_url(source_url, allowed_domains)

    data = dict(payload)
    data["source_id"] = source_id
    data["company_name"] = source["company_name"]
    if not data.get("external_id"):
        seed = f"{source_url}\n{data.get('title', '')}"
        data["external_id"] = f"manual-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24]}"
    posting = JobPosting.model_validate(data)
    flags = find_instruction_injection(posting.to_search_text())
    if flags:
        raise SourceSecurityError(
            "job content failed instruction isolation checks: " + ",".join(flags)
        )

    result = registry.upsert_job_posting(posting, review_status="pending")
    outcome = "changed" if result["changed"] else "unchanged"
    JOB_POSTINGS_INGESTED_TOTAL.labels(source_id, outcome).inc()
    registry.record_event(
        "job_manual_import",
        "job_posting",
        result["job_id"],
        "success",
        {"source_id": source_id, "result": outcome},
    )
    return {
        **result,
        "source_id": source_id,
        "import_method": "structured_manual",
    }


async def import_job_url(
    *,
    registry: Any,
    source_id: str,
    source_url: str,
) -> Dict[str, Any]:
    """Fetch one operator-selected official page and ingest supported structured data."""
    source = _active_source(registry, source_id)
    _assert_import_enabled(source)
    allowed_domains = [source["official_domain"], *source.get("delegated_domains", [])]
    validate_source_url(source_url, allowed_domains)
    fetch_source = dict(source)
    fetch_source["source_url"] = source_url
    try:
        fetched = await fetch_registered_source(fetch_source)
        if not fetched.content_type.startswith("text/html"):
            raise SourceSecurityError("job import requires an official HTML page")
        result = ingest_job_html(
            registry=registry,
            source=source,
            html=fetched.raw_content,
            source_url=fetched.final_url,
            review_status="pending",
        )
        registry.update_source_health(source_id, "success")
        registry.record_event(
            "job_url_import",
            "source",
            source_id,
            "success",
            {
                "discovered": result["discovered"],
                "changed": result["changed"],
                "unchanged": result["unchanged"],
            },
        )
        return {**result, "import_method": "official_url", "source_url": fetched.final_url}
    except Exception as exc:
        rejected = isinstance(exc, (SourceSecurityError, JobAdapterError))
        registry.update_source_health(
            source_id,
            "rejected" if rejected else "failed",
            error_type=type(exc).__name__,
        )
        registry.record_event(
            "job_url_import",
            "source",
            source_id,
            "rejected" if rejected else "failed",
            {"error_type": type(exc).__name__},
        )
        raise


async def refresh_job_source(*, registry: Any, source_id: str) -> Dict[str, Any]:
    """Fetch one approved official source and ingest any structured postings it exposes."""
    source = _active_source(registry, source_id)
    if source["refresh_policy"] != "manual" or not source["automation_allowed"]:
        raise SourceSecurityError("automated job retrieval is not approved for this source")

    try:
        fetch_source = dict(source)
        fetch_source["source_url"] = source.get("job_source_url") or source["source_url"]
        fetched = await fetch_registered_source(fetch_source)
        if not fetched.content_type.startswith("text/html"):
            raise SourceSecurityError("job adapter requires an official HTML page")
        result = ingest_job_html(
            registry=registry,
            source=source,
            html=fetched.raw_content,
            source_url=fetched.final_url,
            review_status="pending",
        )
        registry.update_source_health(source_id, "success")
        registry.record_event(
            "job_source_refresh",
            "source",
            source_id,
            "success",
            {
                "discovered": result["discovered"],
                "changed": result["changed"],
                "unchanged": result["unchanged"],
                "expired": result["expired"],
            },
        )
        JOB_REFRESH_TOTAL.labels(source_id, "success").inc()
        return result
    except Exception as exc:
        rejected = isinstance(exc, (SourceSecurityError, JobAdapterError))
        registry.update_source_health(
            source_id,
            "rejected" if rejected else "failed",
            error_type=type(exc).__name__,
        )
        registry.record_event(
            "job_source_refresh",
            "source",
            source_id,
            "rejected" if rejected else "failed",
            {"error_type": type(exc).__name__},
        )
        JOB_REFRESH_TOTAL.labels(
            source_id,
            "rejected" if rejected else "failed",
        ).inc()
        raise


async def run_job_refresh_task(*, registry: Any, task_id: str) -> Dict[str, Any]:
    """Run one explicitly claimed persistent task in the current process."""
    task = registry.claim_job_refresh_task(task_id)
    try:
        if task["task_type"] == "managed_refresh":
            result = await refresh_job_source(registry=registry, source_id=task["source_id"])
        elif task["task_type"] == "url_import":
            result = await import_job_url(
                registry=registry,
                source_id=task["source_id"],
                source_url=task["source_url"],
            )
        else:
            raise ValueError("unsupported job refresh task type")
        return registry.complete_job_refresh_task(
            task_id, outcome="succeeded", result_summary=result
        )
    except Exception as exc:
        rejected = isinstance(exc, (SourceSecurityError, JobAdapterError))
        registry.complete_job_refresh_task(
            task_id,
            outcome="rejected" if rejected else "failed",
            error_type=type(exc).__name__,
        )
        raise
