import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import career_workspace as workspace_api
from api import main as api_main
from core.career_workspace_registry import CareerWorkspaceRegistry


class PublicCareerWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = CareerWorkspaceRegistry(
            str(Path(self.temp.name) / "workspace.sqlite3")
        )
        workspace_api.configure_workspace_api(
            self.registry,
            knowledge_provider=lambda: None,
            evidence_provider=lambda: None,
        )
        self.local_patch = patch(
            "core.workspace_access.is_local_workspace_request",
            return_value=True,
        )
        self.local_patch.start()
        self.client = TestClient(api_main.app)

    def tearDown(self):
        self.client.close()
        self.local_patch.stop()
        self.temp.cleanup()

    def test_workspace_requires_a_local_session(self):
        response = self.client.get("/v2/workspace/summary")

        self.assertEqual(response.status_code, 401)

    def test_workspace_ui_is_available_without_admin_credentials(self):
        ui_root = Path(api_main.__file__).resolve().parents[1] / "ui"
        html = (ui_root / "index.html").read_text(encoding="utf-8")
        script = (ui_root / "workspace.js").read_text(encoding="utf-8")

        self.assertIn('id="career-workspace-view"', html)
        self.assertIn('src="workspace.js?v=1"', html)
        self.assertIn('href="workspace.css?v=1"', html)
        self.assertIn('const WORKSPACE_API = "/v2/workspace"', script)
        self.assertIn("`${WORKSPACE_API}/session`", script)
        self.assertNotIn("X-Admin-Key", script)

    def test_manual_track_action_export_and_cleanup(self):
        session = self.client.post("/v2/workspace/session")
        self.assertEqual(session.status_code, 204)

        track = self.client.post(
            "/v2/workspace/tracks",
            headers={"Idempotency-Key": "public-track"},
            json={
                "source_kind": "manual_jd",
                "company_name": "示例公司",
                "title": "产品实习生",
                "jd_text": "负责用户研究与产品分析。",
            },
        )
        self.assertEqual(track.status_code, 201, track.text)
        track_id = track.json()["track"]["track_id"]

        action = self.client.post(
            "/v2/workspace/actions",
            headers={"Idempotency-Key": "public-action"},
            json={
                "track_id": track_id,
                "title": "整理项目案例",
                "completion_criteria": "完成一页项目复盘",
                "priority": "high",
                "due_at": (
                    datetime.now(timezone.utc) + timedelta(hours=1)
                ).isoformat(),
            },
        )
        self.assertEqual(action.status_code, 201, action.text)
        action_id = action.json()["action_id"]

        completed = self.client.patch(
            f"/v2/workspace/actions/{action_id}",
            json={"revision": 1, "status": "completed"},
        )
        self.assertEqual(completed.status_code, 200, completed.text)

        stale = self.client.patch(
            f"/v2/workspace/actions/{action_id}",
            json={"revision": 1, "status": "todo"},
        )
        self.assertEqual(stale.status_code, 409)

        exported = self.client.get("/v2/workspace/export")
        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertEqual(len(exported.json()["tracks"]), 1)
        self.assertEqual(len(exported.json()["actions"]), 1)

        impact = self.client.get(
            f"/v2/workspace/tracks/{track_id}/deletion-impact"
        )
        self.assertEqual(impact.json(), {"tracks": 1, "actions": 1})

        deleted = self.client.delete(
            f"/v2/workspace/tracks/{track_id}",
            params={"revision": 1, "cascade_actions": "true"},
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(deleted.json()["deleted"], {"tracks": 1, "actions": 1})


if __name__ == "__main__":
    unittest.main()
