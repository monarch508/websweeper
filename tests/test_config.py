"""Unit tests for config loading and Pydantic validation."""

import pytest
import yaml

from websweeper.config import (
    ConfigValidationError,
    SiteConfig,
    Step,
    Target,
    load_config,
    resolve_template_vars,
)


class TestLoadConfig:
    def test_load_valid_config(self, fixtures_dir):
        config = load_config(fixtures_dir / "valid_config.yaml")

        assert config.site.name == "Test Site"
        assert config.site.id == "test_site"
        assert config.site.login_url == "http://localhost:8080/login"
        assert config.credentials.provider == "env"
        assert config.credentials.env.username_var == "TEST_USERNAME"
        assert len(config.auth.steps) == 3
        assert config.auth.steps[0].action == "fill"
        assert config.auth.steps[0].target.type == "id"
        assert config.auth.steps[0].input == "{username}"
        assert config.auth.mfa.type == "none"
        assert len(config.auth.verify) == 1
        assert len(config.navigation.steps) == 1
        assert config.extraction.mode == "table"
        assert len(config.extraction.table.columns) == 3
        assert config.output.static_fields["account"] == "Test Account"
        assert config.session.session_ttl_hours == 24

    def test_load_minimal_config(self, fixtures_dir):
        config = load_config(fixtures_dir / "minimal_config.yaml")

        assert config.site.name == "Minimal Test"
        assert config.site.id == "minimal"
        # Defaults applied
        assert config.credentials is None
        assert config.auth.steps == []
        assert config.auth.mfa.type == "none"
        assert config.navigation.steps == []
        assert config.extraction is None
        assert config.output.format == "csv"
        assert config.session.reuse_session is True

    def test_load_invalid_config(self, fixtures_dir):
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(fixtures_dir / "invalid_config.yaml")

        errors = exc_info.value.errors
        assert len(errors) > 0
        # Should catch multiple issues
        error_text = " ".join(errors)
        assert "id" in error_text.lower() or "provider" in error_text.lower()

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_non_mapping_yaml(self, tmp_path):
        bad_file = tmp_path / "list.yaml"
        bad_file.write_text("- item1\n- item2\n")

        with pytest.raises(ConfigValidationError, match="YAML mapping"):
            load_config(bad_file)


class TestStepValidation:
    def test_fill_requires_target(self):
        with pytest.raises(ValueError, match="requires a target"):
            Step(action="fill", input="hello")

    def test_fill_requires_input(self):
        with pytest.raises(ValueError, match="requires an input"):
            Step(
                action="fill",
                target=Target(type="id", value="field"),
            )

    def test_click_requires_target(self):
        with pytest.raises(ValueError, match="requires a target"):
            Step(action="click")

    def test_wait_no_target_needed(self):
        step = Step(action="wait", wait_ms=1000)
        assert step.action == "wait"
        assert step.target is None

    def test_valid_fill_step(self):
        step = Step(
            action="fill",
            target=Target(type="id", value="email"),
            input="test@example.com",
            description="Enter email",
        )
        assert step.action == "fill"
        assert step.target.value == "email"
        assert step.input == "test@example.com"


class TestTargetValidation:
    def test_valid_target_types(self):
        for t in ("id", "css", "text", "role", "placeholder"):
            target = Target(type=t, value="test")
            assert target.type == t

    def test_invalid_target_type(self):
        with pytest.raises(ValueError):
            Target(type="xpath", value="//div")


class TestCredentialValidation:
    def test_env_provider_requires_env_config(self):
        with pytest.raises(ValueError, match="requires 'env' config"):
            SiteConfig(
                site={"name": "T", "id": "t", "login_url": "http://x", "base_url": "http://x"},
                credentials={"provider": "env"},
            )

    def test_invalid_provider(self):
        with pytest.raises(ValueError):
            SiteConfig(
                site={"name": "T", "id": "t", "login_url": "http://x", "base_url": "http://x"},
                credentials={"provider": "magic"},
            )


class TestExtractionValidation:
    def test_table_mode_requires_table_config(self):
        with pytest.raises(ValueError, match="requires 'table' config"):
            SiteConfig(
                site={"name": "T", "id": "t", "login_url": "http://x", "base_url": "http://x"},
                extraction={"mode": "table"},
            )


class TestResolveTemplateVars:
    def test_single_var(self):
        result = resolve_template_vars("{site_id}.csv", {"site_id": "bofa"})
        assert result == "bofa.csv"

    def test_multiple_vars(self):
        result = resolve_template_vars(
            "{site_id}_{date_pulled}.csv",
            {"site_id": "bofa", "date_pulled": "2026-03-17"},
        )
        assert result == "bofa_2026-03-17.csv"

    def test_no_vars(self):
        result = resolve_template_vars("plain.csv", {"site_id": "bofa"})
        assert result == "plain.csv"

    def test_unresolved_var_kept(self):
        result = resolve_template_vars("{unknown}.csv", {"site_id": "bofa"})
        assert result == "{unknown}.csv"
