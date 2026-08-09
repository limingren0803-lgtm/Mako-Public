"""
Mako 职业画像数据模型。

用于统一保存求职者的教育、经历、技能、岗位偏好和现实约束。
模型只负责数据结构与校验，不负责数据库读写。
"""

from enum import Enum
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, Field


class FactStatus(str, Enum):
    """职业信息的确认状态。"""

    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    ASSUMED = "assumed"


class PreferenceLevel(str, Enum):
    """用户对岗位、地区等选项的偏好强度。"""

    HARD_CONSTRAINT = "hard_constraint"
    STRONG_PREFERENCE = "strong_preference"
    GENERAL_PREFERENCE = "general_preference"
    UNKNOWN = "unknown"


class DirectionLevel(str, Enum):
    """岗位方向优先级。"""

    MAIN = "main"
    SECONDARY = "secondary"
    EXPLORE = "explore"
    NOT_PRIORITY = "not_priority"


class SkillGapType(str, Enum):
    """能力差距类型。"""

    ACTUAL = "actual"
    EXPRESSION = "expression"
    CAPABILITY = "capability"
    QUALIFICATION_RISK = "qualification_risk"
    UNKNOWN = "unknown"


class CareerFact(BaseModel):
    """带确认状态和来源的单项事实。"""

    value: str
    status: FactStatus = FactStatus.UNCONFIRMED
    source: Optional[str] = None
    last_updated: Optional[str] = None


class EducationRecord(BaseModel):
    """教育经历。"""

    institution: Optional[CareerFact] = None
    degree: Optional[CareerFact] = None
    major: Optional[CareerFact] = None
    start_date: Optional[CareerFact] = None
    graduation_date: Optional[CareerFact] = None
    location: Optional[CareerFact] = None
    credential_status: Optional[CareerFact] = None


class ExperienceRecord(BaseModel):
    """实习、项目或校园经历。"""

    experience_type: str
    organisation: Optional[CareerFact] = None
    role: Optional[CareerFact] = None
    start_date: Optional[CareerFact] = None
    end_date: Optional[CareerFact] = None
    responsibilities: List[CareerFact] = Field(default_factory=list)
    outcomes: List[CareerFact] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)


class SkillRecord(BaseModel):
    """技能及其证据。"""

    name: str
    level: Optional[CareerFact] = None
    evidence: List[str] = Field(default_factory=list)
    gap_type: SkillGapType = SkillGapType.UNKNOWN


class LocationPreference(BaseModel):
    """求职地区偏好。"""

    location: str = Field(
        validation_alias=AliasChoices("location", "city"),
        serialization_alias="location",
    )
    level: PreferenceLevel = PreferenceLevel.UNKNOWN
    status: FactStatus = FactStatus.UNCONFIRMED


class RolePreference(BaseModel):
    """目标岗位或岗位方向。"""

    role: str
    direction_level: DirectionLevel = DirectionLevel.EXPLORE
    preference_level: PreferenceLevel = PreferenceLevel.UNKNOWN
    status: FactStatus = FactStatus.UNCONFIRMED
    reasons: List[str] = Field(default_factory=list)


class CareerConstraint(BaseModel):
    """求职现实约束。"""

    name: str
    value: str
    level: PreferenceLevel = PreferenceLevel.UNKNOWN
    status: FactStatus = FactStatus.UNCONFIRMED


class CareerProfile(BaseModel):
    """Mako 统一职业画像。"""

    education: List[EducationRecord] = Field(default_factory=list)
    experiences: List[ExperienceRecord] = Field(default_factory=list)
    skills: List[SkillRecord] = Field(default_factory=list)
    target_roles: List[RolePreference] = Field(default_factory=list)
    location_preferences: List[LocationPreference] = Field(default_factory=list)
    constraints: List[CareerConstraint] = Field(default_factory=list)
    strengths: List[CareerFact] = Field(default_factory=list)
    gaps: List[CareerFact] = Field(default_factory=list)
    risks: List[CareerFact] = Field(default_factory=list)
    questions_to_confirm: List[str] = Field(default_factory=list)
    last_updated: Optional[str] = None
