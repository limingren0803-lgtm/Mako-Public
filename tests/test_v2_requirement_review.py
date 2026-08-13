from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from api import main as api_main
from core.job_posting import JobPosting, RecruitmentType
from core.v2_evidence import (
    JDRequirementReview,
    RequirementCategory,
    RequirementExtractionStatus,
    RequirementImportance,
    RequirementReviewDecision,
    RequirementSourceField,
)
from core.v2_evidence_registry import (
    EvidenceRegistry,
    RequirementConflictError,
    RequirementReferenceError,
)
from core.v2_requirements import extract_requirement_drafts
from mcp.knowledge_registry import KnowledgeRegistry


NOW = datetime(2026, 8, 12, 12, tzinfo=timezone.utc)
AS_OF = "2026-08-12T12:00:00+00:00"


def posting() -> JobPosting:
    return JobPosting(
        source_id="src_requirement_test",
        external_id="role-review-1",
        company_name="测试企业",
        title="产品分析实习生",
        recruitment_type=RecruitmentType.INTERNSHIP,
        locations=["上海"],
        responsibilities=["分析用户需求并推动产品迭代"],
        requirements=["熟悉 SQL 和数据分析", "英语可作为工作语言"],
        description="面向应届生和留学生的实习岗位",
        source_url="https://careers.example.com/jobs/review-1",
        fetched_at=NOW,
    )


def review(draft, **overrides: object) -> JDRequirementReview:
    payload = {
        "review_id": "review:sql-data",
        "requirement_id": draft.requirement_id,
        "job_version_id": draft.job_version_id,
        "reviewer_id": "reviewer_1",
        "decision": RequirementReviewDecision.CONFIRM,
        "category": RequirementCategory.SKILL,
        "importance": RequirementImportance.REQUIRED,
        "normalized_terms": ["sql", "数据分析"],
        "reviewed_at": NOW,
    }
    payload.update(overrides)
    return JDRequirementReview(**payload)


class RequirementExtractionTests(unittest.TestCase):
    def job_version(self) -> dict:
        return {
            "job_version_id": "jobver_review123",
            "payload": posting().model_dump(mode="json"),
        }

    def test_structured_items_become_stable_review_required_drafts(self):
        first = extract_requirement_drafts(self.job_version())
        second = extract_requirement_drafts(self.job_version())
        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        self.assertTrue(
            all(
                item.extraction_status == RequirementExtractionStatus.NEEDS_REVIEW
                for item in first
            )
        )
        self.assertEqual(first[0].source_field, RequirementSourceField.REQUIREMENTS)
        self.assertEqual(first[0].source_index, 0)
        self.assertEqual(first[-1].source_field, RequirementSourceField.RESPONSIBILITIES)
        self.assertEqual(first[-1].category, RequirementCategory.RESPONSIBILITY)
        self.assertTrue(all(not item.normalized_terms for item in first))

    def test_unstructured_description_is_not_silently_promoted(self):
        payload = self.job_version()
        payload["payload"]["requirements"] = []
        payload["payload"]["responsibilities"] = []
        with self.assertRaisesRegex(ValueError, "no structured requirements"):
            extract_requirement_drafts(payload)


class RequirementRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.registry = EvidenceRegistry(
            os.path.join(self.temp_dir.name, "evidence.sqlite3")
        )
        self.drafts = extract_requirement_drafts(
            {
                "job_version_id": "jobver_review123",
                "payload": posting().model_dump(mode="json"),
            }
        )
        self.draft = self.drafts[0]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_draft_batch_is_atomic_and_idempotent(self):
        first = self.registry.add_requirement_drafts(self.drafts)
        retry = self.registry.add_requirement_drafts(self.drafts)
        self.assertEqual(first, retry)
        self.assertEqual(
            len(self.registry.list_requirement_drafts("jobver_review123")),
            3,
        )
        changed = self.draft.model_copy(update={"text": "不同内容"})
        with self.assertRaisesRegex(RequirementConflictError, "different content"):
            self.registry.add_requirement_drafts([changed])
        self.assertEqual(self.registry.get_requirement_draft(self.draft.requirement_id), self.draft)

    def test_review_is_append_only_and_produces_parsed_state(self):
        self.registry.add_requirement_drafts(self.drafts)
        item = review(self.draft)
        self.assertEqual(self.registry.add_requirement_review(item), item)
        self.assertEqual(self.registry.add_requirement_review(item), item)
        current = self.registry.get_reviewed_requirement(self.draft.requirement_id)
        self.assertEqual(current.extraction_status, RequirementExtractionStatus.PARSED)
        self.assertEqual(current.normalized_terms, ["sql", "数据分析"])
        with self.assertRaisesRegex(RequirementConflictError, "different content"):
            self.registry.add_requirement_review(
                review(self.draft, category=RequirementCategory.EXPERIENCE)
            )

    def test_latest_review_can_reject_without_deleting_history(self):
        self.registry.add_requirement_drafts(self.drafts)
        self.registry.add_requirement_review(review(self.draft))
        self.registry.add_requirement_review(
            review(
                self.draft,
                review_id="review:sql-data-reject",
                decision=RequirementReviewDecision.REJECT,
                normalized_terms=[],
                reviewed_at=NOW + timedelta(seconds=1),
            )
        )
        current = self.registry.get_reviewed_requirement(self.draft.requirement_id)
        self.assertEqual(current.extraction_status, RequirementExtractionStatus.REJECTED)

    def test_effective_review_uses_append_order_not_client_clock(self):
        self.registry.add_requirement_drafts(self.drafts)
        self.registry.add_requirement_review(
            review(self.draft, reviewed_at=NOW + timedelta(days=30))
        )
        self.registry.add_requirement_review(
            review(
                self.draft,
                review_id="review:later-write",
                decision=RequirementReviewDecision.REJECT,
                normalized_terms=[],
                reviewed_at=NOW,
            )
        )
        current = self.registry.get_reviewed_requirement(self.draft.requirement_id)
        self.assertEqual(current.extraction_status, RequirementExtractionStatus.REJECTED)

    def test_correction_and_terms_must_remain_in_source_text(self):
        self.registry.add_requirement_drafts(self.drafts)
        with self.assertRaisesRegex(RequirementReferenceError, "traceable"):
            self.registry.add_requirement_review(
                review(
                    self.draft,
                    decision=RequirementReviewDecision.CORRECT,
                    corrected_text="要求五年管理经验",
                    normalized_terms=["五年管理经验"],
                )
            )
        with self.assertRaisesRegex(RequirementReferenceError, "normalized terms"):
            self.registry.add_requirement_review(
                review(self.draft, normalized_terms=["python"])
            )

    def test_review_requires_existing_matching_draft(self):
        with self.assertRaisesRegex(RequirementReferenceError, "does not exist"):
            self.registry.add_requirement_review(review(self.draft))

    def test_requirement_state_survives_registry_reopen(self):
        self.registry.add_requirement_drafts(self.drafts)
        self.registry.add_requirement_review(review(self.draft))
        reopened = EvidenceRegistry(str(self.registry.path))
        current = reopened.get_reviewed_requirement(self.draft.requirement_id)
        self.assertEqual(current.extraction_status, RequirementExtractionStatus.PARSED)


class RequirementApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.jobs = KnowledgeRegistry(os.path.join(self.temp_dir.name, "jobs.sqlite3"))
        self.jobs.register_source(
            source_id="src_requirement_test",
            company_name="测试企业",
            official_domain="careers.example.com",
            source_url="https://careers.example.com",
            job_source_url="https://careers.example.com/jobs",
            support_level="structured_import",
        )
        self.job = self.jobs.upsert_job_posting(posting(), review_status="approved")
        self.registry = EvidenceRegistry(
            os.path.join(self.temp_dir.name, "evidence.sqlite3")
        )
        self.original_registry = api_main._evidence_registry
        self.original_manager = api_main._tool_manager
        api_main._evidence_registry = self.registry
        jobs = self.jobs

        class KnowledgeStub:
            def search_handler(self, params=None, context=None):
                return []

            def get_current_approved_job_version(self, **kwargs):
                return jobs.get_current_approved_job_version(**kwargs, as_of=AS_OF)

        knowledge = KnowledgeStub()
        api_main._tool_manager = SimpleNamespace(
            _tools={"knowledge_search": SimpleNamespace(handler=knowledge.search_handler)}
        )

    def tearDown(self):
        api_main._evidence_registry = self.original_registry
        api_main._tool_manager = self.original_manager
        self.temp_dir.cleanup()

    @property
    def version_id(self) -> str:
        return self.job["submitted_version_id"]

    def test_extract_list_review_http_flow_is_admin_protected(self):
        key = "r" * 32
        headers = {"X-Admin-Key": key}
        base = f"/v2/jobs/{self.job['job_id']}/versions/{self.version_id}"
        client = TestClient(api_main.app)
        with patch.dict(os.environ, {"MAKO_ADMIN_API_KEY": key}, clear=False):
            denied = client.post(f"{base}/requirements/extract", json={})
            self.assertEqual(denied.status_code, 401)
            extracted = client.post(
                f"{base}/requirements/extract",
                headers=headers,
                json={"job_max_age_days": 30},
            )
            self.assertEqual(extracted.status_code, 200)
            self.assertEqual(extracted.json()["count"], 3)
            draft = extracted.json()["items"][0]
            self.assertEqual(draft["extraction_status"], "needs_review")
            review_body = {
                "review_id": "review:http-sql",
                "requirement_id": draft["requirement_id"],
                "job_version_id": self.version_id,
                "reviewer_id": "reviewer_1",
                "decision": "confirm",
                "category": "skill",
                "importance": "required",
                "normalized_terms": ["sql", "数据分析"],
                "reviewed_at": NOW.isoformat(),
            }
            reviewed = client.post(
                f"{base}/requirements/{draft['requirement_id']}/reviews",
                headers=headers,
                json=review_body,
            )
            self.assertEqual(reviewed.status_code, 200)
            self.assertEqual(reviewed.json()["extraction_status"], "parsed")
            listed = client.get(f"{base}/requirements", headers=headers)
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(listed.json()["items"][0]["extraction_status"], "parsed")

    def test_pending_job_cannot_be_extracted(self):
        pending = self.jobs.upsert_job_posting(
            posting().model_copy(update={"external_id": "pending-role"}),
            review_status="pending",
        )
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                api_main.extract_v2_job_requirements(
                    pending["job_id"],
                    pending["submitted_version_id"],
                    api_main.V2RequirementExtractionInput(),
                )
            )
        self.assertEqual(raised.exception.status_code, 404)

    def test_approved_summary_without_structured_jd_is_not_invented(self):
        summary = posting().model_copy(
            update={
                "external_id": "summary-only-role",
                "requirements": [],
                "responsibilities": [],
                "description": "",
            }
        )
        result = self.jobs.upsert_job_posting(summary, review_status="approved")
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                api_main.extract_v2_job_requirements(
                    result["job_id"],
                    result["submitted_version_id"],
                    api_main.V2RequirementExtractionInput(),
                )
            )
        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("no structured requirements", raised.exception.detail)

    def test_review_path_identifiers_must_match_payload(self):
        extracted = asyncio.run(
            api_main.extract_v2_job_requirements(
                self.job["job_id"],
                self.version_id,
                api_main.V2RequirementExtractionInput(),
            )
        )
        draft = extracted.items[0]
        body = review(draft, review_id="review:path-mismatch")
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                api_main.review_v2_job_requirement(
                    self.job["job_id"],
                    self.version_id,
                    "requirement:other",
                    body,
                )
            )
        self.assertEqual(raised.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
