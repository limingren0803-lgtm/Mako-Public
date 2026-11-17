import unittest

from api.main import BANNER, app


class ReleaseMetadataTests(unittest.TestCase):
    def test_fastapi_metadata_reports_v2_10_0(self):
        self.assertEqual("Mako — AI Career Intelligence System", app.title)
        self.assertEqual("2.10.0", app.version)

    def test_cli_banner_reports_v2_10_0(self):
        self.assertIn("Mako  v2.10.0", BANNER)


if __name__ == "__main__":
    unittest.main()
