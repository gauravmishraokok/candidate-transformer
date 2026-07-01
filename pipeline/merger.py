import hashlib
import logging
from typing import Any, Optional
from schemas.raw_record import RawRecord
from schemas.canonical import (
    CanonicalProfile,
    Location,
    Links,
    SkillEntry,
    ExperienceEntry,
    EducationEntry,
    ProvenanceEntry,
)
from pipeline.normalizers.phone import normalize_phone
from pipeline.normalizers.date_normalizer import normalize_date
from pipeline.normalizers.country import normalize_country

logger = logging.getLogger(__name__)

SOURCE_WEIGHTS: dict[str, float] = {
    "CSV": 0.90,
    "ATS_JSON": 0.88,
    "GITHUB_API": 0.85,
    "LLM_EXTRACTION": 0.70,
}

METHOD_SCORES: dict[str, float] = {
    "direct_field": 1.00,
    "api_response": 0.95,
    "field_mapped": 0.95,
    "llm_extraction": 0.80,
}

FIELD_WEIGHTS: dict[str, float] = {
    "name": 0.15,
    "email": 0.20,
    "skills": 0.20,
    "experience": 0.25,
    "education": 0.10,
    "location": 0.05,
    "headline": 0.05,
}

METHOD_FOR_SOURCE = {
    "CSV": "direct_field",
    "ATS_JSON": "field_mapped",
    "GITHUB_API": "api_response",
    "LLM_EXTRACTION": "llm_extraction",
}


def _base_confidence(source_type: str, method: str, agree_bonus: bool = False) -> float:
    sw = SOURCE_WEIGHTS.get(source_type, 0.5)
    ms = METHOD_SCORES.get(method, 0.80)
    conf = sw * ms
    if agree_bonus:
        conf = min(1.0, conf * 1.15)
    return conf


class CandidateMerger:
    def merge(self, records: list[RawRecord]) -> CanonicalProfile:
        provenance: list[ProvenanceEntry] = []
        field_confidences: dict[str, float] = {}

        # --- full_name ---
        name_candidates = [
            (r, r.full_name, METHOD_FOR_SOURCE.get(r.source_type, "direct_field"))
            for r in records
            if r.full_name
        ]
        full_name, name_conf = self._pick_winner(name_candidates)
        if full_name:
            full_name = full_name.strip().title()
        field_confidences["name"] = name_conf
        for r, val, method in name_candidates:
            if val:
                provenance.append(ProvenanceEntry(
                    field="full_name",
                    source=r.source_id,
                    method=method,
                    raw_value=val,
                    reliability_weight=r.reliability_weight,
                ))

        # --- emails ---
        email_union: list[str] = []
        email_seen: set[str] = set()
        sorted_records = sorted(records, key=lambda r: SOURCE_WEIGHTS.get(r.source_type, 0.5), reverse=True)
        for r in sorted_records:
            method = METHOD_FOR_SOURCE.get(r.source_type, "direct_field")
            for email in r.emails:
                norm = email.lower().strip()
                if norm and norm not in email_seen:
                    email_seen.add(norm)
                    email_union.append(norm)
                if email:
                    provenance.append(ProvenanceEntry(
                        field="emails",
                        source=r.source_id,
                        method=method,
                        raw_value=email,
                        reliability_weight=r.reliability_weight,
                    ))
        email_conf = SOURCE_WEIGHTS.get(sorted_records[0].source_type, 0.5) if sorted_records else 0.5
        field_confidences["email"] = email_conf

        # --- phones ---
        phone_union: list[str] = []
        phone_seen: set[str] = set()
        for r in sorted_records:
            method = METHOD_FOR_SOURCE.get(r.source_type, "direct_field")
            for phone in r.phones:
                normalized = normalize_phone(phone)
                if normalized and normalized not in phone_seen:
                    phone_seen.add(normalized)
                    phone_union.append(normalized)
                provenance.append(ProvenanceEntry(
                    field="phones",
                    source=r.source_id,
                    method=method,
                    raw_value=phone,
                    reliability_weight=r.reliability_weight,
                ))
                if not normalized:
                    logger.warning(f"Phone normalization failed for '{phone}' from {r.source_id}")
                    provenance.append(ProvenanceEntry(
                        field="phones",
                        source=r.source_id,
                        method="normalization_failed",
                        raw_value=phone,
                        reliability_weight=0.0,
                    ))

        # --- location ---
        loc_candidates = [
            (r, r.location_raw, METHOD_FOR_SOURCE.get(r.source_type, "direct_field"))
            for r in records
            if r.location_raw
        ]
        winning_location_raw, loc_conf = self._pick_winner(loc_candidates)
        location: Optional[Location] = None
        if winning_location_raw:
            location = self._parse_location(winning_location_raw)
        field_confidences["location"] = loc_conf
        for r, val, method in loc_candidates:
            if val:
                provenance.append(ProvenanceEntry(
                    field="location",
                    source=r.source_id,
                    method=method,
                    raw_value=val,
                    reliability_weight=r.reliability_weight,
                ))

        # --- links ---
        linkedin = next(
            (r.linkedin_url for r in sorted_records if r.linkedin_url), None
        )
        github = next(
            (r.github_url for r in sorted_records if r.github_url), None
        )
        # portfolio from GitHub summary field
        portfolio = None
        for r in sorted_records:
            if r.source_type == "GITHUB_API" and r.summary:
                portfolio = r.summary
                break

        links: Optional[Links] = None
        if linkedin or github or portfolio:
            links = Links(linkedin=linkedin, github=github, portfolio=portfolio)

        # --- headline ---
        headline_candidates = [
            (r, r.headline, METHOD_FOR_SOURCE.get(r.source_type, "direct_field"))
            for r in records
            if r.headline
        ]
        headline, headline_conf = self._pick_winner(headline_candidates)
        field_confidences["headline"] = headline_conf
        for r, val, method in headline_candidates:
            if val:
                provenance.append(ProvenanceEntry(
                    field="headline",
                    source=r.source_id,
                    method=method,
                    raw_value=val,
                    reliability_weight=r.reliability_weight,
                ))

        # --- years_experience ---
        years_values = [(r.years_experience, r) for r in records if r.years_experience is not None]
        years_experience: Optional[float] = None
        if years_values:
            max_val, max_rec = max(years_values, key=lambda x: x[0])
            years_experience = max_val
            if len(years_values) > 1:
                logger.info(f"years_experience conflict: took max={max_val} from {max_rec.source_id}")
            for yv, r in years_values:
                provenance.append(ProvenanceEntry(
                    field="years_experience",
                    source=r.source_id,
                    method=METHOD_FOR_SOURCE.get(r.source_type, "direct_field"),
                    raw_value=str(yv),
                    reliability_weight=r.reliability_weight,
                ))

        # --- skills ---
        skill_source_map: dict[str, list[tuple[str, str]]] = {}  # canonical → [(source_id, source_type)]
        for r in records:
            method = METHOD_FOR_SOURCE.get(r.source_type, "direct_field")
            for skill in r.skills_raw:
                if not skill:
                    continue
                canonical = skill  # already normalized upstream
                if canonical not in skill_source_map:
                    skill_source_map[canonical] = []
                skill_source_map[canonical].append((r.source_id, r.source_type))
                provenance.append(ProvenanceEntry(
                    field="skills",
                    source=r.source_id,
                    method=method,
                    raw_value=skill,
                    reliability_weight=r.reliability_weight,
                ))

        skills: list[SkillEntry] = []
        for canonical, mentions in skill_source_map.items():
            confs = []
            for sid, stype in mentions:
                m = METHOD_FOR_SOURCE.get(stype, "direct_field")
                confs.append(_base_confidence(stype, m))
            avg_conf = sum(confs) / len(confs)
            if len(confs) >= 2:
                avg_conf = min(1.0, avg_conf * 1.15)
            skills.append(SkillEntry(
                name=canonical,
                confidence=round(avg_conf, 4),
                sources=[sid for sid, _ in mentions],
            ))
        skills.sort(key=lambda s: s.confidence, reverse=True)

        skill_conf = sum(s.confidence for s in skills) / len(skills) if skills else 0.5
        field_confidences["skills"] = skill_conf

        # --- experience ---
        all_exp: list[dict] = []
        for r in records:
            all_exp.extend(r.experience)

        experience = self._merge_experience(all_exp, provenance, records)
        exp_conf = 0.7 if experience else 0.3
        field_confidences["experience"] = exp_conf

        # --- education ---
        all_edu: list[dict] = []
        for r in records:
            all_edu.extend(r.education)

        education = self._merge_education(all_edu, provenance, records)
        edu_conf = 0.7 if education else 0.3
        field_confidences["education"] = edu_conf

        # --- overall_confidence ---
        overall = 0.0
        total_weight = sum(FIELD_WEIGHTS.values())
        for field_key, weight in FIELD_WEIGHTS.items():
            conf = field_confidences.get(field_key, 0.0)
            overall += (weight / total_weight) * conf
        overall = max(0.0, min(1.0, overall))

        # --- candidate_id ---
        candidate_id = self._make_candidate_id(email_union, full_name)

        return CanonicalProfile(
            candidate_id=candidate_id,
            full_name=full_name,
            emails=email_union,
            phones=phone_union,
            location=location,
            links=links,
            headline=headline,
            years_experience=years_experience,
            skills=skills,
            experience=experience,
            education=education,
            provenance=provenance,
            overall_confidence=overall,
        )

    def _pick_winner(
        self, candidates: list[tuple[RawRecord, Any, str]]
    ) -> tuple[Any, float]:
        if not candidates:
            return None, 0.0

        # Count value frequencies for agreement bonus
        value_counts: dict[str, int] = {}
        for _, val, _ in candidates:
            if val:
                key = str(val).lower().strip()
                value_counts[key] = value_counts.get(key, 0) + 1

        best_val = None
        best_conf = -1.0
        for r, val, method in candidates:
            if val is None:
                continue
            key = str(val).lower().strip()
            agree = value_counts.get(key, 1) >= 2
            conf = _base_confidence(r.source_type, method, agree_bonus=agree)
            if conf > best_conf:
                best_conf = conf
                best_val = val

        return best_val, max(0.0, best_conf)

    def _parse_location(self, raw: str) -> Location:
        parts = [p.strip() for p in raw.split(",")]
        city = parts[0] if len(parts) >= 1 else None
        region = parts[1] if len(parts) >= 3 else None
        country_raw = parts[-1] if len(parts) >= 2 else raw
        country = normalize_country(country_raw) or normalize_country(raw)
        return Location(
            city=city if city else None,
            region=region,
            country=country,
        )

    def _merge_experience(
        self,
        all_exp: list[dict],
        provenance: list[ProvenanceEntry],
        records: list[RawRecord],
    ) -> list[ExperienceEntry]:
        seen: dict[tuple, dict] = {}
        for exp in all_exp:
            company = (exp.get("company") or "").strip().lower()
            title = (exp.get("title") or "").strip().lower()
            key = (company, title)
            if key not in seen:
                seen[key] = exp
            else:
                # Merge: keep entry with more data
                existing = seen[key]
                merged = dict(existing)
                for field in ["company", "title", "start_raw", "end_raw", "summary"]:
                    if not merged.get(field) and exp.get(field):
                        merged[field] = exp[field]
                seen[key] = merged

        result = []
        for exp in seen.values():
            start = normalize_date(exp.get("start_raw") or "")
            end = normalize_date(exp.get("end_raw") or "")
            result.append(ExperienceEntry(
                company=exp.get("company"),
                title=exp.get("title"),
                start=start,
                end=end,
                summary=exp.get("summary"),
            ))
        return result

    def _merge_education(
        self,
        all_edu: list[dict],
        provenance: list[ProvenanceEntry],
        records: list[RawRecord],
    ) -> list[EducationEntry]:
        seen: dict[tuple, dict] = {}
        for edu in all_edu:
            institution = (edu.get("institution") or "").strip().lower()
            degree = (edu.get("degree") or "").strip().lower()
            key = (institution, degree)
            if key not in seen:
                seen[key] = edu
            else:
                existing = seen[key]
                merged = dict(existing)
                for field in ["institution", "degree", "field", "end_year_raw"]:
                    if not merged.get(field) and edu.get(field):
                        merged[field] = edu[field]
                seen[key] = merged

        result = []
        for edu in seen.values():
            end_year = None
            raw_year = edu.get("end_year_raw")
            if raw_year:
                try:
                    end_year = int(str(raw_year).strip()[:4])
                except (ValueError, TypeError):
                    pass
            result.append(EducationEntry(
                institution=edu.get("institution"),
                degree=edu.get("degree"),
                field=edu.get("field"),
                end_year=end_year,
            ))
        return result

    def _make_candidate_id(self, emails: list[str], full_name: Optional[str]) -> str:
        if emails:
            source = sorted(emails)[0]
        elif full_name:
            source = full_name.lower().strip()
        else:
            source = "unknown"
        hash_hex = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return f"cand_{hash_hex[:12]}"
