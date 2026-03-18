"""Unit tests for data transforms."""

import pytest

from websweeper.transforms import (
    TransformError,
    apply_transform,
    parse_currency,
    parse_date,
    strip_whitespace,
    lowercase,
    TRANSFORMS,
)


class TestParseDate:
    def test_slash_format(self):
        assert parse_date("01/15/2024") == "2024-01-15"

    def test_dash_format(self):
        assert parse_date("01-15-2024") == "2024-01-15"

    def test_text_format_short(self):
        assert parse_date("Jan 15, 2024") == "2024-01-15"

    def test_text_format_long(self):
        assert parse_date("January 15, 2024") == "2024-01-15"

    def test_iso_passthrough(self):
        assert parse_date("2024-01-15") == "2024-01-15"

    def test_short_year(self):
        assert parse_date("01/15/24") == "2024-01-15"

    def test_invalid_raises(self):
        with pytest.raises(TransformError, match="Cannot parse date"):
            parse_date("not-a-date")

    def test_empty_string(self):
        assert parse_date("") == ""

    def test_whitespace_stripped(self):
        assert parse_date("  01/15/2024  ") == "2024-01-15"


class TestParseCurrency:
    def test_plain_amount(self):
        assert parse_currency("$15.42") == "15.42"

    def test_with_commas(self):
        assert parse_currency("$1,234.56") == "1234.56"

    def test_negative_parens(self):
        assert parse_currency("($42.99)") == "-42.99"

    def test_negative_dash(self):
        assert parse_currency("-$15.00") == "-15.00"

    def test_no_symbol(self):
        assert parse_currency("42.99") == "42.99"

    def test_large_number(self):
        assert parse_currency("$12,345,678.90") == "12345678.90"

    def test_empty_string(self):
        assert parse_currency("") == ""

    def test_invalid_raises(self):
        with pytest.raises(TransformError, match="Cannot parse currency"):
            parse_currency("$abc")


class TestOtherTransforms:
    def test_strip(self):
        assert strip_whitespace("  hello   world  ") == "hello world"

    def test_lowercase(self):
        assert lowercase("HELLO World") == "hello world"


class TestRegistry:
    def test_all_transforms_registered(self):
        assert "parse_date" in TRANSFORMS
        assert "parse_currency" in TRANSFORMS
        assert "strip" in TRANSFORMS
        assert "lowercase" in TRANSFORMS

    def test_apply_transform(self):
        assert apply_transform("parse_currency", "$10.00") == "10.00"

    def test_unknown_transform(self):
        with pytest.raises(TransformError, match="Unknown transform"):
            apply_transform("nonexistent", "value")
