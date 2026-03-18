# WebSweeper

Config-driven Playwright automation framework with a hybrid AI maintenance model.

WebSweeper executes browser workflows (login, navigate, extract data) from declarative YAML configs using Playwright. No LLM is involved at runtime — AI is used only at maintenance time when selectors break, via diagnostic packages that capture everything needed for repair.

## Architecture

Two layers:

- **Base Framework (`src/websweeper/`)** — Generic, reusable web automation. Handles config loading, credential injection, Playwright step execution, session persistence, diagnostic capture, table extraction, and CSV output.
- **Extensions (`extensions/`)** — Domain-specific configs and CLI actions. The `finance` extension targets bank/credit card portals for statement and transaction extraction.

```
Scheduler / CLI
      │
      ▼
  Runner (Python)
  ├── Reads YAML config
  ├── Resolves credentials (env vars)
  ├── Executes Playwright steps
  ├── Extracts data (table scraping)
  └── Writes CSV output
      │
      ▼
  Playwright (headless Chromium)
  ├── No LLM at runtime
  ├── Fast, deterministic
  └── storageState for session reuse

  On Failure → Diagnostic Package
  ├── screenshot.png
  ├── accessibility_tree.txt
  ├── error.log
  ├── config.yaml (copy)
  └── step_context.json
        │
        ▼
  Claude Code (manual invocation) → reads diagnostic, updates config
```

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Install

```bash
# Clone
git clone https://github.com/monarch508/websweeper.git
cd websweeper

# Install with uv (recommended)
uv sync --extra dev

# Install Playwright browser
uv run playwright install chromium

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

### Set up credentials

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

### Run

```bash
# Validate a config
uv run websweeper validate path/to/config.yaml

# Run a config (headless)
uv run websweeper run path/to/config.yaml

# Run with visible browser for debugging
uv run websweeper run path/to/config.yaml --debug

# Dry run (authenticate + navigate, skip extraction)
uv run websweeper run path/to/config.yaml --dry-run

# Force re-authentication (ignore saved session)
uv run websweeper run path/to/config.yaml --force-auth

# Finance extension actions
uv run websweeper finance --help
uv run websweeper finance getbofastatements --start-date 2026-01
```

### Run tests

```bash
uv run pytest              # All tests
uv run pytest -v           # Verbose
uv run pytest tests/test_config.py  # Single module
```

## Project Structure

```
websweeper/
├── pyproject.toml              # Package definition, deps, entry points
├── .env.example                # Credential template
├── .gitignore
├── PROJECT_SPEC.md             # Full project specification
│
├── src/websweeper/             # Base Framework
│   ├── cli.py                  # Click CLI + extension discovery
│   ├── runner.py               # Orchestrator: auth → navigate → extract → output
│   ├── config.py               # Pydantic models + YAML loader
│   ├── credentials.py          # Env var credential resolution
│   ├── executor.py             # Playwright step executor + target resolver
│   ├── extractors/
│   │   └── table.py            # HTML table extraction
│   ├── transforms.py           # parse_date, parse_currency, etc.
│   ├── diagnostics.py          # Failure capture for self-healing
│   ├── session.py              # storageState persistence + TTL
│   ├── output.py               # CSV writer
│   └── utils.py                # Shared utilities
│
├── extensions/finance/
│   ├── actions.py              # Finance CLI actions (stubbed for Phase 2)
│   └── configs/                # Bank-specific YAML configs (Phase 2)
│
├── tests/                      # 83 tests (unit + integration)
│   ├── fixtures/
│   │   ├── test_page.html      # Local test site for integration tests
│   │   └── *.yaml              # Test configs
│   └── test_*.py
│
├── sessions/                   # Saved browser state (gitignored)
├── output/                     # Extracted CSVs (gitignored)
└── failures/                   # Diagnostic packages (gitignored)
```

## Site Config Schema

Each target site is defined by a YAML config. See `tests/fixtures/valid_config.yaml` for a complete example, or `PROJECT_SPEC.md` Section 3 for the full schema reference.

Key sections:

| Section | Purpose |
|---|---|
| `site` | Name, ID, login URL, base URL |
| `credentials` | Provider (`env`) + env var names for username/password |
| `auth` | Login steps, MFA config, post-auth verification |
| `navigation` | Steps to reach the target page after login |
| `extraction` | Mode (`table`) + selectors for data extraction |
| `output` | CSV directory, filename template, static fields |
| `session` | storageState path, reuse flag, TTL |
| `diagnostics` | Screenshot/a11y capture settings, output directory |

## Self-Healing Workflow

When a config breaks (site changed its DOM):

1. Run fails, diagnostic package saved to `failures/{site_id}/{timestamp}/`
2. Point Claude Code at the diagnostic:
   ```bash
   claude "The BofA scraper failed. Diagnostic is in failures/bofa_checking/2026-03-17T14-30-00/.
   Read the step_context.json, examine the screenshot and accessibility tree,
   and update the config with the fix."
   ```
3. Claude Code reads the diagnostic, identifies the change, updates the YAML config
4. Re-run to verify the fix

## Security

- Credentials flow from env vars directly to Playwright — never touch an LLM
- Session state files are chmod 600 and gitignored
- `.env` is gitignored
- Output CSVs contain transaction data — treat as sensitive, gitignored
- Diagnostic packages may contain page content — PII sanitization planned for Phase 6

## License

Private project. Not licensed for distribution.
