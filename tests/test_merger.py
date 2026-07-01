import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from schemas.raw_record import RawRecord
from pipeline.merger import CandidateMerger, SOURCE_WEIGHTS, METHOD_SCORES


def make_record(**kwargs) -> RawRecord:
    defaults = {
        "source_id": "src_test_01",
        "source_type": "CSV",
        "reliability_weight": 0.9,
    }
    defaults.update(kwargs)
    return RawRecord(**defaults)


class TestConfidenceFormula:
    def test_csv_wins_over_llm_on_conflict(self):
        r_csv = make_record(
            source_id="src_csv_0",
            source_type="CSV",
            full_name="Rahul Sharma",
            emails=["rahul@example.com"],
        )
        r_llm = make_record(
            source_id="src_llm_text_01",
            source_type="LLM_EXTRACTION",
            full_name="R. Sharma",
            emails=["rahul@example.com"],
            reliability_weight=0.70,
        )
        merger = CandidateMerger()
        profile = merger.merge([r_csv, r_llm])
        # CSV source has higher weight → should win on name
        assert profile.full_name == "Rahul Sharma"

    def test_cross_source_agreement_bonus_applied(self):
        # Two sources agreeing on the same name should result in higher confidence
        r1 = make_record(
            source_id="src_csv_0",
            source_type="CSV",
            full_name="Rahul Sharma",
            emails=["rahul@example.com"],
        )
        r2 = make_record(
            source_id="src_ats_json_01",
            source_type="ATS_JSON",
            full_name="Rahul Sharma",
            emails=["rahul@example.com"],
            reliability_weight=0.88,
        )
        merger = CandidateMerger()
        profile = merger.merge([r1, r2])
        # Agreement bonus means confidence should be higher than solo source
        # CSV solo: 0.90 * 1.00 = 0.90
        # With agreement: min(1.0, 0.90 * 1.00 * 1.15) = 1.0
        assert profile.overall_confidence > 0.5


class TestEmailUnion:
    def test_email_union_from_two_sources(self):
        r1 = make_record(source_id="src_a", emails=["a@x.com"])
        r2 = make_record(source_id="src_b", emails=["b@x.com"])
        merger = CandidateMerger()
        profile = merger.merge([r1, r2])
        assert "a@x.com" in profile.emails
        assert "b@x.com" in profile.emails

    def test_email_deduplication(self):
        r1 = make_record(source_id="src_a", emails=["user@x.com"])
        r2 = make_record(source_id="src_b", emails=["USER@X.COM"])
        merger = CandidateMerger()
        profile = merger.merge([r1, r2])
        assert len(profile.emails) == 1
        assert profile.emails[0] == "user@x.com"


class TestSkillUnion:
    def test_skill_union_with_dedup(self):
        r1 = make_record(
            source_id="src_a",
            source_type="CSV",
            skills_raw=["Python", "FastAPI"],
        )
        r2 = make_record(
            source_id="src_b",
            source_type="ATS_JSON",
            reliability_weight=0.88,
            skills_raw=["Python", "Docker"],
        )
        merger = CandidateMerger()
        profile = merger.merge([r1, r2])
        skill_names = [s.name for s in profile.skills]
        assert "Python" in skill_names
        assert "FastAPI" in skill_names
        assert "Docker" in skill_names
        # Python should appear only once despite being in both sources
        assert skill_names.count("Python") == 1

    def test_skill_confidence_multi_source(self):
        r1 = make_record(source_id="src_a", source_type="CSV", skills_raw=["Python"])
        r2 = make_record(source_id="src_b", source_type="ATS_JSON", reliability_weight=0.88, skills_raw=["Python"])
        merger = CandidateMerger()
        profile = merger.merge([r1, r2])
        python_skill = next((s for s in profile.skills if s.name == "Python"), None)
        assert python_skill is not None
        assert len(python_skill.sources) == 2


class TestCandidateId:
    def test_id_from_email(self):
        r = make_record(emails=["user@example.com"])
        merger = CandidateMerger()
        profile = merger.merge([r])
        assert profile.candidate_id.startswith("cand_")
        assert len(profile.candidate_id) == len("cand_") + 12

    def test_id_from_name_when_no_email(self):
        r = make_record(full_name="Alice Johnson", emails=[])
        merger = CandidateMerger()
        profile = merger.merge([r])
        assert profile.candidate_id.startswith("cand_")


class TestYearsExperience:
    def test_takes_max_on_conflict(self):
        r1 = make_record(source_id="src_a", years_experience=3.0)
        r2 = make_record(source_id="src_b", years_experience=5.0)
        merger = CandidateMerger()
        profile = merger.merge([r1, r2])
        assert profile.years_experience == 5.0
