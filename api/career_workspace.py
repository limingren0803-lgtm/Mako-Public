"""Local single-user Career Workspace API."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from core.career_workspace import (
    ActionItem,
    ActionOrigin,
    ActionPriority,
    ActionSourceReference,
    ActionSourceType,
    ActionStatus,
    JobTrack,
    JobTrackClosedReason,
    JobTrackSourceKind,
    JobTrackStage,
    WorkspaceRequirementSnapshot,
    normalize_text,
    utc_now,
    validate_https_label,
    validate_workspace_id,
)
from core.career_workspace_registry import (
    CareerWorkspaceRegistry,
    WorkspaceConflictError,
    WorkspaceNotFoundError,
    WorkspaceReferenceError,
    request_fingerprint,
)
from core.v2_evidence import RequirementExtractionStatus
from core.v2_requirements import RequirementReviewError, extract_requirement_drafts
from core.workspace_access import (
    SESSION_TTL_SECONDS,
    WORKSPACE_COOKIE,
    create_workspace_session,
    require_workspace_session,
    revoke_workspace_session,
)


router = APIRouter(prefix="/v2/workspace", tags=["V2 求职工作区"])
_registry: Optional[CareerWorkspaceRegistry] = None
_knowledge_provider = None
_evidence_provider = None


def configure_workspace_api(
    registry: CareerWorkspaceRegistry,
    *,
    knowledge_provider,
    evidence_provider,
) -> None:
    global _registry, _knowledge_provider, _evidence_provider
    _registry = registry
    _knowledge_provider = knowledge_provider
    _evidence_provider = evidence_provider


def workspace_registry() -> CareerWorkspaceRegistry:
    if _registry is None:
        raise HTTPException(503, "求职工作区未初始化")
    return _registry


def _identifier(value: str, field_name: str) -> str:
    try:
        return validate_workspace_id(value, field_name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _knowledge_base():
    if _knowledge_provider is None:
        raise HTTPException(503, "职位库未初始化")
    return _knowledge_provider()


def _evidence_registry():
    if _evidence_provider is None:
        raise HTTPException(503, "V2 证据库未初始化")
    return _evidence_provider()


class JobTrackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_kind: JobTrackSourceKind
    job_id: Optional[str] = Field(default=None, max_length=128)
    job_version_id: Optional[str] = Field(default=None, max_length=128)
    job_max_age_days: int = Field(default=30, ge=1, le=90)
    company_name: Optional[str] = Field(default=None, max_length=200)
    title: Optional[str] = Field(default=None, max_length=500)
    locations: List[str] = Field(default_factory=list, max_length=50)
    jd_text: Optional[str] = Field(default=None, max_length=100_000)
    source_url: Optional[str] = Field(default=None, max_length=2_000)
    deadline: Optional[date] = None

    @field_validator("job_id", "job_version_id")
    @classmethod
    def validate_identifiers(cls, value: Optional[str], info) -> Optional[str]:
        return validate_workspace_id(value, info.field_name) if value is not None else None

    @field_validator("company_name", "title")
    @classmethod
    def normalize_fields(cls, value: Optional[str]) -> Optional[str]:
        return normalize_text(value)

    @field_validator("locations")
    @classmethod
    def validate_locations(cls, value: List[str]) -> List[str]:
        result: List[str] = []
        for item in value:
            clean = normalize_text(item)
            if clean and clean not in result:
                if len(clean) > 500:
                    raise ValueError("location exceeds 500 characters")
                result.append(clean)
        return result

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: Optional[str]) -> Optional[str]:
        return validate_https_label(value)

    @model_validator(mode="after")
    def validate_source(self) -> "JobTrackCreate":
        if self.source_kind == JobTrackSourceKind.REVIEWED_JOB:
            if not self.job_id or not self.job_version_id:
                raise ValueError("reviewed_job requires job_id and job_version_id")
            forbidden = (self.company_name, self.title, self.jd_text, self.source_url)
            if any(value is not None for value in forbidden) or self.locations:
                raise ValueError("official job fields are resolved by the server")
        else:
            if self.job_id is not None or self.job_version_id is not None:
                raise ValueError("manual_jd must not reference the official job registry")
            if not self.company_name or not self.title or not self.jd_text or not self.jd_text.strip():
                raise ValueError("manual_jd requires company_name, title and jd_text")
        return self


class JobTrackUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    stage: Optional[JobTrackStage] = None
    deadline: Optional[date] = None
    closed_reason: Optional[JobTrackClosedReason] = None
    closed_reason_note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("closed_reason_note")
    @classmethod
    def normalize_note(cls, value: Optional[str]) -> Optional[str]:
        return normalize_text(value)


class UserActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: Optional[str] = Field(default=None, max_length=128)
    title: str = Field(min_length=1, max_length=300)
    reason: Optional[str] = Field(default=None, max_length=2_000)
    completion_criteria: str = Field(min_length=1, max_length=2_000)
    priority: ActionPriority = ActionPriority.MEDIUM
    due_at: Optional[datetime] = None

    @field_validator("track_id")
    @classmethod
    def validate_track_id(cls, value: Optional[str]) -> Optional[str]:
        return validate_workspace_id(value, "track_id") if value is not None else None

    @field_validator("title", "completion_criteria")
    @classmethod
    def normalize_required_fields(cls, value: str) -> str:
        clean = normalize_text(value)
        if not clean:
            raise ValueError("field must not be blank")
        return clean

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: Optional[str]) -> Optional[str]:
        return normalize_text(value)

    @field_validator("due_at")
    @classmethod
    def require_aware_due_at(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("due_at must include a timezone")
        return value


class ActionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    completion_criteria: Optional[str] = Field(default=None, min_length=1, max_length=2_000)
    priority: Optional[ActionPriority] = None
    due_at: Optional[datetime] = None
    status: Optional[ActionStatus] = None

    @field_validator("title", "completion_criteria")
    @classmethod
    def normalize_fields(cls, value: Optional[str]) -> Optional[str]:
        return normalize_text(value)

    @field_validator("due_at")
    @classmethod
    def require_aware_due_at(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("due_at must include a timezone")
        return value


class SystemSuggestionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=2_000)
    completion_criteria: str = Field(min_length=1, max_length=2_000)
    source_type: ActionSourceType
    source_ref: ActionSourceReference
    priority: ActionPriority = ActionPriority.MEDIUM
    due_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_source(self) -> "SystemSuggestionDraft":
        if self.source_type == ActionSourceType.NONE:
            raise ValueError("system suggestion requires a traceable source")
        return self


def persist_system_suggestions(
    track_id: str,
    drafts: List[SystemSuggestionDraft],
) -> List[ActionItem]:
    """Server-only bridge for a later Career Planning structured adapter."""
    registry = workspace_registry()
    track = registry.get_track(track_id)
    if track is None:
        raise WorkspaceNotFoundError(track_id)
    if not drafts or len(drafts) > 5:
        raise ValueError("one to five suggestions are required")
    now = utc_now()
    items: List[ActionItem] = []
    for draft in drafts:
        if draft.source_type == ActionSourceType.JOB_REQUIREMENT:
            allowed = {item.source_ref for item in track.requirement_snapshot}
            if draft.source_ref.reference_id not in allowed:
                raise ValueError("suggestion source does not belong to the tracked JD")
        elif not draft.source_ref.reference_id.startswith(f"track:{track_id}:"):
            raise ValueError("suggestion source does not belong to the target job")
        original = draft.model_dump(mode="json")
        item = ActionItem(
            action_id=f"action_{uuid.uuid4().hex}",
            track_id=track_id,
            title=draft.title,
            reason=draft.reason,
            completion_criteria=draft.completion_criteria,
            origin=ActionOrigin.SYSTEM_SUGGESTION,
            source_type=draft.source_type,
            source_ref=draft.source_ref,
            original_suggestion=original,
            status=ActionStatus.SUGGESTED,
            priority=draft.priority,
            due_at=draft.due_at,
            created_at=now,
            updated_at=now,
        )
        items.append(item)
    return registry.create_actions(items)


def _requirements_snapshot(job_version: Dict[str, Any]) -> List[WorkspaceRequirementSnapshot]:
    version_id = str(job_version["job_version_id"])
    reviewed = {
        item.requirement_id: item
        for item in _evidence_registry().list_reviewed_requirements(version_id)
        if item.extraction_status == RequirementExtractionStatus.PARSED
    }
    try:
        drafts = extract_requirement_drafts(job_version)
    except RequirementReviewError:
        drafts = []
    combined = {item.requirement_id: item for item in drafts}
    combined.update(reviewed)
    return [
        WorkspaceRequirementSnapshot(
            requirement_id=item.requirement_id,
            text=item.text,
            source_kind="official_jd",
            source_ref=f"job-version:{version_id}:{item.requirement_id}",
        )
        for item in sorted(combined.values(), key=lambda value: value.requirement_id)
    ]


def _source_state(
    track: JobTrack,
    current_jobs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if track.source_kind == JobTrackSourceKind.MANUAL_JD:
        return {"status": "manual", "current_job_version_id": None}
    jobs = (
        current_jobs
        if current_jobs is not None
        else _knowledge_base().list_job_postings(status="active", limit=500)
    )
    current = next((item for item in jobs if str(item.get("job_id")) == track.job_id), None)
    if not current or current.get("review_status") != "approved":
        return {"status": "unavailable", "current_job_version_id": None}
    current_version = str(current.get("current_version_id") or "")
    return {
        "status": "current" if current_version == track.job_version_id else "updated",
        "current_job_version_id": current_version or None,
        "last_verified_at": current.get("last_verified_at"),
    }


def _track_view(
    track: JobTrack,
    current_jobs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return {"track": track, "source_state": _source_state(track, current_jobs)}


@router.post("/session", status_code=204)
async def start_workspace_session(request: Request, response: Response):
    token = create_workspace_session(request)
    response.set_cookie(
        WORKSPACE_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="strict",
        secure=False,
        path="/v2/workspace",
    )
    return None


@router.delete("/session", status_code=204)
async def end_workspace_session(
    response: Response,
    token: Optional[str] = Cookie(default=None, alias=WORKSPACE_COOKIE),
):
    revoke_workspace_session(token)
    response.delete_cookie(WORKSPACE_COOKIE, path="/v2/workspace")
    return None


@router.post("/tracks", status_code=201, dependencies=[Depends(require_workspace_session)])
async def create_track(
    body: JobTrackCreate,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    now = utc_now()
    if body.source_kind == JobTrackSourceKind.REVIEWED_JOB:
        job = _knowledge_base().get_current_approved_job_version(
            job_id=body.job_id,
            version_id=body.job_version_id,
            max_age_days=body.job_max_age_days,
        )
        if not job:
            raise HTTPException(404, "current approved job version not found")
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        track = JobTrack(
            track_id=f"track_{uuid.uuid4().hex}",
            source_kind=body.source_kind,
            company_name=str(payload.get("company_name") or job.get("company_name") or ""),
            title=str(payload.get("title") or job.get("title") or ""),
            locations=payload.get("locations") or [],
            job_id=str(job["job_id"]),
            job_version_id=str(job["job_version_id"]),
            source_url=str(job.get("source_url") or payload.get("source_url") or ""),
            source_snapshot={
                "source_id": job.get("source_id"),
                "content_hash": job.get("content_hash"),
                "last_verified_at": job.get("last_verified_at"),
                "reviewed_at": job.get("reviewed_at"),
            },
            requirement_snapshot=_requirements_snapshot(job),
            deadline=body.deadline,
            created_at=now,
            updated_at=now,
        )
    else:
        track = JobTrack(
            track_id=f"track_{uuid.uuid4().hex}",
            source_kind=body.source_kind,
            company_name=body.company_name,
            title=body.title,
            locations=body.locations,
            source_url=body.source_url,
            jd_text=body.jd_text,
            source_snapshot={
                "jd_sha256": request_fingerprint(body.jd_text),
                "source_url_is_label_only": True,
            },
            deadline=body.deadline,
            created_at=now,
            updated_at=now,
        )
    try:
        saved = workspace_registry().create_track(
            track,
            idempotency_key=idempotency_key,
            request_hash=request_fingerprint(body.model_dump(mode="json")),
        )
    except WorkspaceConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _track_view(saved)


@router.get("/tracks", dependencies=[Depends(require_workspace_session)])
async def list_tracks(
    stage: Optional[JobTrackStage] = None,
    limit: int = Query(default=100, ge=1, le=200),
):
    items = workspace_registry().list_tracks(
        stage=stage.value if stage else None,
        limit=limit,
    )
    current_jobs = (
        _knowledge_base().list_job_postings(status="active", limit=500)
        if any(item.source_kind == JobTrackSourceKind.REVIEWED_JOB for item in items)
        else []
    )
    return {
        "count": len(items),
        "items": [_track_view(item, current_jobs) for item in items],
    }


@router.get("/tracks/{track_id}", dependencies=[Depends(require_workspace_session)])
async def get_track(track_id: str):
    track = workspace_registry().get_track(_identifier(track_id, "track_id"))
    if track is None:
        raise HTTPException(404, "target job not found")
    return _track_view(track)


@router.patch("/tracks/{track_id}", dependencies=[Depends(require_workspace_session)])
async def update_track(track_id: str, body: JobTrackUpdate):
    track_id = _identifier(track_id, "track_id")
    current = workspace_registry().get_track(track_id)
    if current is None:
        raise HTTPException(404, "target job not found")
    fields = body.model_fields_set
    stage = body.stage if "stage" in fields else current.stage
    deadline = body.deadline if "deadline" in fields else current.deadline
    closed_reason = body.closed_reason if "closed_reason" in fields else current.closed_reason
    closed_note = body.closed_reason_note if "closed_reason_note" in fields else current.closed_reason_note
    if stage != JobTrackStage.CLOSED:
        closed_reason = None
        closed_note = None
    updated = current.model_copy(
        update={
            "stage": stage,
            "deadline": deadline,
            "closed_reason": closed_reason,
            "closed_reason_note": closed_note,
            "updated_at": utc_now(),
            "revision": body.revision + 1,
        }
    )
    try:
        updated = JobTrack.model_validate(updated.model_dump())
        saved = workspace_registry().replace_track(updated, expected_revision=body.revision)
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except WorkspaceConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(404, "target job not found") from exc
    return _track_view(saved)


@router.get(
    "/tracks/{track_id}/deletion-impact",
    dependencies=[Depends(require_workspace_session)],
)
async def track_deletion_impact(track_id: str):
    try:
        return workspace_registry().track_deletion_impact(
            _identifier(track_id, "track_id")
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(404, "target job not found") from exc


@router.delete("/tracks/{track_id}", dependencies=[Depends(require_workspace_session)])
async def delete_track(
    track_id: str,
    revision: int = Query(ge=1),
    cascade_actions: bool = Query(default=False),
):
    try:
        deleted = workspace_registry().delete_track(
            _identifier(track_id, "track_id"),
            expected_revision=revision,
            cascade_actions=cascade_actions,
        )
    except WorkspaceConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(404, "target job not found") from exc
    return {"deleted": deleted}


@router.post("/actions", status_code=201, dependencies=[Depends(require_workspace_session)])
async def create_action(
    body: UserActionCreate,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    now = utc_now()
    action = ActionItem(
        action_id=f"action_{uuid.uuid4().hex}",
        track_id=body.track_id,
        title=body.title,
        reason=body.reason,
        completion_criteria=body.completion_criteria,
        origin=ActionOrigin.USER_CREATED,
        source_type=ActionSourceType.NONE,
        status=ActionStatus.TODO,
        priority=body.priority,
        due_at=body.due_at,
        created_at=now,
        updated_at=now,
    )
    try:
        return workspace_registry().create_action(
            action,
            idempotency_key=idempotency_key,
            request_hash=request_fingerprint(body.model_dump(mode="json")),
        )
    except WorkspaceConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except WorkspaceReferenceError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/actions", dependencies=[Depends(require_workspace_session)])
async def list_actions(
    track_id: Optional[str] = Query(default=None, max_length=128),
    status: Optional[ActionStatus] = None,
    limit: int = Query(default=200, ge=1, le=500),
):
    if track_id is not None:
        track_id = _identifier(track_id, "track_id")
    items = workspace_registry().list_actions(
        track_id=track_id,
        status=status.value if status else None,
        limit=limit,
    )
    return {"count": len(items), "items": items}


@router.get("/actions/{action_id}", dependencies=[Depends(require_workspace_session)])
async def get_action(action_id: str):
    action = workspace_registry().get_action(_identifier(action_id, "action_id"))
    if action is None:
        raise HTTPException(404, "action not found")
    return action


@router.patch("/actions/{action_id}", dependencies=[Depends(require_workspace_session)])
async def update_action(action_id: str, body: ActionUpdate):
    action_id = _identifier(action_id, "action_id")
    current = workspace_registry().get_action(action_id)
    if current is None:
        raise HTTPException(404, "action not found")
    fields = body.model_fields_set
    updates: Dict[str, Any] = {
        "updated_at": utc_now(),
        "revision": body.revision + 1,
    }
    for field in ("title", "completion_criteria", "priority", "due_at", "status"):
        if field in fields:
            updates[field] = getattr(body, field)
    target_status = updates.get("status", current.status)
    if target_status == ActionStatus.COMPLETED:
        updates["completed_at"] = current.completed_at or utc_now()
    else:
        updates["completed_at"] = None
    editable = {"title", "completion_criteria", "priority", "due_at"}
    if current.origin == ActionOrigin.SYSTEM_SUGGESTION and fields.intersection(editable):
        updates["edited_at"] = utc_now()
    try:
        updated = ActionItem.model_validate(current.model_copy(update=updates).model_dump())
        return workspace_registry().replace_action(updated, expected_revision=body.revision)
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except WorkspaceConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except WorkspaceReferenceError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/actions/{action_id}", status_code=204, dependencies=[Depends(require_workspace_session)])
async def delete_action(action_id: str, revision: int = Query(ge=1)):
    try:
        workspace_registry().delete_action(
            _identifier(action_id, "action_id"),
            expected_revision=revision,
        )
    except WorkspaceConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(404, "action not found") from exc
    return Response(status_code=204)


@router.get("/summary", dependencies=[Depends(require_workspace_session)])
async def workspace_summary(
    timezone_offset_minutes: int = Query(default=480, ge=-840, le=840),
):
    local_zone = timezone(timedelta(minutes=timezone_offset_minutes))
    now = datetime.now(timezone.utc)
    local_today = now.astimezone(local_zone).date()
    tracks = workspace_registry().list_tracks(limit=None)
    actions = workspace_registry().list_actions(limit=None)
    track_stage = {track.track_id: track.stage for track in tracks}
    priority_rank = {ActionPriority.HIGH: 0, ActionPriority.MEDIUM: 1, ActionPriority.LOW: 2}
    stage_rank = {
        JobTrackStage.INTERVIEWING: 0,
        JobTrackStage.APPLIED: 1,
        JobTrackStage.PREPARING: 2,
        JobTrackStage.WATCHING: 3,
        JobTrackStage.CLOSED: 4,
    }

    def urgency(item: ActionItem) -> int:
        if item.due_at is None:
            return 2
        due = item.due_at.astimezone(timezone.utc)
        if due < now:
            return 0
        return 1 if due <= now + timedelta(hours=48) else 2

    todo = [item for item in actions if item.status == ActionStatus.TODO]
    todo.sort(
        key=lambda item: (
            urgency(item),
            priority_rank[item.priority],
            stage_rank.get(track_stage.get(item.track_id), 5),
            item.due_at or datetime.max.replace(tzinfo=timezone.utc),
            item.created_at,
            item.action_id,
        )
    )
    next_week = local_today + timedelta(days=7)
    due_soon = [
        item
        for item in todo
        if item.due_at
        and local_today <= item.due_at.astimezone(local_zone).date() <= next_week
    ]
    stage_counts = {stage.value: 0 for stage in JobTrackStage}
    for track in tracks:
        stage_counts[track.stage.value] += 1
    return {
        "timezone_offset_minutes": timezone_offset_minutes,
        "today": local_today,
        "today_priority": todo[:5],
        "due_within_7_days": due_soon,
        "stage_counts": stage_counts,
        "suggested_count": sum(item.status == ActionStatus.SUGGESTED for item in actions),
        "recent_tracks": sorted(tracks, key=lambda item: (item.updated_at, item.track_id), reverse=True)[:5],
    }


@router.get("/export", dependencies=[Depends(require_workspace_session)])
async def export_workspace():
    return {"exported_at": utc_now(), **workspace_registry().export_snapshot()}


@router.get("/deletion-impact", dependencies=[Depends(require_workspace_session)])
async def workspace_deletion_impact():
    return workspace_registry().deletion_impact()


@router.delete("", dependencies=[Depends(require_workspace_session)])
async def clear_workspace(
    confirmation: Literal["DELETE_LOCAL_WORKSPACE"] = Query(),
):
    del confirmation
    return {"deleted": workspace_registry().clear()}
