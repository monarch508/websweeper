"""CSV output — write extracted data to disk."""

import csv
import logging
from pathlib import Path

from websweeper.config import OutputConfig, resolve_template_vars
from websweeper.utils import ensure_directory, iso_date_today

logger = logging.getLogger(__name__)


def write_output(
    data: list[dict[str, str]],
    config: OutputConfig,
    site_id: str,
) -> Path:
    """Write extracted data to CSV.

    Resolves output path from templates, adds static_fields and pulled_date,
    writes CSV. Returns the path to the written file.
    """
    date_pulled = iso_date_today()
    context = {"site_id": site_id, "date_pulled": date_pulled}

    # Resolve output path
    directory = Path(resolve_template_vars(config.directory, context))
    filename = resolve_template_vars(config.filename_template, context)
    output_path = directory / filename
    ensure_directory(directory)

    # Merge static fields and pulled_date into each row
    enriched = []
    for row in data:
        merged = dict(row)
        for key, val in config.static_fields.items():
            merged.setdefault(key, val)
        merged["pulled_date"] = date_pulled
        enriched.append(merged)

    # Determine column order
    if config.columns:
        fieldnames = list(config.columns)
        # Add pulled_date if not in explicit columns
        if "pulled_date" not in fieldnames:
            fieldnames.append("pulled_date")
    else:
        # Use all keys from the data
        fieldnames = []
        seen = set()
        for row in enriched:
            for key in row:
                if key not in seen:
                    fieldnames.append(key)
                    seen.add(key)

    # Write CSV
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched)

    logger.info(f"Wrote {len(enriched)} rows to {output_path}")
    return output_path
