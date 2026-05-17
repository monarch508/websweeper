"""CLI entry point — Click-based command interface with extension discovery."""

import asyncio
import logging

import click

from websweeper import __version__


@click.group()
@click.version_option(version=__version__)
@click.option("--debug", is_flag=True, help="Enable debug logging")
def cli(debug: bool):
    """WebSweeper: Config-driven Playwright automation framework."""
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


@cli.command()
@click.argument("config_path", type=click.Path(exists=True))
@click.option("--debug", is_flag=True, help="Run with visible browser")
@click.option("--dry-run", is_flag=True, help="Authenticate and navigate but don't extract")
@click.option("--force-auth", is_flag=True, help="Ignore saved session, re-authenticate")
def run(config_path: str, debug: bool, dry_run: bool, force_auth: bool):
    """Run a site config to extract data."""
    from websweeper.config import load_config
    from websweeper.runner import run_site

    config = load_config(config_path)
    result = asyncio.run(run_site(config, debug=debug, force_auth=force_auth, dry_run=dry_run))

    if result.status == "success":
        click.echo(f"Success: {result.rows} rows extracted")
        if result.output_path:
            click.echo(f"Output: {result.output_path}")
    else:
        click.echo(f"Failed: {result.error}", err=True)
        if result.diagnostic_path:
            click.echo(f"Diagnostics: {result.diagnostic_path}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("config_path", type=click.Path(exists=True))
def validate(config_path: str):
    """Validate a site config file against the schema."""
    from websweeper.config import ConfigValidationError, load_config

    try:
        config = load_config(config_path)
        click.echo(f"Valid: {config.site.name} ({config.site.id})")
    except ConfigValidationError as e:
        click.echo("Validation errors:", err=True)
        for error in e.errors:
            click.echo(f"  - {error}", err=True)
        raise SystemExit(1)


@cli.command("gmail-auth")
def gmail_auth():
    """Run the one-time Gmail OAuth consent flow and save a refresh token.

    Requires GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env.
    Opens a browser for consent, then writes .credentials/gmail_token.json.
    """
    from websweeper.gmail_auth import run_consent_flow

    run_consent_flow()


def _register_extensions():
    """Discover and register extension CLI groups via entry points."""
    from importlib.metadata import entry_points

    eps = entry_points()
    ext_eps = eps.select(group="websweeper.extensions") if hasattr(eps, "select") else eps.get("websweeper.extensions", [])
    for ep in ext_eps:
        try:
            group = ep.load()
            cli.add_command(group, ep.name)
        except Exception as e:
            click.echo(f"Warning: Failed to load extension '{ep.name}': {e}", err=True)


_register_extensions()
