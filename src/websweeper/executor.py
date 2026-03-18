"""Playwright step executor — maps declarative step dicts to Playwright calls."""

import logging
from typing import Any

from playwright.async_api import Locator, Page

from websweeper import WebSweeperError

logger = logging.getLogger(__name__)


class ExecutionError(WebSweeperError):
    """A step failed during execution."""

    def __init__(self, step: dict, cause: Exception):
        self.step = step
        self.cause = cause
        desc = step.get("description") or step.get("action", "unknown")
        super().__init__(f"Step failed: {desc} — {cause}")


VALID_ACTIONS = {"fill", "click", "select", "wait", "wait_for_selector", "goto"}
VALID_TARGET_TYPES = {"id", "css", "text", "role", "placeholder"}


def resolve_target(page: Page, target: dict) -> Locator:
    """Resolve a target dict to a Playwright Locator.

    Supported target types:
        id          -> page.locator("#value")
        css         -> page.locator(value)
        text        -> page.get_by_text(value)
        role        -> page.get_by_role(role, name=value)
        placeholder -> page.get_by_placeholder(value)
    """
    target_type = target["type"]
    value = target["value"]

    if target_type == "id":
        return page.locator(f"#{value}")
    elif target_type == "css":
        return page.locator(value)
    elif target_type == "text":
        return page.get_by_text(value)
    elif target_type == "role":
        role = target.get("role", value)
        name = target.get("name", value)
        return page.get_by_role(role, name=name)
    elif target_type == "placeholder":
        return page.get_by_placeholder(value)
    else:
        raise ExecutionError(
            {"description": f"resolve target type={target_type}"},
            ValueError(f"Unknown target type: {target_type}"),
        )


def resolve_input(template: str, context: dict[str, str] | None) -> str:
    """Resolve template variables like {username} in step input."""
    if not context or "{" not in template:
        return template
    result = template
    for key, val in context.items():
        result = result.replace(f"{{{key}}}", val)
    return result


async def execute_step(
    page: Page,
    step: dict[str, Any],
    context: dict[str, str] | None = None,
) -> None:
    """Execute a single step against a Playwright page.

    Args:
        page: Playwright page instance.
        step: Step dict with 'action', 'target', optional 'input', 'wait_after', etc.
        context: Template variable context for resolving {username}, {password}, etc.
    """
    action = step["action"]
    desc = step.get("description", action)
    logger.debug(f"Executing step: {desc}")

    try:
        if action == "goto":
            url = step.get("target", {}).get("value", "")
            if not url:
                url = step.get("input", "")
            logger.debug(f"Navigating to {url}")
            await page.goto(url)

        elif action == "wait":
            wait_ms = step.get("wait_ms", 1000)
            await page.wait_for_timeout(wait_ms)

        elif action == "wait_for_selector":
            target = step["target"]
            timeout = step.get("timeout_seconds", 10) * 1000
            locator = resolve_target(page, target)
            await locator.wait_for(timeout=timeout)

        elif action in ("fill", "click", "select"):
            locator = resolve_target(page, step["target"])

            if action == "fill":
                value = resolve_input(step["input"], context)
                await locator.fill(value)
            elif action == "click":
                await locator.click()
            elif action == "select":
                value = resolve_input(step["input"], context)
                await locator.select_option(value)

        else:
            raise ValueError(f"Unknown action: {action}")

        # Post-action wait
        wait_after = step.get("wait_after")
        if wait_after:
            await page.wait_for_timeout(wait_after)

    except Exception as e:
        if isinstance(e, ExecutionError):
            raise
        raise ExecutionError(step, e) from e


async def execute_steps(
    page: Page,
    steps: list[dict[str, Any]],
    context: dict[str, str] | None = None,
) -> None:
    """Execute a sequence of steps in order."""
    for i, step in enumerate(steps):
        logger.debug(f"Step {i + 1}/{len(steps)}")
        await execute_step(page, step, context)
