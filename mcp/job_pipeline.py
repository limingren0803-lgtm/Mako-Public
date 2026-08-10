"""Controlled ingestion pipeline for official job postings."""

from __future__ import annotations

from typing import Any, Dict, List

from prometheus_client import Counter

from mcp.job_adapters import JobAdapterContext, JobAdapterError, adapter_for_source
from mcp.knowledge_sources import SourceSecurityError, fetch_registered_source


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
) -> Dict[str, Any]:
    """Normalize and version one safely retrieved official page."""
    adapter = adapter_for_source(source["source_id"])
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
        result = registry.upsert_job_posting(posting)
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
    }


async def refresh_job_source(*, registry: Any, source_id: str) -> Dict[str, Any]:
    """Fetch one approved official source and ingest any structured postings it exposes."""
    source = registry.get_source(source_id)
    if not source:
        raise KeyError(source_id)
    if source["status"] != "active":
        raise SourceSecurityError("job source is not active")
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
        )
        rejected = isinstance(exc, (SourceSecurityError, JobAdapterError))
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
