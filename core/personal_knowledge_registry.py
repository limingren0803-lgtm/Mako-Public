"""Transactional SQLite registry for personal career materials."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from core.personal_knowledge import (
    MaterialCategory,
    MaterialIndexStatus,
    MaterialSection,
    MaterialStatus,
    PersonalMaterial,
    material_payload,
    validate_identifier,
)


PERSONAL_KNOWLEDGE_SCHEMA_VERSION = 1


class PersonalKnowledgeConflictError(ValueError):
    pass


class PersonalKnowledgeNotFoundError(KeyError):
    pass


class PersonalKnowledgeSchemaError(RuntimeError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class PersonalKnowledgeRegistry:
    """Own personal-material metadata and text without opening other Mako stores."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA secure_delete = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS personal_knowledge_schema (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    schema_version INTEGER NOT NULL
                )"""
            )
            row = connection.execute(
                "SELECT schema_version FROM personal_knowledge_schema WHERE singleton = 1"
            ).fetchone()
            if row and int(row["schema_version"]) != PERSONAL_KNOWLEDGE_SCHEMA_VERSION:
                raise PersonalKnowledgeSchemaError(
                    "personal knowledge database requires an explicit migration"
                )
            if not row:
                connection.execute(
                    "INSERT INTO personal_knowledge_schema VALUES (1, ?)",
                    (PERSONAL_KNOWLEDGE_SCHEMA_VERSION,),
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS personal_materials (
                    material_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 200),
                    original_filename TEXT NOT NULL CHECK(length(original_filename) BETWEEN 1 AND 255),
                    file_type TEXT NOT NULL CHECK(file_type IN ('txt','md','pdf','docx')),
                    category TEXT NOT NULL CHECK(category IN ('resume','project','course','note','other')),
                    status TEXT NOT NULL CHECK(status IN ('active','inactive')),
                    index_status TEXT NOT NULL CHECK(index_status IN ('pending','ready','failed')),
                    content_sha256 TEXT NOT NULL UNIQUE CHECK(length(content_sha256) = 64),
                    text_sha256 TEXT NOT NULL CHECK(length(text_sha256) = 64),
                    byte_size INTEGER NOT NULL CHECK(byte_size BETWEEN 1 AND 10485760),
                    character_count INTEGER NOT NULL CHECK(character_count BETWEEN 1 AND 1000000),
                    section_count INTEGER NOT NULL CHECK(section_count BETWEEN 1 AND 100000),
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK(revision >= 1)
                );
                CREATE INDEX IF NOT EXISTS idx_personal_materials_state
                    ON personal_materials(status, index_status, updated_at DESC, material_id);

                CREATE TABLE IF NOT EXISTS material_sections (
                    section_id TEXT PRIMARY KEY,
                    material_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 0 AND 100000),
                    locator_type TEXT NOT NULL CHECK(locator_type IN ('line','page','heading','paragraph','table')),
                    locator_label TEXT NOT NULL CHECK(length(locator_label) BETWEEN 1 AND 200),
                    text TEXT NOT NULL CHECK(length(text) BETWEEN 1 AND 1000000),
                    FOREIGN KEY(material_id) REFERENCES personal_materials(material_id) ON DELETE CASCADE,
                    UNIQUE(material_id, ordinal)
                );
                CREATE INDEX IF NOT EXISTS idx_material_sections_material
                    ON material_sections(material_id, ordinal);

                CREATE TABLE IF NOT EXISTS personal_idempotency_keys (
                    operation TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(operation, idempotency_key)
                );
                """
            )

    @staticmethod
    def _material(row: sqlite3.Row) -> PersonalMaterial:
        return PersonalMaterial.model_validate_json(row["payload"])

    @staticmethod
    def _section(row: sqlite3.Row) -> MaterialSection:
        return MaterialSection.model_validate(dict(row))

    @staticmethod
    def _idempotency_key(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = value.strip()
        if not clean or len(clean) > 128 or not all(
            char.isascii() and (char.isalnum() or char in "_-:.") for char in clean
        ):
            raise ValueError("invalid Idempotency-Key")
        return clean

    def get_material(self, material_id: str) -> Optional[PersonalMaterial]:
        validate_identifier(material_id, "material_id")
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM personal_materials WHERE material_id = ?",
                (material_id,),
            ).fetchone()
        return self._material(row) if row else None

    def find_by_content_hash(self, content_sha256: str) -> Optional[PersonalMaterial]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM personal_materials WHERE content_sha256 = ?",
                (content_sha256,),
            ).fetchone()
        return self._material(row) if row else None

    def list_materials(
        self, *, status: Optional[MaterialStatus] = None,
        category: Optional[MaterialCategory] = None, limit: Optional[int] = 100,
    ) -> list[PersonalMaterial]:
        query = "SELECT payload FROM personal_materials WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status.value)
        if category:
            query += " AND category = ?"
            params.append(category.value)
        query += " ORDER BY updated_at DESC, material_id"
        if limit is not None:
            query += " LIMIT ?"
            params.append(min(max(limit, 1), 500))
        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [self._material(row) for row in rows]

    def list_sections(
        self, material_id: str, *, offset: int = 0, limit: Optional[int] = 100,
    ) -> list[MaterialSection]:
        validate_identifier(material_id, "material_id")
        query = """SELECT section_id, material_id, ordinal, locator_type,
                   locator_label, text FROM material_sections
                   WHERE material_id = ? ORDER BY ordinal"""
        params: list[Any] = [material_id]
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([min(max(limit, 1), 200), max(offset, 0)])
        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [self._section(row) for row in rows]

    def create_material(
        self, material: PersonalMaterial, sections: list[MaterialSection], *,
        idempotency_key: Optional[str], request_hash: str,
    ) -> tuple[PersonalMaterial, bool]:
        if len(sections) != material.section_count or any(
            section.material_id != material.material_id for section in sections
        ):
            raise ValueError("material section contract mismatch")
        key = self._idempotency_key(idempotency_key)
        with self._lock, self._connection() as connection:
            if key:
                row = connection.execute(
                    """SELECT request_hash, resource_id FROM personal_idempotency_keys
                       WHERE operation = 'create_material' AND idempotency_key = ?""",
                    (key,),
                ).fetchone()
                if row:
                    if row["request_hash"] != request_hash:
                        raise PersonalKnowledgeConflictError(
                            "Idempotency-Key was reused with different content"
                        )
                    existing = connection.execute(
                        "SELECT payload FROM personal_materials WHERE material_id = ?",
                        (row["resource_id"],),
                    ).fetchone()
                    if not existing:
                        raise PersonalKnowledgeConflictError("idempotent material no longer exists")
                    return self._material(existing), False
            duplicate = connection.execute(
                "SELECT material_id FROM personal_materials WHERE content_sha256 = ?",
                (material.content_sha256,),
            ).fetchone()
            if duplicate:
                raise PersonalKnowledgeConflictError(
                    f"material content already exists as {duplicate['material_id']}"
                )
            connection.execute(
                """INSERT INTO personal_materials(
                    material_id,title,original_filename,file_type,category,status,index_status,
                    content_sha256,text_sha256,byte_size,character_count,section_count,payload,
                    created_at,updated_at,revision
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    material.material_id, material.title, material.original_filename,
                    material.file_type.value, material.category.value, material.status.value,
                    material.index_status.value, material.content_sha256, material.text_sha256,
                    material.byte_size, material.character_count, material.section_count,
                    _json(material_payload(material)), material.created_at.isoformat(),
                    material.updated_at.isoformat(), material.revision,
                ),
            )
            connection.executemany(
                """INSERT INTO material_sections(
                    section_id,material_id,ordinal,locator_type,locator_label,text
                ) VALUES (?,?,?,?,?,?)""",
                [(
                    section.section_id, section.material_id, section.ordinal,
                    section.locator_type.value, section.locator_label, section.text,
                ) for section in sections],
            )
            if key:
                connection.execute(
                    "INSERT INTO personal_idempotency_keys VALUES ('create_material',?,?,?,?)",
                    (key, request_hash, material.material_id, material.created_at.isoformat()),
                )
        return material, True

    def replace_material(
        self, material: PersonalMaterial, *, expected_revision: int,
    ) -> PersonalMaterial:
        if material.revision != expected_revision + 1:
            raise ValueError("replacement revision must increment by one")
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                """UPDATE personal_materials SET title=?,category=?,status=?,index_status=?,
                   payload=?,updated_at=?,revision=? WHERE material_id=? AND revision=?""",
                (
                    material.title, material.category.value, material.status.value,
                    material.index_status.value, _json(material_payload(material)),
                    material.updated_at.isoformat(), material.revision,
                    material.material_id, expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                exists = connection.execute(
                    "SELECT 1 FROM personal_materials WHERE material_id=?",
                    (material.material_id,),
                ).fetchone()
                if not exists:
                    raise PersonalKnowledgeNotFoundError(material.material_id)
                raise PersonalKnowledgeConflictError("material was updated by another request")
        return material

    def deletion_impact(self, material_id: str, *, vector_count: int) -> dict[str, int]:
        material = self.get_material(material_id)
        if not material:
            raise PersonalKnowledgeNotFoundError(material_id)
        return {"materials": 1, "sections": material.section_count, "vector_chunks": vector_count}

    def delete_material(self, material_id: str, *, expected_revision: int) -> dict[str, int]:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT revision, section_count FROM personal_materials WHERE material_id=?",
                (material_id,),
            ).fetchone()
            if not row:
                raise PersonalKnowledgeNotFoundError(material_id)
            if int(row["revision"]) != expected_revision:
                raise PersonalKnowledgeConflictError("material was updated by another request")
            connection.execute("DELETE FROM personal_materials WHERE material_id=?", (material_id,))
            connection.execute(
                "DELETE FROM personal_idempotency_keys WHERE resource_id=?", (material_id,)
            )
        self._checkpoint()
        return {"materials": 1, "sections": int(row["section_count"])}

    def export_snapshot(self) -> dict[str, Any]:
        items = []
        for material in self.list_materials(limit=None):
            items.append({
                "material": material.model_dump(mode="json"),
                "sections": [item.model_dump(mode="json") for item in self.list_sections(material.material_id, limit=None)],
            })
        return {"schema_version": PERSONAL_KNOWLEDGE_SCHEMA_VERSION, "materials": items}

    def integrity_report(self) -> dict[str, Any]:
        with self._connection() as connection:
            version = connection.execute(
                "SELECT schema_version FROM personal_knowledge_schema WHERE singleton=1"
            ).fetchone()[0]
            integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
            foreign_keys = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
        return {"schema_version": int(version), "integrity": integrity, "foreign_key_errors": foreign_keys}

    def _checkpoint(self) -> None:
        with self._lock, self._connection() as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
