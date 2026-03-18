"""Integration tests — run the full pipeline against a local test HTML page."""

import csv
import os
from pathlib import Path

import pytest

from websweeper.config import SiteConfig, load_config
from websweeper.runner import run_site

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_PAGE = FIXTURES_DIR / "test_page.html"


def _make_test_config(tmp_path) -> SiteConfig:
    """Create a SiteConfig pointing at the local test page."""
    file_url = f"file://{TEST_PAGE.resolve()}"
    return SiteConfig.model_validate({
        "site": {
            "name": "Local Test",
            "id": "test_local",
            "login_url": file_url,
            "base_url": file_url,
        },
        "credentials": {
            "provider": "env",
            "env": {
                "username_var": "TEST_USERNAME",
                "password_var": "TEST_PASSWORD",
            },
        },
        "auth": {
            "steps": [
                {
                    "action": "fill",
                    "target": {"type": "id", "value": "username"},
                    "input": "{username}",
                    "description": "Enter username",
                },
                {
                    "action": "fill",
                    "target": {"type": "id", "value": "password"},
                    "input": "{password}",
                    "description": "Enter password",
                },
                {
                    "action": "click",
                    "target": {"type": "id", "value": "loginBtn"},
                    "description": "Click sign in",
                },
            ],
            "mfa": {"type": "none"},
            "verify": [
                {
                    "action": "wait_for_selector",
                    "target": {"type": "text", "value": "Welcome"},
                    "timeout_seconds": 5,
                },
            ],
        },
        "navigation": {
            "steps": [
                {
                    "action": "click",
                    "target": {"type": "id", "value": "nav-transactions"},
                    "description": "Navigate to transactions",
                    "wait_after": 500,
                },
            ],
        },
        "extraction": {
            "mode": "table",
            "table": {
                "container": {"type": "id", "value": "transactions"},
                "row_selector": "tr.transaction",
                "columns": [
                    {"name": "date", "selector": "td.date", "transform": "parse_date"},
                    {"name": "description", "selector": "td.desc"},
                    {"name": "amount", "selector": "td.amount", "transform": "parse_currency"},
                ],
            },
        },
        "output": {
            "format": "csv",
            "directory": str(tmp_path / "output" / "{site_id}"),
            "filename_template": "{site_id}_{date_pulled}.csv",
            "columns": ["date", "description", "amount", "account", "source"],
            "static_fields": {"account": "Test Checking", "source": "test_local"},
        },
        "session": {
            "storage_state_path": str(tmp_path / "sessions" / "{site_id}_state.json"),
            "reuse_session": False,
        },
        "diagnostics": {
            "output_directory": str(tmp_path / "failures" / "{site_id}"),
        },
    })


class TestAuthFlow:
    @pytest.mark.asyncio
    async def test_login_and_navigate(self, monkeypatch, tmp_path):
        """Full auth flow: login with credentials, verify welcome, navigate to transactions."""
        monkeypatch.setenv("TEST_USERNAME", "testuser")
        monkeypatch.setenv("TEST_PASSWORD", "testpass")

        config = _make_test_config(tmp_path)
        result = await run_site(config)

        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_dry_run_skips_extraction(self, monkeypatch, tmp_path):
        """Dry run authenticates and navigates but doesn't extract."""
        monkeypatch.setenv("TEST_USERNAME", "testuser")
        monkeypatch.setenv("TEST_PASSWORD", "testpass")

        config = _make_test_config(tmp_path)
        result = await run_site(config, dry_run=True)

        assert result.status == "success"
        assert result.rows == 0
        assert result.output_path is None

    @pytest.mark.asyncio
    async def test_bad_selector_fails(self, monkeypatch, tmp_path):
        """A broken selector in auth should produce a failed result."""
        monkeypatch.setenv("TEST_USERNAME", "testuser")
        monkeypatch.setenv("TEST_PASSWORD", "testpass")

        config = _make_test_config(tmp_path)
        # Break the login button selector
        config.auth.steps[2].target.value = "nonexistent_button"

        result = await run_site(config)

        assert result.status == "failed"
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_missing_credentials_fails(self, monkeypatch, tmp_path):
        """Missing env vars should fail before browser launch."""
        monkeypatch.delenv("TEST_USERNAME", raising=False)
        monkeypatch.delenv("TEST_PASSWORD", raising=False)

        config = _make_test_config(tmp_path)

        from websweeper.credentials import CredentialError

        with pytest.raises(CredentialError):
            await run_site(config)


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_end_to_end_extraction(self, monkeypatch, tmp_path):
        """Full pipeline: login → navigate → extract table → write CSV."""
        monkeypatch.setenv("TEST_USERNAME", "testuser")
        monkeypatch.setenv("TEST_PASSWORD", "testpass")

        config = _make_test_config(tmp_path)
        result = await run_site(config)

        assert result.status == "success"
        assert result.rows == 4  # 4 transactions in test_page.html
        assert result.output_path is not None
        assert result.output_path.exists()

        # Verify CSV content
        with open(result.output_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 4

        # First row: CHIPOTLE
        assert rows[0]["date"] == "2024-01-15"
        assert rows[0]["description"] == "CHIPOTLE MEXICAN GRILL"
        assert rows[0]["amount"] == "-15.42"
        assert rows[0]["account"] == "Test Checking"
        assert rows[0]["source"] == "test_local"

        # Last row: PAYROLL (positive amount)
        assert rows[3]["date"] == "2024-01-18"
        assert rows[3]["description"] == "PAYROLL DEPOSIT"
        assert rows[3]["amount"] == "3245.67"  # parse_currency strips $ and commas
