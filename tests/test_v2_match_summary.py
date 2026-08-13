from __future__ import annotations

import unittest

from pydantic import ValidationError

from core.v2_evidence import (
    JDRequirement,
    MatchDecision,
    MatchStatus,
    RequirementCategory,
    RequirementExtractionStatus,
)
from core.v2_match_summary import (
    MatchSummary,
    pair_match_results,
    summarize_match_decisions,
)


def requirement(identifier: str = "requirement:1") -> JDRequirement:
    return JDRequirement(
        requirement_id=identifier,
        job_version_id="jobver_summary123",
        category=RequirementCategory.SKILL,
        text="熟悉 Python",
        normalized_terms=["python"],
        extraction_status=RequirementExtractionStatus.PARSED,
    )


def decision(
    status: MatchStatus,
    identifier: str = "requirement:1",
) -> MatchDecision:
    return MatchDecision(
        decision_id=f"match:{identifier.split(':')[-1]}:{status.value}",
        requirement_id=identifier,
        status=status,
        reason=f"状态为 {status.value}",
        confidence=1.0 if status in {MatchStatus.MET, MatchStatus.GAP} else 0.0,
    )


class MatchSummaryContractTests(unittest.TestCase):
    def test_summary_counts_every_status_without_a_composite_score(self):
        decisions = [
            decision(MatchStatus.MET, "requirement:met"),
            decision(MatchStatus.PARTIAL, "requirement:partial"),
            decision(MatchStatus.GAP, "requirement:gap"),
            decision(MatchStatus.UNKNOWN, "requirement:unknown"),
            decision(MatchStatus.NOT_APPLICABLE, "requirement:na"),
        ]
        summary = summarize_match_decisions(decisions)
        self.assertEqual(summary.total, 5)
        self.assertEqual(summary.met, 1)
        self.assertEqual(summary.partial, 1)
        self.assertEqual(summary.gap, 1)
        self.assertEqual(summary.unknown, 1)
        self.assertEqual(summary.not_applicable, 1)
        self.assertEqual(summary.requires_follow_up, 3)
        self.assertNotIn("score", summary.model_dump())
        self.assertNotIn("percentage", summary.model_dump())

    def test_ui_primary_states_keep_distinct_counts(self):
        summary = summarize_match_decisions(
            [
                decision(MatchStatus.MET, "requirement:met"),
                decision(MatchStatus.PARTIAL, "requirement:partial"),
                decision(MatchStatus.GAP, "requirement:gap"),
                decision(MatchStatus.UNKNOWN, "requirement:unknown"),
            ]
        )
        self.assertEqual(
            summary.model_dump(),
            {
                "total": 4,
                "met": 1,
                "partial": 1,
                "gap": 1,
                "unknown": 1,
                "not_applicable": 0,
                "requires_follow_up": 3,
            },
        )

    def test_empty_summary_is_valid_and_deterministic(self):
        summary = summarize_match_decisions([])
        self.assertEqual(summary.total, 0)
        self.assertEqual(summary.requires_follow_up, 0)

    def test_inconsistent_summary_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "counts must equal total"):
            MatchSummary(
                total=2,
                met=1,
                partial=0,
                gap=0,
                unknown=0,
                not_applicable=0,
                requires_follow_up=0,
            )
        with self.assertRaisesRegex(ValidationError, "unresolved decisions"):
            MatchSummary(
                total=1,
                met=0,
                partial=1,
                gap=0,
                unknown=0,
                not_applicable=0,
                requires_follow_up=0,
            )

    def test_result_pair_preserves_request_order(self):
        requirements = [
            requirement("requirement:first"),
            requirement("requirement:second"),
        ]
        decisions = [
            decision(MatchStatus.MET, "requirement:first"),
            decision(MatchStatus.UNKNOWN, "requirement:second"),
        ]
        items = pair_match_results(requirements, decisions)
        self.assertEqual(
            [item.requirement.requirement_id for item in items],
            ["requirement:first", "requirement:second"],
        )
        self.assertEqual(items[1].decision.status, MatchStatus.UNKNOWN)

    def test_result_pair_rejects_mismatched_identifiers(self):
        with self.assertRaisesRegex(ValidationError, "identifiers must match"):
            pair_match_results(
                [requirement("requirement:first")],
                [decision(MatchStatus.MET, "requirement:second")],
            )

    def test_result_pair_rejects_length_mismatch(self):
        with self.assertRaisesRegex(ValueError, "equal length"):
            pair_match_results([requirement()], [])


if __name__ == "__main__":
    unittest.main()
