"""Transactional SQLite storage for Mako 2.0 evidence and confirmations."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from core.v2_evidence import (
    ConfirmationObjectType,
    EvidenceRecord,
    JDRequirement,
    JDRequirementReview,
    UserConfirmation,
)
from core.v2_requirements import RequirementReviewError, apply_requirement_review


class EvidenceConflictError(ValueError):
    """Raised when an immutable identifier is reused with different content."""


class EvidenceReferenceError(ValueError):
    """Raised when a confirmation does not reference an owned evidence record."""


class RequirementConflictError(ValueError):
    """Raised when an immutable requirement or review identifier is reused."""


class RequirementReferenceError(ValueError):
    """Raised when a requirement review cannot resolve its draft."""


def _json_payload(
    model: EvidenceRecord | UserConfirmation | JDRequirement | JDRequirementReview,
) -> str:
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _idempotency_payload(
    model: EvidenceRecord | UserConfirmation | JDRequirement | JDRequirementReview,
) -> Dict[str, Any]:
    return model.model_dump(mode="json")


class EvidenceRegistry:
    """Append-only V2 records kept separate from V1 profile and job tables."""

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
                CREATE TABLE IF NOT EXISTS evidence_records (
                    evidence_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    captured_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_user_captured
                    ON evidence_records(user_id, captured_at, evidence_id);
                CREATE TABLE IF NOT EXISTS user_confirmations (
                    confirmation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    FOREIGN KEY(object_id) REFERENCES evidence_records(evidence_id)
                );
                CREATE INDEX IF NOT EXISTS idx_confirmations_user_decided
                    ON user_confirmations(user_id, decided_at, confirmation_id);
                CREATE TABLE IF NOT EXISTS jd_requirement_drafts (
                    requirement_id TEXT PRIMARY KEY,
                    job_version_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_requirement_drafts_version
                    ON jd_requirement_drafts(job_version_id, requirement_id);
                CREATE TABLE IF NOT EXISTS jd_requirement_reviews (
                    review_id TEXT PRIMARY KEY,
                    requirement_id TEXT NOT NULL,
                    job_version_id TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL,
                    FOREIGN KEY(requirement_id)
                        REFERENCES jd_requirement_drafts(requirement_id)
                );
                CREATE INDEX IF NOT EXISTS idx_requirement_reviews_target
                    ON jd_requirement_reviews(
                        requirement_id, reviewed_at DESC, review_id DESC
                    );
                """
            )

    @staticmethod
    def _evidence_from_row(row: sqlite3.Row) -> EvidenceRecord:
        return EvidenceRecord.model_validate_json(row["payload"])

    @staticmethod
    def _confirmation_from_row(row: sqlite3.Row) -> UserConfirmation:
        return UserConfirmation.model_validate_json(row["payload"])

    @staticmethod
    def _requirement_from_row(row: sqlite3.Row) -> JDRequirement:
        return JDRequirement.model_validate_json(row["payload"])

    @staticmethod
    def _requirement_review_from_row(row: sqlite3.Row) -> JDRequirementReview:
        return JDRequirementReview.model_validate_json(row["payload"])

    def add_requirement_drafts(
        self,
        drafts: List[JDRequirement],
    ) -> List[JDRequirement]:
        """Insert one deterministic draft set atomically and idempotently."""
        if not drafts:
            raise ValueError("at least one requirement draft is required")
        version_ids = {draft.job_version_id for draft in drafts}
        if len(version_ids) != 1:
            raise ValueError("requirement drafts must belong to one job version")
        if len({draft.requirement_id for draft in drafts}) != len(drafts):
            raise ValueError("requirement_id is duplicated")
        if any(draft.extraction_status.value != "needs_review" for draft in drafts):
            raise ValueError("new requirement drafts must need review")

        with self._lock, self._connection() as connection:
            for draft in drafts:
                existing_row = connection.execute(
                    "SELECT payload FROM jd_requirement_drafts WHERE requirement_id = ?",
                    (draft.requirement_id,),
                ).fetchone()
                if existing_row:
                    existing = self._requirement_from_row(existing_row)
                    if _idempotency_payload(existing) != _idempotency_payload(draft):
                        raise RequirementConflictError(
                            "requirement_id already exists with different content"
                        )
            for draft in drafts:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO jd_requirement_drafts(
                        requirement_id, job_version_id, payload
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        draft.requirement_id,
                        draft.job_version_id,
                        _json_payload(draft),
                    ),
                )
        return drafts

    def get_requirement_draft(self, requirement_id: str) -> Optional[JDRequirement]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM jd_requirement_drafts WHERE requirement_id = ?",
                (requirement_id,),
            ).fetchone()
        return self._requirement_from_row(row) if row else None

    def list_requirement_drafts(
        self,
        job_version_id: str,
        *,
        limit: int = 100,
    ) -> List[JDRequirement]:
        bounded_limit = min(max(limit, 1), 200)
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM jd_requirement_drafts
                WHERE job_version_id = ?
                ORDER BY requirement_id
                LIMIT ?
                """,
                (job_version_id, bounded_limit),
            ).fetchall()
        return [self._requirement_from_row(row) for row in rows]

    def add_requirement_review(
        self,
        review: JDRequirementReview,
    ) -> JDRequirementReview:
        """Append one explicit review after validating it against its draft."""
        with self._lock, self._connection() as connection:
            existing_row = connection.execute(
                "SELECT payload FROM jd_requirement_reviews WHERE review_id = ?",
                (review.review_id,),
            ).fetchone()
            if existing_row:
                existing = self._requirement_review_from_row(existing_row)
                if _idempotency_payload(existing) == _idempotency_payload(review):
                    return existing
                raise RequirementConflictError(
                    "review_id already exists with different content"
                )
            draft_row = connection.execute(
                "SELECT payload FROM jd_requirement_drafts WHERE requirement_id = ?",
                (review.requirement_id,),
            ).fetchone()
            if not draft_row:
                raise RequirementReferenceError("requirement draft does not exist")
            draft = self._requirement_from_row(draft_row)
            try:
                apply_requirement_review(draft, review)
            except RequirementReviewError as exc:
                raise RequirementReferenceError(str(exc)) from exc
            connection.execute(
                """
                INSERT INTO jd_requirement_reviews(
                    review_id, requirement_id, job_version_id,
                    reviewer_id, payload, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    review.review_id,
                    review.requirement_id,
                    review.job_version_id,
                    review.reviewer_id,
                    _json_payload(review),
                    review.reviewed_at.astimezone(timezone.utc).isoformat(),
                ),
            )
        return review

    def get_reviewed_requirement(
        self,
        requirement_id: str,
    ) -> Optional[JDRequirement]:
        with self._connection() as connection:
            draft_row = connection.execute(
                "SELECT payload FROM jd_requirement_drafts WHERE requirement_id = ?",
                (requirement_id,),
            ).fetchone()
            review_row = connection.execute(
                """
                SELECT payload FROM jd_requirement_reviews
                WHERE requirement_id = ?
                ORDER BY rowid DESC
                LIMIT 1
                """,
                (requirement_id,),
            ).fetchone()
        if not draft_row or not review_row:
            return None
        draft = self._requirement_from_row(draft_row)
        review = self._requirement_review_from_row(review_row)
        return apply_requirement_review(draft, review)

    def list_reviewed_requirements(
        self,
        job_version_id: str,
        *,
        limit: int = 100,
    ) -> List[JDRequirement]:
        result: List[JDRequirement] = []
        for draft in self.list_requirement_drafts(job_version_id, limit=limit):
            reviewed = self.get_reviewed_requirement(draft.requirement_id)
            if reviewed is not None:
                result.append(reviewed)
        return result

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceRecord]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM evidence_records WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
        return self._evidence_from_row(row) if row else None

    def add_evidence(self, record: EvidenceRecord) -> EvidenceRecord:
        """Insert one immutable record or return an equivalent prior insert."""
        with self._lock, self._connection() as connection:
            existing_row = connection.execute(
                "SELECT payload FROM evidence_records WHERE evidence_id = ?",
                (record.evidence_id,),
            ).fetchone()
            if existing_row:
                existing = self._evidence_from_row(existing_row)
                if _idempotency_payload(existing) == _idempotency_payload(record):
                    return existing
                raise EvidenceConflictError("evidence_id already exists with different content")
            connection.execute(
                """
                INSERT INTO evidence_records(evidence_id, user_id, payload, captured_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    record.evidence_id,
                    record.user_id,
                    _json_payload(record),
                    record.captured_at.isoformat(),
                ),
            )
        return record

    def list_evidence(self, user_id: str, *, limit: int = 100) -> List[EvidenceRecord]:
        bounded_limit = min(max(limit, 1), 200)
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM evidence_records
                WHERE user_id = ?
                ORDER BY captured_at DESC, evidence_id
                LIMIT ?
                """,
                (user_id, bounded_limit),
            ).fetchall()
        return [self._evidence_from_row(row) for row in rows]

    def get_confirmation(self, confirmation_id: str) -> Optional[UserConfirmation]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM user_confirmations WHERE confirmation_id = ?",
                (confirmation_id,),
            ).fetchone()
        return self._confirmation_from_row(row) if row else None

    def add_confirmation(self, confirmation: UserConfirmation) -> UserConfirmation:
        """Append a confirmation after checking target existence and ownership."""
        if confirmation.object_type != ConfirmationObjectType.EVIDENCE:
            raise EvidenceReferenceError("only evidence confirmations are supported in this slice")
        with self._lock, self._connection() as connection:
            existing_row = connection.execute(
                "SELECT payload FROM user_confirmations WHERE confirmation_id = ?",
                (confirmation.confirmation_id,),
            ).fetchone()
            if existing_row:
                existing = self._confirmation_from_row(existing_row)
                if _idempotency_payload(existing) == _idempotency_payload(confirmation):
                    return existing
                raise EvidenceConflictError(
                    "confirmation_id already exists with different content"
                )

            target = connection.execute(
                "SELECT user_id FROM evidence_records WHERE evidence_id = ?",
                (confirmation.object_id,),
            ).fetchone()
            if not target:
                raise EvidenceReferenceError("confirmation target does not exist")
            if target["user_id"] != confirmation.user_id:
                raise EvidenceReferenceError("confirmation target belongs to another user")

            connection.execute(
                """
                INSERT INTO user_confirmations(
                    confirmation_id, user_id, object_type, object_id, payload, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    confirmation.confirmation_id,
                    confirmation.user_id,
                    confirmation.object_type.value,
                    confirmation.object_id,
                    _json_payload(confirmation),
                    confirmation.decided_at.isoformat(),
                ),
            )
        return confirmation

    def list_confirmations(
        self,
        user_id: str,
        *,
        limit: int = 100,
    ) -> List[UserConfirmation]:
        bounded_limit = min(max(limit, 1), 200)
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM user_confirmations
                WHERE user_id = ?
                ORDER BY decided_at DESC, confirmation_id
                LIMIT ?
                """,
                (user_id, bounded_limit),
            ).fetchall()
        return [self._confirmation_from_row(row) for row in rows]
