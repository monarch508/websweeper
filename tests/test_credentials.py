"""Unit tests for credential resolution."""

import pytest

from websweeper.config import CredentialConfig, CredentialEnvConfig
from websweeper.credentials import CredentialError, Credentials, resolve_credentials


@pytest.fixture
def env_config():
    return CredentialConfig(
        provider="env",
        env=CredentialEnvConfig(username_var="TEST_USER", password_var="TEST_PASS"),
    )


class TestResolveCredentials:
    def test_resolves_from_env(self, monkeypatch, env_config):
        monkeypatch.setenv("TEST_USER", "sean")
        monkeypatch.setenv("TEST_PASS", "secret123")

        creds = resolve_credentials(env_config)

        assert isinstance(creds, Credentials)
        assert creds.username == "sean"
        assert creds.password == "secret123"

    def test_missing_username_var(self, monkeypatch, env_config):
        monkeypatch.delenv("TEST_USER", raising=False)
        monkeypatch.setenv("TEST_PASS", "secret123")

        with pytest.raises(CredentialError, match="TEST_USER"):
            resolve_credentials(env_config)

    def test_missing_password_var(self, monkeypatch, env_config):
        monkeypatch.setenv("TEST_USER", "sean")
        monkeypatch.delenv("TEST_PASS", raising=False)

        with pytest.raises(CredentialError, match="TEST_PASS"):
            resolve_credentials(env_config)

    def test_empty_username(self, monkeypatch, env_config):
        monkeypatch.setenv("TEST_USER", "")
        monkeypatch.setenv("TEST_PASS", "secret123")

        with pytest.raises(CredentialError, match="TEST_USER"):
            resolve_credentials(env_config)

    def test_empty_password(self, monkeypatch, env_config):
        monkeypatch.setenv("TEST_USER", "sean")
        monkeypatch.setenv("TEST_PASS", "")

        with pytest.raises(CredentialError, match="TEST_PASS"):
            resolve_credentials(env_config)

    def test_unsupported_provider(self):
        # Can't construct with invalid provider via Pydantic,
        # so test the function directly with a mock
        from unittest.mock import MagicMock

        config = MagicMock()
        config.provider = "onepassword"

        with pytest.raises(CredentialError, match="Unsupported"):
            resolve_credentials(config)
