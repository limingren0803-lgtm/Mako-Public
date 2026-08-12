import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from api import main as api_main
from mcp.job_adapters import adapter_for_source
from mcp.knowledge_source_catalog import OFFICIAL_CAREER_SOURCES_CN


class PublicJobIntelligenceTests(unittest.TestCase):
    def test_catalog_covers_domestic_and_multinational_examples(self):
        source_ids = {source["source_id"] for source in OFFICIAL_CAREER_SOURCES_CN}
        self.assertEqual(23, len(OFFICIAL_CAREER_SOURCES_CN))
        self.assertEqual(23, len(source_ids))
        self.assertTrue({
            "src_cn_baidu",
            "src_cn_sap",
            "src_cn_microsoft",
            "src_cn_siemens",
            "src_cn_pg",
            "src_cn_unilever",
            "src_cn_deloitte",
            "src_cn_ey",
            "src_cn_hsbc",
        }.issubset(source_ids))

    def test_representative_sources_use_dedicated_adapters(self):
        self.assertEqual("BaiduJobAdapter", type(adapter_for_source("src_cn_baidu")).__name__)
        self.assertEqual("SapJobAdapter", type(adapter_for_source("src_cn_sap")).__name__)
        self.assertEqual(
            "MicrosoftJobAdapter",
            type(adapter_for_source("src_cn_microsoft")).__name__,
        )

    def test_public_catalog_groups_sources_without_operational_fields(self):
        knowledge_base = Mock()
        knowledge_base.list_sources.return_value = [
            {
                "source_id": "src_cn_baidu",
                "company_name": "百度",
                "official_domain": "talent.baidu.com",
                "source_url": "https://talent.baidu.com/jobs",
                "industry": "互联网与科技",
                "recruitment_channels": ["campus"],
                "support_level": "structured_import",
                "verified_at": "2026-08-11",
                "automation_allowed": False,
            },
            {
                "source_id": "src_cn_hsbc",
                "company_name": "HSBC",
                "official_domain": "portal.careers.hsbc.com",
                "source_url": "https://portal.careers.hsbc.com/careers?location=China",
                "industry": "金融",
                "recruitment_channels": ["experienced"],
                "support_level": "official_directory",
                "verified_at": "2026-08-11",
                "automation_allowed": False,
            },
        ]
        knowledge_base.get_job_source_availability.return_value = {
            "src_cn_baidu": {
                "data_status": "verified_local_data",
                "available_actions": ["verified_local_search", "official_link"],
                "verified_job_count": 10,
                "last_job_verified_at": "2026-08-11T00:00:00+00:00",
            },
            "src_cn_hsbc": {
                "data_status": "official_link_only",
                "available_actions": ["official_link"],
                "verified_job_count": 0,
                "last_job_verified_at": None,
            },
        }

        with patch.object(api_main, "_knowledge_base_instance", return_value=knowledge_base):
            response = TestClient(api_main.app).get("/jobs/sources")

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(2, body["count"])
        self.assertEqual([1, 1], [group["count"] for group in body["capability_groups"]])
        self.assertNotIn("automation_allowed", body["sources"][0])
        self.assertNotIn("health_status", body["sources"][0])


if __name__ == "__main__":
    unittest.main()
