from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import main as api_main
from core.job_posting import JobPosting, RecruitmentType
from core.v2_evidence import (
    EvidenceFactStatus,
    EvidenceRecord,
    EvidenceStrength,
    EvidenceType,
    JDRequirement,
    JDRequirementReview,
    MatchStatus,
    RequirementCategory,
    RequirementExtractionStatus,
    RequirementImportance,
    RequirementReviewDecision,
)
from core.v2_evidence_registry import EvidenceRegistry
from core.v2_job_match import JobMatchBoundaryError, match_approved_job
from core.v2_requirements import extract_requirement_drafts
from mcp.knowledge_registry import KnowledgeRegistry


NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)
AS_OF = "2026-08-12T12:00:00+00:00"


def posting(**overrides: object) -> JobPosting:
    payload = {
        "source_id": "src_test_company",
        "external_id": "role-1",
        "company_name": "测试企业",
        "title": "数据分析实习生",
        "recruitment_type": RecruitmentType.INTERNSHIP,
        "locations": ["上海"],
        "responsibilities": ["使用 Python 完成业务数据分析"],
        "requirements": ["熟悉 Python 和 SQL"],
        "description": "面向应届生和留学生的实习岗位",
        "source_url": "https://careers.example.com/jobs/role-1",
        "fetched_at": NOW,
    }
    payload.update(overrides)
    return JobPosting(**payload)


def requirement(version_id: str, **overrides: object) -> JDRequirement:
    payload = {
        "requirement_id": "requirement:python-sql",
        "job_version_id": version_id,
        "category": RequirementCategory.SKILL,
        "importance": RequirementImportance.REQUIRED,
        "text": "熟悉 Python 和 SQL",
        "normalized_terms": ["python", "sql"],
        "extraction_status": RequirementExtractionStatus.PARSED,
    }
    payload.update(overrides)
    return JDRequirement(**payload)


def evidence(**overrides: object) -> EvidenceRecord:
    payload = {
        "evidence_id": "evidence:python-sql",
        "user_id": "留学生_1",
        "claim": "课程项目使用 Python 和 SQL 完成数据分析",
        "evidence_type": EvidenceType.PORTFOLIO,
        "fact_status": EvidenceFactStatus.CONFIRMED,
        "strength": EvidenceStrength.DIRECT,
        "captured_at": NOW,
        "verified_at": NOW,
    }
    payload.update(overrides)
    return EvidenceRecord(**payload)


class ApprovedJobVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.registry = KnowledgeRegistry(os.path.join(self.temp_dir.name, "jobs.sqlite3"))
        self.registry.register_source(
            source_id="src_test_company",
            company_name="测试企业",
            official_domain="careers.example.com",
            source_url="https://careers.example.com",
            job_source_url="https://careers.example.com/jobs",
            support_level="structured_import",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_current_approved_version_is_returned(self):
        result = self.registry.upsert_job_posting(posting(), review_status="approved")
        version_id = result["submitted_version_id"]
        current = self.registry.get_current_approved_job_version(
            job_id=result["job_id"], version_id=version_id, as_of=AS_OF
        )
        self.assertIsNotNone(current)
        self.assertEqual(current["job_version_id"], version_id)
        self.assertEqual(current["review_status"], "approved")

    def test_pending_version_is_never_returned(self):
        result = self.registry.upsert_job_posting(posting(), review_status="pending")
        current = self.registry.get_current_approved_job_version(
            job_id=result["job_id"], version_id=result["submitted_version_id"], as_of=AS_OF
        )
        self.assertIsNone(current)

    def test_superseded_version_is_never_returned(self):
        first = self.registry.upsert_job_posting(posting(), review_status="approved")
        second = self.registry.upsert_job_posting(
            posting(title="高级数据分析实习生"), review_status="approved"
        )
        old = self.registry.get_current_approved_job_version(
            job_id=first["job_id"], version_id=first["submitted_version_id"], as_of=AS_OF
        )
        current = self.registry.get_current_approved_job_version(
            job_id=second["job_id"], version_id=second["submitted_version_id"], as_of=AS_OF
        )
        self.assertIsNone(old)
        self.assertIsNotNone(current)

    def test_expired_current_version_is_never_returned(self):
        result = self.registry.upsert_job_posting(
            posting(valid_through=datetime(2025, 1, 1, tzinfo=timezone.utc)),
            review_status="approved",
        )
        current = self.registry.get_current_approved_job_version(
            job_id=result["job_id"], version_id=result["submitted_version_id"], as_of=AS_OF
        )
        self.assertIsNone(current)

    def test_version_outside_user_age_window_is_never_returned(self):
        result = self.registry.upsert_job_posting(posting(), review_status="approved")
        current = self.registry.get_current_approved_job_version(
            job_id=result["job_id"],
            version_id=result["submitted_version_id"],
            max_age_days=1,
            as_of="2026-08-14T12:00:00+00:00",
        )
        self.assertIsNone(current)


class JobMatchBoundaryTests(unittest.TestCase):
    def job_version(self) -> dict:
        return {
            "job_version_id": "jobver_test123",
            "payload": posting().model_dump(mode="json"),
        }

    def test_grounded_requirement_can_be_matched(self):
        decisions = match_approved_job(
            self.job_version(),
            [requirement("jobver_test123")],
            [evidence()],
        )
        self.assertEqual(decisions[0].status, MatchStatus.MET)

    def test_requirement_from_another_version_is_rejected(self):
        with self.assertRaisesRegex(JobMatchBoundaryError, "another job version"):
            match_approved_job(
                self.job_version(),
                [requirement("jobver_other")],
                [evidence()],
            )

    def test_invented_requirement_text_is_rejected(self):
        with self.assertRaisesRegex(JobMatchBoundaryError, "not present"):
            match_approved_job(
                self.job_version(),
                [requirement("jobver_test123", text="必须拥有五年工作经验")],
                [evidence()],
            )

    def test_terms_not_present_in_requirement_text_are_rejected(self):
        with self.assertRaisesRegex(JobMatchBoundaryError, "normalized terms"):
            match_approved_job(
                self.job_version(),
                [
                    requirement(
                        "jobver_test123",
                        normalized_terms=["python", "五年经验"],
                    )
                ],
                [evidence()],
            )

    def test_duplicate_requirement_identifier_is_rejected(self):
        item = requirement("jobver_test123")
        with self.assertRaisesRegex(JobMatchBoundaryError, "duplicated"):
            match_approved_job(self.job_version(), [item, item], [evidence()])


class JobMatchApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.jobs = KnowledgeRegistry(os.path.join(self.temp_dir.name, "jobs.sqlite3"))
        self.jobs.register_source(
            source_id="src_test_company",
            company_name="测试企业",
            official_domain="careers.example.com",
            source_url="https://careers.example.com",
            job_source_url="https://careers.example.com/jobs",
            support_level="structured_import",
        )
        self.job = self.jobs.upsert_job_posting(posting(), review_status="approved")
        self.evidence_registry = EvidenceRegistry(
            os.path.join(self.temp_dir.name, "evidence.sqlite3")
        )
        self.evidence_registry.add_evidence(evidence())
        current = self.jobs.get_current_approved_job_version(
            job_id=self.job["job_id"],
            version_id=self.job["submitted_version_id"],
            as_of=AS_OF,
        )
        drafts = extract_requirement_drafts(current)
        self.evidence_registry.add_requirement_drafts(drafts)
        draft = next(item for item in drafts if item.text == "熟悉 Python 和 SQL")
        self.evidence_registry.add_requirement_review(
            JDRequirementReview(
                review_id="review:python-sql",
                requirement_id=draft.requirement_id,
                job_version_id=draft.job_version_id,
                reviewer_id="reviewer_1",
                decision=RequirementReviewDecision.CONFIRM,
                category=RequirementCategory.SKILL,
                importance=RequirementImportance.REQUIRED,
                normalized_terms=["python", "sql"],
                reviewed_at=NOW,
            )
        )
        self.requirement_id = draft.requirement_id
        self.original_registry = api_main._evidence_registry
        self.original_manager = api_main._tool_manager
        api_main._evidence_registry = self.evidence_registry
        jobs = self.jobs

        class KnowledgeStub:
            def search_handler(inner_self, params=None, context=None):
                return []

            def get_current_approved_job_version(inner_self, **kwargs):
                return jobs.get_current_approved_job_version(**kwargs, as_of=AS_OF)

        knowledge = KnowledgeStub()
        api_main._tool_manager = SimpleNamespace(
            _tools={"knowledge_search": SimpleNamespace(handler=knowledge.search_handler)}
        )

    def tearDown(self):
        api_main._evidence_registry = self.original_registry
        api_main._tool_manager = self.original_manager
        self.temp_dir.cleanup()

    def body(self, **overrides: object) -> api_main.V2JobMatchInput:
        version_id = self.job["submitted_version_id"]
        payload = {
            "user_id": "留学生_1",
            "requirement_ids": [self.requirement_id],
            "evidence_ids": ["evidence:python-sql"],
        }
        payload.update(overrides)
        return api_main.V2JobMatchInput(**payload)

    def test_api_returns_bounded_match_summary(self):
        result = asyncio.run(
            api_main.match_v2_approved_job(
                self.job["job_id"],
                self.job["submitted_version_id"],
                self.body(),
            )
        )
        self.assertEqual(result.evidence_count, 1)
        self.assertEqual(result.decisions[0].status, MatchStatus.MET)
        self.assertEqual(result.summary.total, 1)
        self.assertEqual(result.summary.met, 1)
        self.assertEqual(result.summary.requires_follow_up, 0)
        self.assertEqual(result.items[0].requirement.requirement_id, self.requirement_id)
        self.assertEqual(result.items[0].decision, result.decisions[0])
        self.assertEqual(result.company_name, "测试企业")
        self.assertEqual(result.job_max_age_days, 30)
        self.assertFalse(hasattr(result, "payload"))

    def test_api_rejects_unavailable_evidence(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                api_main.match_v2_approved_job(
                    self.job["job_id"],
                    self.job["submitted_version_id"],
                    self.body(evidence_ids=["evidence:missing"]),
                )
            )
        self.assertEqual(raised.exception.status_code, 422)

    def test_api_rejects_non_current_version(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                api_main.match_v2_approved_job(
                    self.job["job_id"],
                    "jobver_missing",
                    self.body(),
                )
            )
        self.assertEqual(raised.exception.status_code, 404)

    def test_api_rejects_unreviewed_requirement(self):
        current = self.jobs.get_current_approved_job_version(
            job_id=self.job["job_id"],
            version_id=self.job["submitted_version_id"],
            as_of=AS_OF,
        )
        draft = next(
            item
            for item in extract_requirement_drafts(current)
            if item.text == "使用 Python 完成业务数据分析"
        )
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                api_main.match_v2_approved_job(
                    self.job["job_id"],
                    self.job["submitted_version_id"],
                    self.body(requirement_ids=[draft.requirement_id]),
                )
            )
        self.assertEqual(raised.exception.status_code, 422)

    def test_api_rejects_requirement_after_latest_review_rejects_it(self):
        self.evidence_registry.add_requirement_review(
            JDRequirementReview(
                review_id="review:python-sql-reject",
                requirement_id=self.requirement_id,
                job_version_id=self.job["submitted_version_id"],
                reviewer_id="reviewer_1",
                decision=RequirementReviewDecision.REJECT,
                category=RequirementCategory.SKILL,
                importance=RequirementImportance.REQUIRED,
                normalized_terms=[],
                reviewed_at=NOW,
            )
        )
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                api_main.match_v2_approved_job(
                    self.job["job_id"],
                    self.job["submitted_version_id"],
                    self.body(),
                )
            )
        self.assertEqual(raised.exception.status_code, 422)

    def test_input_cannot_use_legacy_uploaded_requirement_payload(self):
        with self.assertRaises(ValidationError):
            api_main.V2JobMatchInput(
                user_id="留学生_1",
                requirements=[requirement(self.job["submitted_version_id"])],
                evidence_ids=["evidence:python-sql"],
            )

    def test_input_requires_explicit_evidence_selection(self):
        with self.assertRaises(ValidationError):
            self.body(evidence_ids=[])

    def test_route_is_admin_protected(self):
        route = next(
            route
            for route in api_main.app.routes
            if route.path == "/v2/jobs/{job_id}/versions/{version_id}/match"
        )
        self.assertTrue(route.dependencies)

    def test_http_route_enforces_admin_key_and_returns_decisions(self):
        key = "m" * 32
        version_id = self.job["submitted_version_id"]
        body = self.body().model_dump(mode="json")
        client = TestClient(api_main.app)
        with patch.dict(
            os.environ,
            {"MAKO_ADMIN_API_KEY": key},
            clear=False,
        ):
            url = f"/v2/jobs/{self.job['job_id']}/versions/{version_id}/match"
            denied = client.post(url, json=body)
            accepted = client.post(url, headers={"X-Admin-Key": key}, json=body)
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(accepted.status_code, 200)
        payload = accepted.json()
        self.assertEqual(payload["job_version_id"], version_id)
        self.assertEqual(payload["decisions"][0]["status"], "met")
        self.assertEqual(payload["summary"]["met"], 1)
        self.assertEqual(payload["items"][0]["decision"]["status"], "met")
        self.assertNotIn("score", payload["summary"])
        self.assertNotIn("claim", payload["items"][0])
        self.assertNotIn("payload", payload)


if __name__ == "__main__":
    unittest.main()
