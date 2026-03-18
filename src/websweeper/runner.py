"""Main orchestrator — runs a site config through the Playwright pipeline."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import Page, async_playwright

from websweeper.config import SiteConfig, load_config
from websweeper.executor import execute_steps

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    status: str  # "success" or "failed"
    rows: int = 0
    output_path: Path | None = None
    error: str | None = None
    step_index: int | None = None
    diagnostic_path: Path | None = None


async def _authenticate(page: Page, config: SiteConfig, context: dict[str, str]) -> None:
    """Execute auth steps with credential injection, then verify."""
    auth_steps = [s.model_dump() for s in config.auth.steps]
    if auth_steps:
        logger.info("Executing auth steps")
        await execute_steps(page, auth_steps, context)

    # MFA wait (Phase 1: simple timeout)
    if config.auth.mfa.type != "none":
        wait_ms = config.auth.mfa.wait_seconds * 1000
        logger.info(f"Waiting {config.auth.mfa.wait_seconds}s for MFA ({config.auth.mfa.type})")
        await page.wait_for_timeout(wait_ms)

    # Verify auth succeeded
    verify_steps = [s.model_dump() for s in config.auth.verify]
    if verify_steps:
        logger.info("Verifying auth")
        await execute_steps(page, verify_steps, context)


async def run_site(
    config: SiteConfig,
    debug: bool = False,
    force_auth: bool = False,
    dry_run: bool = False,
) -> RunResult:
    """Execute the full workflow for a site config."""
    logger.info(f"Running site: {config.site.name} ({config.site.id})")

    # Resolve credentials if auth is configured
    context: dict[str, str] = {}
    if config.credentials:
        from websweeper.credentials import resolve_credentials

        creds = resolve_credentials(config.credentials)
        context = {"username": creds.username, "password": creds.password}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not debug)

        # Session management: load existing session or create fresh context
        from websweeper.session import (
            is_session_valid,
            load_or_create_context,
            save_session_state,
        )

        context_obj = await load_or_create_context(browser, config, force_fresh=force_auth)
        page = await context_obj.new_page()

        try:
            # Navigate to login page
            logger.info(f"Navigating to {config.site.login_url}")
            await page.goto(config.site.login_url)

            # Authenticate (skip if valid session exists and not forced)
            needs_auth = force_auth or not is_session_valid(config) or not config.session.reuse_session
            if config.auth.steps and needs_auth:
                await _authenticate(page, config, context)
                await save_session_state(context_obj, config)
                logger.info("Session saved after successful auth")

            # Navigate
            nav_steps = [s.model_dump() for s in config.navigation.steps]
            if nav_steps:
                logger.info("Executing navigation steps")
                await execute_steps(page, nav_steps, context)

            if dry_run:
                logger.info("Dry run — skipping extraction")
                return RunResult(status="success")

            # Extract (MVP 5 will add real extraction)
            data: list[dict[str, str]] = []
            if config.extraction:
                logger.info(f"Extracting data (mode: {config.extraction.mode})")
                if config.extraction.mode == "table" and config.extraction.table:
                    from websweeper.extractors.table import extract_table

                    data = await extract_table(page, config.extraction.table)

            # Output (MVP 5 will add real output)
            output_path = None
            if data:
                from websweeper.output import write_output

                output_path = write_output(data, config.output, config.site.id)

            logger.info(f"Success: {len(data)} rows extracted")
            return RunResult(status="success", rows=len(data), output_path=output_path)

        except Exception as e:
            logger.error(f"Run failed: {e}")
            diag_path = None
            try:
                from websweeper.diagnostics import capture_diagnostics

                step_dict = None
                if hasattr(e, "step"):
                    step_dict = e.step
                diag = await capture_diagnostics(page, config, e, step=step_dict)
                diag_path = diag.directory
                logger.info(f"Diagnostics saved to {diag_path}")
            except Exception as diag_err:
                logger.warning(f"Failed to capture diagnostics: {diag_err}")
            return RunResult(status="failed", error=str(e), diagnostic_path=diag_path)

        finally:
            await browser.close()


def run_from_config_path(config_path: str, debug: bool = False) -> RunResult:
    """Load a config file and run it. Convenience entry point."""
    config = load_config(config_path)
    return asyncio.run(run_site(config, debug=debug))


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 2:
        print("Usage: python -m websweeper.runner <config.yaml>")
        sys.exit(1)

    result = run_from_config_path(sys.argv[1], debug="--debug" in sys.argv)
    print(f"Result: {result.status}")
    if result.error:
        print(f"Error: {result.error}")
