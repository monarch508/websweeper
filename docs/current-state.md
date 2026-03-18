# Current State

**Last updated:** 2026-03-17
**Version:** 0.1.0
**Branch:** main
**Commit:** fd70a78

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
websweeper finance --help          # Extension
websweeper finance getbofastatements --start-date YYYY-MM [--end-date YYYY-MM]  (stub)
websweeper finance getchasetransactions [--days N]  (stub)
```

---

## What's Not Built Yet

### Phase 2: First Real Bank Site
- [ ] Bank of America checking config (real selectors, real auth flow)
- [ ] Wire `getbofastatements` action to real config + run_site()
- [ ] Test against live BofA site with `--debug` mode
- [ ] MFA push notification handling (currently just a timeout wait)
- [ ] Validate the diagnostic repair workflow against a real failure
- [ ] PDF download extraction mode

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
5. **`src/websweeper/config.py`** — Pydantic models define the config contract
6. **`src/websweeper/runner.py`** — Orchestrator shows the full execution flow
7. **`tests/test_integration.py`** — Integration tests show how everything connects
