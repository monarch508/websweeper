"""Finance extension — bank automation actions."""

import asyncio
from pathlib import Path

import click

CONFIGS_DIR = Path(__file__).parent / "configs"


@click.group("finance")
def finance_group():
    """Financial institution automation actions."""
    pass


@finance_group.command()
@click.option("--debug", is_flag=True, help="Run with visible browser")
@click.option("--dry-run", is_flag=True, help="Login and navigate but don't extract")
@click.option("--force-auth", is_flag=True, help="Ignore saved session, re-authenticate")
def getbofastatements(debug: bool, dry_run: bool, force_auth: bool):
    """Login to Bank of America and extract checking account data."""
    from websweeper.config import load_config
    from websweeper.runner import run_site

    config_path = CONFIGS_DIR / "bofa_checking.yaml"
    if not config_path.exists():
        click.echo(f"Config not found: {config_path}", err=True)
        raise SystemExit(1)

    config = load_config(config_path)
    result = asyncio.run(run_site(config, debug=debug, dry_run=dry_run, force_auth=force_auth))

    if result.status == "success":
        click.echo(f"Success: {result.rows} rows extracted")
        if result.output_path:
            click.echo(f"Output: {result.output_path}")
    else:
        click.echo(f"Failed: {result.error}", err=True)
        if result.diagnostic_path:
            click.echo(f"Diagnostics: {result.diagnostic_path}", err=True)
        raise SystemExit(1)


@finance_group.command()
@click.option("--days", default=30, help="Number of days of transactions to fetch")
@click.option("--debug", is_flag=True, help="Run with visible browser")
def getchasetransactions(days: int, debug: bool):
    """Download recent Chase transactions."""
    click.echo(f"[stub] Would download Chase transactions for last {days} days")
    click.echo("This action will be implemented with real bank configs.")
