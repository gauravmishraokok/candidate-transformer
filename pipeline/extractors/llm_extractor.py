import logging
import os
from pathlib import Path
from typing import Optional
import instructor
from groq import Groq
from pydantic import BaseModel
from .base import BaseExtractor
from schemas.raw_record import RawRecord

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a precise data extraction assistant. Extract only "
    "information explicitly stated in the provided text. "
    "Do not infer, assume, or hallucinate any values. "
    "If a field is not mentioned, return null. Never invent data."
)


class ExperienceItem(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    start_raw: Optional[str] = None
    end_raw: Optional[str] = None
    summary: Optional[str] = None


class EducationItem(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year_raw: Optional[str] = None


class IdentityExtraction(BaseModel):
    reasoning: str
    full_name: Optional[str] = None
    emails: list[str] = []
    phones: list[str] = []
    location_raw: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    headline: Optional[str] = None
    years_experience: Optional[float] = None


class ExperienceExtraction(BaseModel):
    reasoning: str
    experiences: list[ExperienceItem] = []


class SkillsExtraction(BaseModel):
    reasoning: str
    skills: list[str] = []
    education: list[EducationItem] = []


class LlmTextExtractor(BaseExtractor):
    SOURCE_TYPE = "LLM_EXTRACTION"
    RELIABILITY_WEIGHT = 0.70

    def extract(self, source: str) -> list[RawRecord]:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY not set — LLM extraction skipped")
            return []

        text = self._load_text(source)
        if not text:
            return []

        try:
            groq_client = Groq(api_key=api_key)
            client = instructor.from_groq(groq_client)
        except Exception as e:
            logger.error(f"Failed to initialize Groq/Instructor client: {e}")
            return []

        identity = self._extract_identity(client, text)
        experience = self._extract_experience(client, text)
        skills = self._extract_skills(client, text)

        record = RawRecord(
            source_id="src_llm_text_01",
            source_type=self.SOURCE_TYPE,
            reliability_weight=self.RELIABILITY_WEIGHT,
            full_name=identity.full_name if identity else None,
            emails=identity.emails if identity else [],
            phones=identity.phones if identity else [],
            location_raw=identity.location_raw if identity else None,
            linkedin_url=identity.linkedin_url if identity else None,
            github_url=identity.github_url if identity else None,
            headline=identity.headline if identity else None,
            years_experience=identity.years_experience if identity else None,
            skills_raw=skills.skills if skills else [],
            experience=[
                {
                    "company": exp.company,
                    "title": exp.title,
                    "start_raw": exp.start_raw,
                    "end_raw": exp.end_raw,
                    "summary": exp.summary,
                }
                for exp in (experience.experiences if experience else [])
            ],
            education=[
                {
                    "institution": edu.institution,
                    "degree": edu.degree,
                    "field": edu.field,
                    "end_year_raw": edu.end_year_raw,
                }
                for edu in (skills.education if skills else [])
            ],
        )

        return [record]

    def _load_text(self, source: str) -> str:
        path = Path(source)
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to read text file {source}: {e}")
                return ""
        return source

    def _extract_identity(self, client, text: str) -> IdentityExtraction | None:
        try:
            result = client.chat.completions.create(
                model="llama3-8b-8192",
                response_model=IdentityExtraction,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract identity information from this text:\n\n{text}"},
                ],
                max_tokens=1024,
            )
            logger.info(f"Identity reasoning: {result.reasoning[:100]}...")
            return result
        except Exception as e:
            logger.error(f"LLM identity extraction error: {e}")
            return None

    def _extract_experience(self, client, text: str) -> ExperienceExtraction | None:
        try:
            result = client.chat.completions.create(
                model="llama3-8b-8192",
                response_model=ExperienceExtraction,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract work experience entries from this text:\n\n{text}"},
                ],
                max_tokens=1024,
            )
            logger.info(f"Experience reasoning: {result.reasoning[:100]}...")
            return result
        except Exception as e:
            logger.error(f"LLM experience extraction error: {e}")
            return None

    def _extract_skills(self, client, text: str) -> SkillsExtraction | None:
        try:
            result = client.chat.completions.create(
                model="llama3-8b-8192",
                response_model=SkillsExtraction,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract skills and education from this text:\n\n{text}"},
                ],
                max_tokens=1024,
            )
            logger.info(f"Skills reasoning: {result.reasoning[:100]}...")
            return result
        except Exception as e:
            logger.error(f"LLM skills extraction error: {e}")
            return None
