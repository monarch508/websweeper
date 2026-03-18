"""Unit tests for CSV output."""

import csv

import pytest

from websweeper.config import OutputConfig
from websweeper.output import write_output


@pytest.fixture
def sample_data():
    return [
        {"date": "2024-01-15", "description": "CHIPOTLE", "amount": "-15.42"},
        {"date": "2024-01-16", "description": "AMAZON.COM", "amount": "-42.99"},
        {"date": "2024-01-17", "description": "SAFEWAY", "amount": "-87.23"},
    ]


class TestWriteOutput:
    def test_basic_csv(self, tmp_path, sample_data):
        config = OutputConfig(
            directory=str(tmp_path / "{site_id}"),
            filename_template="{site_id}_{date_pulled}.csv",
        )

        path = write_output(sample_data, config, "test")

        assert path.exists()
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 3
        assert rows[0]["date"] == "2024-01-15"
        assert rows[0]["description"] == "CHIPOTLE"
        assert "pulled_date" in rows[0]

    def test_with_static_fields(self, tmp_path, sample_data):
        config = OutputConfig(
            directory=str(tmp_path / "{site_id}"),
            filename_template="{site_id}.csv",
            static_fields={"account": "Checking", "source": "bofa"},
        )

        path = write_output(sample_data, config, "test")

        with open(path) as f:
            rows = list(csv.DictReader(f))

        assert rows[0]["account"] == "Checking"
        assert rows[0]["source"] == "bofa"
        assert rows[1]["account"] == "Checking"

    def test_column_ordering(self, tmp_path, sample_data):
        config = OutputConfig(
            directory=str(tmp_path / "{site_id}"),
            filename_template="{site_id}.csv",
            columns=["date", "description", "amount", "account"],
            static_fields={"account": "Checking"},
        )

        path = write_output(sample_data, config, "test")

        with open(path) as f:
            reader = csv.reader(f)
            headers = next(reader)

        # pulled_date appended after explicit columns
        assert headers == ["date", "description", "amount", "account", "pulled_date"]

    def test_creates_directory(self, tmp_path, sample_data):
        nested = tmp_path / "deep" / "nested" / "{site_id}"
        config = OutputConfig(
            directory=str(nested),
            filename_template="{site_id}.csv",
        )

        path = write_output(sample_data, config, "test")
        assert path.exists()

    def test_empty_data(self, tmp_path):
        config = OutputConfig(
            directory=str(tmp_path / "{site_id}"),
            filename_template="{site_id}.csv",
            columns=["date", "amount"],
        )

        path = write_output([], config, "test")

        with open(path) as f:
            reader = csv.reader(f)
            headers = next(reader)
            rows = list(reader)

        assert len(rows) == 0
        assert "date" in headers
