"""Versioned evidence and decision contracts for Mako 2.0."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from core.security import validate_identifier


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceType(str, Enum):
    USER_STATEMENT = "user_statement"
    RESUME = "resume"
    PORTFOLIO = "portfolio"
    CERTIFICATE = "certificate"
    TRANSCRIPT = "transcript"
    OFFICIAL_JD = "official_jd"
    OTHER = "other"


class EvidenceStrength(str, Enum):
    DIRECT = "direct"
    SUPPORTING = "supporting"
    WEAK = "weak"
    UNKNOWN = "unknown"


class EvidenceRelation(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"


class EvidenceFactStatus(str, Enum):
    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    ASSUMED = "assumed"


class PrivacyClass(str, Enum):
    GENERAL = "general"
    PERSONAL = "personal"
    SENSITIVE = "sensitive"


class EvidenceRecord(BaseModel):
    """A bounded reference to evidence without requiring a full source copy."""

    schema_version: str = "2.0"
    evidence_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)
    claim: str = Field(min_length=1, max_length=4_000)
    evidence_type: EvidenceType
    source_ref: Optional[str] = Field(default=None, max_length=1_000)
    fact_status: EvidenceFactStatus = EvidenceFactStatus.UNCONFIRMED
    strength: EvidenceStrength = EvidenceStrength.UNKNOWN
    relation: EvidenceRelation = EvidenceRelation.SUPPORTS
    captured_at: datetime = Field(default_factory=_utc_now)
    verified_at: Optional[datetime] = None
    privacy_class: PrivacyClass = PrivacyClass.PERSONAL

    @field_validator("evidence_id")
    @classmethod
    def _validate_identifier(cls, value: str) -> str:
        clean = value.strip()
        if not clean or not all(
            char.isascii() and (char.isalnum() or char in "_-:")
            for char in clean
        ):
            raise ValueError("identifier contains unsupported characters")
        return clean

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, value: str) -> str:
        return validate_identifier(value, "user_id")

    @field_validator("claim", "source_ref")
    @classmethod
    def _normalize_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = " ".join(value.split())
        return clean or None

    @field_validator("captured_at", "verified_at")
    @classmethod
    def _require_aware_datetime(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def _validate_confirmation_time(self) -> "EvidenceRecord":
        if self.fact_status == EvidenceFactStatus.CONFIRMED and self.verified_at is None:
            raise ValueError("confirmed evidence requires verified_at")
        if self.verified_at is not None and self.verified_at < self.captured_at:
            raise ValueError("verified_at cannot be earlier than captured_at")
        return self


class ConfirmationDecision(str, Enum):
    CONFIRM = "confirm"
    CORRECT = "correct"
    REJECT = "reject"
    WITHDRAW = "withdraw"


class ConfirmationScope(str, Enum):
    REQUEST = "request"
    LONG_TERM_PROFILE = "long_term_profile"


class ConfirmationObjectType(str, Enum):
    EVIDENCE = "evidence"
    MATCH_DECISION = "match_decision"
    RESUME_CLAIM = "resume_claim"
    ACTION_ITEM = "action_item"


class UserConfirmation(BaseModel):
    """An explicit user decision with request-local scope by default."""

    schema_version: str = "2.0"
    confirmation_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)
    object_type: ConfirmationObjectType
    object_id: str = Field(min_length=1, max_length=128)
    decision: ConfirmationDecision
    scope: ConfirmationScope = ConfirmationScope.REQUEST
    request_id: Optional[str] = Field(default=None, max_length=128)
    corrected_value: Optional[str] = Field(default=None, max_length=4_000)
    decided_at: datetime = Field(default_factory=_utc_now)

    @field_validator("confirmation_id", "object_id", "request_id")
    @classmethod
    def _validate_identifier(cls, value: Optional[str]) -> Optional[str]:
        return EvidenceRecord._validate_identifier(value) if value is not None else None

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, value: str) -> str:
        return validate_identifier(value, "user_id")

    @field_validator("corrected_value")
    @classmethod
    def _normalize_correction(cls, value: Optional[str]) -> Optional[str]:
        return EvidenceRecord._normalize_text(value)

    @field_validator("decided_at")
    @classmethod
    def _require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def _validate_correction(self) -> "UserConfirmation":
        if self.scope == ConfirmationScope.REQUEST and not self.request_id:
            raise ValueError("request-scoped confirmation requires request_id")
        if self.decision == ConfirmationDecision.CORRECT:
            if not self.corrected_value:
                raise ValueError("correct decision requires corrected_value")
        elif self.corrected_value is not None:
            raise ValueError("corrected_value is only valid for correct decisions")
        return self


class RequirementCategory(str, Enum):
    QUALIFICATION = "qualification"
    SKILL = "skill"
    EXPERIENCE = "experience"
    RESPONSIBILITY = "responsibility"
    LOCATION = "location"
    LANGUAGE = "language"
    OTHER = "other"


class RequirementImportance(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    UNCLEAR = "unclear"


class RequirementExtractionStatus(str, Enum):
    PARSED = "parsed"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class RequirementReviewDecision(str, Enum):
    CONFIRM = "confirm"
    CORRECT = "correct"
    REJECT = "reject"


class RequirementSourceField(str, Enum):
    REQUIREMENTS = "requirements"
    RESPONSIBILITIES = "responsibilities"


class SourceSpan(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def _validate_order(self) -> "SourceSpan":
        if self.end <= self.start:
            raise ValueError("source span end must be greater than start")
        return self


class JDRequirement(BaseModel):
    """One traceable requirement extracted from an approved job version."""

    schema_version: str = "2.0"
    requirement_id: str = Field(min_length=1, max_length=128)
    job_version_id: str = Field(min_length=1, max_length=128)
    category: RequirementCategory
    importance: RequirementImportance = RequirementImportance.UNCLEAR
    text: str = Field(min_length=1, max_length=4_000)
    normalized_terms: List[str] = Field(default_factory=list, max_length=50)
    extraction_status: RequirementExtractionStatus = RequirementExtractionStatus.NEEDS_REVIEW
    source_field: Optional[RequirementSourceField] = None
    source_index: Optional[int] = Field(default=None, ge=0)
    source_span: Optional[SourceSpan] = None

    @field_validator("requirement_id")
    @classmethod
    def _validate_identifier(cls, value: str) -> str:
        return EvidenceRecord._validate_identifier(value)

    @field_validator("job_version_id")
    @classmethod
    def _validate_job_version_id(cls, value: str) -> str:
        return EvidenceRecord._validate_identifier(value)

    @field_validator("text")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        normalized = EvidenceRecord._normalize_text(value)
        if not normalized:
            raise ValueError("requirement text must not be blank")
        return normalized

    @field_validator("normalized_terms", mode="before")
    @classmethod
    def _normalize_terms(cls, value: object) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("normalized_terms must be a list")
        terms: List[str] = []
        seen = set()
        for item in value:
            term = " ".join(str(item).split()).casefold()
            if len(term) > 200:
                raise ValueError("normalized term exceeds 200 characters")
            if term and term not in seen:
                terms.append(term)
                seen.add(term)
        return terms


class JDRequirementReview(BaseModel):
    """One explicit, immutable review of an extracted JD requirement."""

    schema_version: str = "2.0"
    review_id: str = Field(min_length=1, max_length=128)
    requirement_id: str = Field(min_length=1, max_length=128)
    job_version_id: str = Field(min_length=1, max_length=128)
    reviewer_id: str = Field(min_length=1, max_length=128)
    decision: RequirementReviewDecision
    category: RequirementCategory
    importance: RequirementImportance = RequirementImportance.UNCLEAR
    normalized_terms: List[str] = Field(default_factory=list, max_length=50)
    corrected_text: Optional[str] = Field(default=None, max_length=4_000)
    reviewed_at: datetime = Field(default_factory=_utc_now)

    @field_validator("review_id", "requirement_id", "job_version_id")
    @classmethod
    def _validate_identifier(cls, value: str) -> str:
        return EvidenceRecord._validate_identifier(value)

    @field_validator("reviewer_id")
    @classmethod
    def _validate_reviewer_id(cls, value: str) -> str:
        return validate_identifier(value, "reviewer_id")

    @field_validator("normalized_terms", mode="before")
    @classmethod
    def _normalize_terms(cls, value: object) -> List[str]:
        return JDRequirement._normalize_terms(value)

    @field_validator("corrected_text")
    @classmethod
    def _normalize_corrected_text(cls, value: Optional[str]) -> Optional[str]:
        return EvidenceRecord._normalize_text(value)

    @field_validator("reviewed_at")
    @classmethod
    def _require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reviewed_at must include a timezone")
        return value

    @model_validator(mode="after")
    def _validate_decision_fields(self) -> "JDRequirementReview":
        if self.decision == RequirementReviewDecision.CORRECT:
            if not self.corrected_text:
                raise ValueError("correct decision requires corrected_text")
        elif self.corrected_text is not None:
            raise ValueError("corrected_text is only valid for correct decisions")
        if self.decision == RequirementReviewDecision.REJECT:
            if self.normalized_terms:
                raise ValueError("rejected requirement cannot include normalized_terms")
        elif not self.normalized_terms:
            raise ValueError("accepted requirement requires normalized_terms")
        return self


class MatchStatus(str, Enum):
    MET = "met"
    PARTIAL = "partial"
    GAP = "gap"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class MatchDecision(BaseModel):
    """A requirement-level decision whose evidence remains inspectable."""

    schema_version: str = "2.0"
    decision_id: str = Field(min_length=1, max_length=128)
    requirement_id: str = Field(min_length=1, max_length=128)
    status: MatchStatus
    evidence_ids: List[str] = Field(default_factory=list, max_length=100)
    reason: str = Field(min_length=1, max_length=2_000)
    confidence: float = Field(ge=0.0, le=1.0)
    questions_to_confirm: List[str] = Field(default_factory=list, max_length=20)

    @field_validator("decision_id", "requirement_id")
    @classmethod
    def _validate_identifier(cls, value: str) -> str:
        return EvidenceRecord._validate_identifier(value)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def _deduplicate_evidence_ids(cls, value: object) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("evidence_ids must be a list")
        result: List[str] = []
        for item in value:
            evidence_id = EvidenceRecord._validate_identifier(str(item))
            if evidence_id not in result:
                result.append(evidence_id)
        return result
