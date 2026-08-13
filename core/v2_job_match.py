"""Validation and requirement-level matching for one approved Mako job version."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from core.v2_evidence import EvidenceRecord, JDRequirement, MatchDecision
from core.v2_matching import evaluate_requirement, term_present


class JobMatchBoundaryError(ValueError):
    """Raised when a supplied requirement is not grounded in the approved JD."""


def _normalize(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def _job_source_texts(job_version: Mapping[str, Any]) -> list[str]:
    payload = job_version.get("payload")
    if not isinstance(payload, Mapping):
        raise JobMatchBoundaryError("approved job version has no structured payload")
    texts: list[str] = []
    for field in ("responsibilities", "requirements"):
        value = payload.get(field)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            texts.extend(_normalize(item) for item in value if _normalize(item))
    description = _normalize(payload.get("description"))
    if description:
        texts.append(description)
    return texts


def validate_requirements_against_job(
    job_version: Mapping[str, Any],
    requirements: Iterable[JDRequirement],
) -> list[JDRequirement]:
    """Ensure every reviewed requirement is traceable to the approved payload."""
    version_id = str(job_version.get("job_version_id") or "")
    source_texts = _job_source_texts(job_version)
    if not source_texts:
        raise JobMatchBoundaryError("approved job version has no matchable JD text")

    validated: list[JDRequirement] = []
    seen = set()
    for requirement in requirements:
        if requirement.job_version_id != version_id:
            raise JobMatchBoundaryError("requirement references another job version")
        if requirement.requirement_id in seen:
            raise JobMatchBoundaryError("requirement_id is duplicated")
        seen.add(requirement.requirement_id)
        text = _normalize(requirement.text)
        if not any(text == source or text in source for source in source_texts):
            raise JobMatchBoundaryError("requirement text is not present in the approved JD")
        unsupported_terms = [
            term
            for term in requirement.normalized_terms
            if not term_present(term, text)
        ]
        if unsupported_terms:
            raise JobMatchBoundaryError(
                "normalized terms must be present in the requirement text"
            )
        validated.append(requirement)
    if not validated:
        raise JobMatchBoundaryError("at least one requirement is required")
    return validated


def match_approved_job(
    job_version: Mapping[str, Any],
    requirements: Iterable[JDRequirement],
    evidence_records: Iterable[EvidenceRecord],
) -> list[MatchDecision]:
    """Return deterministic decisions without persisting or mutating user facts."""
    validated = validate_requirements_against_job(job_version, requirements)
    evidence = list(evidence_records)
    return [evaluate_requirement(item, evidence) for item in validated]
