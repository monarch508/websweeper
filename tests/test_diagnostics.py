"""Tests for diagnostic capture on failure."""

import json
from pathlib import Path

import pytest

from websweeper.config import SiteConfig
from websweeper.runner import run_site

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_PAGE = FIXTURES_DIR / "test_page.html"


def _broken_config(tmp_path) -> SiteConfig:
    """Config with a broken selector that will fail during auth."""
    file_url = f"file://{TEST_PAGE.resolve()}"
    return SiteConfig.model_validate({
        "site": {
            "name": "Broken Test",
            "id": "broken_test",
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
                    "action": "click",
                    "target": {"type": "id", "value": "nonexistent_element"},
                    "description": "Click broken selector",
                },
            ],
        },
        "diagnostics": {
            "screenshot_on_failure": True,
            "capture_accessibility_tree": True,
            "output_directory": str(tmp_path / "failures" / "{site_id}"),
        },
    })


class TestDiagnosticCapture:
    @pytest.mark.asyncio
    async def test_failure_creates_diagnostic_package(self, monkeypatch, tmp_path):
        """A broken selector should produce a diagnostic package."""
        monkeypatch.setenv("TEST_USERNAME", "testuser")
        monkeypatch.setenv("TEST_PASSWORD", "testpass")

        config = _broken_config(tmp_path)
        result = await run_site(config)

        assert result.status == "failed"
        assert result.diagnostic_path is not None

        diag_dir = result.diagnostic_path
        assert diag_dir.exists()

        # Check all expected files
        assert (diag_dir / "screenshot.png").exists()
        assert (diag_dir / "screenshot.png").stat().st_size > 0

        assert (diag_dir / "accessibility_tree.txt").exists()
        a11y_text = (diag_dir / "accessibility_tree.txt").read_text()
        assert len(a11y_text) > 0

        assert (diag_dir / "error.log").exists()
        error_text = (diag_dir / "error.log").read_text()
        assert "nonexistent_element" in error_text

        assert (diag_dir / "config.yaml").exists()

        assert (diag_dir / "step_context.json").exists()
        step_ctx = json.loads((diag_dir / "step_context.json").read_text())
        assert "error" in step_ctx
        assert step_ctx["page_url"] != ""
