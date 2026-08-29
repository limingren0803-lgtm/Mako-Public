"""Transactional SQLite storage for the local career workspace."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from core.career_workspace import ActionItem, ActionStatus, JobTrack, JobTrackSourceKind


WORKSPACE_SCHEMA_VERSION = 1
LOCAL_WORKSPACE_ID = "local-default"


class WorkspaceConflictError(ValueError):
    pass


class WorkspaceNotFoundError(KeyError):
    pass


class WorkspaceReferenceError(ValueError):
    pass


class WorkspaceSchemaError(RuntimeError):
    pass


def request_fingerprint(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _payload(model: JobTrack | ActionItem) -> str:
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class CareerWorkspaceRegistry:
    """Own JobTrack and ActionItem data without opening any other Mako store."""

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
                """
                CREATE TABLE IF NOT EXISTS workspace_schema (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    schema_version INTEGER NOT NULL
                )
                """
            )
            row = connection.execute(
                "SELECT schema_version FROM workspace_schema WHERE singleton = 1"
            ).fetchone()
            if row and int(row["schema_version"]) > WORKSPACE_SCHEMA_VERSION:
                raise WorkspaceSchemaError("workspace database schema is newer than this application")
            if row and int(row["schema_version"]) < WORKSPACE_SCHEMA_VERSION:
                raise WorkspaceSchemaError("workspace database requires an explicit migration")
            if not row:
                connection.execute(
                    "INSERT INTO workspace_schema(singleton, schema_version) VALUES (1, ?)",
                    (WORKSPACE_SCHEMA_VERSION,),
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS job_tracks (
                    track_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    job_id TEXT,
                    job_version_id TEXT,
                    stage TEXT NOT NULL,
                    deadline TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_job_tracks_official_version
                    ON job_tracks(workspace_id, job_id, job_version_id)
                    WHERE source_kind = 'reviewed_job';
                CREATE INDEX IF NOT EXISTS idx_job_tracks_stage_updated
                    ON job_tracks(workspace_id, stage, updated_at DESC, track_id);

                CREATE TABLE IF NOT EXISTS action_items (
                    action_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    track_id TEXT,
                    origin TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    due_at TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    FOREIGN KEY(track_id) REFERENCES job_tracks(track_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_actions_status_due
                    ON action_items(workspace_id, status, due_at, action_id);
                CREATE INDEX IF NOT EXISTS idx_actions_track
                    ON action_items(track_id, status, action_id);

                CREATE TABLE IF NOT EXISTS idempotency_keys (
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
    def _track_from_row(row: sqlite3.Row) -> JobTrack:
        return JobTrack.model_validate_json(row["payload"])

    @staticmethod
    def _action_from_row(row: sqlite3.Row) -> ActionItem:
        return ActionItem.model_validate_json(row["payload"])

    @staticmethod
    def _validate_idempotency_key(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = value.strip()
        if not clean or len(clean) > 128:
            raise ValueError("Idempotency-Key must contain 1 to 128 characters")
        if not all(char.isascii() and (char.isalnum() or char in "_-:.") for char in clean):
            raise ValueError("Idempotency-Key contains unsupported characters")
        return clean

    def _idempotent_resource(
        self,
        connection: sqlite3.Connection,
        *,
        operation: str,
        idempotency_key: Optional[str],
        request_hash: str,
    ) -> Optional[str]:
        key = self._validate_idempotency_key(idempotency_key)
        if key is None:
            return None
        row = connection.execute(
            """
            SELECT request_hash, resource_id FROM idempotency_keys
            WHERE operation = ? AND idempotency_key = ?
            """,
            (operation, key),
        ).fetchone()
        if not row:
            return None
        if row["request_hash"] != request_hash:
            raise WorkspaceConflictError("Idempotency-Key was reused with different content")
        return str(row["resource_id"])

    def _remember_idempotency(
        self,
        connection: sqlite3.Connection,
        *,
        operation: str,
        idempotency_key: Optional[str],
        request_hash: str,
        resource_id: str,
        created_at: str,
    ) -> None:
        key = self._validate_idempotency_key(idempotency_key)
        if key is None:
            return
        connection.execute(
            """
            INSERT INTO idempotency_keys(
                operation, idempotency_key, request_hash, resource_id, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (operation, key, request_hash, resource_id, created_at),
        )

    def get_track(self, track_id: str) -> Optional[JobTrack]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM job_tracks WHERE track_id = ? AND workspace_id = ?",
                (track_id, LOCAL_WORKSPACE_ID),
            ).fetchone()
        return self._track_from_row(row) if row else None

    def list_tracks(
        self,
        *,
        stage: Optional[str] = None,
        limit: Optional[int] = 100,
    ) -> List[JobTrack]:
        query = "SELECT payload FROM job_tracks WHERE workspace_id = ?"
        params: List[Any] = [LOCAL_WORKSPACE_ID]
        if stage:
            query += " AND stage = ?"
            params.append(stage)
        query += " ORDER BY updated_at DESC, track_id"
        if limit is not None:
            query += " LIMIT ?"
            params.append(min(max(limit, 1), 200))
        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [self._track_from_row(row) for row in rows]

    def create_track(
        self,
        track: JobTrack,
        *,
        idempotency_key: Optional[str] = None,
        request_hash: str,
    ) -> JobTrack:
        with self._lock, self._connection() as connection:
            existing_id = self._idempotent_resource(
                connection,
                operation="create_track",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if existing_id:
                row = connection.execute(
                    "SELECT payload FROM job_tracks WHERE track_id = ?",
                    (existing_id,),
                ).fetchone()
                if not row:
                    raise WorkspaceConflictError("idempotent track no longer exists")
                return self._track_from_row(row)
            if track.source_kind == JobTrackSourceKind.REVIEWED_JOB:
                duplicate = connection.execute(
                    """
                    SELECT track_id FROM job_tracks
                    WHERE workspace_id = ? AND job_id = ? AND job_version_id = ?
                    """,
                    (LOCAL_WORKSPACE_ID, track.job_id, track.job_version_id),
                ).fetchone()
                if duplicate:
                    raise WorkspaceConflictError(
                        f"official job version is already tracked as {duplicate['track_id']}"
                    )
            connection.execute(
                """
                INSERT INTO job_tracks(
                    track_id, workspace_id, source_kind, job_id, job_version_id,
                    stage, deadline, payload, created_at, updated_at, revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    track.track_id,
                    LOCAL_WORKSPACE_ID,
                    track.source_kind.value,
                    track.job_id,
                    track.job_version_id,
                    track.stage.value,
                    track.deadline.isoformat() if track.deadline else None,
                    _payload(track),
                    track.created_at.isoformat(),
                    track.updated_at.isoformat(),
                    track.revision,
                ),
            )
            self._remember_idempotency(
                connection,
                operation="create_track",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                resource_id=track.track_id,
                created_at=track.created_at.isoformat(),
            )
        return track

    def replace_track(self, track: JobTrack, *, expected_revision: int) -> JobTrack:
        if track.revision != expected_revision + 1:
            raise ValueError("replacement revision must increment by one")
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE job_tracks SET stage = ?, deadline = ?, payload = ?,
                    updated_at = ?, revision = ?
                WHERE track_id = ? AND workspace_id = ? AND revision = ?
                """,
                (
                    track.stage.value,
                    track.deadline.isoformat() if track.deadline else None,
                    _payload(track),
                    track.updated_at.isoformat(),
                    track.revision,
                    track.track_id,
                    LOCAL_WORKSPACE_ID,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                exists = connection.execute(
                    "SELECT 1 FROM job_tracks WHERE track_id = ?",
                    (track.track_id,),
                ).fetchone()
                if not exists:
                    raise WorkspaceNotFoundError(track.track_id)
                raise WorkspaceConflictError("track was updated by another request")
        return track

    def track_deletion_impact(self, track_id: str) -> Dict[str, int]:
        with self._connection() as connection:
            exists = connection.execute(
                "SELECT 1 FROM job_tracks WHERE track_id = ? AND workspace_id = ?",
                (track_id, LOCAL_WORKSPACE_ID),
            ).fetchone()
            if not exists:
                raise WorkspaceNotFoundError(track_id)
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM action_items WHERE track_id = ?",
                (track_id,),
            ).fetchone()
        return {"tracks": 1, "actions": int(row["count"])}

    def delete_track(
        self,
        track_id: str,
        *,
        expected_revision: int,
        cascade_actions: bool,
    ) -> Dict[str, int]:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT revision FROM job_tracks WHERE track_id = ? AND workspace_id = ?",
                (track_id, LOCAL_WORKSPACE_ID),
            ).fetchone()
            if not row:
                raise WorkspaceNotFoundError(track_id)
            if int(row["revision"]) != expected_revision:
                raise WorkspaceConflictError("track was updated by another request")
            action_count = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM action_items WHERE track_id = ?",
                    (track_id,),
                ).fetchone()["count"]
            )
            if action_count and not cascade_actions:
                raise WorkspaceConflictError("track has actions; cascade_actions=true is required")
            connection.execute(
                """
                DELETE FROM idempotency_keys
                WHERE resource_id IN (
                    SELECT action_id FROM action_items WHERE track_id = ?
                )
                """,
                (track_id,),
            )
            connection.execute("DELETE FROM job_tracks WHERE track_id = ?", (track_id,))
            connection.execute(
                "DELETE FROM idempotency_keys WHERE resource_id = ?",
                (track_id,),
            )
        self._checkpoint()
        return {"tracks": 1, "actions": action_count}

    def get_action(self, action_id: str) -> Optional[ActionItem]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM action_items WHERE action_id = ? AND workspace_id = ?",
                (action_id, LOCAL_WORKSPACE_ID),
            ).fetchone()
        return self._action_from_row(row) if row else None

    def list_actions(
        self,
        *,
        track_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = 200,
    ) -> List[ActionItem]:
        query = "SELECT payload FROM action_items WHERE workspace_id = ?"
        params: List[Any] = [LOCAL_WORKSPACE_ID]
        if track_id:
            query += " AND track_id = ?"
            params.append(track_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC, action_id"
        if limit is not None:
            query += " LIMIT ?"
            params.append(min(max(limit, 1), 500))
        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [self._action_from_row(row) for row in rows]

    def create_action(
        self,
        action: ActionItem,
        *,
        idempotency_key: Optional[str] = None,
        request_hash: str,
    ) -> ActionItem:
        with self._lock, self._connection() as connection:
            existing_id = self._idempotent_resource(
                connection,
                operation="create_action",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if existing_id:
                row = connection.execute(
                    "SELECT payload FROM action_items WHERE action_id = ?",
                    (existing_id,),
                ).fetchone()
                if not row:
                    raise WorkspaceConflictError("idempotent action no longer exists")
                return self._action_from_row(row)
            if action.track_id:
                track = connection.execute(
                    "SELECT 1 FROM job_tracks WHERE track_id = ? AND workspace_id = ?",
                    (action.track_id, LOCAL_WORKSPACE_ID),
                ).fetchone()
                if not track:
                    raise WorkspaceReferenceError("track does not exist")
            connection.execute(
                """
                INSERT INTO action_items(
                    action_id, workspace_id, track_id, origin, status, priority,
                    due_at, payload, created_at, updated_at, revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action.action_id,
                    LOCAL_WORKSPACE_ID,
                    action.track_id,
                    action.origin.value,
                    action.status.value,
                    action.priority.value,
                    action.due_at.isoformat() if action.due_at else None,
                    _payload(action),
                    action.created_at.isoformat(),
                    action.updated_at.isoformat(),
                    action.revision,
                ),
            )
            self._remember_idempotency(
                connection,
                operation="create_action",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                resource_id=action.action_id,
                created_at=action.created_at.isoformat(),
            )
        return action

    def create_actions(self, actions: List[ActionItem]) -> List[ActionItem]:
        """Insert one server-generated suggestion set atomically."""
        if not actions:
            raise ValueError("at least one action is required")
        if len({item.action_id for item in actions}) != len(actions):
            raise WorkspaceConflictError("action_id is duplicated")
        with self._lock, self._connection() as connection:
            track_ids = {item.track_id for item in actions if item.track_id}
            for track_id in track_ids:
                track = connection.execute(
                    "SELECT 1 FROM job_tracks WHERE track_id = ? AND workspace_id = ?",
                    (track_id, LOCAL_WORKSPACE_ID),
                ).fetchone()
                if not track:
                    raise WorkspaceReferenceError("track does not exist")
            existing = connection.execute(
                f"SELECT action_id FROM action_items WHERE action_id IN ({','.join('?' for _ in actions)})",
                tuple(item.action_id for item in actions),
            ).fetchone()
            if existing:
                raise WorkspaceConflictError("action_id already exists")
            for action in actions:
                connection.execute(
                    """
                    INSERT INTO action_items(
                        action_id, workspace_id, track_id, origin, status, priority,
                        due_at, payload, created_at, updated_at, revision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action.action_id,
                        LOCAL_WORKSPACE_ID,
                        action.track_id,
                        action.origin.value,
                        action.status.value,
                        action.priority.value,
                        action.due_at.isoformat() if action.due_at else None,
                        _payload(action),
                        action.created_at.isoformat(),
                        action.updated_at.isoformat(),
                        action.revision,
                    ),
                )
        return actions

    def replace_action(self, action: ActionItem, *, expected_revision: int) -> ActionItem:
        allowed = {
            ActionStatus.SUGGESTED: {ActionStatus.TODO, ActionStatus.CANCELLED},
            ActionStatus.TODO: {ActionStatus.TODO, ActionStatus.COMPLETED, ActionStatus.CANCELLED},
            ActionStatus.COMPLETED: {ActionStatus.TODO, ActionStatus.COMPLETED},
            ActionStatus.CANCELLED: {ActionStatus.TODO, ActionStatus.CANCELLED},
        }
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT payload, revision FROM action_items WHERE action_id = ?",
                (action.action_id,),
            ).fetchone()
            if not row:
                raise WorkspaceNotFoundError(action.action_id)
            if int(row["revision"]) != expected_revision:
                raise WorkspaceConflictError("action was updated by another request")
            current = self._action_from_row(row)
            if action.status != current.status and action.status not in allowed[current.status]:
                raise WorkspaceConflictError(
                    f"action cannot move from {current.status.value} to {action.status.value}"
                )
            if action.revision != expected_revision + 1:
                raise ValueError("replacement revision must increment by one")
            if action.track_id:
                track = connection.execute(
                    "SELECT 1 FROM job_tracks WHERE track_id = ?",
                    (action.track_id,),
                ).fetchone()
                if not track:
                    raise WorkspaceReferenceError("track does not exist")
            connection.execute(
                """
                UPDATE action_items SET track_id = ?, status = ?, priority = ?,
                    due_at = ?, payload = ?, updated_at = ?, revision = ?
                WHERE action_id = ? AND revision = ?
                """,
                (
                    action.track_id,
                    action.status.value,
                    action.priority.value,
                    action.due_at.isoformat() if action.due_at else None,
                    _payload(action),
                    action.updated_at.isoformat(),
                    action.revision,
                    action.action_id,
                    expected_revision,
                ),
            )
        return action

    def delete_action(self, action_id: str, *, expected_revision: int) -> None:
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM action_items
                WHERE action_id = ? AND workspace_id = ? AND revision = ?
                """,
                (action_id, LOCAL_WORKSPACE_ID, expected_revision),
            )
            if cursor.rowcount != 1:
                exists = connection.execute(
                    "SELECT 1 FROM action_items WHERE action_id = ?",
                    (action_id,),
                ).fetchone()
                if not exists:
                    raise WorkspaceNotFoundError(action_id)
                raise WorkspaceConflictError("action was updated by another request")
            connection.execute(
                "DELETE FROM idempotency_keys WHERE resource_id = ?",
                (action_id,),
            )
        self._checkpoint()

    def deletion_impact(self) -> Dict[str, int]:
        with self._connection() as connection:
            tracks = int(connection.execute("SELECT COUNT(*) FROM job_tracks").fetchone()[0])
            actions = int(connection.execute("SELECT COUNT(*) FROM action_items").fetchone()[0])
        return {"tracks": tracks, "actions": actions}

    def clear(self) -> Dict[str, int]:
        impact = self.deletion_impact()
        with self._lock, self._connection() as connection:
            connection.execute("DELETE FROM action_items")
            connection.execute("DELETE FROM job_tracks")
            connection.execute("DELETE FROM idempotency_keys")
        self._checkpoint(vacuum=True)
        return impact

    def export_snapshot(self) -> Dict[str, Any]:
        return {
            "schema_version": WORKSPACE_SCHEMA_VERSION,
            "workspace_id": LOCAL_WORKSPACE_ID,
            "tracks": [item.model_dump(mode="json") for item in self.list_tracks(limit=None)],
            "actions": [item.model_dump(mode="json") for item in self.list_actions(limit=None)],
        }

    def integrity_report(self) -> Dict[str, Any]:
        with self._connection() as connection:
            integrity = [row[0] for row in connection.execute("PRAGMA integrity_check").fetchall()]
            foreign_keys = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check").fetchall()]
            version = int(
                connection.execute(
                    "SELECT schema_version FROM workspace_schema WHERE singleton = 1"
                ).fetchone()[0]
            )
        return {
            "schema_version": version,
            "integrity": integrity,
            "foreign_key_errors": foreign_keys,
            **self.deletion_impact(),
        }

    def _checkpoint(self, *, vacuum: bool = False) -> None:
        with self._lock:
            connection = sqlite3.connect(self.path, timeout=10.0)
            try:
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                if vacuum:
                    connection.execute("VACUUM")
            finally:
                connection.close()
