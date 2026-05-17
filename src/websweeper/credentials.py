"""Credential resolution from environment variables (Phase 1) or 1Password (Phase 2+)."""

import logging
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from websweeper import WebSweeperError
from websweeper.config import CredentialConfig

logger = logging.getLogger(__name__)


class CredentialError(WebSweeperError):
    """Failed to resolve credentials."""
    pass


@dataclass
class Credentials:
    username: str
    password: str
    extras: dict[str, str] = field(default_factory=dict)


def resolve_credentials(config: CredentialConfig) -> Credentials:
    """Resolve credentials based on the config's provider setting.

    Raises:
        CredentialError: If required env vars are not set or empty.
    """
    if config.provider == "env":
        return _resolve_env_credentials(config.env)
    else:
        raise CredentialError(f"Unsupported credential provider: {config.provider}")


def _resolve_env_credentials(env_config) -> Credentials:
    """Read username and password from environment variables."""
    # Load .env file if present (idempotent)
    load_dotenv()

    username_var = env_config.username_var
    password_var = env_config.password_var

    username = os.environ.get(username_var, "")
    if not username:
        raise CredentialError(
            f"Environment variable '{username_var}' is not set or empty. "
            f"Set it in your .env file or shell environment."
        )

    password = os.environ.get(password_var, "")
    if not password:
        raise CredentialError(
            f"Environment variable '{password_var}' is not set or empty. "
            f"Set it in your .env file or shell environment."
        )

    extras: dict[str, str] = {}
    for template_key, var_name in env_config.extra_vars.items():
        value = os.environ.get(var_name, "")
        if not value:
            raise CredentialError(
                f"Environment variable '{var_name}' (extra credential '{template_key}') "
                f"is not set or empty. Set it in your .env file or shell environment."
            )
        extras[template_key] = value

    resolved_vars = [username_var, password_var] + list(env_config.extra_vars.values())
    logger.debug(f"Credentials resolved from env vars: {', '.join(resolved_vars)}")
    return Credentials(username=username, password=password, extras=extras)
