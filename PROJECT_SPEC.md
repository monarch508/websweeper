# WebSweeper: Hybrid Playwright Automation Framework

## Project Spec for Claude Code Handoff

**Author:** Sean O'Brien + Claude (discovery session, March 2026)
**Target Environment:** WSL2 Ubuntu on Windows 11 (HP OMEN, i7-14650HX, 32GB RAM)
**Production Target:** Linux VPS (same codebase, no modifications needed)
**Language:** Python 3.11+
**Key Dependencies:** Playwright, PyYAML, python-dotenv

---

## 0. Project Organization

This project has two layers:

**Layer A: Base Framework (`websweeper/`)** is a generic, reusable web automation framework. It knows nothing about banks, budgets, or financial data. It provides: config-driven Playwright execution, credential injection, session persistence, diagnostic capture for self-healing, and a CLI. This layer could automate any authenticated website workflow (e.g., pulling reports from a vendor portal, scraping government records, downloading invoices).

**Layer B: Financial Extension (`extensions/finance/`)** applies the base framework to a specific scenario: downloading bank and credit card statements, extracting transactions, classifying them via a vendor-to-category mapping, and outputting structured CSVs for a downstream budgeting application. This layer contains all the bank-specific configs, the classification taxonomy, and the output formatting specific to personal finance.

The separation is intentional. The base framework is the reusable asset. The financial extension is one use case built on top of it. Future extensions (e.g., automating utility bill downloads, pulling insurance documents, scraping price comparisons) would follow the same pattern without modifying the base.

---

## 1. Problem Statement

### Base Framework Problem

Authenticated websites require repetitive manual interaction: logging in, navigating, extracting data. Traditional automation (Playwright, Selenium) solves this but breaks when UIs change, requiring developer intervention. AI-in-the-loop automation (Browserbase, browser-use) is resilient but slow and expensive in LLM tokens. The hybrid approach uses deterministic Playwright at runtime (fast, free) and AI only at maintenance time (infrequent, targeted). The framework must:

- Execute config-driven browser workflows (login, navigate, extract) without LLM involvement at runtime
- Support multiple credential providers (env vars, 1Password CLI)
- Persist authenticated sessions across runs
- Produce structured diagnostic packages on failure for Claude Code repair
- Run headless in WSL2/Linux without a display server
- Support both batch (on-demand) and scheduled (cron) execution

### Financial Extension Problem

Automate downloading bank and credit card statements/transactions from financial institution web portals (Bank of America, Chase, Citi, Target RedCard, Best Buy/Citi). Extract transaction data, apply a vendor-to-category classification mapping, and output structured CSVs for a downstream budgeting application. Support both monthly batch (statement downloads) and frequent polling (target: every 20 minutes with on-call activation, to be validated against bank tolerance).

---

## 2. Architecture Overview

### Design Philosophy: Hybrid AI Maintenance

The core insight is that Playwright scripts are deterministic and fast when they work. They only break when the target site changes its DOM. The expensive part is not writing the script; it is maintaining it. This framework separates:

- **"What to do"** (YAML site configs, declarative)
- **"How to do it"** (selectors and interaction logic, generated/maintained by Claude Code)
- **"Running it"** (Playwright executor, deterministic, no LLM at runtime)

**AI is used at maintenance time, not runtime.** When a script fails, the framework produces a diagnostic package (screenshot, accessibility tree, error log, config). The developer points Claude Code at the diagnostic and it identifies what changed and updates the config. Normal runs burn zero LLM tokens.

### Layer Diagram

```
┌─────────────────────────────────────────────────┐
│  Scheduler (cron / systemd timer / on-demand)   │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│  Runner (Python)                                 │
│  - Reads site config (YAML)                      │
│  - Resolves credentials (env vars / 1Password)   │
│  - Executes Playwright steps                     │
│  - Captures diagnostics on failure               │
│  - Outputs extracted data (CSV)                  │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│  Playwright (headless Chromium)                   │
│  - No LLM involved at runtime                    │
│  - Fast, deterministic                           │
│  - storageState for session persistence          │
└─────────────────────────────────────────────────┘

  ── On Failure ──

┌─────────────────────────────────────────────────┐
│  Diagnostic Package                              │
│  - screenshot.png                                │
│  - accessibility_tree.txt                        │
│  - error.log (Python traceback)                  │
│  - config.yaml (current)                         │
│  - step_index (which step failed)                │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
        Claude Code (manual invocation)
        Reads diagnostic, updates config
```

---

## 3. Site Config Schema (Base Framework)

Each target site gets a YAML config file. The config is the contract between the declarative workflow description and the Playwright executor. The schema is generic; it knows nothing about banks or finance. The financial extension's bank configs follow this same schema with finance-specific output settings layered on top.

### Example: `configs/bofa_checking.yaml`

```yaml
# Site identification
site:
  name: "Bank of America - Checking"
  id: "bofa_checking"
  login_url: "https://www.bankofamerica.com/login"
  base_url: "https://www.bankofamerica.com"

# Credential resolution
# Phase 1: env vars (BOFA_USERNAME, BOFA_PASSWORD)
# Phase 2: 1Password CLI (op://Finance/BofA/username)
credentials:
  provider: "env"  # "env" or "onepassword"
  env:
    username_var: "BOFA_USERNAME"
    password_var: "BOFA_PASSWORD"
  onepassword:
    username_ref: "op://Finance/BofA/username"
    password_ref: "op://Finance/BofA/password"

# Authentication flow
auth:
  steps:
    - action: "fill"
      target:
        type: "id"         # "id", "css", "text", "role", "placeholder"
        value: "onlineId1"
      input: "{username}"
      description: "Enter username"

    - action: "fill"
      target:
        type: "id"
        value: "passcode1"
      input: "{password}"
      description: "Enter password"

    - action: "click"
      target:
        type: "id"
        value: "signIn"
      description: "Click sign in"

  # MFA handling
  mfa:
    type: "push"           # "push", "totp", "sms", "none"
    wait_seconds: 45       # How long to wait for MFA completion
    # For TOTP: totp_secret_var: "BOFA_TOTP_SECRET"

  # Post-auth verification: confirm login succeeded
  verify:
    - type: "wait_for_selector"
      target:
        type: "text"
        value: "Accounts Overview"
      timeout_seconds: 15

# Navigation to target page
navigation:
  steps:
    - action: "click"
      target:
        type: "text"
        value: "Statements & Documents"
      description: "Navigate to statements page"
      wait_after: 3000  # ms to wait after action

    - action: "click"
      target:
        type: "text"
        value: "Statements"
      description: "Select statements tab"
      wait_after: 2000

# Data extraction
extraction:
  mode: "table"  # "table", "pdf_download", "page_scrape"

  # For mode: table
  table:
    container:
      type: "css"
      value: ".transaction-list"
    row_selector: ".transaction-row"
    columns:
      - name: "date"
        selector: ".date-column"
        transform: "parse_date"  # optional post-processing
      - name: "description"
        selector: ".description-column"
      - name: "amount"
        selector: ".amount-column"
        transform: "parse_currency"

  # For mode: pdf_download
  pdf:
    download_trigger:
      type: "css"
      value: ".download-statement-link"
    filename_pattern: "eStmt_{year}-{month}.pdf"

# Output configuration
output:
  format: "csv"
  directory: "./output/{site_id}/"
  filename_template: "{site_id}_{date_pulled}.csv"
  # Columns to include in output
  columns: ["date", "description", "amount", "category", "account"]
  # Static values to add to every row
  static_fields:
    account: "Checking (5844)"
    source: "bofa_checking"

# Session persistence
session:
  storage_state_path: "./sessions/{site_id}_state.json"
  reuse_session: true
  session_ttl_hours: 24  # Re-authenticate after this long

# Diagnostic settings
diagnostics:
  screenshot_on_failure: true
  capture_accessibility_tree: true
  output_directory: "./failures/{site_id}/"

# Metadata for self-healing
metadata:
  last_verified: "2026-03-16"
  last_modified_by: "sean"
  selector_confidence:
    high: ["#onlineId1", "#passcode1", "#signIn"]
    medium: [".transaction-list", ".transaction-row"]
    low: [".date-column", ".description-column", ".amount-column"]
  notes: "BofA uses dynamic class names on some elements. Text-based selectors more stable."
```

### Config Design Notes

- **Target types** support multiple selector strategies. Text-based and role-based selectors are more resilient to DOM changes than CSS selectors. Use the most stable selector available for each element.
- **`selector_confidence`** guides Claude Code during repair: low-confidence selectors should be checked first when something breaks.
- **`wait_after`** handles pages that load content dynamically after navigation.
- **`{username}` and `{password}`** are template variables resolved at runtime from the credential provider.

---

## 4. Runner Implementation (Base Framework)

### Project Structure

```
websweeper/
├── pyproject.toml
├── README.md
├── .env                          # Credentials (gitignored)
├── .gitignore
│
├── websweeper/            # LAYER A: Base Framework
│   ├── __init__.py
│   ├── cli.py                    # CLI entry point (click)
│   ├── runner.py                 # Main orchestrator
│   ├── config.py                 # YAML config loader and validator
│   ├── credentials.py            # Credential resolution (env, 1password)
│   ├── executor.py               # Playwright step executor
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── table.py              # Table extraction logic
│   │   ├── pdf_download.py       # PDF download logic
│   │   └── page_scrape.py        # Generic page scraping
│   ├── transforms.py             # Data transformers (parse_date, parse_currency, etc.)
│   ├── diagnostics.py            # Failure capture (screenshot, a11y tree, logs)
│   ├── session.py                # Session state management
│   ├── output.py                 # Base output formatting (CSV, JSON)
│   └── utils.py                  # Shared utilities
│
├── extensions/                   # LAYER B: Use-Case Extensions
│   └── finance/
│       ├── __init__.py
│       ├── cli.py                # Finance-specific CLI commands
│       ├── classifier.py         # Vendor-to-category mapping engine
│       ├── taxonomy.py           # Category schema (Major:Minor definitions)
│       ├── labels.py             # Label schema (activity, trigger, necessity, who)
│       ├── output_finance.py     # Finance-specific CSV formatting
│       ├── dedup.py              # Transaction deduplication logic
│       ├── configs/              # Bank-specific site configs
│       │   ├── bofa_checking.yaml
│       │   ├── bofa_savings.yaml
│       │   ├── chase.yaml
│       │   ├── target_redcard.yaml
│       │   ├── citi_421.yaml
│       │   ├── citi_431.yaml
│       │   └── bestbuy_citi.yaml
│       ├── mappings/
│       │   ├── vendor_map.json       # Vendor name -> category mapping
│       │   ├── category_schema.json  # Major:Minor taxonomy definition
│       │   └── label_schema.json     # Label vocabulary and defaults
│       └── rules/
│           └── classification_rules.json  # Special rules (Freeport Gas <$25 = Treats, etc.)
│
├── sessions/                     # Persisted browser state (gitignored)
├── output/                       # Extracted CSVs
└── failures/                     # Diagnostic packages for broken scripts
```

### Runner Flow

```python
# Pseudocode for runner.py

async def run_site(config_path: str, debug: bool = False):
    """Execute a single site's extraction workflow."""
    config = load_config(config_path)
    creds = resolve_credentials(config)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not debug)
        context = await load_or_create_context(browser, config)
        page = await context.new_page()

        try:
            # Step 1: Authenticate (or verify existing session)
            if not await session_is_valid(page, config):
                await authenticate(page, config, creds)
                await handle_mfa(page, config)
                await verify_auth(page, config)
                await save_session_state(context, config)

            # Step 2: Navigate
            for step in config.navigation.steps:
                await execute_step(page, step)

            # Step 3: Extract
            data = await extract_data(page, config)

            # Step 4: Output
            write_output(data, config)

            return {"status": "success", "rows": len(data)}

        except Exception as e:
            # Capture diagnostics for Claude Code repair
            await capture_diagnostics(page, config, e)
            return {"status": "failed", "error": str(e), "step": current_step}

        finally:
            await browser.close()
```

### Step Executor

The executor maps config actions to Playwright calls:

```python
# Pseudocode for executor.py

async def execute_step(page, step):
    """Execute a single config step against the page."""
    element = await resolve_target(page, step.target)

    if step.action == "fill":
        await element.fill(step.input)
    elif step.action == "click":
        await element.click()
    elif step.action == "select":
        await element.select_option(step.input)
    elif step.action == "wait":
        await page.wait_for_timeout(step.wait_ms)

    if step.wait_after:
        await page.wait_for_timeout(step.wait_after)


async def resolve_target(page, target):
    """Resolve a config target to a Playwright locator."""
    if target.type == "id":
        return page.locator(f"#{target.value}")
    elif target.type == "css":
        return page.locator(target.value)
    elif target.type == "text":
        return page.get_by_text(target.value)
    elif target.type == "role":
        return page.get_by_role(target.role, name=target.value)
    elif target.type == "placeholder":
        return page.get_by_placeholder(target.value)
```

---

## 5. Credential Handling

### Phase 1: Environment Variables

Simple `.env` file, loaded via `python-dotenv`:

```bash
# .env (gitignored)
BOFA_USERNAME=your_username
BOFA_PASSWORD=your_password
CHASE_USERNAME=your_username
CHASE_PASSWORD=your_password
# etc.
```

### Phase 2: 1Password CLI

When ready to upgrade, the credential resolver switches to `op` CLI:

```python
import subprocess

def resolve_onepassword(reference: str) -> str:
    """Resolve a 1Password secret reference."""
    result = subprocess.run(
        ["op", "read", reference],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()
```

The config's `credentials.provider` field controls which resolver is used. No code changes needed to switch, just update the config.

---

## 6. Diagnostic Package for Self-Healing

When a step fails, the diagnostics module captures everything Claude Code needs to fix it:

```
failures/bofa_checking/2026-03-16T14-30-00/
├── screenshot.png           # Full page screenshot at failure point
├── accessibility_tree.txt   # Page accessibility tree (text representation)
├── error.log                # Full Python traceback
├── config.yaml              # Copy of the config that was used
├── step_context.json        # Which step failed, what was expected
│   {
│     "step_index": 3,
│     "step_description": "Navigate to statements page",
│     "expected_target": {"type": "text", "value": "Statements & Documents"},
│     "page_url": "https://www.bankofamerica.com/accounts/",
│     "page_title": "Accounts Overview | Bank of America"
│   }
└── page_content.txt         # Optional: stripped text content of page
```

### Claude Code Repair Workflow

When a failure occurs, the developer invokes Claude Code:

```bash
claude "The BofA checking scraper failed. Diagnostic package is in
failures/bofa_checking/2026-03-16T14-30-00/. Read the step_context.json
to understand what failed, examine the screenshot and accessibility tree
to find the correct current selector, and update
configs/bofa_checking.yaml with the fix. Then run a verification pass
with: python -m websweeper run bofa_checking --debug --dry-run"
```

Claude Code:
1. Reads the diagnostic package
2. Compares the expected selector to the actual page state
3. Identifies the change (e.g., "Statements & Documents" renamed to "Documents & Statements")
4. Updates the YAML config
5. Optionally runs a verification

**Important:** The accessibility tree capture should strip or mask sensitive data (account numbers, balances) before writing to disk. The diagnostic package may be shared with Claude Code, so PII exposure must be minimized. Implement a sanitization pass that replaces account numbers with masked versions (e.g., "****5844") and redacts dollar amounts.

---

## 7. Session Management

Playwright's `storageState` saves cookies and local storage to a JSON file. This allows subsequent runs to skip authentication if the session is still valid.

```python
# Save after successful auth
await context.storage_state(path=config.session.storage_state_path)

# Load on next run
context = await browser.new_context(
    storage_state=config.session.storage_state_path
)
```

Session validity is checked by navigating to a post-login page and looking for the auth verification selector. If it fails, the runner falls back to full authentication.

The `session_ttl_hours` config value sets a maximum session age. Even if the session file exists, re-authenticate after this period to avoid stale sessions.

**Security note:** Session state files contain authentication tokens. They must be:
- Stored in a gitignored directory
- Readable only by the running user (chmod 600)
- Excluded from any backup or sync that leaves the machine

---

## 8. CLI Interface

### Base Framework Commands

```bash
# Run a single site config
python -m websweeper run configs/bofa_checking.yaml

# Run all configs in a directory
python -m websweeper run-all configs/

# Run with visible browser for debugging
python -m websweeper run configs/bofa_checking.yaml --debug

# Dry run: authenticate and navigate but don't extract
python -m websweeper run configs/bofa_checking.yaml --dry-run

# Validate a config file against the schema
python -m websweeper validate configs/bofa_checking.yaml

# List configured sites and their last run status
python -m websweeper status

# Force re-authentication (ignore saved session)
python -m websweeper run configs/bofa_checking.yaml --force-auth
```

### Financial Extension Commands

```bash
# Run a bank config with classification applied
python -m websweeper finance run bofa_checking

# Run all bank configs with classification
python -m websweeper finance run-all

# Classify a raw CSV against the vendor map (standalone, no scraping)
python -m websweeper finance classify output/raw/chase_2026-03-16.csv

# Show vendor map coverage stats
python -m websweeper finance map-stats

# Show unclassified vendors from the last run
python -m websweeper finance unclassified

# Export the current vendor map, category schema, and rules as JSON
python -m websweeper finance export-mappings ./export/
```

The finance extension registers its commands as a CLI subgroup under `finance`. The base `run` command produces raw CSVs. The `finance run` command calls the base runner and then pipes the output through the classifier.

---

## 9. MFA Handling

MFA is the hardest part of automated bank authentication. Strategies by type:

### Push Notification (BofA, Chase)
The script waits `mfa.wait_seconds` for the user to approve on their phone. During this wait, the script polls for the post-auth verification selector. If the user approves in time, the script continues. If not, it fails with a clear "MFA timeout" diagnostic.

For scheduled/unattended runs, this requires the user to have their phone available. Not ideal for fully autonomous operation, but acceptable for the "on-call activation" use case where Sean triggers a run and approves the MFA manually.

### TOTP (Time-based One-Time Password)
If the bank supports TOTP (authenticator app), the script can generate the code programmatically using the TOTP secret:

```python
import pyotp
totp = pyotp.TOTP(os.environ["BOFA_TOTP_SECRET"])
code = totp.now()
```

This enables fully unattended runs. Requires the TOTP seed, which can be extracted when setting up the authenticator app.

### SMS
Similar to push: wait for the user to enter the code. The script detects the SMS input field, waits for user input (in debug/headed mode), or accepts the code via stdin in headless mode.

---

## 10. Output Format

### Base Framework Output

The base framework writes raw extracted data as CSV with whatever columns the site config defines. No classification, no labels, no domain-specific formatting. The output module is extensible: extensions register their own output formatters.

```csv
date,description,amount,source,pulled_date
2024-01-15,CHIPOTLE MEXICAN GRILL,-15.42,chase,2026-03-16
2024-01-16,AMAZON.COM,-42.99,chase,2026-03-16
```

### Financial Extension Output

The finance extension's output formatter adds classification and labeling on top of the raw extraction. It applies the vendor-to-category mapping and outputs CSVs matching the schema established in the 2024 BofA characterization project:

```csv
date,description,amount,category,account,source,classification,labels,notes,pulled_date
2024-01-15,CHIPOTLE MEXICAN GRILL,-15.42,Purchase,Chase Freedom,chase,Food: Fast Casual,"activity:routine, trigger:, necessity:flexible, who:",,2026-03-16
2024-01-16,AMAZON.COM,-42.99,Purchase,Chase Freedom,chase,Shopping: General,"activity:routine, trigger:, necessity:flexible, who:",,2026-03-16
```

Transactions that match a known vendor in the mapping get auto-classified. Unknown vendors are flagged with `classification: Unclassified` for manual review. The extension tracks classification hit rate per run so the user can gauge how much manual work remains.

---

## 11. Development Roadmap

### Phase 1: Base Framework Foundation (Target: 1-2 sessions)
- [ ] Project scaffolding (pyproject.toml, directory structure, base + extension layout)
- [ ] Config loader and validator (YAML schema)
- [ ] Credential resolver (env vars only)
- [ ] Playwright executor (generic step runner from config)
- [ ] Target resolver (id, css, text, role, placeholder strategies)
- [ ] Diagnostic capture module (screenshot, a11y tree, error context)
- [ ] Session state persistence (storageState save/load, TTL check)
- [ ] Base output module (raw CSV)
- [ ] CLI with `run`, `validate`, `status` commands

### Phase 2: First Site End-to-End (Target: 1 session)
- [ ] Bank of America checking config (best understood site from prior work)
- [ ] Auth flow with MFA wait
- [ ] Table extraction for transactions
- [ ] Verify headless operation in WSL2
- [ ] Diagnostic package generation on simulated failure
- [ ] Claude Code repair workflow: break something, produce diagnostic, repair via Claude Code

### Phase 3: Financial Extension, Classification (Target: 1-2 sessions)
- [ ] Vendor-to-category mapping engine (`extensions/finance/classifier.py`)
- [ ] Export vendor map from 2024 characterization data (JSON, ~712 vendors)
- [ ] Category schema definition (Major:Minor taxonomy as JSON)
- [ ] Label schema definition (activity, trigger, necessity, who vocabularies as JSON)
- [ ] Classification rules engine (conditional rules: amount thresholds, keyword matching)
- [ ] Finance-specific output formatter (classified CSV with labels column)
- [ ] Unknown vendor flagging and reporting

### Phase 4: Multi-Site Expansion (Target: 2-3 sessions)
- [ ] Chase config
- [ ] Target RedCard config
- [ ] Citi 421 config
- [ ] Citi 431 config
- [ ] Best Buy/Citi config
- [ ] BofA savings config
- [ ] Table extraction generalized across sites (different DOM structures)
- [ ] PDF download mode (for statement PDFs vs. transaction scraping)

### Phase 5: Scheduling and Polling (Target: 1-2 sessions)
- [ ] Cron/systemd timer integration
- [ ] Transaction deduplication logic (don't re-extract known transactions)
- [ ] Incremental extraction (only new transactions since last pull)
- [ ] Configurable polling frequency per site
- [ ] Rate limit awareness and backoff
- [ ] On-call activation mode (trigger a pull on demand, approve MFA, return to idle)

### Phase 6: Hardening (Target: 1-2 sessions)
- [ ] 1Password CLI credential provider
- [ ] PII sanitization in diagnostic captures
- [ ] Session file encryption at rest
- [ ] Alerting on failure (email, ntfy, or similar)
- [ ] VPS deployment playbook

---

## 12. Dependencies

```
# pyproject.toml or requirements.txt
playwright>=1.40
pyyaml>=6.0
python-dotenv>=1.0
pyotp>=2.9          # For TOTP MFA
click>=8.0          # CLI framework
```

### Playwright Browser Installation

```bash
# Install Playwright and browsers
pip install playwright
playwright install chromium
playwright install-deps  # System dependencies for headless on Linux/WSL
```

---

## 13. Security Considerations

1. **Credentials never touch the LLM.** The LLM is not involved at runtime. Credentials flow from env vars (or 1Password) directly into Playwright's fill() calls.

2. **Diagnostic packages are sanitized.** Account numbers, balances, and other PII are masked before writing to the failures/ directory. Claude Code sees masked data when repairing configs.

3. **Session state files are sensitive.** They contain auth tokens. Gitignored, chmod 600, not backed up to cloud.

4. **The .env file is sensitive.** Gitignored. On VPS, use systemd environment directives or a secrets manager instead.

5. **Vendor map and classification configs are not sensitive.** They contain merchant names and category labels, not account data. Safe to commit to git, share across projects, or export for the budgeting app.

6. **Output CSVs contain transaction data.** They include dates, descriptions, and amounts. Treat as sensitive. Gitignored in the repo; stored in a controlled directory on the local machine or VPS.

7. **Bank terms of service.** Automated access may violate bank ToS. This is a personal tool for personal account management. Use responsible polling frequencies. If a bank blocks or flags the account, stop immediately.

---

## 14. Financial Extension Detail

### Vendor-to-Category Mapping

The 2024 BofA characterization project classified ~712 unique vendors across 1,864 transactions. This mapping is the seed data for the classification engine. It is exported as `extensions/finance/mappings/vendor_map.json`:

```json
{
  "CHIPOTLE": {
    "classification": "Food: Fast Casual",
    "confidence": "high",
    "match_type": "contains"
  },
  "SAFEWAY": {
    "classification": "Food: Groceries",
    "confidence": "high",
    "match_type": "contains"
  },
  "FREEPORT GAS": {
    "classification": null,
    "confidence": "rule",
    "match_type": "contains",
    "rule": "amount_threshold",
    "rule_config": {
      "below_25": "Food: Treats",
      "above_25": "Transportation: Gas/Fuel"
    }
  }
}
```

The classifier tries to match each transaction description against the vendor map using the specified match strategy (contains, starts_with, exact, regex). Unmatched vendors get `Unclassified` and are flagged for manual review. The map grows over time as new vendors are encountered and classified.

### Category Schema (Major:Minor Taxonomy)

Exported as `extensions/finance/mappings/category_schema.json`. Defines the valid classification values and their properties:

```json
{
  "Food: Groceries": {
    "group": "Food",
    "subcategory": "Groceries",
    "necessity": "flexible",
    "description": "Safeway, Raley's, Costco, WinCo, Taylor's Market, Sprouts, Nugget Market"
  },
  "Food: Restaurants": {
    "group": "Food",
    "subcategory": "Restaurants",
    "necessity": "flexible",
    "description": "Sit-down restaurants, delivery, breweries, bars"
  }
}
```

19 groups, 56 subcategories as of the current characterization. The schema is the authoritative list of valid classification values. The classifier rejects any assignment not in the schema.

### Label Schema

Exported as `extensions/finance/mappings/label_schema.json`:

```json
{
  "activity": {
    "values": ["routine", "outing", "trip"],
    "description": "What form did the spend take?"
  },
  "trigger": {
    "values": ["recurring", "planned", "spontaneous", "holiday", "event", "need"],
    "description": "What motivated this spend?"
  },
  "necessity": {
    "values": ["fixed", "flexible", "optional"],
    "description": "Budget relationship: can't cut / can dial up-down / could eliminate"
  },
  "who": {
    "values": ["family", "couple", "self", "spouse", "kids", "gift", "pet"],
    "description": "Primary beneficiary"
  }
}
```

Labels are stored as a single comma-separated `key:value` string in the CSV labels column. Blank values after the colon mean "not yet reviewed," distinct from absent keys. The notes column remains freeform for one-off context (trip names, gift recipients, etc.).

### Classification Rules Engine

Some vendors require conditional logic beyond simple name matching. These rules are in `extensions/finance/rules/classification_rules.json`:

```json
{
  "rules": [
    {
      "name": "gas_station_snacks",
      "description": "Small charges at gas stations are treats, not fuel",
      "match": {"vendor_contains": ["CHEVRON", "SHELL", "ARCO", "76 "]},
      "condition": {"amount_less_than": 10},
      "classification": "Food: Treats",
      "notes": "Gas station snack (amount < $10)"
    },
    {
      "name": "arco_air",
      "description": "ARCO AIR is tire inflation, not fuel",
      "match": {"vendor_contains": ["ARCO AIR"]},
      "classification": "Transportation: Auto Maintenance",
      "priority": 10
    }
  ]
}
```

Rules are evaluated in priority order (lower number = higher priority). The first matching rule wins. Rules take precedence over the vendor map when both match, allowing exceptions to be cleanly expressed.

### Relation to Budgeting App

This framework (base + finance extension) is a standalone data pipeline that feeds the budgeting application. The budgeting app (separate project, architecture TBD) will:

- Import classified CSVs produced by this framework
- Use the same category schema and label vocabulary (shared JSON configs)
- Provide dual-persona UX: power user analytics for Sean, simplified "can I spend this?" interface for Kim
- Consume the vendor map and classification rules to classify transactions that arrive via other channels (manual entry, bank API, email alerts)
- The vendor map and rules JSON files are the integration contract between the scraper and the budgeting app

The scraper framework (base layer) does not need to know about categories or labels. It extracts raw transaction data. The finance extension applies classification. The budgeting app consumes the classified output. Each layer has a clean boundary.
