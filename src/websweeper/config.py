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
    # Named extra credentials beyond username/password. Map of template-key to
    # env-var name. The template-key is what auth/MFA steps reference in their
    # `input:` templates (e.g. `{card_pin}`); the env-var name is the actual
    # variable read from the environment.
    extra_vars: dict[str, str] = {}


class CredentialConfig(BaseModel):
    provider: Literal["env"] = "env"
    env: CredentialEnvConfig | None = None

    @model_validator(mode="after")
    def validate_provider_config(self):
        if self.provider == "env" and self.env is None:
            raise ValueError("Provider 'env' requires 'env' config with username_var and password_var")
        return self


class MfaConfig(BaseModel):
    type: Literal["push", "totp", "sms", "email", "none"] = "none"
    wait_seconds: int = 30
    # Common: steps before code entry (e.g., click "Next" to send SMS, or
    # click "different way" + Next to send email).
    pre_code_steps: list["Step"] = []
    code_input_target: "Target | None" = None  # Where to type the auth code
    remember_device_target: "Target | None" = None  # "Remember this device" checkbox/radio
    submit_target: "Target | None" = None   # Submit button after code entry
    # Common: steps to execute AFTER filling the code, BEFORE submit. Used for
    # step-up checks such as the ATM-card-and-PIN gate BofA imposes on the
    # email-MFA path. Templates like `{card_pin}` resolve via credentials.
    post_code_steps: list["Step"] = []
    # Email-MFA only: Gmail polling parameters.
    email_sender_filter: str | None = None
    email_subject_filter: str | None = None
    email_body_regex: str | None = None
    email_timeout_seconds: int = 60


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


class PdfDownloadConfig(BaseModel):
    """Config for downloading PDF files from a page."""
    # Selector for download links/buttons
    download_links_selector: str  # CSS selector to find all download links
    # Where to save downloaded PDFs
    download_directory: str = "./output/{site_id}/statements/"
    # Optional: filter link text with a regex pattern
    link_text_filter: str | None = None
    # Timeout for each download in seconds
    download_timeout_seconds: int = 30


class ExtractionConfig(BaseModel):
    mode: Literal["table", "pdf_download"] = "table"
    table: TableExtractionConfig | None = None
    pdf: PdfDownloadConfig | None = None

    @model_validator(mode="after")
    def validate_extraction_config(self):
        if self.mode == "table" and self.table is None:
            raise ValueError("Extraction mode 'table' requires 'table' config")
        if self.mode == "pdf_download" and self.pdf is None:
            raise ValueError("Extraction mode 'pdf_download' requires 'pdf' config")
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
