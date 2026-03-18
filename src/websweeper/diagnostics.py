"""Diagnostic capture for self-healing — captures everything Claude Code needs to fix failures."""

import json
import logging
import traceback
from dataclasses import dataclass
from pathlib import Path

import yaml
from playwright.async_api import Page

from websweeper.config import SiteConfig, resolve_template_vars
from websweeper.utils import ensure_directory, timestamp_slug

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticPackage:
    directory: Path
    screenshot_path: Path | None = None
    accessibility_tree_path: Path | None = None
    error_log_path: Path | None = None
    config_copy_path: Path | None = None
    step_context_path: Path | None = None


async def capture_diagnostics(
    page: Page | None,
    config: SiteConfig,
    error: Exception,
    step: dict | None = None,
    step_index: int | None = None,
) -> DiagnosticPackage:
    """Capture a full diagnostic package for a failure.

    Creates a timestamped directory with screenshot, a11y tree,
    error log, config copy, and step context.
    """
    # Resolve output directory
    base_dir = resolve_template_vars(
        config.diagnostics.output_directory,
        {"site_id": config.site.id},
    )
    diag_dir = ensure_directory(Path(base_dir) / timestamp_slug())
    logger.info(f"Capturing diagnostics to {diag_dir}")

    package = DiagnosticPackage(directory=diag_dir)

    # Screenshot
    if page and config.diagnostics.screenshot_on_failure:
        try:
            package.screenshot_path = diag_dir / "screenshot.png"
            await page.screenshot(path=str(package.screenshot_path), full_page=True)
            logger.debug("Screenshot captured")
        except Exception as e:
            logger.warning(f"Failed to capture screenshot: {e}")

    # Accessibility tree / page content
    if page and config.diagnostics.capture_accessibility_tree:
        try:
            package.accessibility_tree_path = diag_dir / "accessibility_tree.txt"
            # Use aria_snapshot for structured accessibility info
            try:
                aria = await page.locator("body").aria_snapshot()
                tree_text = aria
            except Exception:
                # Fallback: capture page text content + HTML structure
                text_content = await page.locator("body").inner_text()
                tree_text = f"=== Page Text Content ===\n{text_content}"
            package.accessibility_tree_path.write_text(tree_text)
            logger.debug("Accessibility tree captured")
        except Exception as e:
            logger.warning(f"Failed to capture accessibility tree: {e}")

    # Error log
    try:
        package.error_log_path = diag_dir / "error.log"
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        package.error_log_path.write_text("".join(tb))
        logger.debug("Error log captured")
    except Exception as e:
        logger.warning(f"Failed to write error log: {e}")

    # Config copy
    try:
        package.config_copy_path = diag_dir / "config.yaml"
        config_dict = config.model_dump(mode="json")
        package.config_copy_path.write_text(yaml.dump(config_dict, default_flow_style=False))
        logger.debug("Config copy captured")
    except Exception as e:
        logger.warning(f"Failed to copy config: {e}")

    # Step context
    try:
        package.step_context_path = diag_dir / "step_context.json"
        page_url = ""
        page_title = ""
        if page:
            try:
                page_url = page.url
                page_title = await page.title()
            except Exception:
                pass

        context = {
            "step_index": step_index,
            "step": step,
            "error": str(error),
            "page_url": page_url,
            "page_title": page_title,
        }
        package.step_context_path.write_text(json.dumps(context, indent=2))
        logger.debug("Step context captured")
    except Exception as e:
        logger.warning(f"Failed to write step context: {e}")

    return package


def _format_a11y_tree(node: dict | None, indent: int = 0) -> str:
    """Format an accessibility tree snapshot as readable text."""
    if node is None:
        return "(empty accessibility tree)"

    prefix = "  " * indent
    parts = []

    role = node.get("role", "")
    name = node.get("name", "")
    value = node.get("value", "")

    line = f"{prefix}{role}"
    if name:
        line += f' "{name}"'
    if value:
        line += f" value={value}"
    parts.append(line)

    for child in node.get("children", []):
        parts.append(_format_a11y_tree(child, indent + 1))

    return "\n".join(parts)
