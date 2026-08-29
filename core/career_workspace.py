"""Persistent contracts for the local Mako career workspace."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_workspace_id(value: str, field_name: str) -> str:
    clean = value.strip()
    if not clean or len(clean) > 128:
        raise ValueError(f"{field_name} is invalid")
    if not all(char.isascii() and (char.isalnum() or char in "_-:") for char in clean):
        raise ValueError(f"{field_name} contains unsupported characters")
    return clean


def normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    clean = " ".join(value.split())
    return clean or None


def validate_https_label(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("source_url must be an HTTPS URL")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("source_url contains unsupported connection details")
    return value


class JobTrackSourceKind(str, Enum):
    REVIEWED_JOB = "reviewed_job"
    MANUAL_JD = "manual_jd"


class JobTrackStage(str, Enum):
    WATCHING = "watching"
    PREPARING = "preparing"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    CLOSED = "closed"


class JobTrackClosedReason(str, Enum):
    NOT_APPLIED = "not_applied"
    REJECTED = "rejected"
    USER_WITHDREW = "user_withdrew"
    OFFER_RECEIVED = "offer_received"
    OTHER = "other"


class ActionOrigin(str, Enum):
    SYSTEM_SUGGESTION = "system_suggestion"
    USER_CREATED = "user_created"


class ActionSourceType(str, Enum):
    JOB_REQUIREMENT = "job_requirement"
    INFORMATION_GAP = "information_gap"
    USER_INPUT = "user_input"
    NONE = "none"


class ActionStatus(str, Enum):
    SUGGESTED = "suggested"
    TODO = "todo"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ActionPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class WorkspaceRequirementSnapshot(BaseModel):
    requirement_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=4_000)
    source_kind: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1, max_length=256)

    @field_validator("requirement_id")
    @classmethod
    def validate_requirement_id(cls, value: str) -> str:
        return validate_workspace_id(value, "requirement_id")

    @field_validator("text")
    @classmethod
    def normalize_requirement_text(cls, value: str) -> str:
        clean = normalize_text(value)
        if not clean:
            raise ValueError("requirement text must not be blank")
        return clean


class ActionSourceReference(BaseModel):
    reference_id: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=500)
    excerpt: Optional[str] = Field(default=None, max_length=2_000)

    @field_validator("reference_id")
    @classmethod
    def validate_reference_id(cls, value: str) -> str:
        return validate_workspace_id(value, "reference_id")

    @field_validator("label", "excerpt")
    @classmethod
    def normalize_reference_text(cls, value: Optional[str]) -> Optional[str]:
        return normalize_text(value)


class JobTrack(BaseModel):
    schema_version: str = "2.3"
    track_id: str = Field(min_length=1, max_length=128)
    source_kind: JobTrackSourceKind
    company_name: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    locations: List[str] = Field(default_factory=list, max_length=50)
    job_id: Optional[str] = Field(default=None, max_length=128)
    job_version_id: Optional[str] = Field(default=None, max_length=128)
    source_url: Optional[str] = Field(default=None, max_length=2_000)
    jd_text: Optional[str] = Field(default=None, max_length=100_000)
    source_snapshot: Dict[str, Any] = Field(default_factory=dict)
    requirement_snapshot: List[WorkspaceRequirementSnapshot] = Field(
        default_factory=list,
        max_length=200,
    )
    stage: JobTrackStage = JobTrackStage.WATCHING
    deadline: Optional[date] = None
    closed_reason: Optional[JobTrackClosedReason] = None
    closed_reason_note: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    revision: int = Field(default=1, ge=1)

    @field_validator("track_id", "job_id", "job_version_id")
    @classmethod
    def validate_identifiers(cls, value: Optional[str], info) -> Optional[str]:
        return validate_workspace_id(value, info.field_name) if value is not None else None

    @field_validator("company_name", "title", "closed_reason_note")
    @classmethod
    def normalize_fields(cls, value: Optional[str]) -> Optional[str]:
        return normalize_text(value)

    @field_validator("locations", mode="before")
    @classmethod
    def normalize_locations(cls, value: object) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("locations must be a list")
        result: List[str] = []
        for item in value:
            clean = normalize_text(str(item))
            if clean and clean not in result:
                if len(clean) > 500:
                    raise ValueError("location exceeds 500 characters")
                result.append(clean)
        return result

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: Optional[str]) -> Optional[str]:
        return validate_https_label(value)

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_source_and_stage(self) -> "JobTrack":
        if self.source_kind == JobTrackSourceKind.REVIEWED_JOB:
            if not self.job_id or not self.job_version_id:
                raise ValueError("reviewed_job requires job_id and job_version_id")
            if self.jd_text is not None:
                raise ValueError("reviewed_job must not copy jd_text into the workspace")
        else:
            if self.job_id is not None or self.job_version_id is not None:
                raise ValueError("manual_jd must not reference the official job registry")
            if not self.jd_text or not self.jd_text.strip():
                raise ValueError("manual_jd requires jd_text")
        if self.stage == JobTrackStage.CLOSED:
            if self.closed_reason is None:
                raise ValueError("closed track requires closed_reason")
        elif self.closed_reason is not None or self.closed_reason_note is not None:
            raise ValueError("closed reason is only valid for a closed track")
        if self.closed_reason == JobTrackClosedReason.OTHER and not self.closed_reason_note:
            raise ValueError("other closed reason requires a note")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self


class ActionItem(BaseModel):
    schema_version: str = "2.3"
    action_id: str = Field(min_length=1, max_length=128)
    track_id: Optional[str] = Field(default=None, max_length=128)
    title: str = Field(min_length=1, max_length=300)
    reason: Optional[str] = Field(default=None, max_length=2_000)
    completion_criteria: str = Field(min_length=1, max_length=2_000)
    origin: ActionOrigin
    source_type: ActionSourceType = ActionSourceType.NONE
    source_ref: Optional[ActionSourceReference] = None
    original_suggestion: Optional[Dict[str, Any]] = None
    status: ActionStatus
    priority: ActionPriority = ActionPriority.MEDIUM
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    edited_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    revision: int = Field(default=1, ge=1)

    @field_validator("action_id", "track_id")
    @classmethod
    def validate_identifiers(cls, value: Optional[str], info) -> Optional[str]:
        return validate_workspace_id(value, info.field_name) if value is not None else None

    @field_validator("title", "reason", "completion_criteria")
    @classmethod
    def normalize_fields(cls, value: Optional[str]) -> Optional[str]:
        return normalize_text(value)

    @field_validator("due_at", "completed_at", "edited_at", "created_at", "updated_at")
    @classmethod
    def require_aware_datetime(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_origin_and_status(self) -> "ActionItem":
        if self.origin == ActionOrigin.SYSTEM_SUGGESTION:
            if not self.reason or self.source_type == ActionSourceType.NONE or not self.source_ref:
                raise ValueError("system suggestion requires a reason and traceable source")
            if self.original_suggestion is None:
                raise ValueError("system suggestion requires an immutable original snapshot")
        elif self.status == ActionStatus.SUGGESTED:
            raise ValueError("user-created action cannot use suggested status")
        if self.source_type == ActionSourceType.NONE and self.source_ref is not None:
            raise ValueError("source_ref requires a source_type")
        if self.source_type != ActionSourceType.NONE and self.source_ref is None:
            raise ValueError("source_type requires source_ref")
        if self.status == ActionStatus.COMPLETED:
            if self.completed_at is None:
                raise ValueError("completed action requires completed_at")
        elif self.completed_at is not None:
            raise ValueError("completed_at is only valid for completed actions")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self
