"""Persistent source and document lifecycle metadata for the Mako knowledge base."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
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
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
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
                    FOREIGN KEY(job_id) REFERENCES job_postings(job_id),
                    UNIQUE(job_id, version_number),
                    UNIQUE(job_id, content_hash)
                );
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

    def upsert_job_posting(self, posting: Any) -> Dict[str, Any]:
        """Insert a normalized posting or activate a new content version."""
        from core.job_posting import JobPosting
        from mcp.knowledge_sources import SourceSecurityError, validate_source_url

        if not isinstance(posting, JobPosting):
            posting = JobPosting.model_validate(posting)
        content_hash = posting.content_hash()
        payload = posting.model_dump_json()
        fetched_at = posting.fetched_at.isoformat()
        published_at = posting.published_at.isoformat() if posting.published_at else None
        expires_at = posting.valid_through.isoformat() if posting.valid_through else None

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
            else:
                job_id = f"job_{uuid.uuid4().hex[:16]}"
                connection.execute(
                    """
                    INSERT INTO job_postings (
                        job_id, source_id, external_id, company_name, title,
                        status, first_seen_at, last_seen_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        posting.source_id,
                        posting.external_id,
                        posting.company_name,
                        posting.title,
                        posting.status.value,
                        fetched_at,
                        fetched_at,
                        expires_at,
                    ),
                )

            duplicate = connection.execute(
                "SELECT job_version_id FROM job_versions WHERE job_id = ? AND content_hash = ?",
                (job_id, content_hash),
            ).fetchone()
            if duplicate:
                connection.execute(
                    """
                    UPDATE job_postings
                    SET company_name = ?, title = ?, status = ?, last_seen_at = ?, expires_at = ?
                    WHERE job_id = ?
                    """,
                    (
                        posting.company_name,
                        posting.title,
                        posting.status.value,
                        fetched_at,
                        expires_at,
                        job_id,
                    ),
                )
                changed = False
                version_id = duplicate["job_version_id"]
            else:
                version_number = connection.execute(
                    "SELECT COALESCE(MAX(version_number), 0) + 1 FROM job_versions WHERE job_id = ?",
                    (job_id,),
                ).fetchone()[0]
                version_id = f"jobver_{uuid.uuid4().hex[:16]}"
                connection.execute(
                    """
                    UPDATE job_versions
                    SET validation_status = 'superseded'
                    WHERE job_id = ? AND validation_status = 'active'
                    """,
                    (job_id,),
                )
                connection.execute(
                    """
                    INSERT INTO job_versions (
                        job_version_id, job_id, version_number, content_hash,
                        payload, source_url, fetched_at, published_at, validation_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
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
                    ),
                )
                connection.execute(
                    """
                    UPDATE job_postings
                    SET company_name = ?, title = ?, status = ?, current_version_id = ?,
                        last_seen_at = ?, expires_at = ?
                    WHERE job_id = ?
                    """,
                    (
                        posting.company_name,
                        posting.title,
                        posting.status.value,
                        version_id,
                        fetched_at,
                        expires_at,
                        job_id,
                    ),
                )
                changed = True

        self.record_event(
            "job_version_activated" if changed else "job_seen_unchanged",
            "job_posting",
            job_id,
            "success",
            {"job_version_id": version_id, "source_id": posting.source_id},
        )
        result = self.get_job_posting(job_id) or {}
        result["changed"] = changed
        return result

    def get_job_posting(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT j.*, v.version_number, v.content_hash, v.payload,
                       v.source_url, v.fetched_at, v.published_at
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
        return result

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
                   v.source_url, v.fetched_at, v.published_at
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

    def search_job_postings(self, query: str, *, limit: int = 5) -> List[Dict[str, Any]]:
        """Search active local postings without refreshing any external source."""
        from core.job_search import rank_job_postings

        candidates = self.list_job_postings(status="active", limit=500)
        return rank_job_postings(query, candidates, limit=limit)

    def expire_job_postings(self, *, as_of: Optional[str] = None) -> int:
        """Mark active postings expired when their declared validity has ended."""
        as_of = as_of or _utc_now()
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE job_postings SET status = 'expired'
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
