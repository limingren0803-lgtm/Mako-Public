"""Data contracts for the local personal career knowledge base."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class MaterialFileType(str, Enum):
    TXT = "txt"
    MARKDOWN = "md"
    PDF = "pdf"
    DOCX = "docx"


class MaterialCategory(str, Enum):
    RESUME = "resume"
    PROJECT = "project"
    COURSE = "course"
    NOTE = "note"
    OTHER = "other"


class MaterialStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MaterialIndexStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class LocatorType(str, Enum):
    LINE = "line"
    PAGE = "page"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_identifier(value: str, label: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"invalid {label}")
    return value


def normalize_text(value: str, *, max_length: int, label: str) -> str:
    clean = " ".join(value.split())
    if not clean:
        raise ValueError(f"{label} is required")
    if len(clean) > max_length:
        raise ValueError(f"{label} exceeds {max_length} characters")
    return clean


class ExtractedSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int = Field(ge=0, le=100_000)
    locator_type: LocatorType
    locator_label: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=1_000_000)

    @field_validator("locator_label")
    @classmethod
    def normalize_locator(cls, value: str) -> str:
        return normalize_text(value, max_length=200, label="locator label")

    @field_validator("text")
    @classmethod
    def normalize_section_text(cls, value: str) -> str:
        clean = value.replace("\x00", "").strip()
        if not clean:
            raise ValueError("section text is required")
        return clean


class ExtractedMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_filename: str = Field(min_length=1, max_length=255)
    file_type: MaterialFileType
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=1, le=10 * 1024 * 1024)
    character_count: int = Field(ge=1, le=1_000_000)
    sections: List[ExtractedSection] = Field(min_length=1, max_length=100_000)
    warnings: List[str] = Field(default_factory=list, max_length=20)

    @property
    def normalized_text(self) -> str:
        return "\n\n".join(section.text for section in self.sections)


class MaterialSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    material_id: str
    ordinal: int = Field(ge=0, le=100_000)
    locator_type: LocatorType
    locator_label: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=1_000_000)

    @field_validator("section_id", "material_id")
    @classmethod
    def identifiers(cls, value: str, info) -> str:
        return validate_identifier(value, info.field_name)


class PersonalMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str
    title: str = Field(min_length=1, max_length=200)
    original_filename: str = Field(min_length=1, max_length=255)
    file_type: MaterialFileType
    category: MaterialCategory
    status: MaterialStatus = MaterialStatus.ACTIVE
    index_status: MaterialIndexStatus = MaterialIndexStatus.PENDING
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=1, le=10 * 1024 * 1024)
    character_count: int = Field(ge=1, le=1_000_000)
    section_count: int = Field(ge=1, le=100_000)
    created_at: datetime
    updated_at: datetime
    revision: int = Field(default=1, ge=1)

    @field_validator("material_id")
    @classmethod
    def identifier(cls, value: str) -> str:
        return validate_identifier(value, "material_id")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return normalize_text(value, max_length=200, label="title")

    @field_validator("original_filename")
    @classmethod
    def normalize_filename(cls, value: str) -> str:
        if "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError("original_filename must be a basename")
        return normalize_text(value, max_length=255, label="original_filename")


class PersonalKnowledgeSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str
    title: str
    category: MaterialCategory
    locators: List[str] = Field(min_length=1, max_length=20)
    excerpts: List[str] = Field(min_length=1, max_length=20)


class MaterialSearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str
    title: str
    category: MaterialCategory
    section_id: str
    locator_type: LocatorType
    locator_label: str
    excerpt: str = Field(max_length=500)
    distance: float = Field(ge=0)


def material_payload(material: PersonalMaterial) -> Dict[str, Any]:
    return material.model_dump(mode="json")
