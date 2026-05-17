"""Read Gmail messages for MFA code retrieval.

The runner triggers email-MFA on a site (e.g., BofA's "Get code a different way"),
then calls `wait_for_code()` to poll Gmail for the resulting message and extract
the code via a configurable regex.

Designed to be called from synchronous code paths inside the Playwright runner.
"""

import base64
import html as html_module
import logging
import re
import time
from html.parser import HTMLParser

from websweeper.gmail_auth import load_credentials

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 3


def wait_for_code(
    sender_filter: str,
    body_regex: str,
    subject_filter: str | None = None,
    timeout_seconds: int = 60,
    not_before_unix: int | None = None,
) -> str | None:
    """Poll Gmail until a matching message arrives, then return the extracted code.

    Args:
        sender_filter: Gmail query fragment matched as `from:<this>`. Example:
            `onlinebanking@ealerts.bankofamerica.com`.
        body_regex: Regex applied to the decoded (and HTML-stripped) message
            body. The first capture group is returned if present, otherwise
            the whole match.
        subject_filter: Optional substring or phrase included in the Gmail
            query as `subject:<this>` to narrow to MFA-specific messages.
        timeout_seconds: Total wall-clock time to poll before giving up.
        not_before_unix: If set, restrict to messages received at or after this
            unix timestamp. Defaults to the current time so we ignore older
            BofA codes that may already be in the inbox.

    Returns:
        The extracted code string, or None if nothing matched in the window.
    """
    from googleapiclient.discovery import build

    creds = load_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    pattern = re.compile(body_regex)

    if not_before_unix is None:
        not_before_unix = int(time.time())

    query_parts = [f"from:{sender_filter}", f"after:{not_before_unix}"]
    if subject_filter:
        # Gmail accepts subject:"multi word phrase" via quotes
        query_parts.append(f'subject:"{subject_filter}"')
    query = " ".join(query_parts)
    deadline = time.time() + timeout_seconds
    logger.info("Polling Gmail for MFA code (query: %r, timeout: %ds)", query, timeout_seconds)

    while time.time() < deadline:
        result = service.users().messages().list(
            userId="me", q=query, maxResults=5
        ).execute()
        messages = result.get("messages", [])
        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="full"
            ).execute()
            body = _extract_body(msg)
            match = pattern.search(body)
            if match:
                code = match.group(1) if match.groups() else match.group(0)
                logger.info("Extracted MFA code from message %s", msg_ref["id"])
                return code
        time.sleep(POLL_INTERVAL_SECONDS)

    logger.warning("Timed out waiting for MFA email")
    return None


def _extract_body(msg: dict) -> str:
    """Decode the message body and return plain text.

    Prefers text/plain when present. If only text/html is available (as with
    BofA MFA emails), strips tags plus style/script blocks and returns the
    visible text.
    """
    payload = msg.get("payload", {})
    parts = _flatten_parts(payload)
    plain = next((p for p in parts if p.get("mimeType") == "text/plain"), None)
    html = next((p for p in parts if p.get("mimeType") == "text/html"), None)

    if plain:
        return _decode_part(plain)
    if html:
        return _html_to_text(_decode_part(html))
    # Single-part message: payload itself holds the body.
    raw = _decode_part(payload)
    return _html_to_text(raw) if _looks_html(raw) else raw


def _decode_part(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")


def _flatten_parts(part: dict) -> list[dict]:
    """Walk a possibly-nested multipart structure and return all leaf parts."""
    result = []
    if "parts" in part:
        for p in part["parts"]:
            result.extend(_flatten_parts(p))
    else:
        result.append(part)
    return result


def _looks_html(s: str) -> bool:
    lowered = s.lower()
    return "<html" in lowered or "<body" in lowered or lowered.count("<") > 50


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("style", "script"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag.lower() in ("style", "script"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        joined = " ".join(self._parts)
        return re.sub(r"\s+", " ", html_module.unescape(joined)).strip()


def _html_to_text(s: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(s)
        p.close()
    except Exception:
        return s
    return p.text()
