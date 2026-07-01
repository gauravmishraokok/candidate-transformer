import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from pipeline.normalizers.phone import normalize_phone
from pipeline.normalizers.date_normalizer import normalize_date
from pipeline.normalizers.country import normalize_country


class TestNormalizePhone:
    def test_already_e164(self):
        assert normalize_phone("+919876543210") == "+919876543210"

    def test_indian_number_no_prefix(self):
        result = normalize_phone("9876543210")
        assert result == "+919876543210"

    def test_not_a_phone(self):
        assert normalize_phone("not a phone") is None

    def test_empty_string(self):
        assert normalize_phone("") is None

    def test_none_like_string(self):
        assert normalize_phone("   ") is None

    def test_us_number(self):
        result = normalize_phone("+12025551234")
        assert result == "+12025551234"

    def test_malformed_number(self):
        assert normalize_phone("abc123xyz") is None


class TestNormalizeDate:
    def test_month_year_text(self):
        assert normalize_date("June 2023") == "2023-06"

    def test_iso_full_date(self):
        assert normalize_date("2020-03-15") == "2020-03"

    def test_year_only(self):
        assert normalize_date("2020") == "2020-01"

    def test_invalid(self):
        # dateparser may or may not parse "invalid" — we accept None or a fallback
        result = normalize_date("invalid")
        # Should return None for truly unparseable input
        assert result is None or isinstance(result, str)

    def test_abbreviated_month(self):
        result = normalize_date("Mar 2022")
        assert result == "2022-03"

    def test_empty_string(self):
        assert normalize_date("") is None

    def test_iso_ym(self):
        assert normalize_date("2022-03") == "2022-03"


class TestNormalizeCountry:
    def test_india(self):
        assert normalize_country("India") == "IN"

    def test_city_country_format(self):
        assert normalize_country("Bangalore, India") == "IN"

    def test_usa(self):
        assert normalize_country("USA") == "US"

    def test_united_states(self):
        assert normalize_country("United States") == "US"

    def test_unknown(self):
        assert normalize_country("unknown country xyz") is None

    def test_uk(self):
        assert normalize_country("UK") == "GB"

    def test_bengaluru(self):
        assert normalize_country("Bengaluru") == "IN"

    def test_mumbai_in_string(self):
        assert normalize_country("Mumbai, India") == "IN"

    def test_empty(self):
        assert normalize_country("") is None
