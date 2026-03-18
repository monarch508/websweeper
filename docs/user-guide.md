# WebSweeper User Guide

## Overview

WebSweeper automates browser workflows from YAML config files. You define what to do (fill fields, click buttons, extract tables) in a config, and WebSweeper executes it with Playwright.

The framework handles:
- **Authentication** — fill login forms, inject credentials from env vars, wait for MFA
- **Navigation** — click through pages to reach your target
- **Extraction** — scrape tables into structured data
- **Output** — write CSV files with transforms applied (date parsing, currency normalization)
- **Session reuse** — skip login on subsequent runs using saved browser state
- **Failure diagnostics** — capture screenshots, accessibility trees, and error context for debugging

---

## Installation

### Using uv (recommended)

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/monarch508/websweeper.git
cd websweeper
uv sync --extra dev

# Install the browser
uv run playwright install chromium
```

### Using pip

```bash
git clone https://github.com/monarch508/websweeper.git
cd websweeper
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

### System dependencies (Linux/WSL2)

If Playwright complains about missing system libraries:
```bash
playwright install-deps chromium   # Requires sudo
```

---

## Setting Up Credentials

Copy the template and fill in real values:

```bash
cp .env.example .env
```

Edit `.env`:
```bash
BOFA_USERNAME=your_real_username
BOFA_PASSWORD=your_real_password
```

The `.env` file is gitignored and should never be committed.

Your site config references these by variable name:
```yaml
credentials:
  provider: "env"
  env:
    username_var: "BOFA_USERNAME"
    password_var: "BOFA_PASSWORD"
```

---

## Writing a Site Config

A site config is a YAML file that describes how to interact with a website. Here's a minimal example:

```yaml
site:
  name: "My Site"
  id: "my_site"
  login_url: "https://example.com/login"
  base_url: "https://example.com"

credentials:
  provider: "env"
  env:
    username_var: "MY_USERNAME"
    password_var: "MY_PASSWORD"

auth:
  steps:
    - action: "fill"
      target: { type: "id", value: "username" }
      input: "{username}"
    - action: "fill"
      target: { type: "id", value: "password" }
      input: "{password}"
    - action: "click"
      target: { type: "id", value: "submit" }
  verify:
    - action: "wait_for_selector"
      target: { type: "text", value: "Dashboard" }
      timeout_seconds: 15
```

### Step Actions

| Action | Description | Requires |
|---|---|---|
| `fill` | Type text into an input field | `target`, `input` |
| `click` | Click an element | `target` |
| `select` | Select a dropdown option | `target`, `input` |
| `wait` | Wait a fixed duration | `wait_ms` |
| `wait_for_selector` | Wait for an element to appear | `target`, `timeout_seconds` |

### Target Types

| Type | Description | Example |
|---|---|---|
| `id` | HTML element ID | `{ type: "id", value: "loginBtn" }` |
| `css` | CSS selector | `{ type: "css", value: ".submit-button" }` |
| `text` | Visible text content | `{ type: "text", value: "Sign In" }` |
| `role` | ARIA role + name | `{ type: "role", value: "Submit", role: "button", name: "Submit" }` |
| `placeholder` | Input placeholder text | `{ type: "placeholder", value: "Enter email" }` |

**Selector stability:** Text-based and role-based selectors are more resilient to DOM changes than CSS selectors. Prefer `text` or `role` when possible. Use `id` for form fields (usually stable). Use `css` as a last resort.

### Template Variables

Use `{username}` and `{password}` in step inputs — they're resolved from credentials at runtime:

```yaml
- action: "fill"
  target: { type: "id", value: "user" }
  input: "{username}"    # Replaced with actual credential value
```

### MFA Configuration

```yaml
auth:
  mfa:
    type: "push"         # "push", "totp", "sms", or "none"
    wait_seconds: 45     # How long to wait for approval
```

For `push` and `sms`, the framework waits for you to approve on your phone. For `totp`, programmatic code generation will be added in a future phase.

### Table Extraction

```yaml
extraction:
  mode: "table"
  table:
    container:
      type: "id"
      value: "transactions-table"
    row_selector: "tr.transaction"
    columns:
      - name: "date"
        selector: "td.date"
        transform: "parse_date"       # Normalizes to YYYY-MM-DD
      - name: "description"
        selector: "td.description"
      - name: "amount"
        selector: "td.amount"
        transform: "parse_currency"   # Strips $, commas, handles negatives
```

### Available Transforms

| Transform | Input | Output |
|---|---|---|
| `parse_date` | `01/15/2024`, `Jan 15, 2024` | `2024-01-15` |
| `parse_currency` | `$1,234.56`, `($42.99)`, `-$15.00` | `1234.56`, `-42.99`, `-15.00` |
| `strip` | `"  hello   world  "` | `"hello world"` |
| `lowercase` | `"HELLO World"` | `"hello world"` |

### Output Configuration

```yaml
output:
  format: "csv"
  directory: "./output/{site_id}/"
  filename_template: "{site_id}_{date_pulled}.csv"
  columns: ["date", "description", "amount", "account"]
  static_fields:
    account: "Checking (5844)"
    source: "bofa_checking"
```

`static_fields` are added to every row. `pulled_date` is always added automatically.

### Session Persistence

```yaml
session:
  storage_state_path: "./sessions/{site_id}_state.json"
  reuse_session: true
  session_ttl_hours: 24
```

After successful authentication, browser cookies and storage are saved. Subsequent runs within the TTL window skip login entirely. Session files are chmod 600.

---

## CLI Commands

### Base commands

```bash
# Run a config
websweeper run path/to/config.yaml

# Run with visible browser (debugging)
websweeper run path/to/config.yaml --debug

# Authenticate + navigate but don't extract
websweeper run path/to/config.yaml --dry-run

# Force re-authentication (ignore saved session)
websweeper run path/to/config.yaml --force-auth

# Validate config syntax
websweeper validate path/to/config.yaml
```

### Finance extension

```bash
# List finance actions
websweeper finance --help

# Download BofA statements (Phase 2 — currently stubbed)
websweeper finance getbofastatements --start-date 2026-01

# Download Chase transactions (Phase 2 — currently stubbed)
websweeper finance getchasetransactions --days 30
```

---

## Debugging Failures

When a run fails, a diagnostic package is saved to `failures/{site_id}/{timestamp}/`:

```
failures/bofa_checking/2026-03-17T14-30-00/
├── screenshot.png            # What the page looked like
├── accessibility_tree.txt    # Page structure (for finding new selectors)
├── error.log                 # Full Python traceback
├── config.yaml               # The config that was used
└── step_context.json         # Which step failed, page URL, error details
```

### Manual debugging

1. Run with `--debug` to see the browser
2. Check the `step_context.json` to see which step failed
3. Look at the screenshot to see the page state
4. Check the accessibility tree for current element names/roles
5. Update the config YAML with corrected selectors
6. Re-run to verify

### Claude Code repair

```bash
claude "The scraper failed. Diagnostic is in failures/bofa_checking/2026-03-17T14-30-00/.
Read step_context.json, examine the screenshot and accessibility tree,
find the correct selector, and update the config."
```

---

## Running Tests

```bash
# Full suite (83 tests)
uv run pytest

# Verbose output
uv run pytest -v

# Single test file
uv run pytest tests/test_config.py

# Single test
uv run pytest tests/test_integration.py::TestFullPipeline::test_end_to_end_extraction
```

Integration tests run against a local HTML test page (`tests/fixtures/test_page.html`) — no external sites or credentials needed.
