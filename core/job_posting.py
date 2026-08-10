"""Normalized job posting model for official career sources."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class RecruitmentType(str, Enum):
    """Recruitment channel published by the employer."""

    CAMPUS = "campus"
    EXPERIENCED = "experienced"
    INTERNSHIP = "internship"
    GRADUATE = "graduate"
    OTHER = "other"


class JobPostingStatus(str, Enum):
    """Lifecycle state of a normalized posting."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobPosting(BaseModel):
    """A traceable job posting normalized from an official career source."""

    schema_version: str = "1.0"
    source_id: str = Field(min_length=1, max_length=128)
    external_id: str = Field(min_length=1, max_length=256)
    company_name: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    department: Optional[str] = Field(default=None, max_length=500)
    job_category: Optional[str] = Field(default=None, max_length=200)
    recruitment_type: RecruitmentType = RecruitmentType.OTHER
    employment_type: Optional[str] = Field(default=None, max_length=200)
    locations: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=100_000)
    published_at: Optional[datetime] = None
    source_updated_at: Optional[datetime] = None
    valid_through: Optional[datetime] = None
    source_url: str
    fetched_at: datetime = Field(default_factory=_utc_now)
    status: JobPostingStatus = JobPostingStatus.ACTIVE

    @field_validator(
        "source_id",
        "external_id",
        "company_name",
        "title",
        "department",
        "job_category",
        "employment_type",
        mode="before",
    )
    @classmethod
    def _strip_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = " ".join(value.split())
            return value or None
        return value

    @field_validator("source_id", "external_id", "company_name", "title")
    @classmethod
    def _require_text(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("locations", "responsibilities", "requirements", mode="before")
    @classmethod
    def _normalize_list(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("value must be a list of strings")
        result: List[str] = []
        seen = set()
        for item in value:
            clean = " ".join(str(item).split())
            key = clean.casefold()
            if clean and key not in seen:
                result.append(clean)
                seen.add(key)
        return result

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: Any) -> str:
        return " ".join(str(value or "").split())

    @field_validator("source_url")
    @classmethod
    def _validate_source_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("source_url must be an HTTPS URL")
        if parsed.username or parsed.password:
            raise ValueError("source_url must not contain credentials")
        if parsed.port not in (None, 443):
            raise ValueError("source_url uses an unapproved port")
        return value

    def canonical_payload(self) -> dict[str, Any]:
        """Return the stable fields used to detect meaningful content changes."""
        return self.model_dump(
            mode="json",
            exclude={"fetched_at", "status"},
            exclude_none=True,
        )

    def content_hash(self) -> str:
        payload = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_search_text(self) -> str:
        """Build searchable text without dropping the source identity."""
        sections = [
            self.company_name,
            self.title,
            self.department or "",
            self.job_category or "",
            " ".join(self.locations),
            " ".join(self.responsibilities),
            " ".join(self.requirements),
            self.description,
            self.source_url,
        ]
        return "\n".join(section for section in sections if section)
