"""Shared utilities."""

from datetime import datetime
from pathlib import Path


def ensure_directory(path: Path) -> Path:
    """Create directory and parents if they don't exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def timestamp_slug() -> str:
    """Return current timestamp in filesystem-safe format: 2026-03-17T14-30-00"""
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def iso_date_today() -> str:
    """Return today's date as YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")
