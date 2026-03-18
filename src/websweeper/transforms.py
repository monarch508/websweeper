"""Data transformers — parse_date, parse_currency, etc. Referenced by name in configs."""

import re
from datetime import datetime
from typing import Callable

from websweeper import WebSweeperError


class TransformError(WebSweeperError):
    """A transform function failed."""
    pass


# Registry of named transforms
TRANSFORMS: dict[str, Callable[[str], str]] = {}


def register_transform(name: str):
    """Decorator to register a transform function."""
    def decorator(func):
        TRANSFORMS[name] = func
        return func
    return decorator


def get_transform(name: str) -> Callable[[str], str]:
    """Get a transform function by name."""
    if name not in TRANSFORMS:
        raise TransformError(f"Unknown transform: {name}")
    return TRANSFORMS[name]


def apply_transform(name: str, value: str) -> str:
    """Apply a named transform to a value."""
    return get_transform(name)(value)


@register_transform("parse_date")
def parse_date(raw: str) -> str:
    """Normalize various date formats to YYYY-MM-DD.

    Handles: MM/DD/YYYY, MM-DD-YYYY, Mon DD, YYYY, ISO passthrough.
    """
    raw = raw.strip()
    if not raw:
        return raw

    # ISO format passthrough
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw

    # Try common formats
    formats = [
        "%m/%d/%Y",      # 01/15/2024
        "%m-%d-%Y",      # 01-15-2024
        "%b %d, %Y",     # Jan 15, 2024
        "%B %d, %Y",     # January 15, 2024
        "%m/%d/%y",      # 01/15/24
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    raise TransformError(f"Cannot parse date: '{raw}'")


@register_transform("parse_currency")
def parse_currency(raw: str) -> str:
    """Normalize currency strings to plain decimal numbers.

    "$1,234.56" -> "1234.56"
    "($42.99)" -> "-42.99"
    "-$15.00" -> "-15.00"
    """
    raw = raw.strip()
    if not raw:
        return raw

    negative = False

    # Parentheses mean negative: ($42.99)
    if raw.startswith("(") and raw.endswith(")"):
        negative = True
        raw = raw[1:-1]

    # Leading minus
    if raw.startswith("-"):
        negative = True
        raw = raw[1:]

    # Strip currency symbols and commas
    raw = raw.replace("$", "").replace(",", "").strip()

    # Validate it's a number
    try:
        float(raw)
    except ValueError:
        raise TransformError(f"Cannot parse currency: '{raw}'")

    if negative:
        return f"-{raw}"
    return raw


@register_transform("strip")
def strip_whitespace(raw: str) -> str:
    """Strip leading/trailing whitespace and collapse internal whitespace."""
    return " ".join(raw.split())


@register_transform("lowercase")
def lowercase(raw: str) -> str:
    """Convert to lowercase."""
    return raw.lower()
