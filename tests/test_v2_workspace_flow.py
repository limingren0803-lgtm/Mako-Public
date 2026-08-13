from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api import main as api_main
from core.job_posting import JobPosting, RecruitmentType
from core.v2_evidence import (
    JDRequirementReview,
    RequirementCategory,
    RequirementImportance,
    RequirementReviewDecision,
)
from core.v2_evidence_registry import EvidenceRegistry
from core.v2_requirements import extract_requirement_drafts
from mcp.knowledge_registry import KnowledgeRegistry


NOW = datetime(2026, 8, 13, tzinfo=timezone.utc)


def posting(**overrides: object) -> JobPosting:
    payload = {
        "source_id": "src_workspace_company",
        "external_id": "workspace-role-1",
        "company_name": "示例企业",
        "title": "数据分析实习生",
        "recruitment_type": RecruitmentType.INTERNSHIP,
        "locations": ["上海"],
        "responsibilities": ["使用 Python 完成业务数据分析"],
        "requirements": ["熟悉 Python 和 SQL"],
        "description": "面向应届生和留学生的实习岗位",
        "source_url": "https://careers.example.com/jobs/workspace-role-1",
        "fetched_at": NOW,
    }
    payload.update(overrides)
    return JobPosting(**payload)


class WorkspaceFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.jobs = KnowledgeRegistry(os.path.join(self.temp_dir.name, "jobs.sqlite3"))
        self.jobs.register_source(
            source_id="src_workspace_company",
            company_name="示例企业",
            official_domain="careers.example.com",
            source_url="https://careers.example.com",
            job_source_url="https://careers.example.com/jobs",
            support_level="structured_import",
        )
        self.job = self.jobs.upsert_job_posting(posting(), review_status="approved")
        self.version_id = self.job["submitted_version_id"]
        current = self.jobs.get_current_approved_job_version(
            job_id=self.job["job_id"],
            version_id=self.version_id,
            as_of=NOW.isoformat(),
        )
        self.evidence_registry = EvidenceRegistry(
            os.path.join(self.temp_dir.name, "evidence.sqlite3")
        )
        drafts = self.evidence_registry.add_requirement_drafts(
            extract_requirement_drafts(current)
        )
        draft = next(item for item in drafts if item.text == "熟悉 Python 和 SQL")
        self.raw_requirement_id = next(
            item.requirement_id
            for item in drafts
            if item.text == "使用 Python 完成业务数据分析"
        )
        self.evidence_registry.add_requirement_review(
            JDRequirementReview(
                review_id="review:workspace-python-sql",
                requirement_id=draft.requirement_id,
                job_version_id=self.version_id,
                reviewer_id="reviewer_workspace",
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

            def list_job_postings(inner_self, **kwargs):
                return jobs.list_job_postings(**kwargs)

            def get_current_approved_job_version(inner_self, **kwargs):
                return jobs.get_current_approved_job_version(
                    **kwargs, as_of=NOW.isoformat()
                )

        knowledge = KnowledgeStub()
        api_main._tool_manager = SimpleNamespace(
            _tools={"knowledge_search": SimpleNamespace(handler=knowledge.search_handler)}
        )
        self.client = TestClient(api_main.app)

    def tearDown(self):
        api_main._evidence_registry = self.original_registry
        api_main._tool_manager = self.original_manager
        self.temp_dir.cleanup()

    def job_url(self, suffix: str) -> str:
        return (
            f"/v2/workspace/jobs/{self.job['job_id']}"
            f"/versions/{self.version_id}/{suffix}"
        )

    def test_public_job_list_exposes_only_safe_match_fields(self):
        response = self.client.get("/v2/workspace/jobs?max_age_days=30")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        item = payload["items"][0]
        self.assertTrue(item["match_ready"])
        self.assertEqual(item["requirement_count"], 2)
        self.assertNotIn("payload", item)
        self.assertNotIn("review_notes", item)

    def test_job_search_can_be_narrowed_without_refreshing_sources(self):
        matched = self.client.get("/v2/workspace/jobs?query=上海")
        missing = self.client.get("/v2/workspace/jobs?query=北京")
        self.assertEqual(matched.json()["count"], 1)
        self.assertEqual(missing.json()["count"], 0)

    def test_workspace_lists_only_reviewed_requirements(self):
        response = self.client.get(self.job_url("requirements"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        states = {
            item["requirement_id"]: item["extraction_status"]
            for item in payload["items"]
        }
        self.assertEqual(states[self.requirement_id], "parsed")
        self.assertEqual(states[self.raw_requirement_id], "needs_review")

    def test_confirmed_request_local_material_produces_match(self):
        before = self.evidence_registry.list_evidence("request_unused")
        response = self.client.post(
            self.job_url("match"),
            json={
                "requirement_ids": [self.requirement_id],
                "requirement_terms": {},
                "evidence": ["课程项目使用 Python 和 SQL 完成数据分析"],
                "material_confirmed": True,
                "job_max_age_days": 30,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["met"], 1)
        self.assertEqual(payload["items"][0]["decision"]["status"], "met")
        self.assertEqual(payload["confirmation_scope"], "request")
        self.assertFalse(payload["evidence_persisted"])
        self.assertEqual(before, [])
        with self.evidence_registry._connection() as connection:
            count = connection.execute("SELECT COUNT(*) FROM evidence_records").fetchone()[0]
        self.assertEqual(count, 0)

    def test_user_can_confirm_exact_terms_for_request_local_requirement(self):
        response = self.client.post(
            self.job_url("match"),
            json={
                "requirement_ids": [self.raw_requirement_id],
                "requirement_terms": {
                    self.raw_requirement_id: ["python", "数据分析"],
                },
                "evidence": ["课程项目使用 Python 完成业务数据分析"],
                "material_confirmed": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["met"], 1)
        self.assertFalse(payload["evidence_persisted"])
        self.assertIsNone(
            self.evidence_registry.get_reviewed_requirement(self.raw_requirement_id)
        )

    def test_request_local_terms_must_appear_in_official_jd_text(self):
        response = self.client.post(
            self.job_url("match"),
            json={
                "requirement_ids": [self.raw_requirement_id],
                "requirement_terms": {
                    self.raw_requirement_id: ["五年工作经验"],
                },
                "evidence": ["具有五年工作经验"],
                "material_confirmed": True,
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_material_confirmation_is_required(self):
        response = self.client.post(
            self.job_url("match"),
            json={
                "requirement_ids": [self.requirement_id],
                "requirement_terms": {},
                "evidence": ["使用 Python 和 SQL"],
                "material_confirmed": False,
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_unreviewed_requirement_identifier_is_rejected(self):
        response = self.client.post(
            self.job_url("match"),
            json={
                "requirement_ids": ["requirement:not-reviewed"],
                "requirement_terms": {
                    "requirement:not-reviewed": ["python"],
                },
                "evidence": ["使用 Python 和 SQL"],
                "material_confirmed": True,
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_workspace_routes_do_not_require_or_accept_an_admin_key(self):
        routes = {
            route.path: route
            for route in api_main.app.routes
            if route.path.startswith("/v2/workspace/")
        }
        self.assertEqual(len(routes), 3)
        self.assertTrue(all(not route.dependencies for route in routes.values()))


if __name__ == "__main__":
    unittest.main()
