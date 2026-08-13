from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from core.v2_evidence import (
    ConfirmationDecision,
    ConfirmationScope,
    EvidenceFactStatus,
    EvidenceRecord,
    EvidenceRelation,
    EvidenceStrength,
    EvidenceType,
    JDRequirement,
    MatchStatus,
    RequirementCategory,
    RequirementExtractionStatus,
    RequirementImportance,
    SourceSpan,
    UserConfirmation,
)
from core.v2_matching import evaluate_requirement


NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)


def evidence(**overrides: object) -> EvidenceRecord:
    payload = {
        "evidence_id": "evidence:python-project",
        "user_id": "student_1",
        "claim": "在课程项目中使用 Python 完成数据分析",
        "evidence_type": EvidenceType.PORTFOLIO,
        "fact_status": EvidenceFactStatus.CONFIRMED,
        "strength": EvidenceStrength.DIRECT,
        "captured_at": NOW,
        "verified_at": NOW,
    }
    payload.update(overrides)
    return EvidenceRecord(**payload)


def requirement(**overrides: object) -> JDRequirement:
    payload = {
        "requirement_id": "requirement:python-data",
        "job_version_id": "jobver_test123",
        "category": RequirementCategory.SKILL,
        "importance": RequirementImportance.REQUIRED,
        "text": "熟悉 Python 和数据分析",
        "normalized_terms": ["Python", "数据分析"],
        "extraction_status": RequirementExtractionStatus.PARSED,
        "source_span": SourceSpan(start=10, end=28),
    }
    payload.update(overrides)
    return JDRequirement(**payload)


class EvidenceContractTests(unittest.TestCase):
    def test_confirmed_evidence_requires_verification_time(self):
        with self.assertRaisesRegex(ValidationError, "requires verified_at"):
            evidence(verified_at=None)

    def test_verification_cannot_predate_capture(self):
        with self.assertRaisesRegex(ValidationError, "earlier than captured_at"):
            evidence(verified_at=NOW - timedelta(seconds=1))

    def test_evidence_timestamps_require_timezone(self):
        with self.assertRaisesRegex(ValidationError, "include a timezone"):
            evidence(captured_at=datetime(2026, 8, 12), verified_at=None)

    def test_identifiers_reject_path_like_values(self):
        with self.assertRaisesRegex(ValidationError, "unsupported characters"):
            evidence(evidence_id="../../resume")

    def test_request_scope_is_the_default_confirmation_scope(self):
        confirmation = UserConfirmation(
            confirmation_id="confirmation:1",
            user_id="student_1",
            object_type="evidence",
            object_id="evidence:python-project",
            decision=ConfirmationDecision.CONFIRM,
            request_id="request:1",
        )
        self.assertEqual(confirmation.scope, ConfirmationScope.REQUEST)

    def test_request_scope_requires_request_id(self):
        with self.assertRaisesRegex(ValidationError, "requires request_id"):
            UserConfirmation(
                confirmation_id="confirmation:1",
                user_id="student_1",
                object_type="evidence",
                object_id="evidence:python-project",
                decision=ConfirmationDecision.CONFIRM,
            )

    def test_correction_requires_a_value(self):
        with self.assertRaisesRegex(ValidationError, "requires corrected_value"):
            UserConfirmation(
                confirmation_id="confirmation:1",
                user_id="student_1",
                object_type="evidence",
                object_id="evidence:python-project",
                decision=ConfirmationDecision.CORRECT,
                request_id="request:1",
            )

    def test_non_correction_cannot_smuggle_a_replacement_value(self):
        with self.assertRaisesRegex(ValidationError, "only valid"):
            UserConfirmation(
                confirmation_id="confirmation:1",
                user_id="student_1",
                object_type="evidence",
                object_id="evidence:python-project",
                decision=ConfirmationDecision.CONFIRM,
                request_id="request:1",
                corrected_value="替换内容",
            )

    def test_requirement_terms_are_normalized_and_deduplicated(self):
        item = requirement(normalized_terms=[" Python ", "python", " 数据分析 "])
        self.assertEqual(item.normalized_terms, ["python", "数据分析"])

    def test_requirement_terms_have_a_size_limit(self):
        with self.assertRaisesRegex(ValidationError, "exceeds 200"):
            requirement(normalized_terms=["a" * 201])

    def test_source_span_must_be_ordered(self):
        with self.assertRaisesRegex(ValidationError, "greater than start"):
            SourceSpan(start=9, end=9)


class RequirementMatchingTests(unittest.TestCase):
    def test_confirmed_direct_evidence_covering_all_terms_is_met(self):
        decision = evaluate_requirement(requirement(), [evidence()])
        self.assertEqual(decision.status, MatchStatus.MET)
        self.assertEqual(decision.evidence_ids, ["evidence:python-project"])
        self.assertEqual(decision.confidence, 1.0)

    def test_unconfirmed_evidence_cannot_be_reported_as_met(self):
        decision = evaluate_requirement(
            requirement(),
            [
                evidence(
                    fact_status=EvidenceFactStatus.UNCONFIRMED,
                    verified_at=None,
                )
            ],
        )
        self.assertEqual(decision.status, MatchStatus.PARTIAL)
        self.assertTrue(decision.questions_to_confirm)

    def test_supporting_evidence_cannot_be_reported_as_met(self):
        decision = evaluate_requirement(
            requirement(),
            [evidence(strength=EvidenceStrength.SUPPORTING)],
        )
        self.assertEqual(decision.status, MatchStatus.PARTIAL)

    def test_ascii_terms_do_not_match_inside_other_words(self):
        decision = evaluate_requirement(
            requirement(
                text="熟悉 SQL",
                normalized_terms=["sql"],
            ),
            [evidence(claim="使用 NoSQL 数据库完成课程项目")],
        )
        self.assertEqual(decision.status, MatchStatus.UNKNOWN)

    def test_confirmed_direct_contradiction_is_a_gap(self):
        decision = evaluate_requirement(
            requirement(normalized_terms=["python"]),
            [
                evidence(
                    claim="用户确认没有 Python 使用经历",
                    relation=EvidenceRelation.CONTRADICTS,
                )
            ],
        )
        self.assertEqual(decision.status, MatchStatus.GAP)
        self.assertEqual(decision.confidence, 1.0)

    def test_missing_evidence_stays_unknown_instead_of_becoming_a_gap(self):
        decision = evaluate_requirement(requirement(), [])
        self.assertEqual(decision.status, MatchStatus.UNKNOWN)
        self.assertEqual(decision.evidence_ids, [])

    def test_unreviewed_requirement_is_not_matched(self):
        decision = evaluate_requirement(
            requirement(extraction_status=RequirementExtractionStatus.NEEDS_REVIEW),
            [evidence()],
        )
        self.assertEqual(decision.status, MatchStatus.UNKNOWN)
        self.assertEqual(decision.evidence_ids, [])

    def test_explicitly_inapplicable_requirement_is_preserved(self):
        decision = evaluate_requirement(requirement(), [evidence()], applicable=False)
        self.assertEqual(decision.status, MatchStatus.NOT_APPLICABLE)
        self.assertEqual(decision.confidence, 1.0)

    def test_evidence_from_multiple_users_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "one user"):
            evaluate_requirement(
                requirement(),
                [evidence(), evidence(evidence_id="evidence:2", user_id="student_2")],
            )

    def test_decision_id_is_stable_for_evidence_order(self):
        second = evidence(
            evidence_id="evidence:course",
            claim="Python 数据分析课程已完成",
        )
        first_decision = evaluate_requirement(requirement(), [evidence(), second])
        second_decision = evaluate_requirement(requirement(), [second, evidence()])
        self.assertEqual(first_decision.decision_id, second_decision.decision_id)


if __name__ == "__main__":
    unittest.main()
