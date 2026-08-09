import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools.persistence_backup import ARCHIVE_SCHEMA_VERSION, VOLUMES, validate_backup


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PersistenceBackupValidationTests(unittest.TestCase):
    def _create_backup(self, root: Path, *, unsafe: bool = False) -> Path:
        archives = {}
        for logical_name, volume_name in VOLUMES.items():
            archive_path = root / f"{logical_name}.tar.gz"
            payload = f"{logical_name}-data".encode()
            member_name = "../escape" if unsafe and logical_name == "redis" else "data/file.txt"
            with tarfile.open(archive_path, "w:gz") as archive:
                info = tarfile.TarInfo(member_name)
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
            with tarfile.open(archive_path, "r:gz") as archive:
                member_count = len(archive.getmembers())
            archives[logical_name] = {
                "source_volume": volume_name,
                "filename": archive_path.name,
                "size_bytes": archive_path.stat().st_size,
                "sha256": _sha256(archive_path),
                "member_count": member_count,
            }

        manifest = {
            "schema_version": ARCHIVE_SCHEMA_VERSION,
            "created_at": "2026-08-10T00:00:00+00:00",
            "compose_project": "echomind",
            "archives": archives,
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        return root

    def test_valid_backup_manifest_and_archives_are_accepted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = self._create_backup(Path(temp_dir))

            manifest = validate_backup(backup_dir)

            self.assertEqual(set(VOLUMES), set(manifest["archives"]))

    def test_modified_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = self._create_backup(Path(temp_dir))
            with (backup_dir / "redis.tar.gz").open("ab") as stream:
                stream.write(b"tampered")

            with self.assertRaisesRegex(ValueError, "size mismatch"):
                validate_backup(backup_dir)

    def test_path_traversal_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = self._create_backup(Path(temp_dir), unsafe=True)

            with self.assertRaisesRegex(ValueError, "Unsafe archive member"):
                validate_backup(backup_dir)


if __name__ == "__main__":
    unittest.main()
