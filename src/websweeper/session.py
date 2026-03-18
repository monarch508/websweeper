"""Session state management — save/load Playwright storageState for session reuse."""

import logging
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path

from playwright.async_api import Browser, BrowserContext

from websweeper.config import SiteConfig, resolve_template_vars
from websweeper.utils import ensure_directory

logger = logging.getLogger(__name__)


def session_file_path(config: SiteConfig) -> Path:
    """Resolve the session file path from config template vars."""
    return Path(resolve_template_vars(
        config.session.storage_state_path,
        {"site_id": config.site.id},
    ))


def is_session_valid(config: SiteConfig) -> bool:
    """Check if a saved session file exists and is within TTL.

    Returns False if:
    - File does not exist
    - File is older than session_ttl_hours
    - reuse_session is False in config
    """
    if not config.session.reuse_session:
        logger.debug("Session reuse disabled in config")
        return False

    path = session_file_path(config)
    if not path.exists():
        logger.debug(f"No session file at {path}")
        return False

    # Check TTL
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    max_age = timedelta(hours=config.session.session_ttl_hours)
    if datetime.now() - mtime > max_age:
        logger.info(f"Session expired (older than {config.session.session_ttl_hours}h)")
        return False

    logger.info(f"Valid session found at {path}")
    return True


async def load_or_create_context(
    browser: Browser,
    config: SiteConfig,
    force_fresh: bool = False,
) -> BrowserContext:
    """Load saved session state or create a fresh context."""
    if not force_fresh and is_session_valid(config):
        path = session_file_path(config)
        logger.info(f"Loading session from {path}")
        return await browser.new_context(storage_state=str(path))

    logger.info("Creating fresh browser context")
    return await browser.new_context()


async def save_session_state(context: BrowserContext, config: SiteConfig) -> Path:
    """Save the current browser context's storageState to disk.

    Creates parent directories if needed. Sets file permissions to 600.
    """
    path = session_file_path(config)
    ensure_directory(path.parent)

    await context.storage_state(path=str(path))

    # Restrict permissions to owner only
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600

    logger.info(f"Session state saved to {path}")
    return path


def clear_session(config: SiteConfig) -> None:
    """Delete the saved session file if it exists."""
    path = session_file_path(config)
    if path.exists():
        path.unlink()
        logger.info(f"Session cleared: {path}")
