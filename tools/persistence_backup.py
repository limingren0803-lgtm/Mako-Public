"""Create and validate Mako Redis/ChromaDB volume backups.

The restore check always uses newly created temporary Docker volumes. It never
writes to the live V1 volumes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


ARCHIVE_SCHEMA_VERSION = 1
HELPER_IMAGE = "alpine:3.20"
VOLUMES = {
    "redis": "echomind_redis-data",
    "chromadb": "echomind_chromadb-data",
}
TEMP_VOLUME_PREFIX = "mako-restore-check-"


def _run(command: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout.strip() if capture else ""


def _docker_executable() -> str:
    executable = shutil.which("docker")
    if not executable:
        raise RuntimeError("Docker CLI is not available on PATH.")
    return executable


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_members(path: Path) -> list[tarfile.TarInfo]:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
    if not members:
        raise ValueError(f"Backup archive is empty: {path.name}")
    for member in members:
        member_path = PurePosixPath(member.name)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise ValueError(f"Unsafe archive member in {path.name}")
    return members


def validate_backup(backup_dir: Path) -> dict[str, Any]:
    backup_dir = backup_dir.resolve()
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("manifest.json is missing from the backup directory.")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != ARCHIVE_SCHEMA_VERSION:
        raise ValueError("Unsupported backup manifest schema version.")

    archives = manifest.get("archives")
    if not isinstance(archives, dict) or set(archives) != set(VOLUMES):
        raise ValueError("Backup manifest does not contain the expected volumes.")

    for logical_name, metadata in archives.items():
        filename = metadata.get("filename")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError(f"Invalid archive filename for {logical_name}.")
        archive_path = backup_dir / filename
        if not archive_path.is_file():
            raise ValueError(f"Backup archive is missing: {filename}")
        if archive_path.stat().st_size != int(metadata.get("size_bytes", -1)):
            raise ValueError(f"Backup archive size mismatch: {filename}")
        if _sha256(archive_path) != metadata.get("sha256"):
            raise ValueError(f"Backup archive checksum mismatch: {filename}")
        members = _archive_members(archive_path)
        if len(members) != int(metadata.get("member_count", -1)):
            raise ValueError(f"Backup archive member count mismatch: {filename}")

    return manifest


def create_backup(output_root: Path) -> Path:
    docker = _docker_executable()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = (output_root / f"mako-persistence-{timestamp}").resolve()
    backup_dir.mkdir(parents=True, exist_ok=False)

    manifest: dict[str, Any] = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "compose_project": "echomind",
        "archives": {},
    }

    try:
        for logical_name, volume_name in VOLUMES.items():
            _run([docker, "volume", "inspect", volume_name], capture=True)
            attached = _run(
                [docker, "ps", "--filter", f"volume={volume_name}", "--format", "{{.Names}}"],
                capture=True,
            )
            if attached:
                raise RuntimeError(
                    f"Volume {volume_name} is attached to a running container. "
                    "Stop the Mako application and data services before backup."
                )

            filename = f"{logical_name}.tar.gz"
            _run(
                [
                    docker,
                    "run",
                    "--rm",
                    "--volume",
                    f"{volume_name}:/source:ro",
                    "--volume",
                    f"{backup_dir}:/backup",
                    HELPER_IMAGE,
                    "tar",
                    "-czf",
                    f"/backup/{filename}",
                    "-C",
                    "/source",
                    ".",
                ]
            )
            archive_path = backup_dir / filename
            manifest["archives"][logical_name] = {
                "source_volume": volume_name,
                "filename": filename,
                "size_bytes": archive_path.stat().st_size,
                "sha256": _sha256(archive_path),
                "member_count": len(_archive_members(archive_path)),
            }

        (backup_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        validate_backup(backup_dir)
        return backup_dir
    except Exception:
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise


def restore_check(backup_dir: Path) -> None:
    manifest = validate_backup(backup_dir)
    docker = _docker_executable()
    run_id = uuid.uuid4().hex[:12]
    created_volumes: list[str] = []

    try:
        for logical_name, metadata in manifest["archives"].items():
            temp_volume = f"{TEMP_VOLUME_PREFIX}{run_id}-{logical_name}"
            if not temp_volume.startswith(TEMP_VOLUME_PREFIX):
                raise RuntimeError("Refusing to create an unexpected temporary volume name.")
            _run([docker, "volume", "create", temp_volume], capture=True)
            created_volumes.append(temp_volume)
            _run(
                [
                    docker,
                    "run",
                    "--rm",
                    "--volume",
                    f"{temp_volume}:/restore",
                    "--volume",
                    f"{backup_dir.resolve()}:/backup:ro",
                    HELPER_IMAGE,
                    "tar",
                    "-xzf",
                    f"/backup/{metadata['filename']}",
                    "-C",
                    "/restore",
                ]
            )
            restored_entry = _run(
                [
                    docker,
                    "run",
                    "--rm",
                    "--volume",
                    f"{temp_volume}:/restore:ro",
                    HELPER_IMAGE,
                    "find",
                    "/restore",
                    "-mindepth",
                    "1",
                    "-print",
                    "-quit",
                ],
                capture=True,
            )
            if not restored_entry:
                raise RuntimeError(f"Restore check produced an empty {logical_name} volume.")
    finally:
        for volume_name in reversed(created_volumes):
            if volume_name.startswith(TEMP_VOLUME_PREFIX):
                subprocess.run(
                    [docker, "volume", "rm", volume_name],
                    check=False,
                    text=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Back up and validate Mako Redis/ChromaDB Docker volumes."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Create a cold backup.")
    backup_parser.add_argument("--output", type=Path, default=Path("backups"))

    for command in ("verify", "restore-check"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("backup_dir", type=Path)

    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "backup":
        backup_dir = create_backup(args.output)
        print(f"Backup created and verified: {backup_dir}")
    elif args.command == "verify":
        validate_backup(args.backup_dir)
        print("Backup manifest, checksums, and archives are valid.")
    else:
        restore_check(args.backup_dir)
        print("Restore check passed in isolated temporary Docker volumes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
