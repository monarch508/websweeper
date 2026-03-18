"""Finance extension — bank automation actions."""

import click


@click.group("finance")
def finance_group():
    """Financial institution automation actions."""
    pass


@finance_group.command()
@click.option("--start-date", required=True, help="Start date (YYYY-MM format)")
@click.option("--end-date", help="End date (YYYY-MM format, defaults to current month)")
@click.option("--debug", is_flag=True, help="Run with visible browser")
def getbofastatements(start_date: str, end_date: str | None, debug: bool):
    """Download Bank of America statements for a date range."""
    # Phase 2: will load configs/bofa_checking.yaml, inject date range, run pipeline
    click.echo(f"[stub] Would download BofA statements from {start_date} to {end_date or 'current'}")
    click.echo("This action will be implemented in Phase 2 with real bank configs.")


@finance_group.command()
@click.option("--days", default=30, help="Number of days of transactions to fetch")
@click.option("--debug", is_flag=True, help="Run with visible browser")
def getchasetransactions(days: int, debug: bool):
    """Download recent Chase transactions."""
    # Phase 2 stub
    click.echo(f"[stub] Would download Chase transactions for last {days} days")
    click.echo("This action will be implemented in Phase 2 with real bank configs.")
