"""PDF download extraction — download PDF files triggered by page links."""

import logging
import re
from pathlib import Path

from playwright.async_api import Page

from websweeper import WebSweeperError
from websweeper.config import PdfDownloadConfig, resolve_template_vars
from websweeper.utils import ensure_directory

logger = logging.getLogger(__name__)


class PdfDownloadError(WebSweeperError):
    """PDF download failed."""
    pass


async def download_pdfs(
    page: Page,
    config: PdfDownloadConfig,
    site_id: str,
) -> list[dict[str, str]]:
    """Download PDFs by clicking download links on the page.

    Finds all elements matching the download_links_selector, optionally
    filters by link text, clicks each one, and captures the download.

    Returns a list of dicts with download metadata (one per file).
    """
    download_dir = Path(resolve_template_vars(config.download_directory, {"site_id": site_id}))
    ensure_directory(download_dir)

    # Find all download links
    links = page.locator(config.download_links_selector)
    count = await links.count()
    logger.info(f"Found {count} potential download links")

    if count == 0:
        raise PdfDownloadError(
            f"No download links found with selector: {config.download_links_selector}"
        )

    # Filter by link text if configured
    text_filter = None
    if config.link_text_filter:
        text_filter = re.compile(config.link_text_filter, re.IGNORECASE)

    results = []
    for i in range(count):
        link = links.nth(i)

        # Check visibility
        if not await link.is_visible():
            continue

        # Get link text for filtering and metadata
        link_text = (await link.text_content() or "").strip()
        if text_filter and not text_filter.search(link_text):
            logger.debug(f"Skipping link (text filter): {link_text}")
            continue

        logger.info(f"Downloading: {link_text}")

        try:
            # Trigger the download via JS event dispatch.
            # Some sites (e.g., BofA) use Vue/custom frameworks where force-click
            # doesn't trigger the framework's event handler. Dispatching a native
            # click event via JS reliably triggers the download.
            timeout_ms = config.download_timeout_seconds * 1000
            async with page.expect_download(timeout=timeout_ms) as download_info:
                await link.evaluate("el => el.dispatchEvent(new Event('click', { bubbles: true }))")

            download = await download_info.value
            suggested_name = download.suggested_filename or f"download_{i}.pdf"
            save_path = download_dir / suggested_name

            # Avoid overwriting — append index if file exists
            if save_path.exists():
                stem = save_path.stem
                suffix = save_path.suffix
                save_path = download_dir / f"{stem}_{i}{suffix}"

            await download.save_as(str(save_path))
            file_size = save_path.stat().st_size
            logger.info(f"Saved: {save_path} ({file_size} bytes)")

            results.append({
                "filename": save_path.name,
                "path": str(save_path),
                "link_text": link_text,
                "size_bytes": str(file_size),
            })

        except Exception as e:
            logger.warning(f"Failed to download '{link_text}': {e}")
            results.append({
                "filename": "",
                "path": "",
                "link_text": link_text,
                "size_bytes": "0",
                "error": str(e),
            })

    if not results:
        logger.warning("No PDFs were downloaded")

    return results
