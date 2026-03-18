"""YAML config loader with Pydantic validation."""

import logging
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ValidationError, model_validator

from websweeper import WebSweeperError

logger = logging.getLogger(__name__)


class ConfigValidationError(WebSweeperError):
    """Config file failed validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Config validation failed: {'; '.join(errors)}")


# --- Pydantic Models ---


class Target(BaseModel):
    type: Literal["id", "css", "text", "role", "placeholder"]
    value: str
    role: str | None = None
    name: str | None = None


class Step(BaseModel):
    action: Literal["fill", "click", "select", "wait", "wait_for_selector", "goto"]
    target: Target | None = None
    input: str | None = None
    description: str = ""
    wait_after: int | None = None
    timeout_seconds: int | None = None
    wait_ms: int | None = None

    @model_validator(mode="after")
    def validate_step_requirements(self):
        needs_target = {"fill", "click", "select", "wait_for_selector"}
        if self.action in needs_target and self.target is None:
            raise ValueError(f"Action '{self.action}' requires a target")
        if self.action == "fill" and self.input is None:
            raise ValueError("Action 'fill' requires an input value")
        if self.action == "select" and self.input is None:
            raise ValueError("Action 'select' requires an input value")
        return self


class SiteInfo(BaseModel):
    name: str
    id: str
    login_url: str
    base_url: str


class CredentialEnvConfig(BaseModel):
    username_var: str
    password_var: str


class CredentialConfig(BaseModel):
    provider: Literal["env"] = "env"
    env: CredentialEnvConfig | None = None

    @model_validator(mode="after")
    def validate_provider_config(self):
        if self.provider == "env" and self.env is None:
            raise ValueError("Provider 'env' requires 'env' config with username_var and password_var")
        return self


class MfaConfig(BaseModel):
    type: Literal["push", "totp", "sms", "none"] = "none"
    wait_seconds: int = 30
    # SMS MFA: steps to trigger code send, then enter code interactively
    pre_code_steps: list["Step"] = []       # Steps before code entry (e.g., click "Next" to send SMS)
    code_input_target: "Target | None" = None  # Where to type the auth code
    remember_device_target: "Target | None" = None  # "Remember this device" checkbox/radio
    submit_target: "Target | None" = None   # Submit button after code entry


class AuthConfig(BaseModel):
    steps: list[Step] = []
    mfa: MfaConfig = MfaConfig()
    verify: list[Step] = []


class ColumnDef(BaseModel):
    name: str
    selector: str
    transform: str | None = None


class TableExtractionConfig(BaseModel):
    container: Target
    row_selector: str
    columns: list[ColumnDef]


class ExtractionConfig(BaseModel):
    mode: Literal["table", "pdf_download"] = "table"
    table: TableExtractionConfig | None = None

    @model_validator(mode="after")
    def validate_extraction_config(self):
        if self.mode == "table" and self.table is None:
            raise ValueError("Extraction mode 'table' requires 'table' config")
        return self


class OutputConfig(BaseModel):
    format: Literal["csv"] = "csv"
    directory: str = "./output/{site_id}/"
    filename_template: str = "{site_id}_{date_pulled}.csv"
    columns: list[str] = []
    static_fields: dict[str, str] = {}


class SessionConfig(BaseModel):
    storage_state_path: str = "./sessions/{site_id}_state.json"
    reuse_session: bool = True
    session_ttl_hours: int = 24


class DiagnosticsConfig(BaseModel):
    screenshot_on_failure: bool = True
    capture_accessibility_tree: bool = True
    output_directory: str = "./failures/{site_id}/"


class NavigationConfig(BaseModel):
    steps: list[Step] = []


class SiteConfig(BaseModel):
    site: SiteInfo
    credentials: CredentialConfig | None = None
    auth: AuthConfig = AuthConfig()
    navigation: NavigationConfig = NavigationConfig()
    extraction: ExtractionConfig | None = None
    output: OutputConfig = OutputConfig()
    session: SessionConfig = SessionConfig()
    diagnostics: DiagnosticsConfig = DiagnosticsConfig()


# --- Loader ---


def load_config(path: str | Path) -> SiteConfig:
    """Load a YAML config file and return a validated SiteConfig.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ConfigValidationError: If the config fails validation.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ConfigValidationError(["Config file must contain a YAML mapping"])

    try:
        return SiteConfig.model_validate(raw)
    except ValidationError as e:
        errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        raise ConfigValidationError(errors) from e


def resolve_template_vars(template: str, context: dict[str, str]) -> str:
    """Resolve {site_id}, {date_pulled}, etc. in path templates."""
    result = template
    for key, val in context.items():
        result = result.replace(f"{{{key}}}", val)
    return result
