"""Unit tests for session management."""

import os
import time
from pathlib import Path

import pytest

from websweeper.config import SiteConfig
from websweeper.session import clear_session, is_session_valid, session_file_path


def _minimal_config(tmp_path, reuse=True, ttl_hours=24) -> SiteConfig:
    return SiteConfig.model_validate({
        "site": {
            "name": "Test",
            "id": "test_site",
            "login_url": "http://localhost",
            "base_url": "http://localhost",
        },
        "session": {
            "storage_state_path": str(tmp_path / "sessions" / "{site_id}_state.json"),
            "reuse_session": reuse,
            "session_ttl_hours": ttl_hours,
        },
    })


class TestSessionFilePath:
    def test_resolves_template(self, tmp_path):
        config = _minimal_config(tmp_path)
        path = session_file_path(config)
        assert "test_site" in str(path)
        assert str(path).endswith("test_site_state.json")


class TestIsSessionValid:
    def test_no_file(self, tmp_path):
        config = _minimal_config(tmp_path)
        assert is_session_valid(config) is False

    def test_fresh_file(self, tmp_path):
        config = _minimal_config(tmp_path)
        path = session_file_path(config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")  # Create the file
        assert is_session_valid(config) is True

    def test_expired_file(self, tmp_path):
        config = _minimal_config(tmp_path, ttl_hours=0)  # 0 hours = always expired
        path = session_file_path(config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
        # Set mtime to 2 hours ago
        old_time = time.time() - 7200
        os.utime(path, (old_time, old_time))
        assert is_session_valid(config) is False

    def test_reuse_disabled(self, tmp_path):
        config = _minimal_config(tmp_path, reuse=False)
        path = session_file_path(config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
        assert is_session_valid(config) is False


class TestClearSession:
    def test_deletes_file(self, tmp_path):
        config = _minimal_config(tmp_path)
        path = session_file_path(config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
        assert path.exists()

        clear_session(config)
        assert not path.exists()

    def test_no_file_no_error(self, tmp_path):
        config = _minimal_config(tmp_path)
        clear_session(config)  # Should not raise
