"""Conservative deterministic requirement matching for Mako 2.0."""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

from core.v2_evidence import (
    EvidenceFactStatus,
    EvidenceRecord,
    EvidenceRelation,
    EvidenceStrength,
    JDRequirement,
    MatchDecision,
    MatchStatus,
    RequirementExtractionStatus,
)


def _decision_id(requirement_id: str, evidence_ids: Iterable[str]) -> str:
    payload = "\n".join([requirement_id, *sorted(evidence_ids)])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"match:{requirement_id}:{digest}"


def term_present(term: str, claim: str) -> bool:
    """Return whether one normalized term appears as a bounded claim term."""
    if term.isascii():
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
        return re.search(pattern, claim) is not None
    return term in claim


def _matching_terms(requirement: JDRequirement, evidence: EvidenceRecord) -> set[str]:
    claim = evidence.claim.casefold()
    return {term for term in requirement.normalized_terms if term_present(term, claim)}


def evaluate_requirement(
    requirement: JDRequirement,
    evidence_records: Iterable[EvidenceRecord],
    *,
    applicable: bool = True,
) -> MatchDecision:
    """Evaluate one reviewed requirement without inferring unsupported facts."""

    records = list(evidence_records)
    if len({evidence.user_id for evidence in records}) > 1:
        raise ValueError("evidence records must belong to one user")

    if not applicable:
        return MatchDecision(
            decision_id=_decision_id(requirement.requirement_id, []),
            requirement_id=requirement.requirement_id,
            status=MatchStatus.NOT_APPLICABLE,
            reason="该要求已由调用方明确标记为不适用。",
            confidence=1.0,
        )

    if requirement.extraction_status != RequirementExtractionStatus.PARSED:
        return MatchDecision(
            decision_id=_decision_id(requirement.requirement_id, []),
            requirement_id=requirement.requirement_id,
            status=MatchStatus.UNKNOWN,
            reason="该 JD 条目尚未完成结构化复核，暂不据此判断。",
            confidence=0.0,
            questions_to_confirm=["请先复核该 JD 条目的原文和分类。"],
        )

    if not requirement.normalized_terms:
        return MatchDecision(
            decision_id=_decision_id(requirement.requirement_id, []),
            requirement_id=requirement.requirement_id,
            status=MatchStatus.UNKNOWN,
            reason="该 JD 条目没有可用于确定性匹配的规范化词项。",
            confidence=0.0,
            questions_to_confirm=["请补充或复核该要求的关键条件。"],
        )

    matched = [
        (record, _matching_terms(requirement, record))
        for record in records
        if _matching_terms(requirement, record)
    ]
    evidence_ids = [record.evidence_id for record, _ in matched]
    direct_conflicts = [
        record
        for record, _ in matched
        if record.relation == EvidenceRelation.CONTRADICTS
        and record.fact_status == EvidenceFactStatus.CONFIRMED
        and record.strength == EvidenceStrength.DIRECT
    ]
    if direct_conflicts:
        ids = [record.evidence_id for record in direct_conflicts]
        return MatchDecision(
            decision_id=_decision_id(requirement.requirement_id, ids),
            requirement_id=requirement.requirement_id,
            status=MatchStatus.GAP,
            evidence_ids=ids,
            reason="已确认的直接证据与该要求存在冲突。",
            confidence=1.0,
        )

    confirmed_direct = [
        (record, terms)
        for record, terms in matched
        if record.relation == EvidenceRelation.SUPPORTS
        and record.fact_status == EvidenceFactStatus.CONFIRMED
        and record.strength == EvidenceStrength.DIRECT
    ]
    covered_terms = set().union(*(terms for _, terms in confirmed_direct)) if confirmed_direct else set()
    if covered_terms == set(requirement.normalized_terms):
        ids = [record.evidence_id for record, _ in confirmed_direct]
        return MatchDecision(
            decision_id=_decision_id(requirement.requirement_id, ids),
            requirement_id=requirement.requirement_id,
            status=MatchStatus.MET,
            evidence_ids=ids,
            reason="已确认的直接证据覆盖该要求的全部规范化条件。",
            confidence=1.0,
        )

    if matched:
        missing = [term for term in requirement.normalized_terms if term not in covered_terms]
        question = (
            f"请确认或补充以下条件的直接证据：{'、'.join(missing)}。"
            if missing
            else "请确认现有证据是否足以用于该岗位判断。"
        )
        return MatchDecision(
            decision_id=_decision_id(requirement.requirement_id, evidence_ids),
            requirement_id=requirement.requirement_id,
            status=MatchStatus.PARTIAL,
            evidence_ids=evidence_ids,
            reason="现有证据与该要求相关，但确认状态、证据强度或条件覆盖仍不完整。",
            confidence=0.5,
            questions_to_confirm=[question],
        )

    return MatchDecision(
        decision_id=_decision_id(requirement.requirement_id, []),
        requirement_id=requirement.requirement_id,
        status=MatchStatus.UNKNOWN,
        reason="当前没有与该要求直接关联的用户证据。",
        confidence=0.0,
        questions_to_confirm=["请补充相关经历、技能或资格信息。"],
    )
