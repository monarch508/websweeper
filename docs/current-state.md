# Current State

**Last updated:** 2026-05-16
**Version:** 0.1.0
**Branch:** main (11 commits ahead of `origin/main`, all local, no push)

---

## Recent Activity (2026-05-14 to 2026-05-16)

Three things happened across this window:

1. **Email-MFA path proven and shipped.** D21 selected email-MFA via the Gmail API for unattended BofA logins. The implementation now runs end-to-end: login, click "Get code a different way", trigger email, poll Gmail (resilient ANY/ALL query with 5-min trigger window), fill the code, handle BofA's ATM-card-and-PIN step-up, submit. First successful live run extracted 50 transaction rows on 2026-05-16.
2. **Watch mode removed.** D19 watch mode was preserved through D21 (shelved as a feature). D22 promotes that to deletion: with email-MFA reliable, scheduled batch runs cover the use case and the persistent-poller approach has no caller. `watcher.py`, `watch`, `watch-bofa`, and `keepalive_url` are all gone.
3. **D22 schema additions for new operations.** Pydantic models for `statements` and `transactions` blocks landed with 9 new unit tests. Operation-first CLI shape (`list-statements <config>`, `pull-transactions <config> --days-back N`, etc.) is decided. Base framework implementations and CLI actions still to do.

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

**92 tests, all passing** (as of 2026-05-16)

```
tests/test_config.py          — 28 tests (config loading, Pydantic validation, D22 schema)
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
websweeper --help                                       # Base CLI
websweeper run <config> [--debug] [--dry-run] [--force-auth]
websweeper validate <config>
websweeper gmail-auth                                   # One-time OAuth consent for email-MFA
websweeper finance --help                               # Extension
websweeper finance getbofastatements [--debug] [--dry-run] [--force-auth]   # legacy, to be retired per D22
websweeper finance getbofastatementpdfs [--debug] [--force-auth]            # legacy, to be retired per D22
websweeper finance getchasetransactions [--days N]                          # stub, to be retired per D22
```

Operation-first commands (D22) still to be implemented: `list-statements <config>`, `list-last-statement <config>`, `pull-statement <config> <statement-id>`, `pull-last-statement <config>`, `pull-transactions <config> [--days-back N]`.

---

## Phase 2 Progress: BofA Checking (In Progress)

### Completed
- [x] BofA checking config with real selectors (`extensions/finance/configs/bofa_checking.yaml`)
- [x] Login flow: User ID (`#oid`), Password (`#pass`), Log in button (`#secure-signin-submit`)
- [x] **Email-MFA flow (D21):** click "Get code a different way" (role-targeted link) → click Next → poll Gmail API → fill code (`#ahAuthcodeValidateOTP`) → handle ATM-card-and-PIN step-up (radio + `#ahAuthcodeValidatePIN`) → submit (`#ah-authcode-validate-continue-btn`)
- [x] Gmail API runtime path: `gmail_auth.py` + `gmail_reader.py`; OAuth refresh token persisted at `.credentials/gmail_token.json` (gitignored, chmod 600); polling uses ANY-first sender-domain query then ALL-strict subject and body match locally, within a 5-minute trigger window
- [x] Session reuse verified — subsequent headless runs skip login/MFA entirely
- [x] Transaction extraction working: 50 rows extracted from `#txn-activity-table` with `tbody tr.activity-row` rows
- [x] CSV output with date, description, type, amount, account, source columns
- [x] `goto` action added to executor for direct URL navigation
- [x] Diagnostic repair workflow validated (broken selector → screenshot + a11y tree + error log captured)
- [x] Auto re-auth — detects stale server-side sessions, clears cookies, re-authenticates
- [x] PDF statement download — JS event dispatch triggers BofA's Vue framework, Playwright captures download
- [x] `pdf_download` extraction mode added to base framework with `PdfDownloadConfig`
- [x] Watch mode **removed** (D22): the email-MFA path makes scheduled batch runs viable, so the persistent-poller approach has no caller.
- [x] **D22 schema layer:** `StatementsBlock` and `TransactionsBlock` Pydantic models added to `config.py` with 9 new unit tests. Operation-first CLI naming committed in `docs/decisions.md`.

### Auth strategy (D20 + D21, 2026-05-14; implemented 2026-05-16)

Plaid and other financial aggregators are explicitly off the table. The DIY pursue-list from D20 was investigated live the same day; results are recorded in D21 and the implementation landed two days later:

1. Device-trust cookie + session reuse: **blocked.** BofA's account-level "We will verify your identity every time you log in" toggle is ON, which makes BofA require MFA regardless of device recognition. Device-trust cookies refresh correctly; the account setting overrides them.
2. TOTP authenticator-app MFA: **not offered** on BofA consumer accounts. Confirmed via Security Center and 2FA management captures; no method-management UI exists.
3. Email-code retrieval via Gmail API: **implemented and proven live (2026-05-16).** On the MFA method-select page, the runner clicks "Get code a different way" (role-targeted link to disambiguate from hidden help-panel matches), clicks Next, polls Gmail with a permissive sender-domain query plus a 5-minute trigger window, applies the strict subject and body regex locally, fills the code, handles BofA's ATM-card-and-PIN step-up, and submits. Two BofA-specific gotchas surfaced during integration and are now documented: sender variance (codes arrive from `onlinebanking_ealerts@bankofamerica.com` and `onlinebanking@ealerts.bankofamerica.com`, both legitimate, so filter on the parent domain), and the step-up gate on the email path (requires picking an ATM card via radio and filling its PIN at `#ahAuthcodeValidatePIN` before submit).

### Remaining (still open after 2026-05-16)
- [ ] Date parsing for "Processing" entries (currently passed through as-is, not transformed)
- [ ] D22 implementation work: base framework operations + operation-first CLI actions + BofA config migration to the new `statements:` / `transactions:` blocks (see "What's Not Built Yet" below)

### Key Findings
- **BofA MFA path is email** (D21), not SMS. The "Get code a different way" link toggles delivery. BofA dispatches MFA codes from at least two sender addresses, so the Gmail filter is on the parent domain plus a subject substring.
- **Email path triggers a step-up gate**: after filling the code, BofA shows an ATM-card radio plus a PIN field (`#ahAuthcodeValidatePIN`) before Submit will accept.
- **Session TTL is shorter than expected** — BofA sessions expire in practice well before the configured 12h. The `storageState` cookies become invalid, and the site redirects to the public homepage with `SMAUTHReason=0`. The runner's auto-re-auth detects this and re-runs full auth.
- **Transaction table** is `#txn-activity-table` with class `activity-row` for data rows. Columns: date-cell, desc-cell (.desc-text for clean text), type-cell, amount-cell, avail-balance-cell.
- **Pending transactions** show "Processing" in the posting-date column and carry an "amount may change" note in the description.
- **Custom-date filter excludes pending.** BofA's date filter is a posting-date filter; rows without a posting date (still pending) are stripped. Two-step scrape required: pending from the unfiltered view, posted from the filtered view.
- **Custom-date filter UI:** filter panel toggle is `a:has-text('Filter')`; timeframe select is `#search-filter-timeframe-select` with value `custom-date`; date inputs are `#search-from-date-input` and `#search-to-date-input` in MM/DD/YYYY; Apply button is `button:has-text('Apply')`. URL params for date range are stripped by BofA, so UI interaction is the only path.
- **Statements page:** year dropdown is `#yearDropDown` with options 2019-2026 (eight years available); default view shows only the most recent statement; each download link's text contains the month name (parse with `for (\w+) Statement`); `href="#"` so download requires JS event dispatch (D18 pattern).
- **Navigation requires `goto` action** — with session reuse, the login_url loads the public homepage, not the accounts page. Must navigate to `secure.bankofamerica.com/myaccounts/brain/redirect.go?source=overview` explicitly.
- **Account link selector**: `a[name='DDA_details']` for checking account on the overview page. Statements page reached via `#tab-statementsdocs` from the checking detail page.

## What's Not Built Yet

### D22 Implementation Work (in flight)
- [ ] Base framework operations: `list_statements`, `list_last_statement`, `pull_statement`, `pull_last_statement`, `pull_transactions` (likely in a new `statements.py` and extensions to `runner.py`)
- [ ] Operation-first CLI actions in `extensions/finance/actions.py`
- [ ] Migrate `bofa_checking.yaml` to add the new `statements:` and `transactions:` blocks
- [ ] Retire `bofa_statements.yaml` (its scope is absorbed into `bofa_checking.yaml`'s new `statements:` block)
- [ ] Retire legacy actions: `getbofastatements`, `getbofastatementpdfs`, `getchasetransactions` (stub)
- [ ] Tests for each new operation (fixture-driven, no live calls)

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
8. **`src/websweeper/gmail_auth.py` / `gmail_reader.py`** — Email-MFA runtime path (consent flow + Gmail polling)
9. **`tests/test_integration.py`** — Integration tests show how everything connects
