"""Table extraction — extract structured data from HTML tables."""

import logging

from playwright.async_api import Page

from websweeper import WebSweeperError
from websweeper.config import TableExtractionConfig
from websweeper.executor import resolve_target
from websweeper.transforms import apply_transform

logger = logging.getLogger(__name__)


class ExtractionError(WebSweeperError):
    """Data extraction failed."""
    pass


async def extract_table(
    page: Page,
    config: TableExtractionConfig,
) -> list[dict[str, str]]:
    """Extract tabular data from a page.

    1. Locate container element using config.container target.
    2. Find all rows within container using config.row_selector.
    3. For each row, extract text from each column's selector.
    4. Apply transforms to column values where specified.
    5. Return list of dicts, one per row.
    """
    # Find the container
    container = resolve_target(page, config.container.model_dump())
    count_check = await container.count()
    if count_check == 0:
        raise ExtractionError(
            f"Container not found: {config.container.type}={config.container.value}"
        )

    # Find rows
    rows = container.locator(config.row_selector)
    row_count = await rows.count()
    logger.info(f"Found {row_count} rows")

    if row_count == 0:
        raise ExtractionError(
            f"No rows found with selector: {config.row_selector}"
        )

    # Extract data from each row
    results = []
    for i in range(row_count):
        row = rows.nth(i)
        row_data = {}

        for col in config.columns:
            cell = row.locator(col.selector)
            text = (await cell.text_content() or "").strip()

            if col.transform and text:
                text = apply_transform(col.transform, text)

            row_data[col.name] = text

        results.append(row_data)
        logger.debug(f"Row {i + 1}: {row_data}")

    return results
