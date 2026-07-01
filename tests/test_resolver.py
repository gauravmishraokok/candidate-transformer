import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from schemas.raw_record import RawRecord
from pipeline.resolver import EntityResolver


def make_record(**kwargs) -> RawRecord:
    defaults = {
        "source_id": "src_test_01",
        "source_type": "CSV",
        "reliability_weight": 0.9,
    }
    defaults.update(kwargs)
    return RawRecord(**defaults)


class TestResolverTier1Email:
    def test_same_email_same_group(self):
        r1 = make_record(source_id="src_csv_0", emails=["user@example.com"])
        r2 = make_record(source_id="src_ats_01", emails=["user@example.com"])
        resolver = EntityResolver()
        groups = resolver.resolve([r1, r2])
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_different_email_different_group(self):
        r1 = make_record(source_id="src_csv_0", emails=["alice@example.com"])
        r2 = make_record(source_id="src_csv_1", emails=["bob@example.com"])
        resolver = EntityResolver()
        groups = resolver.resolve([r1, r2])
        assert len(groups) == 2

    def test_email_case_insensitive(self):
        r1 = make_record(source_id="src_a", emails=["User@Example.COM"])
        r2 = make_record(source_id="src_b", emails=["user@example.com"])
        resolver = EntityResolver()
        groups = resolver.resolve([r1, r2])
        assert len(groups) == 1


class TestResolverTier1LinkedIn:
    def test_same_linkedin_same_group(self):
        url = "https://linkedin.com/in/johndoe"
        r1 = make_record(source_id="src_a", linkedin_url=url)
        r2 = make_record(source_id="src_b", linkedin_url=url)
        resolver = EntityResolver()
        groups = resolver.resolve([r1, r2])
        assert len(groups) == 1

    def test_linkedin_trailing_slash(self):
        r1 = make_record(source_id="src_a", linkedin_url="https://linkedin.com/in/johndoe/")
        r2 = make_record(source_id="src_b", linkedin_url="https://linkedin.com/in/johndoe")
        resolver = EntityResolver()
        groups = resolver.resolve([r1, r2])
        assert len(groups) == 1


class TestResolverTier2NameSimilarity:
    def test_probable_name_match(self):
        r1 = make_record(source_id="src_a", full_name="Rahul Sharma")
        r2 = make_record(source_id="src_b", full_name="Rahul S.")
        resolver = EntityResolver()
        groups = resolver.resolve([r1, r2])
        # Should merge as probable match
        assert len(groups) == 1

    def test_completely_different_names_no_match(self):
        r1 = make_record(source_id="src_a", full_name="Alice Johnson")
        r2 = make_record(source_id="src_b", full_name="Bob Smith")
        resolver = EntityResolver()
        groups = resolver.resolve([r1, r2])
        assert len(groups) == 2


class TestResolverTransitive:
    def test_transitive_linkage(self):
        # A↔B by email, B↔C by LinkedIn → all same group
        r_a = make_record(source_id="src_a", emails=["user@x.com"])
        r_b = make_record(
            source_id="src_b",
            emails=["user@x.com"],
            linkedin_url="https://linkedin.com/in/user",
        )
        r_c = make_record(
            source_id="src_c",
            linkedin_url="https://linkedin.com/in/user",
        )
        resolver = EntityResolver()
        groups = resolver.resolve([r_a, r_b, r_c])
        assert len(groups) == 1
        assert len(groups[0]) == 3


class TestResolverEdge:
    def test_empty_input(self):
        resolver = EntityResolver()
        groups = resolver.resolve([])
        assert groups == []

    def test_single_record(self):
        r = make_record()
        resolver = EntityResolver()
        groups = resolver.resolve([r])
        assert len(groups) == 1
        assert groups[0][0] is r
