import json
import logging
from pathlib import Path
from .base import BaseExtractor
from schemas.raw_record import RawRecord

logger = logging.getLogger(__name__)

FIELD_MAP = {
    "full_name": ["candidate_name", "full_name", "name", "applicant_name"],
    "email": ["email_address", "email", "contact_email"],
    "phone": ["mobile", "phone", "phone_number", "contact_phone"],
    "title": ["current_title", "job_title", "position", "title"],
    "company": ["employer", "current_employer", "company", "current_company"],
    "location": ["location", "city", "address"],
    "linkedin_url": ["profile_url", "linkedin", "linkedin_profile"],
    "github_url": ["github", "github_profile", "github_url"],
    "years_experience": ["experience_years", "years_exp", "years_experience"],
    "skills": ["skills", "skill_list", "competencies", "technical_skills"],
    "work_history": ["work_history", "employment", "experience", "jobs"],
    "education": ["education", "academic", "schooling"],
}


def _first_match(data: dict, variants: list[str]):
    for key in variants:
        if key in data and data[key] is not None:
            return data[key]
    return None


class AtsJsonExtractor(BaseExtractor):
    SOURCE_TYPE = "ATS_JSON"
    RELIABILITY_WEIGHT = 0.88

    def extract(self, source: str) -> list[RawRecord]:
        try:
            path = Path(source)
            if not path.exists():
                logger.error(f"ATS JSON file not found: {source}")
                return []

            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            return [self._parse(data)]

        except FileNotFoundError:
            logger.error(f"ATS JSON file not found: {source}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"ATS JSON parse error: {e}")
            return []
        except Exception as e:
            logger.error(f"ATS JSON extraction error: {e}")
            return []

    def _parse(self, data: dict) -> RawRecord:
        source_id = "src_ats_json_01"

        full_name_raw = _first_match(data, FIELD_MAP["full_name"])
        full_name = str(full_name_raw).strip() if full_name_raw else None

        email_raw = _first_match(data, FIELD_MAP["email"])
        emails = [str(email_raw).strip().lower()] if email_raw else []

        phone_raw = _first_match(data, FIELD_MAP["phone"])
        phones = [str(phone_raw).strip()] if phone_raw else []

        title = _first_match(data, FIELD_MAP["title"])
        company = _first_match(data, FIELD_MAP["company"])
        location_raw = _first_match(data, FIELD_MAP["location"])
        linkedin_url = _first_match(data, FIELD_MAP["linkedin_url"])
        github_url = _first_match(data, FIELD_MAP["github_url"])

        years_exp_raw = _first_match(data, FIELD_MAP["years_experience"])
        years_experience = None
        if years_exp_raw is not None:
            try:
                years_experience = float(years_exp_raw)
            except (ValueError, TypeError):
                logger.warning(f"Cannot parse years_experience: {years_exp_raw}")

        skills_raw_val = _first_match(data, FIELD_MAP["skills"])
        skills_raw = []
        if isinstance(skills_raw_val, list):
            skills_raw = [str(s).strip() for s in skills_raw_val if s]
        elif isinstance(skills_raw_val, str):
            skills_raw = [s.strip() for s in skills_raw_val.split(",") if s.strip()]

        work_history_raw = _first_match(data, FIELD_MAP["work_history"])
        experience = []
        if isinstance(work_history_raw, list):
            for job in work_history_raw:
                if not isinstance(job, dict):
                    continue
                exp_entry = {
                    "company": job.get("company") or job.get("employer"),
                    "title": job.get("title") or job.get("position") or job.get("job_title"),
                    "start_raw": job.get("start_date") or job.get("start"),
                    "end_raw": job.get("end_date") or job.get("end"),
                    "summary": job.get("description") or job.get("summary"),
                }
                experience.append(exp_entry)
        elif company or title:
            experience.append({
                "company": company,
                "title": title,
                "start_raw": None,
                "end_raw": None,
                "summary": None,
            })

        education_raw = _first_match(data, FIELD_MAP["education"])
        education = []
        if isinstance(education_raw, list):
            for edu in education_raw:
                if not isinstance(edu, dict):
                    continue
                edu_entry = {
                    "institution": edu.get("institution") or edu.get("school") or edu.get("university"),
                    "degree": edu.get("degree"),
                    "field": edu.get("field") or edu.get("major") or edu.get("subject"),
                    "end_year_raw": str(edu.get("end_year") or edu.get("graduation_year") or ""),
                }
                education.append(edu_entry)

        if location_raw is not None:
            location_raw = str(location_raw).strip() or None

        return RawRecord(
            source_id=source_id,
            source_type=self.SOURCE_TYPE,
            reliability_weight=self.RELIABILITY_WEIGHT,
            full_name=full_name,
            emails=emails,
            phones=phones,
            location_raw=location_raw,
            linkedin_url=str(linkedin_url).strip() if linkedin_url else None,
            github_url=str(github_url).strip() if github_url else None,
            years_experience=years_experience,
            skills_raw=skills_raw,
            experience=experience,
            education=education,
        )
