import asyncio
import io
import os
import pathlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from pydantic import ValidationError

from api import main as api_main
from core.security import cors_origins, require_admin_key, validate_identifier


class SecurityConfigurationTests(unittest.TestCase):
    def test_cors_defaults_are_local_only(self):
        with patch.dict(os.environ, {}, clear=True):
            origins = cors_origins()
        self.assertIn("http://localhost", origins)
        self.assertNotIn("*", origins)

    def test_cors_explicit_origins_are_parsed(self):
        with patch.dict(
            os.environ,
            {"MAKO_CORS_ALLOW_ORIGINS": "https://mako.example, https://admin.example"},
            clear=True,
        ):
            self.assertEqual(
                cors_origins(),
                ["https://mako.example", "https://admin.example"],
            )

    def test_admin_api_is_closed_when_key_is_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(require_admin_key(None))
        self.assertEqual(503, ctx.exception.status_code)

    def test_admin_api_rejects_short_configured_key(self):
        with patch.dict(os.environ, {"MAKO_ADMIN_API_KEY": "too-short"}, clear=True):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(require_admin_key("too-short"))
        self.assertEqual(503, ctx.exception.status_code)

    def test_admin_api_rejects_wrong_key_and_accepts_correct_key(self):
        key = "a" * 32
        with patch.dict(os.environ, {"MAKO_ADMIN_API_KEY": key}, clear=True):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(require_admin_key("b" * 32))
            self.assertEqual(401, ctx.exception.status_code)
            self.assertIsNone(asyncio.run(require_admin_key(key)))

    def test_identifier_rejects_controls_and_excessive_length(self):
        with self.assertRaises(ValueError):
            validate_identifier("user\nother", "user_id")
        with self.assertRaises(ValueError):
            validate_identifier("u" * 129, "user_id")

    def test_chat_request_bounds_identifiers_and_message(self):
        self.assertEqual("用户-1", api_main.ChatRequest(message="你好", user_id="用户-1").user_id)
        with self.assertRaises(ValidationError):
            api_main.ChatRequest(message="")
        with self.assertRaises(ValidationError):
            api_main.ChatRequest(message="hello", conv_id="bad\r\nid")

    def test_sensitive_routes_have_admin_dependency(self):
        protected = {
            "/skills",
            "/skills/reload",
            "/monitor",
            "/debug/profile/{user_id}",
            "/knowledge/add",
            "/knowledge/upload",
            "/knowledge/stats",
            "/eval/run",
        }
        routes = {route.path: route for route in api_main.app.routes}
        for path in protected:
            self.assertTrue(routes[path].dependencies, path)

    def test_sensitive_payloads_are_not_named_in_runtime_logs(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        files = [
            root / "memory" / "conversation_memory.py",
            root / "core" / "skill_loader.py",
            root / "mcp" / "tool_manager.py",
        ]
        source = "\n".join(path.read_text(encoding="utf-8") for path in files)
        self.assertNotIn("PROFILE_EXTRACTED_DATA", source)
        self.assertNotIn("message=%r", source)
        self.assertNotIn("查询改写: {query!r}", source)

    def test_chromadb_telemetry_is_disabled_for_server_and_client(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
        requirements = (root / "requirements.txt").read_text(encoding="utf-8")
        self.assertEqual(2, compose.count("ANONYMIZED_TELEMETRY=FALSE"))
        self.assertIn("posthog==5.4.0", requirements)


class UploadBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.original_manager = api_main._tool_manager
        self.added = []

        class KnowledgeBaseStub:
            doc_count = 0

            def add_documents(inner_self, docs):
                self.added.extend(docs)
                inner_self.doc_count += len(docs)
                return len(docs)

            def search_handler(inner_self):
                return None

        kb = KnowledgeBaseStub()
        tool = SimpleNamespace(handler=kb.search_handler)
        api_main._tool_manager = SimpleNamespace(_tools={"knowledge_search": tool})

    def tearDown(self):
        api_main._tool_manager = self.original_manager

    def test_upload_rejects_unapproved_extension(self):
        upload = UploadFile(filename="payload.exe", file=io.BytesIO(b"data"))
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(api_main.upload_knowledge(upload))
        self.assertEqual(415, ctx.exception.status_code)

    def test_upload_rejects_non_utf8_content(self):
        upload = UploadFile(filename="profile.txt", file=io.BytesIO(b"\xff\xfe"))
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(api_main.upload_knowledge(upload))
        self.assertEqual(400, ctx.exception.status_code)

    def test_upload_sanitizes_filename(self):
        upload = UploadFile(filename="../private/notes.md", file=io.BytesIO("安全说明".encode()))
        result = asyncio.run(api_main.upload_knowledge(upload))
        self.assertEqual("notes", self.added[0]["title"])
        self.assertEqual("文件 notes.md 导入成功", result["message"])


if __name__ == "__main__":
    unittest.main()
