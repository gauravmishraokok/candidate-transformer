from pydantic import BaseModel, field_validator
from typing import Optional


class Location(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None  # ISO-3166 alpha-2


class Links(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: list[str] = []


class SkillEntry(BaseModel):
    name: str
    confidence: float
    sources: list[str] = []


class ExperienceEntry(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None  # YYYY-MM
    end: Optional[str] = None    # YYYY-MM or None if current
    summary: Optional[str] = None


class EducationEntry(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year: Optional[int] = None


class ProvenanceEntry(BaseModel):
    field: str
    source: str
    method: str  # "direct_field" | "api_response" | "llm_extraction" | "field_mapped"
    raw_value: str
    reliability_weight: float


class CanonicalProfile(BaseModel):
    candidate_id: str
    full_name: Optional[str] = None
    emails: list[str] = []
    phones: list[str] = []
    location: Optional[Location] = None
    links: Optional[Links] = None
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list[SkillEntry] = []
    experience: list[ExperienceEntry] = []
    education: list[EducationEntry] = []
    provenance: list[ProvenanceEntry] = []
    overall_confidence: float = 0.0

    @field_validator('overall_confidence')
    @classmethod
    def confidence_bounded(cls, v):
        return max(0.0, min(1.0, v))
