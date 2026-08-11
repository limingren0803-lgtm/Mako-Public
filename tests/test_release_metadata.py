import unittest

from api.main import BANNER, app


class ReleaseMetadataTests(unittest.TestCase):
    def test_fastapi_metadata_reports_v1_8_0(self):
        self.assertEqual("Mako — AI Career Intelligence System", app.title)
        self.assertEqual("1.8.0", app.version)

    def test_cli_banner_reports_v1_8_0(self):
        self.assertIn("Mako  v1.8.0", BANNER)


if __name__ == "__main__":
    unittest.main()
