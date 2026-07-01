from pydantic import BaseModel
from typing import Optional


class RawProvenanceItem(BaseModel):
    source_id: str
    source_type: str
    raw_value: str
    reliability_weight: float


class RawRecord(BaseModel):
    """
    Intermediate record returned by every extractor.
    Fields are Optional — extractors only fill what they can find.
    All string values here are RAW (not yet normalized).
    """
    source_id: str
    source_type: str  # "CSV" | "ATS_JSON" | "GITHUB_API" | "LLM_TEXT"
    reliability_weight: float

    full_name: Optional[str] = None
    emails: list[str] = []
    phones: list[str] = []
    location_raw: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    years_experience: Optional[float] = None

    skills_raw: list[str] = []

    experience: list[dict] = []
    # Each dict: {company, title, start_raw, end_raw, summary}

    education: list[dict] = []
    # Each dict: {institution, degree, field, end_year_raw}
