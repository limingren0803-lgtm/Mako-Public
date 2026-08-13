"""UI-ready, score-free summaries for Mako V2 requirement matching."""

from __future__ import annotations

from typing import Iterable, List

from pydantic import BaseModel, Field, model_validator

from core.v2_evidence import JDRequirement, MatchDecision, MatchStatus


class MatchSummary(BaseModel):
    """Exact status counts without reducing evidence to a composite score."""

    total: int = Field(ge=0)
    met: int = Field(ge=0)
    partial: int = Field(ge=0)
    gap: int = Field(ge=0)
    unknown: int = Field(ge=0)
    not_applicable: int = Field(ge=0)
    requires_follow_up: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_counts(self) -> "MatchSummary":
        classified = (
            self.met
            + self.partial
            + self.gap
            + self.unknown
            + self.not_applicable
        )
        if classified != self.total:
            raise ValueError("match summary counts must equal total")
        if self.requires_follow_up != self.partial + self.gap + self.unknown:
            raise ValueError("requires_follow_up must count unresolved decisions")
        return self


class RequirementMatchItem(BaseModel):
    """One reviewed requirement paired with its evidence-based decision."""

    requirement: JDRequirement
    decision: MatchDecision

    @model_validator(mode="after")
    def _validate_pair(self) -> "RequirementMatchItem":
        if self.requirement.requirement_id != self.decision.requirement_id:
            raise ValueError("requirement and decision identifiers must match")
        return self


def summarize_match_decisions(
    decisions: Iterable[MatchDecision],
) -> MatchSummary:
    items = list(decisions)
    counts = {status: 0 for status in MatchStatus}
    for decision in items:
        counts[decision.status] += 1
    return MatchSummary(
        total=len(items),
        met=counts[MatchStatus.MET],
        partial=counts[MatchStatus.PARTIAL],
        gap=counts[MatchStatus.GAP],
        unknown=counts[MatchStatus.UNKNOWN],
        not_applicable=counts[MatchStatus.NOT_APPLICABLE],
        requires_follow_up=(
            counts[MatchStatus.PARTIAL]
            + counts[MatchStatus.GAP]
            + counts[MatchStatus.UNKNOWN]
        ),
    )


def pair_match_results(
    requirements: Iterable[JDRequirement],
    decisions: Iterable[MatchDecision],
) -> List[RequirementMatchItem]:
    reviewed = list(requirements)
    evaluated = list(decisions)
    if len(reviewed) != len(evaluated):
        raise ValueError("requirements and decisions must have equal length")
    return [
        RequirementMatchItem(requirement=requirement, decision=decision)
        for requirement, decision in zip(reviewed, evaluated)
    ]
