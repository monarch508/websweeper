"""Gmail OAuth helpers.

Two responsibilities:
  1. `run_consent_flow()` runs the one-time OAuth 2.0 consent flow against the
     user's Google account and persists the resulting refresh token to disk.
  2. `load_credentials()` loads that persisted token at runtime, refreshing it
     transparently if needed.

The token file lives at `.credentials/gmail_token.json`, chmod 600, gitignored.
The OAuth client id and secret come from environment variables (.env), so no
secrets ever land in committed code.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = Path(".credentials/gmail_token.json")


def _client_config_from_env() -> dict:
    load_dotenv()
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit(
            "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set in .env."
        )
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def run_consent_flow() -> None:
    """One-time: launch the OAuth flow, persist the refresh token to disk."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_config = _client_config_from_env()
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

    print()
    print("=" * 70)
    print("Open the URL printed above in any browser (Windows Chrome is fine).")
    print("After authorizing, you'll be redirected to localhost and this")
    print("command will finish on its own.")
    print("=" * 70)
    print()
    creds = flow.run_local_server(port=0, open_browser=False)

    TOKEN_PATH.parent.mkdir(exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())
    TOKEN_PATH.chmod(0o600)

    logger.info("Saved Gmail refresh token to %s (chmod 600).", TOKEN_PATH)
    print()
    print(f"Refresh token saved to {TOKEN_PATH} (chmod 600, gitignored).")
    print("You can now use email-MFA in site configs.")


def load_credentials():
    """Load the persisted refresh token and return a refreshed Credentials.

    Raises:
        FileNotFoundError: If the token file does not exist (run gmail-auth).
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"Gmail token not found at {TOKEN_PATH}. "
            "Run 'websweeper gmail-auth' to grant access first."
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
        TOKEN_PATH.chmod(0o600)
    return creds
