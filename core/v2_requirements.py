"""Deterministic extraction and review transitions for approved Mako JDs."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from core.v2_evidence import (
    JDRequirement,
    JDRequirementReview,
    RequirementCategory,
    RequirementExtractionStatus,
    RequirementReviewDecision,
    RequirementSourceField,
)
from core.v2_matching import term_present


class RequirementReviewError(ValueError):
    """Raised when a requirement draft or review crosses the JD boundary."""


def _normalize(value: object) -> str:
    return " ".join(str(value or "").split())


def _requirement_id(
    job_version_id: str,
    source_field: RequirementSourceField,
    source_index: int,
    text: str,
) -> str:
    payload = f"{job_version_id}\n{source_field.value}\n{source_index}\n{text}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"requirement:{digest}"


def extract_requirement_drafts(job_version: Mapping[str, Any]) -> list[JDRequirement]:
    """Create stable review-required drafts from structured JD list fields."""
    version_id = str(job_version.get("job_version_id") or "")
    payload = job_version.get("payload")
    if not version_id or not isinstance(payload, Mapping):
        raise RequirementReviewError("approved job version has no structured payload")

    drafts: list[JDRequirement] = []
    fields = (
        (RequirementSourceField.REQUIREMENTS, RequirementCategory.OTHER),
        (RequirementSourceField.RESPONSIBILITIES, RequirementCategory.RESPONSIBILITY),
    )
    for source_field, category in fields:
        values = payload.get(source_field.value)
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            continue
        for source_index, value in enumerate(values):
            text = _normalize(value)
            if not text:
                continue
            drafts.append(
                JDRequirement(
                    requirement_id=_requirement_id(
                        version_id,
                        source_field,
                        source_index,
                        text,
                    ),
                    job_version_id=version_id,
                    category=category,
                    text=text,
                    extraction_status=RequirementExtractionStatus.NEEDS_REVIEW,
                    source_field=source_field,
                    source_index=source_index,
                )
            )
    if not drafts:
        raise RequirementReviewError("approved job version has no structured requirements")
    return drafts


def apply_requirement_review(
    draft: JDRequirement,
    review: JDRequirementReview,
) -> JDRequirement:
    """Return the reviewed state while retaining the immutable source location."""
    if draft.requirement_id != review.requirement_id:
        raise RequirementReviewError("review references another requirement")
    if draft.job_version_id != review.job_version_id:
        raise RequirementReviewError("review references another job version")
    if draft.extraction_status != RequirementExtractionStatus.NEEDS_REVIEW:
        raise RequirementReviewError("only extracted drafts can be reviewed")

    if review.decision == RequirementReviewDecision.REJECT:
        return draft.model_copy(
            update={"extraction_status": RequirementExtractionStatus.REJECTED}
        )

    text = review.corrected_text or draft.text
    normalized_source = draft.text.casefold()
    if text.casefold() not in normalized_source:
        raise RequirementReviewError("corrected text must remain traceable to the JD source")
    unsupported_terms = [
        term for term in review.normalized_terms if not term_present(term, text.casefold())
    ]
    if unsupported_terms:
        raise RequirementReviewError("normalized terms must be present in the reviewed text")
    return draft.model_copy(
        update={
            "category": review.category,
            "importance": review.importance,
            "text": text,
            "normalized_terms": review.normalized_terms,
            "extraction_status": RequirementExtractionStatus.PARSED,
        }
    )
