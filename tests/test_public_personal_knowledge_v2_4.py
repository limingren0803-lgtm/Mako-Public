import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document
from fastapi.testclient import TestClient

from api import main as api_main
from api import personal_knowledge as personal_api
from core.material_parser import parse_material
from core.personal_knowledge import MaterialSearchHit
from core.personal_knowledge_registry import PersonalKnowledgeRegistry


def text_pdf(text="Mako career project"):
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, item in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + item + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)


class FakeIndex:
    def __init__(self):
        self.rows = {}

    def index_material(self, material, sections):
        self.rows[material.material_id] = list(sections)
        return len(sections)

    def delete_material(self, material_id):
        self.rows.pop(material_id, None)

    def count_material(self, material_id):
        return len(self.rows.get(material_id, []))

    def search(self, query, *, registry, material_ids=None, top_k=5):
        if "Python" not in query:
            return []
        material = next((item for item in registry.list_materials(limit=None)
                         if not material_ids or item.material_id in material_ids), None)
        if not material or material.status.value != "active":
            return []
        section = registry.list_sections(material.material_id, limit=1)[0]
        return [MaterialSearchHit(
            material_id=material.material_id,
            title=material.title,
            category=material.category,
            section_id=section.section_id,
            locator_type=section.locator_type,
            locator_label=section.locator_label,
            excerpt=section.text,
            distance=0.1,
        )]


class PublicPersonalKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = PersonalKnowledgeRegistry(
            str(Path(self.temp.name) / "personal.sqlite3")
        )
        self.index = FakeIndex()

        async def analyze(payload, request, context):
            return {
                "request_id": "public_request",
                "conv_id": "public_conversation",
                "response": "完成分析",
                "intent": payload["career_intent"],
                "agent_type": "career",
                "review_required": False,
                "latency_ms": 1.0,
            }

        personal_api.configure_personal_knowledge_api(
            self.registry, self.index, analysis_provider=analyze
        )
        self.local_patch = patch(
            "core.workspace_access.is_local_workspace_request", return_value=True
        )
        self.local_patch.start()
        self.client = TestClient(api_main.app)

    def tearDown(self):
        self.client.close()
        self.local_patch.stop()
        self.temp.cleanup()

    def test_supported_formats_have_traceable_locations(self):
        txt = parse_material("resume.txt", "教育经历\n项目经历".encode())
        markdown = parse_material("project.md", "# 项目\n\n完成分析".encode())
        pdf = parse_material("project.pdf", text_pdf())
        document = Document()
        document.add_heading("项目经历", level=1)
        document.add_paragraph("使用 Python 完成分析。")
        output = io.BytesIO()
        document.save(output)
        docx = parse_material("project.docx", output.getvalue())

        self.assertEqual(txt.sections[0].locator_label, "第 1-2 行")
        self.assertEqual(markdown.sections[0].locator_label, "第 1 行")
        self.assertEqual(pdf.sections[0].locator_label, "第 1 页")
        self.assertTrue(any(section.locator_label == "项目经历" for section in docx.sections))

    def test_material_workflow_requires_session_and_preserves_sources(self):
        self.assertEqual(self.client.get("/v2/workspace/materials").status_code, 401)
        self.assertEqual(self.client.post("/v2/workspace/session").status_code, 204)

        preview = self.client.post(
            "/v2/workspace/materials/preview",
            files={"file": ("project.txt", "使用 Python 完成分析。".encode(), "text/plain")},
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(self.registry.list_materials(), [])

        created = self.client.post(
            "/v2/workspace/materials",
            headers={"Idempotency-Key": "public-material"},
            data={"title": "课程项目", "category": "project"},
            files={"file": ("project.txt", "使用 Python 完成分析。".encode(), "text/plain")},
        )
        self.assertEqual(created.status_code, 201, created.text)
        material = created.json()["material"]

        analyzed = self.client.post(
            "/v2/workspace/analyze",
            json={"message": "请分析我的 Python 项目", "career_intent": "career_resume"},
        )
        self.assertEqual(analyzed.status_code, 200, analyzed.text)
        self.assertTrue(analyzed.json()["personal_knowledge_used"])
        self.assertEqual(analyzed.json()["personal_knowledge_sources"][0]["title"], "课程项目")

        deleted = self.client.delete(
            f"/v2/workspace/materials/{material['material_id']}",
            params={
                "revision": material["revision"],
                "confirmation": "DELETE_PERSONAL_MATERIAL",
            },
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)

    def test_material_ui_is_public_and_does_not_use_admin_credentials(self):
        ui_root = Path(api_main.__file__).resolve().parents[1] / "ui"
        html = (ui_root / "index.html").read_text(encoding="utf-8")
        script = (ui_root / "materials.js").read_text(encoding="utf-8")

        self.assertIn('data-page="materials"', html)
        self.assertIn('src="materials.js?v=1"', html)
        self.assertIn('window.MakoWorkspace.fetch("/materials/preview"', script)
        self.assertNotIn("X-Admin-Key", script)


if __name__ == "__main__":
    unittest.main()
