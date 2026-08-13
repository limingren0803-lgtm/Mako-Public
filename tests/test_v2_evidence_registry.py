from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from api import main as api_main
from core.v2_evidence import (
    ConfirmationDecision,
    ConfirmationObjectType,
    ConfirmationScope,
    EvidenceFactStatus,
    EvidenceRecord,
    EvidenceStrength,
    EvidenceType,
    UserConfirmation,
)
from core.v2_evidence_registry import (
    EvidenceConflictError,
    EvidenceReferenceError,
    EvidenceRegistry,
)


NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)


def evidence(**overrides: object) -> EvidenceRecord:
    payload = {
        "evidence_id": "evidence:python-project",
        "user_id": "留学生_1",
        "claim": "在课程项目中使用 Python 完成数据分析",
        "evidence_type": EvidenceType.PORTFOLIO,
        "fact_status": EvidenceFactStatus.CONFIRMED,
        "strength": EvidenceStrength.DIRECT,
        "captured_at": NOW,
        "verified_at": NOW,
    }
    payload.update(overrides)
    return EvidenceRecord(**payload)


def confirmation(**overrides: object) -> UserConfirmation:
    payload = {
        "confirmation_id": "confirmation:python-project",
        "user_id": "留学生_1",
        "object_type": ConfirmationObjectType.EVIDENCE,
        "object_id": "evidence:python-project",
        "decision": ConfirmationDecision.CONFIRM,
        "scope": ConfirmationScope.REQUEST,
        "request_id": "request:review-1",
        "decided_at": NOW,
    }
    payload.update(overrides)
    return UserConfirmation(**payload)


class EvidenceRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.registry = EvidenceRegistry(os.path.join(self.temp_dir.name, "evidence.sqlite3"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_schema_initialization_is_repeatable(self):
        EvidenceRegistry(str(self.registry.path))
        self.assertEqual(self.registry.list_evidence("留学生_1"), [])

    def test_evidence_insert_and_retry_are_idempotent(self):
        first = self.registry.add_evidence(evidence())
        retry = self.registry.add_evidence(evidence())
        self.assertEqual(first, retry)
        self.assertEqual(len(self.registry.list_evidence("留学生_1")), 1)

    def test_evidence_timestamp_change_is_not_silently_ignored(self):
        self.registry.add_evidence(evidence())
        changed_at = NOW.replace(microsecond=500)
        with self.assertRaisesRegex(EvidenceConflictError, "different content"):
            self.registry.add_evidence(
                evidence(captured_at=changed_at, verified_at=changed_at)
            )

    def test_evidence_identifier_cannot_overwrite_different_content(self):
        self.registry.add_evidence(evidence())
        with self.assertRaisesRegex(EvidenceConflictError, "different content"):
            self.registry.add_evidence(evidence(claim="不同的经历"))
        self.assertEqual(self.registry.get_evidence("evidence:python-project").claim,
                         "在课程项目中使用 Python 完成数据分析")

    def test_confirmation_requires_an_existing_owned_evidence_record(self):
        with self.assertRaisesRegex(EvidenceReferenceError, "does not exist"):
            self.registry.add_confirmation(confirmation())
        self.registry.add_evidence(evidence())
        with self.assertRaisesRegex(EvidenceReferenceError, "another user"):
            self.registry.add_confirmation(confirmation(user_id="student_2"))

    def test_confirmation_insert_and_retry_are_idempotent(self):
        self.registry.add_evidence(evidence())
        first = self.registry.add_confirmation(confirmation())
        retry = self.registry.add_confirmation(confirmation())
        self.assertEqual(first, retry)
        self.assertEqual(len(self.registry.list_confirmations("留学生_1")), 1)

    def test_records_remain_readable_after_registry_reopens(self):
        self.registry.add_evidence(evidence())
        self.registry.add_confirmation(confirmation())
        reopened = EvidenceRegistry(str(self.registry.path))
        self.assertEqual(reopened.get_evidence("evidence:python-project"), evidence())
        self.assertEqual(
            reopened.get_confirmation("confirmation:python-project"),
            confirmation(),
        )

    def test_unsupported_confirmation_object_is_rejected(self):
        self.registry.add_evidence(evidence())
        with self.assertRaisesRegex(EvidenceReferenceError, "only evidence"):
            self.registry.add_confirmation(
                confirmation(object_type=ConfirmationObjectType.MATCH_DECISION)
            )

    def test_result_limits_are_bounded(self):
        for index in range(3):
            self.registry.add_evidence(
                evidence(evidence_id=f"evidence:{index}", claim=f"项目经历 {index}")
            )
        self.assertEqual(len(self.registry.list_evidence("留学生_1", limit=2)), 2)
        self.assertEqual(len(self.registry.list_evidence("留学生_1", limit=0)), 1)


class EvidenceApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.registry = EvidenceRegistry(os.path.join(self.temp_dir.name, "evidence.sqlite3"))
        self.original_registry = api_main._evidence_registry
        api_main._evidence_registry = self.registry

    def tearDown(self):
        api_main._evidence_registry = self.original_registry
        self.temp_dir.cleanup()

    def test_api_functions_persist_and_list_evidence(self):
        created = asyncio.run(api_main.create_v2_evidence(evidence()))
        listed = asyncio.run(api_main.list_v2_evidence("留学生_1", limit=100))
        self.assertEqual(created.evidence_id, "evidence:python-project")
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["items"][0].claim, evidence().claim)

    def test_api_maps_conflicts_and_missing_targets(self):
        asyncio.run(api_main.create_v2_evidence(evidence()))
        with self.assertRaises(HTTPException) as conflict:
            asyncio.run(api_main.create_v2_evidence(evidence(claim="不同内容")))
        self.assertEqual(conflict.exception.status_code, 409)
        with self.assertRaises(HTTPException) as missing:
            asyncio.run(api_main.create_v2_confirmation(
                confirmation(object_id="evidence:missing")
            ))
        self.assertEqual(missing.exception.status_code, 422)

    def test_v2_routes_are_admin_protected(self):
        protected = {
            "/v2/evidence",
            "/v2/confirmations",
        }
        routes = {route.path: route for route in api_main.app.routes}
        for path in protected:
            self.assertTrue(routes[path].dependencies, path)

    def test_admin_boundary_still_rejects_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(api_main.require_admin_key(None))
        self.assertEqual(raised.exception.status_code, 503)

    def test_http_boundary_requires_key_and_keeps_user_results_separate(self):
        key = "v" * 32
        headers = {"X-Admin-Key": key}
        client = TestClient(api_main.app)
        with patch.dict(os.environ, {"MAKO_ADMIN_API_KEY": key}, clear=False):
            denied = client.get("/v2/evidence", params={"user_id": "留学生_1"})
            self.assertEqual(denied.status_code, 401)

            created = client.post(
                "/v2/evidence",
                headers=headers,
                json=evidence().model_dump(mode="json"),
            )
            self.assertEqual(created.status_code, 200)
            own = client.get(
                "/v2/evidence",
                params={"user_id": "留学生_1"},
                headers=headers,
            )
            other = client.get(
                "/v2/evidence",
                params={"user_id": "another/user"},
                headers=headers,
            )
            self.assertEqual(own.status_code, 200)
            self.assertEqual(own.json()["count"], 1)
            self.assertEqual(other.status_code, 200)
            self.assertEqual(other.json(), {"count": 0, "items": []})

            confirmed = client.post(
                "/v2/confirmations",
                headers=headers,
                json=confirmation().model_dump(mode="json"),
            )
            self.assertEqual(confirmed.status_code, 200)
            confirmations = client.get(
                "/v2/confirmations",
                params={"user_id": "留学生_1"},
                headers=headers,
            )
            self.assertEqual(confirmations.status_code, 200)
            self.assertEqual(confirmations.json()["count"], 1)


if __name__ == "__main__":
    unittest.main()
