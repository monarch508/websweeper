"""Watch mode — persistent browser with keepalive for polling extraction."""

import asyncio
import logging
import signal
from datetime import datetime

from playwright.async_api import Page, BrowserContext, Browser, async_playwright

from websweeper.config import SiteConfig
from websweeper.executor import execute_steps
from websweeper.runner import RunResult, _authenticate, _check_session_alive, run_extraction

logger = logging.getLogger(__name__)


async def watch_site(
    config: SiteConfig,
    interval_seconds: int = 1200,
    keepalive_seconds: int = 180,
    debug: bool = False,
) -> None:
    """Run extraction in a loop with session keepalive between cycles.

    Keeps a single browser alive, authenticates once (with MFA if needed),
    and polls at the configured interval. Keepalive pings prevent the
    server-side session from expiring between polls.

    Args:
        config: Site configuration.
        interval_seconds: Seconds between extraction cycles (default 20 min).
        keepalive_seconds: Seconds between keepalive pings (default 3 min).
        debug: If True, run browser in headed mode.
    """
    # Resolve credentials
    cred_context: dict[str, str] = {}
    if config.credentials:
        from websweeper.credentials import resolve_credentials

        creds = resolve_credentials(config.credentials)
        cred_context = {
            "username": creds.username,
            "password": creds.password,
            **creds.extras,
        }

    shutdown_requested = False
    total_polls = 0
    total_rows = 0
    start_time = datetime.now()

    def request_shutdown():
        nonlocal shutdown_requested
        shutdown_requested = True
        logger.info("Shutdown requested — finishing current cycle...")

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, request_shutdown)

    print(f"Starting watch mode for {config.site.name}")
    print(f"  Poll interval: {interval_seconds}s ({interval_seconds // 60}m)")
    print(f"  Keepalive interval: {keepalive_seconds}s ({keepalive_seconds // 60}m)")
    print(f"  Press Ctrl-C to stop\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not debug)

        from websweeper.session import (
            load_or_create_context,
            save_session_state,
            clear_session,
        )

        context_obj = await load_or_create_context(browser, config)
        page = await context_obj.new_page()

        try:
            # Initial authentication
            page, context_obj = await _ensure_authenticated(
                page, context_obj, browser, config, cred_context
            )

            while not shutdown_requested:
                # --- Extraction cycle ---
                cycle_start = datetime.now()
                total_polls += 1
                logger.info(f"=== Poll cycle {total_polls} at {cycle_start.strftime('%H:%M:%S')} ===")

                try:
                    # Navigate to the target page
                    nav_steps = [s.model_dump() for s in config.navigation.steps]
                    if nav_steps:
                        await execute_steps(page, nav_steps, cred_context)

                    # Extract
                    result = await run_extraction(page, config)

                    if result.status == "success":
                        total_rows += result.rows
                        print(f"[{cycle_start.strftime('%H:%M:%S')}] Poll {total_polls}: {result.rows} rows extracted (total: {total_rows})")
                        if result.output_path:
                            print(f"  Output: {result.output_path}")
                    else:
                        print(f"[{cycle_start.strftime('%H:%M:%S')}] Poll {total_polls}: FAILED — {result.error}")

                except Exception as e:
                    logger.error(f"Extraction failed: {e}")
                    print(f"[{cycle_start.strftime('%H:%M:%S')}] Poll {total_polls}: ERROR — {e}")

                    # Check if it's a session issue
                    try:
                        alive = await _check_session_alive(page, config)
                        if not alive:
                            logger.warning("Session died during extraction — re-authenticating")
                            page, context_obj = await _ensure_authenticated(
                                page, context_obj, browser, config, cred_context, force=True
                            )
                    except Exception:
                        pass

                if shutdown_requested:
                    break

                # --- Keepalive loop between extraction cycles ---
                next_poll = datetime.now().timestamp() + interval_seconds
                logger.info(f"Next poll at {datetime.fromtimestamp(next_poll).strftime('%H:%M:%S')}")

                while datetime.now().timestamp() < next_poll and not shutdown_requested:
                    # Sleep in small increments so we can respond to shutdown quickly
                    sleep_time = min(keepalive_seconds, next_poll - datetime.now().timestamp())
                    if sleep_time <= 0:
                        break

                    await asyncio.sleep(sleep_time)

                    if shutdown_requested:
                        break

                    # Keepalive ping
                    if config.session.keepalive_url:
                        try:
                            logger.debug(f"Keepalive ping: {config.session.keepalive_url}")
                            await page.goto(config.session.keepalive_url)
                            await page.wait_for_timeout(2000)

                            # Verify we're still authenticated
                            alive = await _check_session_alive(page, config)
                            if not alive:
                                logger.warning("Session expired during keepalive — re-authenticating")
                                page, context_obj = await _ensure_authenticated(
                                    page, context_obj, browser, config, cred_context, force=True
                                )
                        except Exception as e:
                            logger.warning(f"Keepalive failed: {e}")

        finally:
            # Graceful shutdown
            uptime = datetime.now() - start_time
            print(f"\nShutting down watch mode...")
            print(f"  Uptime: {uptime}")
            print(f"  Total polls: {total_polls}")
            print(f"  Total rows extracted: {total_rows}")

            try:
                await save_session_state(context_obj, config)
                logger.info("Session saved on shutdown")
            except Exception as e:
                logger.warning(f"Failed to save session on shutdown: {e}")

            await browser.close()
            print("Browser closed. Goodbye.")


async def _ensure_authenticated(
    page: Page,
    context_obj: BrowserContext,
    browser: Browser,
    config: SiteConfig,
    cred_context: dict[str, str],
    force: bool = False,
) -> tuple[Page, BrowserContext]:
    """Ensure the page is authenticated. Re-auth if needed.

    Returns a (possibly new) page and context.
    """
    from websweeper.session import (
        load_or_create_context,
        save_session_state,
        clear_session,
    )

    if force:
        clear_session(config)
        await page.close()
        await context_obj.close()
        context_obj = await load_or_create_context(browser, config, force_fresh=True)
        page = await context_obj.new_page()

    # Check if already authenticated
    if not force and config.session.keepalive_url:
        try:
            await page.goto(config.session.keepalive_url)
            await page.wait_for_timeout(3000)
            if await _check_session_alive(page, config):
                logger.info("Already authenticated")
                return page, context_obj
        except Exception:
            pass

    # Need to authenticate
    logger.info("Authenticating...")
    await page.goto(config.site.login_url)
    await _authenticate(page, config, cred_context)
    await save_session_state(context_obj, config)
    logger.info("Authentication successful, session saved")

    return page, context_obj
