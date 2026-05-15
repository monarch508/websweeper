# Current State

**Last updated:** 2026-05-14
**Version:** 0.1.0
**Branch:** main

---

## Uncommitted Work in Progress

Watch mode is implemented but **not yet committed** and **not yet tested against a live site**. Working tree as of 2026-05-14:

- New: `src/websweeper/watcher.py` (persistent-browser polling loop with keepalive)
- New: `CLAUDE.md` (this fleshed-out version, replacing the external scaffold)
- Modified: `src/websweeper/runner.py` (extracted `run_extraction()` for reuse by the watcher)
- Modified: `src/websweeper/config.py` (`keepalive_url` field on `SessionConfig`)
- Modified: `src/websweeper/cli.py` (`watch` command + `_parse_duration` helper)
- Modified: `extensions/finance/actions.py` (`watch-bofa` action)
- Modified: `extensions/finance/configs/bofa_checking.yaml` (`keepalive_url` set)

83 tests still pass with these changes. Next step is a live watch-mode run against BofA.

---

## What's Built (Phase 1 — Complete)

Phase 1 delivered the full base framework through 8 iterative MVPs:

| MVP | Capability | Status |
|---|---|---|
| 0 | Playwright proof of life (google.com screenshot in WSL2) | Done |
| 1 | Step executor (fill, click, select, wait + 5 target types) | Done |
| 2 | YAML config loading with Pydantic validation | Done |
| 3 | Credential resolution from env vars + auth flow | Done |
| 4 | Diagnostic capture on failure (screenshot, a11y tree, error log) | Done |
| 5 | Table extraction + data transforms + CSV output | Done |
| 6 | Session persistence (storageState, TTL, chmod 600) | Done |
| 7 | Click CLI + finance extension registration via entry points | Done |

### Test Suite

**83 tests, all passing** (as of 2026-03-17)

```
tests/test_config.py          — 19 tests (config loading, Pydantic validation)
tests/test_credentials.py     — 6 tests (env var resolution, error cases)
tests/test_executor.py         — 18 tests (target resolution, step execution, mocks)
tests/test_session.py          — 6 tests (TTL, file management)
tests/test_transforms.py      — 17 tests (parse_date, parse_currency)
tests/test_output.py           — 5 tests (CSV writing, static fields, column ordering)
tests/test_diagnostics.py     — 1 test (full diagnostic package capture)
tests/test_integration.py     — 5 tests (end-to-end login → extract → CSV)
```

Integration tests run against `tests/fixtures/test_page.html` — a local HTML page with a login form and transactions table containing 4 known rows.

### Modules

| Module | Purpose | Lines |
|---|---|---|
| `config.py` | Pydantic models, YAML loader, validation | ~160 |
| `executor.py` | Step execution, target resolution, input templating | ~120 |
| `runner.py` | Orchestrator: auth → navigate → extract → output | ~110 |
| `credentials.py` | Env var credential resolution | ~55 |
| `session.py` | storageState save/load, TTL checking | ~80 |
| `diagnostics.py` | Failure capture (screenshot, a11y, error, context) | ~110 |
| `extractors/table.py` | HTML table extraction with transforms | ~60 |
| `transforms.py` | parse_date, parse_currency, strip, lowercase | ~100 |
| `output.py` | CSV writer with template paths and static fields | ~60 |
| `cli.py` | Click CLI, extension discovery | ~65 |
| `utils.py` | ensure_directory, timestamp_slug, iso_date_today | ~20 |

### CLI Commands Available

```
websweeper --help                  # Base CLI
websweeper run <config> [--debug] [--dry-run] [--force-auth]
websweeper validate <config>
websweeper watch <config> [--interval 20m] [--keepalive 3m] [--debug]
websweeper finance --help          # Extension
websweeper finance getbofastatements [--debug] [--dry-run] [--force-auth]
websweeper finance getbofastatementpdfs [--debug] [--force-auth]
websweeper finance watch-bofa [--interval 20m] [--keepalive 3m] [--debug]
websweeper finance getchasetransactions [--days N]  (stub)
```

---

## Phase 2 Progress: BofA Checking (In Progress)

### Completed
- [x] BofA checking config with real selectors (`extensions/finance/configs/bofa_checking.yaml`)
- [x] Login flow: User ID (`#oid`), Password (`#pass`), Log in button (`#secure-signin-submit`)
- [x] SMS MFA flow: click Next (`#ah-authcode-select-continue-btn`) → enter code (`#ahAuthcodeValidateOTP`) → remember device (`#rememberDevice`) → submit (`#ah-authcode-validate-continue-btn`)
- [x] Interactive MFA: code entered via stdin (terminal) or browser window (headed mode)
- [x] Session reuse verified — subsequent headless runs skip login/MFA entirely
- [x] `getbofastatements` action wired to real config + `run_site()`
- [x] Transaction extraction working: 50 rows extracted from `#txn-activity-table` with `tbody tr.activity-row` rows
- [x] CSV output with date, description, type, amount, account, source columns
- [x] `goto` action added to executor for direct URL navigation
- [x] Diagnostic repair workflow validated (broken selector → screenshot + a11y tree + error log captured)
- [x] Auto re-auth — detects stale server-side sessions, clears cookies, re-authenticates
- [x] PDF statement download — JS event dispatch triggers BofA's Vue framework, Playwright captures download
- [x] `getbofastatementpdfs` action — downloads statement PDFs (eStmt_2026-03-09.pdf, 281KB, 14 pages)
- [x] `pdf_download` extraction mode added to base framework with `PdfDownloadConfig`
- [x] Watch mode — persistent browser with keepalive polling (`watcher.py`, `watch`/`watch-bofa` commands). Shelved as a feature per D21; see "Auth strategy" below.

### Auth strategy (D20 + D21, 2026-05-14)

Plaid and other financial aggregators are explicitly off the table. The DIY pursue-list from D20 was investigated live the same day; results are recorded in D21:

1. Device-trust cookie + session reuse: **blocked.** BofA's account-level "We will verify your identity every time you log in" toggle is ON, which makes BofA require MFA regardless of device recognition. Device-trust cookies refresh correctly; the account setting overrides them.
2. TOTP authenticator-app MFA: **not offered** on BofA consumer accounts. Confirmed via Security Center and 2FA management captures; no method-management UI exists, keyword scan found no TOTP/authenticator references.
3. Email-code retrieval via Gmail MCP: **selected.** BofA's "Get code a different way" link on the MFA method-select page switches delivery from SMS to email (monarch508@gmail.com). Gmail MCP is already authenticated and is scopable to a BofA sender filter.

The path forward is to implement an email-MFA flow in the framework: on the method-select page click "Get code a different way" before Next, wait for the BofA MFA email via Gmail MCP, parse the 6-digit code from the body, type and submit. This makes scheduled batch runs fully unattended without weakening any account security setting.

### Remaining
- [ ] Implement email-MFA mode in the config schema and executor (D21)
- [ ] Wire Gmail MCP read with sender filter and code regex into the MFA flow
- [ ] Live test of the email-MFA path end-to-end against BofA
- [ ] Date parsing for "Processing" entries (currently passed through as-is, not transformed)

### Key Findings
- **BofA MFA is SMS-based**, not push. The flow is: login → "Get authorization code" page → click Next → enter code → remember device → submit
- **"Remember this device"** reduces MFA frequency but doesn't eliminate it
- **Session TTL is shorter than expected** — BofA sessions expire in practice well before the configured 12h. The `storageState` cookies become invalid, and the site redirects to the public homepage with `SMAUTHReason=0`
- **Transaction table** is `#txn-activity-table` with class `activity-row` for data rows. Columns: date-cell, desc-cell (.desc-text for clean text), type-cell, amount-cell, avail-balance-cell
- **Pending transactions** show "Processing" instead of a date
- **Navigation requires `goto` action** — with session reuse, the login_url loads the public homepage, not the accounts page. Must navigate to `secure.bankofamerica.com/myaccounts/brain/redirect.go?source=overview` explicitly
- **Account link selector**: `a[name='DDA_details']` for checking account on the overview page

## What's Not Built Yet

### Phase 2 Remaining: Hardening
- [ ] Statement download by date range (year dropdown + expandable categories on Statements page)
- [ ] Live verification of watch mode's auto re-auth path (the code path exists in `watcher._ensure_authenticated`; not yet exercised against a real expired session)

### Phase 3: Financial Extension — Classification
- [ ] Vendor-to-category mapping engine
- [ ] Category schema (Major:Minor taxonomy, 19 groups, 56 subcategories)
- [ ] Label schema (activity, trigger, necessity, who)
- [ ] Classification rules engine (amount thresholds, conditional logic)
- [ ] Finance-specific CSV output with classification + labels columns
- [ ] Import seed data from 2024 BofA characterization (~712 vendors)

### Phase 4: Multi-Site Expansion
- [ ] Chase, Citi (421, 431), Target RedCard, Best Buy/Citi, BofA Savings configs
- [ ] Generalize table extraction across different bank DOM structures
- [ ] `run-all` command
- [ ] `status` command (run history tracking)

### Phase 5: Scheduling and Polling
- [ ] Cron/systemd timer integration
- [ ] Transaction deduplication
- [ ] Incremental extraction (only new since last pull)
- [ ] Rate limiting and backoff
- [ ] On-call activation mode

### Phase 6: Hardening
- [ ] 1Password CLI credential provider
- [ ] PII sanitization in diagnostic captures
- [ ] Session file encryption at rest
- [ ] Failure alerting (email, ntfy)
- [ ] VPS deployment playbook

### Open Questions
- [ ] `page_scrape` extraction mode — what is the use case? Flagged for clarification.

---

## Environment

- **Dev machine:** WSL2 Ubuntu on Windows 11 (HP OMEN, i7-14650HX, 32GB RAM)
- **WSLg:** Working — headed Playwright browser windows display on Windows desktop
- **Python:** 3.12.3
- **Playwright:** 1.58.0
- **Pydantic:** 2.12.5
- **Package manager:** uv
- **Build backend:** hatchling
- **Production target:** Linux VPS (same codebase, no modifications)

---

## Key Files for Resuming Work

If starting a new session, these files provide full context:

1. **`PROJECT_SPEC.md`** — Full project specification (architecture, config schema, roadmap)
2. **`docs/decisions.md`** — Why things are the way they are
3. **`docs/current-state.md`** — This file (what's done, what's next)
4. **`pyproject.toml`** — Dependencies, entry points, build config
5. **`CLAUDE.md`** — Conventions, config schema, credential/session/diagnostic patterns
6. **`src/websweeper/config.py`** — Pydantic models define the config contract
7. **`src/websweeper/runner.py`** — Orchestrator shows the full execution flow
8. **`src/websweeper/watcher.py`** — Watch-mode polling loop (uncommitted)
9. **`tests/test_integration.py`** — Integration tests show how everything connects
