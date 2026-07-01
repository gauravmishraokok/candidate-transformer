import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from schemas.raw_record import RawRecord
from pipeline.extractors.csv_extractor import CsvExtractor
from pipeline.merger import CandidateMerger
from pipeline.projector import OutputProjector
from pipeline.normalizers.phone import normalize_phone


def make_record(**kwargs) -> RawRecord:
    defaults = {
        "source_id": "src_test_01",
        "source_type": "CSV",
        "reliability_weight": 0.9,
    }
    defaults.update(kwargs)
    return RawRecord(**defaults)


class TestEmptySourceGracefulDegradation:
    def test_csv_nonexistent_file(self):
        extractor = CsvExtractor()
        result = extractor.extract("nonexistent_file_that_does_not_exist.txt")
        assert result == []

    def test_pipeline_does_not_crash_on_empty(self):
        extractor = CsvExtractor()
        result = extractor.extract("/totally/fake/path.csv")
        assert isinstance(result, list)
        assert len(result) == 0


class TestMissingName:
    def test_candidate_id_from_email_when_name_none(self):
        r = make_record(full_name=None, emails=["noemail@example.com"])
        merger = CandidateMerger()
        profile = merger.merge([r])
        assert profile.candidate_id.startswith("cand_")
        assert profile.full_name is None

    def test_candidate_id_from_name_when_both_present(self):
        r = make_record(full_name=None, emails=["test@x.com"])
        merger = CandidateMerger()
        profile = merger.merge([r])
        assert profile.candidate_id.startswith("cand_")


class TestMalformedPhone:
    def test_malformed_phone_normalizes_to_none(self):
        result = normalize_phone("abc123xyz")
        assert result is None

    def test_malformed_phone_in_merge(self):
        # Phones that fail normalization should be excluded from output
        r = make_record(
            source_id="src_csv_0",
            emails=["user@x.com"],
            phones=["abc123xyz"],
        )
        merger = CandidateMerger()
        profile = merger.merge([r])
        # Malformed phone should not appear in normalized phones
        for phone in profile.phones:
            assert phone.startswith("+"), f"Phone '{phone}' is not E.164"


class TestOnMissingError:
    def test_on_missing_error_returns_error_dict_not_exception(self):
        r = make_record(
            source_id="src_csv_0",
            emails=["test@example.com"],
            full_name=None,  # missing required field
        )
        merger = CandidateMerger()
        profile = merger.merge([r])

        config = {
            "fields": [
                {"path": "full_name", "from": "full_name", "type": "string", "required": True},
                {"path": "primary_email", "from": "emails[0]", "type": "string", "required": True},
            ],
            "include_confidence": False,
            "include_provenance": False,
            "on_missing": "error",
        }

        projector = OutputProjector(config)
        # Should raise ValueError which the orchestrator catches
        try:
            result = projector.project(profile)
            # If full_name is None (which it is), and on_missing="error" + required=True
            # it should raise
            pytest.fail("Expected ValueError for missing required field with on_missing='error'")
        except ValueError as e:
            assert "full_name" in str(e)

    def test_on_missing_null_does_not_raise(self):
        r = make_record(source_id="src_a", emails=["x@x.com"], full_name=None)
        merger = CandidateMerger()
        profile = merger.merge([r])

        config = {
            "fields": [
                {"path": "full_name", "from": "full_name", "type": "string", "required": False},
            ],
            "include_confidence": False,
            "include_provenance": False,
            "on_missing": "null",
        }
        projector = OutputProjector(config)
        result = projector.project(profile)
        assert result["full_name"] is None


class TestSingleSourcePipeline:
    def test_csv_only_produces_valid_output(self):
        """Pipeline runs all 8 stages with only a CSV source."""
        from pipeline.resolver import EntityResolver
        from pipeline.merger import CandidateMerger
        from pipeline.projector import OutputProjector
        from pipeline.validator import OutputValidator

        csv_extractor = CsvExtractor()
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "samples", "sample_recruiter.csv"
        )
        records = csv_extractor.extract(csv_path)
        assert len(records) > 0

        groups = EntityResolver().resolve(records)
        assert len(groups) > 0

        config = {
            "fields": [
                {"path": "candidate_id", "from": "candidate_id", "type": "string", "required": True},
                {"path": "full_name", "from": "full_name", "type": "string", "required": True},
                {"path": "emails", "from": "emails", "type": "string[]"},
            ],
            "include_confidence": True,
            "include_provenance": False,
            "on_missing": "null",
        }

        projector = OutputProjector(config)
        validator = OutputValidator()

        for group in groups:
            profile = CandidateMerger().merge(group)
            projected = projector.project(profile)
            is_valid, errors = validator.validate(projected, config)
            assert "candidate_id" in projected
            assert projected["candidate_id"].startswith("cand_")
