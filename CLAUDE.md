# CLAUDE.md (websweeper)

> Originally scaffolded 2026-05-12 from a Windows-side session; fleshed out 2026-05-14 from a session running inside `/home/monarch508/dev/websweeper/`.

## What this is

Config-driven Playwright automation framework with a hybrid AI maintenance model. Two intentional layers:

1. **Base framework (`src/websweeper/`)** — generic, reusable web automation. Knows nothing about banks, budgets, or financial data. Provides config loading, credential injection, Playwright step execution, session persistence, diagnostic capture, table/PDF extraction, CSV output, and a CLI.
2. **Finance extension (`extensions/finance/`)** — applies the base to one scenario: downloading bank/credit-card statement PDFs and extracting transactions. Output feeds the `StatementProcessing` project (Windows side), which extracts transactions to Excel.

The separation is the point. The base framework is the reusable asset; the finance extension is one use case. Future extensions (utility bills, insurance docs, price comparisons) follow the same pattern without touching the base.

**Hybrid AI model:** no LLM at runtime. Playwright runs deterministically (fast, zero tokens). Claude Code is invoked only at *maintenance* time, when a site changes its DOM and a config breaks. The diagnostic capture system (`failures/`) provides everything needed for repair.

## Targets

- **Dev:** WSL2 Ubuntu on Windows 11. Python 3.12, Playwright 1.58, Pydantic 2.x, package manager `uv`, build backend hatchling.
- **Production:** Linux VPS, same codebase, no modifications.

## Layering conventions

- Base framework code lives in `src/websweeper/`. It must **never** import from or reference `extensions/`. Domain logic does not leak into the framework.
- Extension code lives in `extensions/<name>/`. Extensions import freely from `websweeper.*`.
- An extension is a directory with `actions.py` (a Click group) and a `configs/` directory of YAML site definitions. It registers its CLI group via a `pyproject.toml` entry point under `[project.entry-points."websweeper.extensions"]`.
- New capability that any site could use → base framework. New site, bank, or workflow → a config (and maybe an action) in an extension. Prefer config over code: a new bank should ideally be just a new YAML file plus a thin action wrapper.

## Config schema

Each target site is one YAML file validated by `SiteConfig` in `src/websweeper/config.py` (Pydantic v2). Sections:

| Section | Purpose |
|---|---|
| `site` | `name`, `id`, `login_url`, `base_url` |
| `credentials` | `provider: env` + `env.username_var` / `env.password_var` (names of env vars, never values) |
| `auth` | `steps` (login), `mfa` (type + interactive code-entry targets), `verify` (post-auth check steps) |
| `navigation` | `steps` to reach the target page after login |
| `extraction` | `mode: table` or `mode: pdf_download`, with the matching sub-config |
| `output` | CSV `directory`, `filename_template`, `columns`, `static_fields` |
| `session` | `storage_state_path`, `reuse_session`, `session_ttl_hours`, `keepalive_url` (watch mode) |
| `diagnostics` | screenshot / a11y capture flags, `output_directory` |

**Step actions:** `fill`, `click`, `select`, `wait`, `wait_for_selector`, `goto`. **Target types:** `id`, `css`, `text`, `role`, `placeholder`. Pydantic `model_validator`s enforce cross-field rules (e.g. `fill` requires both a target and an input; `extraction.mode: table` requires a `table` block).

Path templates resolve `{site_id}`, `{date_pulled}`, etc. via `resolve_template_vars`.

## Credential handling

- Provider is `env` only (Phase 6 may add a 1Password CLI provider). The config names two env vars; `src/websweeper/credentials.py` resolves them at runtime.
- Credentials flow env var → Playwright directly. They never touch an LLM and never appear in a committed file.
- `.env` is gitignored; `.env.example` holds the variable *names* only. **Never put a real credential in any committed file** (configs, docs, commit messages, test fixtures). Reference them generically.

## Session persistence

- After successful auth, Playwright's `storageState` (cookies + localStorage) is saved to `sessions/{site_id}_state.json`, chmod 600, gitignored.
- On the next run, if `reuse_session` is true and the file is within `session_ttl_hours`, login/MFA is skipped.
- File-based TTL is not enough for some sites: the runner also live-checks the session by testing the first navigation step against the `auth.verify` selectors. If the server expired the session early, it clears the file, opens a fresh context, and runs full auth (auto re-auth).

## Diagnostic capture (self-healing)

On failure the runner writes a diagnostic package to `failures/{site_id}/{timestamp}/`: `screenshot.png`, `accessibility_tree.txt`, `error.log`, a copy of the config, and `step_context.json`. To repair a broken config, point Claude Code at that directory: it reads the context, compares the a11y tree to the config selectors, and updates the YAML.

## Finance extension specifics

- Configs in `extensions/finance/configs/` — currently `bofa_checking.yaml` (transactions) and `bofa_statements.yaml` (PDF downloads).
- Actions in `extensions/finance/actions.py`, exposed as `websweeper finance <action>`.
- Extracted CSVs land in `output/{site_id}/`; downloaded PDFs in `output/{site_id}/statements/`. All of `output/`, `sessions/`, `failures/` are gitignored.
- BofA specifics worth knowing: MFA is SMS (not push), so first auth needs an interactive code entry; server-side sessions expire in ~5-10 min idle; the `login_url` loads the public homepage on session reuse, so a `goto` step to the accounts-overview URL is required; statement-download links are Vue-driven (`data-v-trigger`) and need a JS `dispatchEvent`, not a normal click.

## Watch mode (in progress, uncommitted as of 2026-05-14)

`src/websweeper/watcher.py` keeps one browser alive, authenticates once, and polls extraction on an interval, sending keepalive pings (`session.keepalive_url`) between cycles to outlast short server-side session windows. Exposed as `websweeper watch <config>` and `websweeper finance watch-bofa`. `run_extraction()` was split out of `run_site()` in `runner.py` so both the one-off runner and the watcher share the same extraction core. Implemented and unit-test-clean, but not yet run against a live site.

## Working with this codebase

- **Build in thin vertical slices, not horizontal layers.** Each change should produce something runnable and testable. This is a standing preference, validated through the MVP 0-7 build of Phase 1.
- **Tests are part of the architecture.** Every module has tests; integration tests run the full pipeline against `tests/fixtures/test_page.html` (no external calls). Run `uv run pytest` (currently 83 passing). Live bank sites are expensive to fail against (lockouts, rate limits), so validate offline first.
- Commands: `uv sync --extra dev`, `uv run playwright install chromium`, `uv run pytest`, `uv run websweeper ...`.
- Commit messages: one-line imperative, no AI attribution / co-author trailers.

## See also

- `PROJECT_SPEC.md` — full spec authored at handoff (March 2026).
- `README.md` — README-level summary, project structure, self-healing workflow.
- `docs/current-state.md` — what's done / in progress / next.
- `docs/decisions.md` — architectural decisions D01-D19 with rationale.
- `docs/user-guide.md` — usage walkthrough.
- Downstream sibling: `StatementProcessing` (Windows) consumes the PDFs this project downloads.
