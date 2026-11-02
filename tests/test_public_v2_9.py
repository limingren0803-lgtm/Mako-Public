import unittest
from pathlib import Path

from mcp.knowledge_source_catalog import OFFICIAL_CAREER_SOURCES_CN


class PublicV29Tests(unittest.TestCase):
    def test_official_source_directory_has_current_public_scope(self):
        self.assertEqual(109, len(OFFICIAL_CAREER_SOURCES_CN))
        self.assertTrue(all(source.get("source_url") for source in OFFICIAL_CAREER_SOURCES_CN))

    def test_unverified_sources_are_not_presented_as_verified_jobs(self):
        verified_summaries = [
            source for source in OFFICIAL_CAREER_SOURCES_CN
            if source.get("recruitment_summary")
        ]
        self.assertGreater(len(verified_summaries), 0)
        self.assertLess(len(verified_summaries), len(OFFICIAL_CAREER_SOURCES_CN))

    def test_public_boundary_copy_is_explicit(self):
        root = Path(__file__).resolve().parents[1]
        expected = (
            "招聘信息来自公开网络及企业官方招聘平台；"
            "目录入口不代表具体岗位已经核验，"
            "实际岗位、条件和截止时间以企业官网为准。"
        )
        self.assertIn(expected, (root / "README.md").read_text(encoding="utf-8"))
        self.assertIn(expected, (root / "ui" / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
