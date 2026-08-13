"""Persistent source and document lifecycle metadata for the Mako knowledge base."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class KnowledgeRegistry:
    """SQLite registry for sources, documents, versions, and audit events."""

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
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS sources (
                    source_id TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    official_domain TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    delegated_domains TEXT NOT NULL DEFAULT '[]',
                    source_type TEXT NOT NULL DEFAULT 'company_careers',
                    refresh_policy TEXT NOT NULL DEFAULT 'manual',
                    automation_allowed INTEGER NOT NULL DEFAULT 0,
                    policy_url TEXT,
                    industry TEXT,
                    recruitment_channels TEXT NOT NULL DEFAULT '[]',
                    support_level TEXT NOT NULL DEFAULT 'official_directory',
                    verified_at TEXT,
                    health_status TEXT NOT NULL DEFAULT 'unknown',
                    last_checked_at TEXT,
                    last_success_at TEXT,
                    last_failure_at TEXT,
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    last_error_type TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    source_id TEXT,
                    external_id TEXT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    current_version_id TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_verified_at TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES sources(source_id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_source_external
                    ON documents(source_id, external_id)
                    WHERE source_id IS NOT NULL AND external_id IS NOT NULL;
                CREATE TABLE IF NOT EXISTS versions (
                    version_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_url TEXT,
                    fetched_at TEXT NOT NULL,
                    published_at TEXT,
                    validation_status TEXT NOT NULL DEFAULT 'staged',
                    validation_notes TEXT NOT NULL DEFAULT '[]',
                    FOREIGN KEY(document_id) REFERENCES documents(document_id),
                    UNIQUE(document_id, version_number),
                    UNIQUE(document_id, content_hash)
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_postings (
                    job_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    current_version_id TEXT,
                    pending_version_id TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    last_verified_at TEXT,
                    freshness_status TEXT NOT NULL DEFAULT 'fresh',
                    expires_at TEXT,
                    FOREIGN KEY(source_id) REFERENCES sources(source_id),
                    UNIQUE(source_id, external_id)
                );
                CREATE INDEX IF NOT EXISTS idx_job_postings_source_status
                    ON job_postings(source_id, status);
                CREATE TABLE IF NOT EXISTS job_versions (
                    job_version_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    job_source_url TEXT,
                    fetched_at TEXT NOT NULL,
                    published_at TEXT,
                    validation_status TEXT NOT NULL DEFAULT 'active',
                    review_status TEXT NOT NULL DEFAULT 'approved',
                    review_notes TEXT NOT NULL DEFAULT '[]',
                    reviewed_at TEXT,
                    FOREIGN KEY(job_id) REFERENCES job_postings(job_id),
                    UNIQUE(job_id, version_number),
                    UNIQUE(job_id, content_hash)
                );
                CREATE TABLE IF NOT EXISTS job_refresh_tasks (
                    task_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    source_url TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 1,
                    result_summary TEXT NOT NULL DEFAULT '{}',
                    error_type TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY(source_id) REFERENCES sources(source_id)
                );
                CREATE INDEX IF NOT EXISTS idx_job_refresh_tasks_status_created
                    ON job_refresh_tasks(status, created_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_job_refresh_tasks_one_open_source
                    ON job_refresh_tasks(source_id)
                    WHERE status IN ('queued', 'running');
                """
            )
            source_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(sources)").fetchall()
            }
            if "automation_allowed" not in source_columns:
                connection.execute(
                    "ALTER TABLE sources ADD COLUMN automation_allowed INTEGER NOT NULL DEFAULT 0"
                )
            if "policy_url" not in source_columns:
                connection.execute("ALTER TABLE sources ADD COLUMN policy_url TEXT")
            if "job_source_url" not in source_columns:
                connection.execute("ALTER TABLE sources ADD COLUMN job_source_url TEXT")
            if "industry" not in source_columns:
                connection.execute("ALTER TABLE sources ADD COLUMN industry TEXT")
            if "recruitment_channels" not in source_columns:
                connection.execute(
                    "ALTER TABLE sources ADD COLUMN recruitment_channels TEXT NOT NULL DEFAULT '[]'"
                )
            if "support_level" not in source_columns:
                connection.execute(
                    "ALTER TABLE sources ADD COLUMN support_level TEXT NOT NULL DEFAULT 'official_directory'"
                )
            if "verified_at" not in source_columns:
                connection.execute("ALTER TABLE sources ADD COLUMN verified_at TEXT")
            if "health_status" not in source_columns:
                connection.execute(
                    "ALTER TABLE sources ADD COLUMN health_status TEXT NOT NULL DEFAULT 'unknown'"
                )
            if "last_checked_at" not in source_columns:
                connection.execute("ALTER TABLE sources ADD COLUMN last_checked_at TEXT")
            if "last_success_at" not in source_columns:
                connection.execute("ALTER TABLE sources ADD COLUMN last_success_at TEXT")
            if "last_failure_at" not in source_columns:
                connection.execute("ALTER TABLE sources ADD COLUMN last_failure_at TEXT")
            if "consecutive_failures" not in source_columns:
                connection.execute(
                    "ALTER TABLE sources ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0"
                )
            if "last_error_type" not in source_columns:
                connection.execute("ALTER TABLE sources ADD COLUMN last_error_type TEXT")

            job_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(job_postings)").fetchall()
            }
            if "pending_version_id" not in job_columns:
                connection.execute("ALTER TABLE job_postings ADD COLUMN pending_version_id TEXT")
            if "last_verified_at" not in job_columns:
                connection.execute("ALTER TABLE job_postings ADD COLUMN last_verified_at TEXT")
            if "freshness_status" not in job_columns:
                connection.execute(
                    "ALTER TABLE job_postings ADD COLUMN freshness_status TEXT NOT NULL DEFAULT 'fresh'"
                )
            connection.execute(
                "UPDATE job_postings SET last_verified_at = COALESCE(last_verified_at, last_seen_at)"
            )

            version_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(job_versions)").fetchall()
            }
            if "review_status" not in version_columns:
                connection.execute(
                    "ALTER TABLE job_versions ADD COLUMN review_status TEXT NOT NULL DEFAULT 'approved'"
                )
            if "review_notes" not in version_columns:
                connection.execute(
                    "ALTER TABLE job_versions ADD COLUMN review_notes TEXT NOT NULL DEFAULT '[]'"
                )
            if "reviewed_at" not in version_columns:
                connection.execute("ALTER TABLE job_versions ADD COLUMN reviewed_at TEXT")
            connection.execute(
                """
                UPDATE job_versions
                SET reviewed_at = COALESCE(reviewed_at, fetched_at)
                WHERE review_status = 'approved'
                """
            )

    def register_source(
        self,
        *,
        company_name: str,
        official_domain: str,
        source_url: str,
        job_source_url: Optional[str] = None,
        delegated_domains: Optional[List[str]] = None,
        source_type: str = "company_careers",
        refresh_policy: str = "manual",
        automation_allowed: bool = False,
        policy_url: Optional[str] = None,
        industry: Optional[str] = None,
        recruitment_channels: Optional[List[str]] = None,
        support_level: str = "official_directory",
        verified_at: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _utc_now()
        source_id = source_id or f"src_{uuid.uuid4().hex[:16]}"
        delegated = sorted(set(delegated_domains or []))
        channels = sorted(set(recruitment_channels or []))
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO sources (
                    source_id, company_name, official_domain, source_url, job_source_url,
                    delegated_domains, source_type, refresh_policy,
                    automation_allowed, policy_url, industry, recruitment_channels,
                    support_level, verified_at, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    source_id,
                    company_name,
                    official_domain,
                    source_url,
                    job_source_url,
                    json.dumps(delegated, ensure_ascii=False),
                    source_type,
                    refresh_policy,
                    int(automation_allowed),
                    policy_url,
                    industry,
                    json.dumps(channels, ensure_ascii=False),
                    support_level,
                    verified_at,
                    now,
                    now,
                ),
            )
        self.record_event("source_registered", "source", source_id, "success")
        return self.get_source(source_id) or {}

    def ensure_source(self, **kwargs: Any) -> Dict[str, Any]:
        """Create a stable catalog source once without overwriting operator changes."""
        source_id = kwargs.get("source_id")
        if not source_id:
            raise ValueError("catalog sources require a stable source_id")
        existing = self.get_source(source_id)
        if existing:
            updates: Dict[str, Any] = {}
            job_source_url = kwargs.get("job_source_url")
            if job_source_url and not existing.get("job_source_url"):
                updates["job_source_url"] = job_source_url
            for key in ("industry", "support_level", "verified_at"):
                if kwargs.get(key) and kwargs.get(key) != existing.get(key):
                    updates[key] = kwargs[key]
            channels = sorted(set(kwargs.get("recruitment_channels") or []))
            if channels and channels != existing.get("recruitment_channels"):
                updates["recruitment_channels"] = json.dumps(channels, ensure_ascii=False)
            if updates:
                assignments = ", ".join(f"{key} = ?" for key in updates)
                with self._lock, self._connection() as connection:
                    connection.execute(
                        f"UPDATE sources SET {assignments}, updated_at = ? WHERE source_id = ?",
                        (*updates.values(), _utc_now(), source_id),
                    )
                return self.get_source(source_id) or existing
            return existing
        try:
            return self.register_source(**kwargs)
        except sqlite3.IntegrityError:
            existing = self.get_source(source_id)
            if existing:
                return existing
            raise

    def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM sources WHERE source_id = ?", (source_id,)
            ).fetchone()
        return self._source_row(row) if row else None

    def list_sources(
        self,
        status: Optional[str] = None,
        *,
        industry: Optional[str] = None,
        support_level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM sources"
        clauses: List[str] = []
        params: List[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if industry:
            clauses.append("industry = ?")
            params.append(industry)
        if support_level:
            clauses.append("support_level = ?")
            params.append(support_level)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY company_name, source_id"
        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [self._source_row(row) for row in rows]

    def get_job_source_availability(
        self,
        *,
        source_ids: Optional[List[str]] = None,
        max_age_days: int = 30,
        as_of: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Describe safe user-facing actions from current approved local data."""
        if not 1 <= max_age_days <= 90:
            raise ValueError("job max age must be between 1 and 90 days")

        now = datetime.fromisoformat(as_of) if as_of else datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        cutoff = (now - timedelta(days=max_age_days)).isoformat()
        query = """
            SELECT
                s.source_id,
                COUNT(CASE
                    WHEN p.status = 'active'
                     AND p.current_version_id IS NOT NULL
                     AND p.last_verified_at IS NOT NULL
                     AND p.last_verified_at >= ?
                     AND (p.expires_at IS NULL OR p.expires_at > ?)
                    THEN 1
                END) AS verified_job_count,
                MAX(CASE
                    WHEN p.status = 'active'
                     AND p.current_version_id IS NOT NULL
                     AND p.last_verified_at IS NOT NULL
                     AND p.last_verified_at >= ?
                     AND (p.expires_at IS NULL OR p.expires_at > ?)
                    THEN p.last_verified_at
                END) AS last_job_verified_at
            FROM sources AS s
            LEFT JOIN job_postings AS p ON p.source_id = s.source_id
            WHERE s.status = 'active'
        """
        params: List[Any] = [cutoff, now.isoformat(), cutoff, now.isoformat()]
        if source_ids is not None:
            if not source_ids:
                return {}
            placeholders = ",".join("?" for _ in source_ids)
            query += f" AND s.source_id IN ({placeholders})"
            params.extend(source_ids)
        query += " GROUP BY s.source_id ORDER BY s.source_id"

        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        availability: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            verified_job_count = int(row["verified_job_count"] or 0)
            actions = ["official_link"]
            if verified_job_count:
                actions.insert(0, "verified_local_search")
            availability[row["source_id"]] = {
                "data_status": (
                    "verified_local_data" if verified_job_count else "official_link_only"
                ),
                "available_actions": actions,
                "verified_job_count": verified_job_count,
                "last_job_verified_at": row["last_job_verified_at"],
            }
        return availability

    def set_source_status(self, source_id: str, status: str) -> Dict[str, Any]:
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                "UPDATE sources SET status = ?, updated_at = ? WHERE source_id = ?",
                (status, _utc_now(), source_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(source_id)
        self.record_event("source_status_changed", "source", source_id, "success", {"status": status})
        return self.get_source(source_id) or {}

    def set_source_policy(
        self,
        source_id: str,
        *,
        refresh_policy: str,
        automation_allowed: bool,
        policy_url: Optional[str],
    ) -> Dict[str, Any]:
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE sources
                SET refresh_policy = ?, automation_allowed = ?, policy_url = ?, updated_at = ?
                WHERE source_id = ?
                """,
                (
                    refresh_policy,
                    int(automation_allowed),
                    policy_url,
                    _utc_now(),
                    source_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(source_id)
        self.record_event(
            "source_policy_changed",
            "source",
            source_id,
            "success",
            {
                "refresh_policy": refresh_policy,
                "automation_allowed": automation_allowed,
                "policy_url": policy_url,
            },
        )
        return self.get_source(source_id) or {}

    def ensure_document(
        self,
        *,
        title: str,
        source_id: Optional[str] = None,
        external_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _utc_now()
        with self._lock, self._connection() as connection:
            if source_id and external_id:
                existing = connection.execute(
                    "SELECT * FROM documents WHERE source_id = ? AND external_id = ?",
                    (source_id, external_id),
                ).fetchone()
                if existing:
                    connection.execute(
                        "UPDATE documents SET title = ?, last_verified_at = ? WHERE document_id = ?",
                        (title, now, existing["document_id"]),
                    )
                    document_id = existing["document_id"]
                else:
                    document_id = document_id or f"doc_{uuid.uuid4().hex[:16]}"
            else:
                document_id = document_id or f"doc_{uuid.uuid4().hex[:16]}"

            row = connection.execute(
                "SELECT document_id FROM documents WHERE document_id = ?", (document_id,)
            ).fetchone()
            if not row:
                connection.execute(
                    """
                    INSERT INTO documents (
                        document_id, source_id, external_id, title, status,
                        first_seen_at, last_verified_at
                    ) VALUES (?, ?, ?, ?, 'active', ?, ?)
                    """,
                    (document_id, source_id, external_id, title, now, now),
                )
            else:
                connection.execute(
                    "UPDATE documents SET title = ?, last_verified_at = ? WHERE document_id = ?",
                    (title, now, document_id),
                )
        return self.get_document(document_id) or {}

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT d.*, v.version_number, v.content_hash, v.source_url,
                       v.fetched_at, v.published_at
                FROM documents d
                LEFT JOIN versions v ON v.version_id = d.current_version_id
                WHERE d.document_id = ?
                """,
                (document_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_documents(
        self,
        *,
        source_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if source_id:
            clauses.append("d.source_id = ?")
            params.append(source_id)
        if status:
            clauses.append("d.status = ?")
            params.append(status)
        query = """
            SELECT d.*, v.version_number, v.content_hash, v.source_url,
                   v.fetched_at, v.published_at
            FROM documents d
            LEFT JOIN versions v ON v.version_id = d.current_version_id
        """
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY d.last_verified_at DESC, d.document_id"
        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def stage_version(
        self,
        *,
        document_id: str,
        content: str,
        content_hash: str,
        source_url: Optional[str] = None,
        validation_notes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        now = _utc_now()
        with self._lock, self._connection() as connection:
            duplicate = connection.execute(
                "SELECT * FROM versions WHERE document_id = ? AND content_hash = ?",
                (document_id, content_hash),
            ).fetchone()
            if duplicate:
                connection.execute(
                    "UPDATE documents SET last_verified_at = ? WHERE document_id = ?",
                    (now, document_id),
                )
                result = dict(duplicate)
                result["duplicate"] = True
                return result
            next_number = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 FROM versions WHERE document_id = ?",
                (document_id,),
            ).fetchone()[0]
            version_id = f"ver_{uuid.uuid4().hex[:16]}"
            connection.execute(
                """
                INSERT INTO versions (
                    version_id, document_id, version_number, content_hash,
                    content, source_url, fetched_at, validation_status,
                    validation_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'staged', ?)
                """,
                (
                    version_id,
                    document_id,
                    next_number,
                    content_hash,
                    content,
                    source_url,
                    now,
                    json.dumps(validation_notes or [], ensure_ascii=False),
                ),
            )
        return self.get_version(version_id) or {}

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM versions WHERE version_id = ?", (version_id,)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["validation_notes"] = json.loads(result.get("validation_notes") or "[]")
        return result

    def list_versions(self, document_id: str) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM versions WHERE document_id = ? ORDER BY version_number DESC",
                (document_id,),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["validation_notes"] = json.loads(item.get("validation_notes") or "[]")
            results.append(item)
        return results

    def activate_version(self, document_id: str, version_id: str) -> Dict[str, Any]:
        now = _utc_now()
        with self._lock, self._connection() as connection:
            version = connection.execute(
                "SELECT document_id FROM versions WHERE version_id = ?", (version_id,)
            ).fetchone()
            if not version or version["document_id"] != document_id:
                raise KeyError(version_id)
            connection.execute(
                "UPDATE versions SET validation_status = 'superseded' WHERE document_id = ? AND validation_status = 'active'",
                (document_id,),
            )
            connection.execute(
                "UPDATE versions SET validation_status = 'active', published_at = COALESCE(published_at, ?) WHERE version_id = ?",
                (now, version_id),
            )
            connection.execute(
                """
                UPDATE documents
                SET current_version_id = ?, status = 'active', last_verified_at = ?
                WHERE document_id = ?
                """,
                (version_id, now, document_id),
            )
        self.record_event("version_activated", "document", document_id, "success", {"version_id": version_id})
        return self.get_document(document_id) or {}

    def set_document_status(self, document_id: str, status: str) -> Dict[str, Any]:
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                "UPDATE documents SET status = ?, last_verified_at = ? WHERE document_id = ?",
                (status, _utc_now(), document_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(document_id)
        self.record_event("document_status_changed", "document", document_id, "success", {"status": status})
        return self.get_document(document_id) or {}

    def upsert_job_posting(
        self,
        posting: Any,
        *,
        review_status: str = "approved",
    ) -> Dict[str, Any]:
        """Insert a posting while keeping unreviewed versions out of retrieval."""
        from core.job_posting import JobPosting
        from mcp.knowledge_sources import SourceSecurityError, validate_source_url

        if review_status not in {"approved", "pending"}:
            raise ValueError("invalid job review status")
        if not isinstance(posting, JobPosting):
            posting = JobPosting.model_validate(posting)
        content_hash = posting.content_hash()
        payload = posting.model_dump_json()
        fetched_at = posting.fetched_at.isoformat()
        published_at = posting.published_at.isoformat() if posting.published_at else None
        expires_at = posting.valid_through.isoformat() if posting.valid_through else None
        reviewed_at = _utc_now() if review_status == "approved" else None

        with self._lock, self._connection() as connection:
            source = connection.execute(
                "SELECT * FROM sources WHERE source_id = ? AND status = 'active'",
                (posting.source_id,),
            ).fetchone()
            if not source:
                raise KeyError(posting.source_id)
            allowed_domains = [
                source["official_domain"],
                *json.loads(source["delegated_domains"] or "[]"),
            ]
            validate_source_url(posting.source_url, allowed_domains)
            if posting.company_name != source["company_name"]:
                raise SourceSecurityError("job company does not match the registered source")

            job = connection.execute(
                "SELECT * FROM job_postings WHERE source_id = ? AND external_id = ?",
                (posting.source_id, posting.external_id),
            ).fetchone()
            if job:
                job_id = job["job_id"]
                current_version_id = job["current_version_id"]
            else:
                job_id = f"job_{uuid.uuid4().hex[:16]}"
                current_version_id = None
                connection.execute(
                    """
                    INSERT INTO job_postings (
                        job_id, source_id, external_id, company_name, title,
                        status, first_seen_at, last_seen_at, last_verified_at,
                        freshness_status, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'fresh', ?)
                    """,
                    (
                        job_id,
                        posting.source_id,
                        posting.external_id,
                        posting.company_name,
                        posting.title,
                        posting.status.value if review_status == "approved" else "inactive",
                        fetched_at,
                        fetched_at,
                        fetched_at if review_status == "approved" else None,
                        expires_at,
                    ),
                )

            duplicate = connection.execute(
                """
                SELECT job_version_id, version_number, review_status, validation_status
                FROM job_versions WHERE job_id = ? AND content_hash = ?
                """,
                (job_id, content_hash),
            ).fetchone()
            if duplicate:
                changed = False
                version_id = duplicate["job_version_id"]
                version_number = duplicate["version_number"]
                if duplicate["review_status"] == "approved":
                    connection.execute(
                        """
                        UPDATE job_postings
                        SET company_name = ?, title = ?, status = ?, last_seen_at = ?,
                            last_verified_at = ?, freshness_status = 'fresh', expires_at = ?
                        WHERE job_id = ?
                        """,
                        (
                            posting.company_name,
                            posting.title,
                            posting.status.value,
                            fetched_at,
                            fetched_at,
                            expires_at,
                            job_id,
                        ),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE job_postings
                        SET pending_version_id = ?, last_seen_at = ?, expires_at = ?
                        WHERE job_id = ?
                        """,
                        (version_id, fetched_at, expires_at, job_id),
                    )
            else:
                version_number = connection.execute(
                    "SELECT COALESCE(MAX(version_number), 0) + 1 FROM job_versions WHERE job_id = ?",
                    (job_id,),
                ).fetchone()[0]
                version_id = f"jobver_{uuid.uuid4().hex[:16]}"
                validation_status = "active" if review_status == "approved" else "staged"
                connection.execute(
                    """
                    INSERT INTO job_versions (
                        job_version_id, job_id, version_number, content_hash,
                        payload, source_url, fetched_at, published_at, validation_status,
                        review_status, reviewed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version_id,
                        job_id,
                        version_number,
                        content_hash,
                        payload,
                        posting.source_url,
                        fetched_at,
                        published_at,
                        validation_status,
                        review_status,
                        reviewed_at,
                    ),
                )
                if review_status == "approved":
                    connection.execute(
                        """
                        UPDATE job_versions
                        SET validation_status = 'superseded'
                        WHERE job_id = ? AND validation_status = 'active'
                          AND job_version_id <> ?
                        """,
                        (job_id, version_id),
                    )
                    connection.execute(
                        """
                        UPDATE job_postings
                        SET company_name = ?, title = ?, status = ?, current_version_id = ?,
                            pending_version_id = NULL, last_seen_at = ?, last_verified_at = ?,
                            freshness_status = 'fresh', expires_at = ?
                        WHERE job_id = ?
                        """,
                        (
                            posting.company_name,
                            posting.title,
                            posting.status.value,
                            version_id,
                            fetched_at,
                            fetched_at,
                            expires_at,
                            job_id,
                        ),
                    )
                else:
                    previous_pending = connection.execute(
                        "SELECT pending_version_id FROM job_postings WHERE job_id = ?",
                        (job_id,),
                    ).fetchone()[0]
                    if previous_pending and previous_pending != version_id:
                        connection.execute(
                            """
                            UPDATE job_versions
                            SET validation_status = 'superseded', review_status = 'rejected',
                                review_notes = ?, reviewed_at = ?
                            WHERE job_version_id = ? AND review_status = 'pending'
                            """,
                            (
                                json.dumps(["superseded_by_newer_pending_version"]),
                                _utc_now(),
                                previous_pending,
                            ),
                        )
                    connection.execute(
                        """
                        UPDATE job_postings
                        SET pending_version_id = ?, last_seen_at = ?, expires_at = ?,
                            status = CASE WHEN current_version_id IS NULL THEN 'inactive' ELSE status END
                        WHERE job_id = ?
                        """,
                        (version_id, fetched_at, expires_at, job_id),
                    )
                changed = True

        self.record_event(
            (
                "job_version_activated"
                if changed and review_status == "approved"
                else "job_version_staged"
                if changed
                else "job_seen_unchanged"
            ),
            "job_posting",
            job_id,
            "success",
            {
                "job_version_id": version_id,
                "source_id": posting.source_id,
                "review_status": review_status,
            },
        )
        result = self.get_job_posting(job_id) or {}
        result["changed"] = changed
        result["submitted_version_id"] = version_id
        result["submitted_version_number"] = version_number
        result["review_status"] = duplicate["review_status"] if duplicate else review_status
        result["previous_active_version_preserved"] = bool(
            review_status == "pending" and current_version_id
        )
        return result

    def get_job_posting(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT j.*, v.version_number, v.content_hash, v.payload,
                       v.source_url, v.fetched_at, v.published_at,
                       v.validation_status, v.review_status, v.review_notes, v.reviewed_at
                FROM job_postings j
                LEFT JOIN job_versions v ON v.job_version_id = j.current_version_id
                WHERE j.job_id = ?
                """,
                (job_id,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["payload"] = json.loads(result["payload"]) if result.get("payload") else None
        result["review_notes"] = json.loads(result.get("review_notes") or "[]")
        return result

    def get_current_approved_job_version(
        self,
        *,
        job_id: str,
        version_id: str,
        max_age_days: int = 30,
        as_of: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return one current approved version or no result for any other state."""
        if not 1 <= max_age_days <= 90:
            raise ValueError("max_age_days must be between 1 and 90")
        now = (
            datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            if as_of
            else datetime.now(timezone.utc)
        )
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        cutoff = now - timedelta(days=max_age_days)
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT j.job_id, j.source_id, j.external_id, j.company_name, j.title,
                       j.status, j.current_version_id, j.last_verified_at,
                       j.freshness_status, j.expires_at,
                       v.job_version_id, v.version_number, v.content_hash, v.payload,
                       v.source_url, v.fetched_at, v.published_at,
                       v.validation_status, v.review_status, v.reviewed_at
                FROM job_postings AS j
                JOIN job_versions AS v ON v.job_version_id = j.current_version_id
                WHERE j.job_id = ?
                  AND v.job_version_id = ?
                  AND j.status = 'active'
                  AND v.review_status = 'approved'
                  AND v.validation_status = 'active'
                """,
                (job_id, version_id),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        last_verified_at = result.get("last_verified_at")
        if not last_verified_at:
            return None
        try:
            verified = datetime.fromisoformat(
                str(last_verified_at).replace("Z", "+00:00")
            )
        except ValueError:
            return None
        if verified.tzinfo is None:
            verified = verified.replace(tzinfo=timezone.utc)
        if verified < cutoff:
            return None
        expires_at = result.get("expires_at")
        if expires_at:
            try:
                expires = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            except ValueError:
                return None
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= now:
                return None
        result["payload"] = json.loads(result["payload"])
        return result

    def list_pending_job_versions(
        self,
        *,
        source_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return staged job versions awaiting an operator decision."""
        limit = min(max(limit, 1), 500)
        query = """
            SELECT j.job_id, j.source_id, j.external_id, j.company_name, j.title,
                   j.current_version_id, j.pending_version_id, s.official_domain,
                   v.job_version_id, v.version_number, v.content_hash, v.payload,
                   v.source_url, v.fetched_at, v.published_at, v.validation_status,
                   v.review_status, v.review_notes, v.reviewed_at
            FROM job_versions v
            JOIN job_postings j ON j.job_id = v.job_id
            JOIN sources s ON s.source_id = j.source_id
            WHERE v.review_status = 'pending' AND v.validation_status = 'staged'
        """
        params: List[Any] = []
        if source_id:
            query += " AND j.source_id = ?"
            params.append(source_id)
        query += " ORDER BY v.fetched_at, v.job_version_id LIMIT ?"
        params.append(limit)
        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item["payload"])
            item["review_notes"] = json.loads(item.get("review_notes") or "[]")
            results.append(item)
        return results

    def review_job_version(
        self,
        *,
        job_id: str,
        version_id: str,
        decision: str,
        notes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Approve or reject one staged version without exposing it beforehand."""
        if decision not in {"approved", "rejected"}:
            raise ValueError("invalid job review decision")
        clean_notes = [str(note).strip() for note in (notes or []) if str(note).strip()]
        reviewed_at = _utc_now()
        with self._lock, self._connection() as connection:
            job = connection.execute(
                "SELECT * FROM job_postings WHERE job_id = ?", (job_id,)
            ).fetchone()
            if not job:
                raise KeyError(job_id)
            version = connection.execute(
                "SELECT * FROM job_versions WHERE job_version_id = ? AND job_id = ?",
                (version_id, job_id),
            ).fetchone()
            if not version:
                raise KeyError(version_id)
            if version["review_status"] != "pending" or version["validation_status"] != "staged":
                raise ValueError("job version is not pending review")

            if decision == "approved":
                payload = json.loads(version["payload"])
                connection.execute(
                    """
                    UPDATE job_versions SET validation_status = 'superseded'
                    WHERE job_id = ? AND validation_status = 'active'
                    """,
                    (job_id,),
                )
                connection.execute(
                    """
                    UPDATE job_versions
                    SET validation_status = 'active', review_status = 'approved',
                        review_notes = ?, reviewed_at = ?
                    WHERE job_version_id = ?
                    """,
                    (json.dumps(clean_notes, ensure_ascii=False), reviewed_at, version_id),
                )
                connection.execute(
                    """
                    UPDATE job_postings
                    SET company_name = ?, title = ?, status = ?, current_version_id = ?,
                        pending_version_id = NULL, last_verified_at = ?,
                        freshness_status = 'fresh', expires_at = ?
                    WHERE job_id = ?
                    """,
                    (
                        payload["company_name"], payload["title"], payload["status"],
                        version_id, reviewed_at, payload.get("valid_through"), job_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE job_versions
                    SET validation_status = 'rejected', review_status = 'rejected',
                        review_notes = ?, reviewed_at = ?
                    WHERE job_version_id = ?
                    """,
                    (json.dumps(clean_notes, ensure_ascii=False), reviewed_at, version_id),
                )
                connection.execute(
                    """
                    UPDATE job_postings
                    SET pending_version_id = CASE WHEN pending_version_id = ? THEN NULL
                                                  ELSE pending_version_id END
                    WHERE job_id = ?
                    """,
                    (version_id, job_id),
                )
        self.record_event(
            "job_version_reviewed", "job_posting", job_id, decision,
            {"job_version_id": version_id, "notes_count": len(clean_notes)},
        )
        result = self.get_job_posting(job_id) or {}
        result["reviewed_version_id"] = version_id
        result["decision"] = decision
        return result

    def review_job_versions_batch(
        self,
        reviews: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Preflight and apply explicit decisions for a bounded review batch."""
        if not reviews:
            raise ValueError("job review batch must contain at least one decision")
        if len(reviews) > 50:
            raise ValueError("job review batch exceeds the 50-decision limit")

        seen = set()
        with self._lock, self._connection() as connection:
            for index, review in enumerate(reviews):
                job_id = str(review.get("job_id") or "")
                version_id = str(review.get("version_id") or "")
                decision = str(review.get("decision") or "")
                key = (job_id, version_id)
                if key in seen:
                    raise ValueError(f"job review batch item {index} is duplicated")
                seen.add(key)
                if decision not in {"approved", "rejected"}:
                    raise ValueError(f"job review batch item {index} has an invalid decision")
                pending = connection.execute(
                    """
                    SELECT 1
                    FROM job_versions v
                    JOIN job_postings j ON j.job_id = v.job_id
                    WHERE v.job_id = ? AND v.job_version_id = ?
                      AND v.review_status = 'pending'
                      AND v.validation_status = 'staged'
                      AND j.pending_version_id = v.job_version_id
                    """,
                    (job_id, version_id),
                ).fetchone()
                if not pending:
                    raise ValueError(f"job review batch item {index} is not pending")

        results = [
            self.review_job_version(
                job_id=review["job_id"],
                version_id=review["version_id"],
                decision=review["decision"],
                notes=review.get("notes"),
            )
            for review in reviews
        ]
        approved = sum(1 for result in results if result["decision"] == "approved")
        return {
            "submitted": len(results),
            "approved": approved,
            "rejected": len(results) - approved,
            "items": results,
        }

    def list_job_postings(
        self,
        *,
        source_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        limit = min(max(limit, 1), 500)
        clauses: List[str] = []
        params: List[Any] = []
        if source_id:
            clauses.append("j.source_id = ?")
            params.append(source_id)
        if status:
            clauses.append("j.status = ?")
            params.append(status)
        query = """
            SELECT j.*, v.version_number, v.content_hash, v.payload,
                   v.source_url, v.fetched_at, v.published_at,
                   v.validation_status, v.review_status, v.review_notes, v.reviewed_at
            FROM job_postings j
            LEFT JOIN job_versions v ON v.job_version_id = j.current_version_id
        """
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY j.last_seen_at DESC, j.job_id LIMIT ?"
        params.append(limit)
        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item["payload"]) if item.get("payload") else None
            item["review_notes"] = json.loads(item.get("review_notes") or "[]")
            results.append(item)
        return results

    def reconcile_job_snapshot(
        self,
        *,
        source_id: str,
        observed_external_ids: List[str],
        complete_snapshot: bool,
    ) -> int:
        """Deactivate missing jobs only when the caller confirms a complete snapshot."""
        if not complete_snapshot:
            raise ValueError("job deactivation requires a complete source snapshot")
        observed = sorted(set(observed_external_ids))
        with self._lock, self._connection() as connection:
            source = connection.execute(
                "SELECT source_id FROM sources WHERE source_id = ?",
                (source_id,),
            ).fetchone()
            if not source:
                raise KeyError(source_id)
            if observed:
                placeholders = ",".join("?" for _ in observed)
                cursor = connection.execute(
                    f"""
                    UPDATE job_postings SET status = 'inactive'
                    WHERE source_id = ? AND status = 'active'
                      AND external_id NOT IN ({placeholders})
                    """,
                    (source_id, *observed),
                )
            else:
                cursor = connection.execute(
                    """
                    UPDATE job_postings SET status = 'inactive'
                    WHERE source_id = ? AND status = 'active'
                    """,
                    (source_id,),
                )
            count = cursor.rowcount
        self.record_event(
            "job_snapshot_reconciled",
            "source",
            source_id,
            "success",
            {"observed_count": len(observed), "deactivated_count": count},
        )
        return count

    def search_job_postings(
        self,
        query: str,
        *,
        limit: int = 5,
        max_age_days: int = 30,
        source_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search active local postings without refreshing any external source."""
        from core.job_search import rank_job_postings

        if not 1 <= max_age_days <= 90:
            raise ValueError("job max age must be between 1 and 90 days")
        selected_sources: Optional[set[str]] = None
        if source_ids:
            if len(source_ids) > 5:
                raise ValueError("at most five job sources may be selected")
            selected_sources = set(source_ids)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=max_age_days)
        self.update_job_freshness(as_of=now.isoformat())
        candidates: List[Dict[str, Any]] = []
        for item in self.list_job_postings(status="active", limit=500):
            if selected_sources is not None and item.get("source_id") not in selected_sources:
                continue
            if item.get("freshness_status") == "expired":
                continue
            verified_value = item.get("last_verified_at")
            if not verified_value:
                continue
            try:
                verified_at = datetime.fromisoformat(
                    str(verified_value).replace("Z", "+00:00")
                )
            except ValueError:
                continue
            if verified_at.tzinfo is None:
                verified_at = verified_at.replace(tzinfo=timezone.utc)
            if verified_at >= cutoff:
                candidates.append(item)
        return rank_job_postings(query, candidates, limit=limit)

    def update_job_freshness(
        self,
        *,
        as_of: Optional[str] = None,
        fresh_days: int = 7,
        stale_days: int = 30,
    ) -> Dict[str, int]:
        """Classify approved jobs by verification age and declared expiry."""
        if fresh_days < 0 or stale_days <= fresh_days:
            raise ValueError("invalid freshness thresholds")
        now = datetime.fromisoformat(as_of) if as_of else datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        fresh_cutoff = (now - timedelta(days=fresh_days)).isoformat()
        stale_cutoff = (now - timedelta(days=stale_days)).isoformat()
        counts = {"fresh": 0, "aging": 0, "stale": 0, "expired": 0}
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT job_id, last_verified_at, expires_at FROM job_postings WHERE status = 'active'"
            ).fetchall()
            for row in rows:
                if row["expires_at"] and row["expires_at"] <= now.isoformat():
                    freshness, status = "expired", "expired"
                elif row["last_verified_at"] and row["last_verified_at"] >= fresh_cutoff:
                    freshness, status = "fresh", "active"
                elif row["last_verified_at"] and row["last_verified_at"] >= stale_cutoff:
                    freshness, status = "aging", "active"
                else:
                    freshness, status = "stale", "active"
                connection.execute(
                    "UPDATE job_postings SET freshness_status = ?, status = ? WHERE job_id = ?",
                    (freshness, status, row["job_id"]),
                )
                counts[freshness] += 1
        return counts

    def expire_job_postings(self, *, as_of: Optional[str] = None) -> int:
        """Mark active postings expired when their declared validity has ended."""
        as_of = as_of or _utc_now()
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE job_postings SET status = 'expired', freshness_status = 'expired'
                WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at <= ?
                """,
                (as_of,),
            )
            count = cursor.rowcount
        if count:
            self.record_event(
                "jobs_expired",
                "job_posting",
                "batch",
                "success",
                {"as_of": as_of, "expired_count": count},
            )
        return count

    def update_source_health(
        self,
        source_id: str,
        outcome: str,
        *,
        error_type: Optional[str] = None,
        checked_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a bounded source check without storing response content."""
        if outcome not in {"success", "failed", "rejected"}:
            raise ValueError("invalid source health outcome")
        checked_at = checked_at or _utc_now()
        with self._lock, self._connection() as connection:
            source = connection.execute(
                "SELECT consecutive_failures FROM sources WHERE source_id = ?", (source_id,)
            ).fetchone()
            if not source:
                raise KeyError(source_id)
            if outcome == "success":
                health_status = "healthy"
                failures = 0
                connection.execute(
                    """
                    UPDATE sources SET health_status = ?, last_checked_at = ?,
                        last_success_at = ?, consecutive_failures = 0,
                        last_error_type = NULL, updated_at = ?
                    WHERE source_id = ?
                    """,
                    (health_status, checked_at, checked_at, checked_at, source_id),
                )
            else:
                failures = int(source["consecutive_failures"] or 0) + 1
                health_status = (
                    "review_required" if outcome == "rejected"
                    else "unavailable" if failures >= 3
                    else "degraded"
                )
                connection.execute(
                    """
                    UPDATE sources SET health_status = ?, last_checked_at = ?,
                        last_failure_at = ?, consecutive_failures = ?,
                        last_error_type = ?, updated_at = ?
                    WHERE source_id = ?
                    """,
                    (
                        health_status, checked_at, checked_at, failures,
                        error_type or "UnknownError", checked_at, source_id,
                    ),
                )
        return self.get_source(source_id) or {}

    def create_job_refresh_task(
        self,
        *,
        source_id: str,
        task_type: str,
        source_url: Optional[str] = None,
        max_attempts: int = 1,
    ) -> Dict[str, Any]:
        """Create one persistent operator-run refresh task."""
        if task_type not in {"managed_refresh", "url_import"}:
            raise ValueError("invalid job refresh task type")
        if task_type == "url_import" and not source_url:
            raise ValueError("url_import requires source_url")
        if task_type == "managed_refresh" and source_url:
            raise ValueError("managed_refresh does not accept source_url")
        if not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        source = self.get_source(source_id)
        if not source:
            raise KeyError(source_id)
        if source["status"] != "active":
            raise ValueError("job source is not active")
        if task_type == "url_import":
            from mcp.knowledge_sources import validate_source_url

            validate_source_url(
                source_url or "",
                [source["official_domain"], *source.get("delegated_domains", [])],
            )
        elif source["refresh_policy"] != "manual" or not source["automation_allowed"]:
            raise ValueError("managed refresh is not approved for this source")
        self.recover_stale_job_refresh_tasks()
        task_id = f"jobtask_{uuid.uuid4().hex[:16]}"
        created_at = _utc_now()
        try:
            with self._lock, self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO job_refresh_tasks (
                        task_id, source_id, task_type, source_url, max_attempts, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (task_id, source_id, task_type, source_url, max_attempts, created_at),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("source already has an open refresh task") from exc
        self.record_event(
            "job_refresh_task_created", "job_refresh_task", task_id, "success",
            {"source_id": source_id, "task_type": task_type},
        )
        return self.get_job_refresh_task(task_id) or {}

    def get_job_refresh_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM job_refresh_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        return self._task_row(row) if row else None

    def list_job_refresh_tasks(
        self,
        *,
        source_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        allowed = {"queued", "running", "succeeded", "failed", "rejected"}
        if status and status not in allowed:
            raise ValueError("invalid job refresh task status")
        limit = min(max(limit, 1), 500)
        query = "SELECT * FROM job_refresh_tasks"
        clauses: List[str] = []
        params: List[Any] = []
        if source_id:
            clauses.append("source_id = ?")
            params.append(source_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC, task_id LIMIT ?"
        params.append(limit)
        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [self._task_row(row) for row in rows]

    def claim_job_refresh_task(self, task_id: str) -> Dict[str, Any]:
        with self._lock, self._connection() as connection:
            task = connection.execute(
                "SELECT * FROM job_refresh_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not task:
                raise KeyError(task_id)
            if task["status"] != "queued":
                raise ValueError("job refresh task is not queued")
            if task["attempts"] >= task["max_attempts"]:
                raise ValueError("job refresh task has no attempts remaining")
            cursor = connection.execute(
                """
                UPDATE job_refresh_tasks SET status = 'running', attempts = attempts + 1,
                    started_at = ?, completed_at = NULL, error_type = NULL
                WHERE task_id = ? AND status = 'queued' AND attempts < max_attempts
                """,
                (_utc_now(), task_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("job refresh task could not be claimed")
        return self.get_job_refresh_task(task_id) or {}

    def recover_stale_job_refresh_tasks(
        self,
        *,
        as_of: Optional[str] = None,
        timeout_minutes: int = 30,
    ) -> int:
        """Release tasks left running after an interrupted request."""
        if not 1 <= timeout_minutes <= 1440:
            raise ValueError("invalid job refresh task timeout")
        now = datetime.fromisoformat(as_of) if as_of else datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        cutoff = (now - timedelta(minutes=timeout_minutes)).isoformat()
        completed_at = now.isoformat()
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE job_refresh_tasks
                SET status = 'failed', error_type = 'ProcessInterrupted',
                    result_summary = '{}', completed_at = ?
                WHERE status = 'running'
                  AND (started_at IS NULL OR started_at <= ?)
                """,
                (completed_at, cutoff),
            )
            count = cursor.rowcount
        if count:
            self.record_event(
                "job_refresh_tasks_recovered", "job_refresh_task", "batch", "success",
                {"recovered_count": count},
            )
        return count

    def complete_job_refresh_task(
        self,
        task_id: str,
        *,
        outcome: str,
        result_summary: Optional[Dict[str, Any]] = None,
        error_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        if outcome not in {"succeeded", "failed", "rejected"}:
            raise ValueError("invalid job refresh task outcome")
        with self._lock, self._connection() as connection:
            task = connection.execute(
                "SELECT status FROM job_refresh_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not task:
                raise KeyError(task_id)
            if task["status"] != "running":
                raise ValueError("job refresh task is not running")
            connection.execute(
                """
                UPDATE job_refresh_tasks
                SET status = ?, result_summary = ?, error_type = ?, completed_at = ?
                WHERE task_id = ?
                """,
                (
                    outcome, json.dumps(result_summary or {}, ensure_ascii=False),
                    error_type, _utc_now(), task_id,
                ),
            )
        self.record_event(
            "job_refresh_task_completed", "job_refresh_task", task_id, outcome,
            {"error_type": error_type} if error_type else {},
        )
        return self.get_job_refresh_task(task_id) or {}

    def retry_job_refresh_task(self, task_id: str) -> Dict[str, Any]:
        self.recover_stale_job_refresh_tasks()
        with self._lock, self._connection() as connection:
            task = connection.execute(
                "SELECT * FROM job_refresh_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not task:
                raise KeyError(task_id)
            if task["status"] not in {"failed", "rejected"}:
                raise ValueError("only failed or rejected tasks can be retried")
            if task["attempts"] >= task["max_attempts"]:
                raise ValueError("job refresh task has no attempts remaining")
            open_task = connection.execute(
                """
                SELECT task_id FROM job_refresh_tasks
                WHERE source_id = ? AND status IN ('queued', 'running')
                """,
                (task["source_id"],),
            ).fetchone()
            if open_task:
                raise ValueError("source already has an open refresh task")
            connection.execute(
                """
                UPDATE job_refresh_tasks SET status = 'queued', result_summary = '{}',
                    error_type = NULL, started_at = NULL, completed_at = NULL
                WHERE task_id = ?
                """,
                (task_id,),
            )
        return self.get_job_refresh_task(task_id) or {}

    def record_event(
        self,
        action: str,
        target_type: str,
        target_id: str,
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    event_id, action, target_type, target_id, outcome, details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"evt_{uuid.uuid4().hex[:16]}",
                    action,
                    target_type,
                    target_id,
                    outcome,
                    json.dumps(details or {}, ensure_ascii=False),
                    _utc_now(),
                ),
            )

    def list_events(
        self,
        *,
        target_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        limit = min(max(limit, 1), 500)
        query = "SELECT * FROM audit_events"
        params: List[Any] = []
        if target_id:
            query += " WHERE target_id = ?"
            params.append(target_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.get("details") or "{}")
            results.append(item)
        return results

    @staticmethod
    def _source_row(row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        result["delegated_domains"] = json.loads(result.get("delegated_domains") or "[]")
        result["recruitment_channels"] = json.loads(
            result.get("recruitment_channels") or "[]"
        )
        result["automation_allowed"] = bool(result.get("automation_allowed"))
        return result

    @staticmethod
    def _task_row(row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        result["result_summary"] = json.loads(result.get("result_summary") or "{}")
        return result
