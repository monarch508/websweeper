# Decision Log

Architectural and design decisions made during development, with rationale.

---

## 2026-03-17 — Project Kickoff & Phase 1 Implementation

### D01: Two-Layer Architecture (Base + Extensions)

**Decision:** Separate the project into a generic base framework (`src/websweeper/`) and domain-specific extensions (`extensions/`).

**Rationale:** The base framework (config loading, Playwright execution, credential injection, session management, diagnostics) is reusable for any authenticated website. The finance extension applies it to bank portals. Future extensions (utility bills, insurance docs, etc.) can follow the same pattern without modifying the base.

**Trade-off:** Slightly more complex project structure, but clean separation prevents domain logic from leaking into the framework.

---

### D02: Hybrid AI Maintenance Model

**Decision:** No LLM at runtime. Use Playwright deterministically for all execution. AI (Claude Code) is used only at maintenance time when selectors break.

**Rationale:** LLM-in-the-loop automation (e.g., browser-use) is resilient but slow and expensive in tokens. Playwright scripts are fast and free when they work. They only break when a site changes its DOM — which is infrequent. The diagnostic capture system provides everything Claude Code needs to identify and fix the break.

**Trade-off:** Manual intervention required when sites change, but this is infrequent and the diagnostic package makes repairs quick.

---

### D03: Python Tooling — uv

**Decision:** Use `uv` as the Python package manager and virtual environment tool.

**Rationale:** Single binary, installs with one curl command on any Linux system (WSL2 and VPS). Replaces pip + venv + pip-tools. Fast dependency resolution. Works with standard `pyproject.toml` — no lock-in, pip still works as a fallback.

**Alternative considered:** pip + venv (familiar, zero learning curve). Chose uv for VPS deployability and developer experience.

---

### D04: src Layout

**Decision:** Use `src/websweeper/` (src layout) instead of `websweeper/websweeper/` (flat layout).

**Rationale:** Modern Python packaging standard. Prevents accidentally importing the uninstalled package during development. Works correctly with `uv`, hatch, and pytest. Recommended by PyPA.

---

### D05: Pydantic v2 for Config Schema

**Decision:** Use Pydantic BaseModel classes instead of stdlib dataclasses for config types.

**Rationale:** Rich validation with `Literal` types for enums, `model_validator` for cross-field rules (e.g., "fill requires target + input"), clear error messages, automatic type coercion from YAML. Config validation is the most important correctness check in the framework — Pydantic makes bad configs fail fast with helpful messages.

**Alternative considered:** stdlib dataclasses (no dependency). Chose Pydantic because config validation is foundational and worth the dependency.

---

### D06: Action-Based CLI

**Decision:** Users invoke named actions (`websweeper finance getbofastatements --start-date 2026-01`) rather than generic config paths (`websweeper run configs/bofa.yaml`).

**Rationale:** Actions are the user-facing concept. They have typed arguments (date ranges, etc.), sensible defaults, and map to specific workflows. The generic `run` command still exists for ad-hoc config execution, but the action pattern is the primary interface.

**Implementation:** Click command groups. The base CLI provides `run` and `validate`. Extensions register additional groups via `pyproject.toml` entry points. The finance extension adds the `finance` group with bank-specific actions.

---

### D07: Extension Discovery via Entry Points

**Decision:** Extensions register CLI groups via `pyproject.toml` entry points (`websweeper.extensions` group), discovered at CLI startup with `importlib.metadata.entry_points()`.

**Rationale:** Standard Python plugin mechanism. No magic directory scanning, no import hacks. Works after `pip install -e .` or `uv sync`. Any Python package can register as a WebSweeper extension by declaring the entry point.

---

### D08: Iterative MVP Build Order

**Decision:** Build in thin vertical slices (MVP 0-7), each producing a working, testable milestone. Not horizontal layers built sequentially.

**Rationale:** Validates the pipeline incrementally. MVP 0 proved Playwright works in WSL2 before writing any framework code. Each subsequent MVP added one capability and proved it end-to-end before moving on. Issues (like Google's CAPTCHA blocking automated search, or Playwright's deprecated accessibility API) were caught and fixed immediately.

**Lesson learned:** The strict-mode selector conflict in integration tests (text "Transactions" matching both a link and a heading) was caught in MVP 3 and fixed immediately — would have been much harder to debug if found after building all modules.

---

### D09: Tests as Part of Base Architecture

**Decision:** Every module has tests from day one. Integration tests run the full pipeline against a local HTML test page.

**Rationale:** The framework will be pointed at live bank sites where failures are expensive (account lockouts, rate limiting). Every component must be validated offline first. The local test page (`tests/fixtures/test_page.html`) simulates login, navigation, and table extraction without hitting any external service.

**Test breakdown (83 tests):**
- Config loading and Pydantic validation: 19 tests
- Credential resolution: 6 tests
- Step executor (mock-based): 18 tests
- Session management: 6 tests
- Data transforms: 17 tests
- CSV output: 5 tests
- Diagnostics (integration): 1 test
- Full pipeline (integration): 5 tests
- Remaining: 6 tests across other modules

---

### D10: Extraction-Only Scope for Phase 1

**Decision:** Focus on extracting statements/transactions from bank portals. No classification, taxonomy, labels, vendor mapping, or budgeting app integration.

**Rationale:** Get the core automation pipeline working end-to-end before layering on data processing. The classification engine (vendor-to-category mapping, rules, labels) is a separate concern that can be built independently once raw data extraction is reliable.

---

### D11: Session Persistence with storageState

**Decision:** Save Playwright's `storageState` (cookies + localStorage) after successful auth. Reuse on subsequent runs within TTL.

**Rationale:** Bank logins require MFA, which requires manual phone interaction. Session reuse skips login entirely when the session is still valid, enabling unattended runs within the TTL window.

**Security:** Session files are chmod 600 (owner-only) and gitignored. They contain auth tokens and must not leave the machine.

---

### D12: Deferred Decisions

The following were explicitly deferred:

| Item | Deferred To | Reason |
|---|---|---|
| `page_scrape` extraction mode | Needs clarification | Purpose unclear from original spec |
| PDF download extraction | Phase 2 | Needs real bank testing |
| 1Password credential provider | Phase 6 | Env vars sufficient for now |
| PII sanitization in diagnostics | Phase 6 | Not needed until sharing diagnostic packages |
| Session file encryption | Phase 6 | chmod 600 sufficient for personal machine |
| Transaction deduplication | Phase 5 | Not needed until polling is implemented |

---

## 2026-03-17 — Phase 2: BofA Integration

### D13: SMS MFA with Interactive Code Entry

**Decision:** Support interactive MFA code entry via stdin (terminal mode) or browser window (headed mode). The runner detects whether stdin is available and falls back to waiting for the user to interact with the headed browser directly.

**Rationale:** BofA uses SMS-based MFA, not push notifications as originally assumed. The code must be entered by the user. In terminal contexts (direct CLI invocation), `input()` prompts for the code. When stdin is unavailable (e.g., running through a tool or non-interactive shell), the user enters the code in the visible browser window and clicks Submit themselves.

**Trade-off:** Not fully automated, but combined with "remember this device" and session persistence, MFA is only needed on first login or after session expiry.

---

### D14: `goto` Action for Direct URL Navigation

**Decision:** Added `goto` as a new step action type that navigates the page to a URL.

**Rationale:** With session reuse, loading the `login_url` (public homepage) doesn't redirect to the authenticated accounts page. The runner needs to navigate directly to `secure.bankofamerica.com/myaccounts/brain/redirect.go?source=overview`. A `goto` action allows this without special-casing in the runner.

---

### D15: BofA Session TTL Reality

**Decision:** Set BofA session TTL to 12 hours in config, but documented that actual BofA session validity is shorter and unpredictable.

**Rationale:** BofA's server-side session expiry is not under our control. The `session_ttl_hours` config controls when we proactively re-auth, but BofA may invalidate the session earlier. The runner already handles this gracefully — if the session cookies are stale, the page redirects to the public homepage, auth verification fails, and the diagnostic package is captured. Future improvement: detect the redirect and trigger re-auth automatically instead of failing.

---

### D16: CSS Selectors for BofA Transaction Table

**Decision:** Use CSS class-based selectors for the BofA transaction table (`td.date-cell`, `td.desc-cell .desc-text`, `td.amount-cell`) rather than positional or text-based selectors.

**Rationale:** The BofA transaction table has stable class names on its cells. The `.desc-text` sub-selector within `desc-cell` extracts clean description text without extra metadata. These are more reliable than positional selectors (nth-child) which would break if columns are reordered.

---

### D17: Auto Re-Auth on Stale Session

**Decision:** The runner detects server-side session expiry by testing the first navigation step and checking auth verify selectors. If stale, it clears the session file, creates a fresh browser context, and runs full auth.

**Rationale:** BofA expires sessions in ~5-10 minutes idle, much shorter than the configured TTL. Relying only on file-based TTL is insufficient. The runner now proactively tests whether saved cookies are still valid before attempting extraction, and falls back to full auth when they're not.

---

### D18: PDF Downloads via JS Event Dispatch

**Decision:** Use `element.dispatchEvent(new Event('click', { bubbles: true }))` to trigger PDF downloads instead of Playwright's `click()` or `click(force=True)`.

**Rationale:** BofA's statement download links use Vue.js `data-v-trigger` attributes rather than standard `href` or `onclick` handlers. Playwright's `click()` failed because an overlapping card UI element intercepted pointer events. `click(force=True)` bypassed the overlay but didn't trigger Vue's event system. JavaScript `dispatchEvent` triggers the Vue handler which initiates the actual download via XHR, and Playwright's `download` event captures the resulting file.

---

### D19: Watch Mode over Daemon Architecture

**Decision:** Implement session keepalive as a "watch" mode (single long-running process with a polling loop) rather than a daemon with IPC.

**Rationale:** The immediate problem is BofA's ~5-10 minute session timeout killing automated polling. A watch mode solves this by keeping the browser alive and sending keepalive pings between extraction cycles. A full daemon with socket/HTTP IPC would add significant complexity (state management, error handling, client/server protocol) for no immediate benefit — there's currently one user running one site. Watch mode can run in tmux, screen, or as a systemd service. Can upgrade to daemon architecture later if multi-client or multi-site concurrent access is needed.

---

## 2026-05-14 — Auth Strategy Re-Examination

### D20: DIY Auth Techniques Only, No Aggregator (Plaid Rejected)

**Status:** Re-affirming a recurring discussion. This conversation has happened before across sessions; this entry exists so it does not need to happen again.

**Decision:** Pursue seamless BofA login via DIY techniques in this order:

1. Verify that the device-trust cookie captured in `storageState` provides MFA-free fresh logins within the trust window.
2. Check whether BofA offers TOTP authenticator-app MFA. The config schema already supports `mfa.type: totp`, so adopting it would make MFA fully unattended without code changes.
3. Fall back to email-code retrieval (via the Gmail MCP) if 1 and 2 fail and an unattended fresh login is required.

Financial aggregators (Plaid, Yodlee, MX, Finicity) are **explicitly off the table.**

**Rationale, Plaid rejected:**

1. Prior personal experience with unreliable transaction polling.
2. Prior personal experience with the connection to BofA repeatedly breaking and requiring re-authorization.
3. Cost: Plaid is B2B-priced and not viable for individual use.
4. Third-party API dependency contradicts the project's self-hosted, no-LLM-at-runtime philosophy.

**Evidence basis (not just preference):** Reasons 1 and 2 align with documented Plaid + BofA reliability issues following the 2022-2023 OAuth migration, when retail-side BofA users widely reported intermittent transaction sync failures, missed or duplicated entries, and connections that required re-authorization every few weeks or after BofA security events. The "Plaid is seamless" framing is accurate on the happy path; for BofA specifically the happy path is not the common path. So this rejection is grounded in both lived experience and a broader documented track record, not in taste.

**Rationale, reframe:**

The recurring framing was "watch mode solves BofA's 5-10 min session timeout." On closer inspection, session timeout only matters if you poll more often than the session lives. For a budgeting pipeline (statements monthly, transactions at most daily), the natural model is a scheduled batch run, not a persistent poller. The real friction is MFA on every fresh login, not session expiry. Banks split that into two cookies: a short session cookie and a long device-trust cookie. If `storageState` captures the device-trust cookie, scheduled batch logins skip MFA inside the trust window. That makes watch mode unnecessary for the actual use case.

**What this means for watch mode (D19):**

The implementation stays. It is done, unit-test-clean, and can be revived if a real intraday-polling need ever appears. It is no longer the next thing to test or build on. It is shelved as a feature pending that need.

**Next concrete steps:**

1. Inspect the existing `sessions/bofa_checking_state.json` to confirm a device-trust cookie is captured and identify its expiry.
2. Trigger the auto-re-auth path by letting the session cookies go stale, then run `getbofastatements` and observe whether MFA is prompted. If MFA is skipped, device trust is doing its job.
3. Check BofA security settings for authenticator-app MFA support.

**Trade-off:** This relies on bank-internal cookie semantics, which BofA can change unilaterally. If they revoke the device-trust pattern, every scheduled run would prompt MFA again and we would fall back to technique 2 or 3. That is an acceptable failure mode for a manual or weekly cadence; only an intraday-polling need would force watch mode back into play.

---

### D21: Email-MFA via Gmail MCP (Investigation Outcome)

**Date:** 2026-05-14 (evening, same day as D20).

**Status:** Closes out the D20 pursue-list with live evidence.

**Investigation summary.** The three D20 techniques were tested live on 2026-05-14:

1. **Device-trust cookie + session reuse: blocked, not viable.** BofA does roll the device-trust candidate cookies (`ctd`, `MMID`, `gl_prefill`, `BOA_0020`, `FPID`) forward on each successful login. However, the account-level "We will verify your identity every time you log in" toggle is currently ON, and BofA enforces MFA regardless of device recognition when that toggle is on. The cookies are healthy; the account setting overrides them. Turning the toggle off would unblock this path, but the email-MFA path below removes the need to do so.
2. **TOTP authenticator-app MFA: not offered.** Live navigation to the Security Center and the 2FA management area (via `fsdgoto('securitycenter')` and `fsdgoto('extraSecurity')` JS calls) confirmed BofA exposes no TOTP, no authenticator-app, and no method-management UI for consumer accounts. Visible delivery channels are SMS, phone call, and email only. Keyword scan of the rendered body text found no matches for `authenticator`, `TOTP`, `Google Authenticator`, `Authy`, `app-based`, `time-based`, or `Add a method`. Confidence ~95%.
3. **Email-code retrieval via Gmail API: viable, selected.** On the BofA MFA method-select page, the link **"Get code a different way"** toggles delivery from SMS to email. Email is sent to monarch508@gmail.com (masked by BofA as `m••••8@gmail.com`). The Gmail MCP confirmed delivery during exploration but is a Claude-session integration and is not callable from the websweeper runner. At runtime the runner will read Gmail directly via Google's Gmail API Python client, using OAuth 2.0 with a refresh token, `gmail.readonly` scope, and sender-scoped queries so the inbox access stays narrow. This keeps Claude / the MCP out of the runtime path, consistent with D02.

**Decision.** The auth path for unattended BofA runs is:

1. Keep "verify every time" ON. No change to the BofA account security posture.
2. The runner authenticates, then on the MFA method-select page clicks "Get code a different way" to switch delivery to email, then clicks Next.
3. The runner waits for the BofA MFA email by polling the Gmail API directly (sender-scoped read), parses the 6-digit code from the body via regex, types it into the code-entry field, and submits.
4. Scheduled batch runs become fully unattended without weakening any account security setting.

**Watch mode disposition.** Watch mode (D19) is **definitively shelved as a feature.** Email-MFA combined with a normal scheduled batch run covers the actual use case. The implementation (`src/websweeper/watcher.py`, the `watch` and `watch-bofa` CLI commands, the `keepalive_url` config field, and the `run_extraction()` refactor in `runner.py`) stays in the tree as preserved code, ready to revive if a real intraday-polling need ever appears.

**Trade-offs accepted.**

1. Each unattended login pays the cost of one Gmail round-trip (typically seconds). Acceptable.
2. The pipeline now depends on (a) the Gmail API OAuth refresh token staying valid for monarch508@gmail.com and (b) BofA not changing the email-MFA flow. Lower-risk than aggregator dependency, higher-risk than TOTP would have been (if it existed).
3. The Gmail API scope is constrained to `gmail.readonly`, and the runtime query filters on the BofA sender, limiting exposure even if the token were leaked.

**Next concrete steps.**

1. **Gmail API prereq (one-time):** create a Google Cloud project, enable the Gmail API, create an OAuth 2.0 client, run the consent flow once for monarch508@gmail.com with `gmail.readonly` scope, persist the refresh token via env vars (gitignored).
2. Extend the config schema with an MFA mode that supports email delivery selection (click "Get code a different way" before Next on the method-select page) and a Gmail-fetch hook with sender filter, body regex, and wait timeout.
3. Implement the executor / runner integration that calls the Gmail API for code retrieval after triggering email-MFA.
4. End-to-end live test of email-MFA against BofA on a scheduled run.

**Evidence basis.** Direct evidence from live exploration on 2026-05-14: storageState inspection (58-day-old and fresh state cookie analysis), three live BofA MFA cycles, Playwright captures of the login form, MFA method-select page, "Get code a different way" alternative-delivery view, post-auth landing, Security Center, and the 2FA management area. Sean independently captured `bofa_sec_1`, `bofa_sec_2`, and `bofa_sec_3` screenshots of the security settings and the email-delivery state. Exploratory screenshots and scripts were transient artifacts and are not retained in the repo.

---

## 2026-05-16 — CLI Naming Schema

### D22: Operation-First CLI Command Naming

**Decision.** All cross-site operations follow a verb-resource shape with the site config as the first positional argument:

```
list-statements      <config>                       # all available, slim records (date + id)
list-last-statement  <config>                       # most recent only, single record
pull-last-statement  <config>                       # download most recent
pull-statement       <config> <statement-id>        # download a specific one
pull-transactions    <config> [--days-back N]       # transactions, window N days back
```

`<config>` is the YAML basename without extension (e.g. `bofa_checking`) and resolves against `extensions/finance/configs/`. `<statement-id>` is opaque to the caller and comes from a `list-statements` record; for BofA it will typically be the cycle date string.

Existing site-prefixed actions (`getbofastatements`, `getbofastatementpdfs`, `getchasetransactions`) are retired in favor of the operation-first shape.

**Rationale.**

1. **API-shape over CLI-shape.** The consumption pattern for this project is not yet decided (POC for each site). Making the operations read like API methods (`list_statements(config)`, `pull_transactions(config, days_back=N)`) keeps every downstream wrapper, script, scheduled job, or future web layer using the same uniform invocation surface. Click commands are just one consumer.
2. **Apples-to-apples across sites.** Each new bank or extension gets the same operation names, not new verbs. `websweeper finance list-statements --help` documents the operation once for every site that implements it. The help index does not grow N sites × M operations.
3. **Explicit verbs over flag combinatorics.** `list-last-statement` over `list-statements --last` because each verb does exactly one thing. Easier to grep callers by command name and there is no "did I forget the `--last` flag" footgun.
4. **Singular vs plural matches return cardinality.** `list-statements` returns a list. `list-last-statement` returns one. `pull-statement` operates on one. `pull-transactions` returns many. The Python signatures mirror this (`list[Statement]` vs `Statement` vs `Path`).
5. **Config as first positional.** Every operation accepts the site identifier in the same slot. Scripts stay uniform across banks. Range and window knobs are flags (`--days-back N`), not positionals.

**Naming conventions.**

1. **Kebab-case at the CLI, snake_case in Python.** Click translates `list_last_statement()` Python functions to `list-last-statement` CLI commands automatically. Hyphens are operators in Python, so the function name has no choice; kebab is the dominant convention across modern CLIs (`git`, `kubectl`, `docker`, `gh`, `cargo`, `npm`) and matches Click's defaults.
2. **Modifier in the middle, resource at the end.** `list-last-statement` reads as "list the last statement" and matches the Python form `list_last_statement()`.
3. **Forward-compatible with non-bank extensions.** Future extensions can reuse the shapes: `list-bills`, `pull-last-bill`, `pull-transactions` for any time-series data source.

**Alternatives rejected.**

1. **Site-prefixed (`bofa-list-statements`).** Help index grows by sites times operations; calling code has to know the prefix. The existing pattern is being abandoned.
2. **Resource-first (`statements list <config>`).** Reads like `kubectl get pods` but forces a Click sub-group per resource, mismatches Python function names, and adds depth without benefit.
3. **Filter-flag instead of separate verb (`list-statements --last`).** Smaller surface but conflates collection and singleton return. Loses the cardinality-in-the-verb signal.
4. **Single positional resource (`pull <config> statements --last`).** Flexible but ambiguous which positional is the operation vs the target. Worse for scripted use.

**Watch mode disposition (revisit of D19 and D21).** The email-MFA path from D21 makes scheduled batch runs viable, and `--days-back N` covers incremental-sync needs without a persistent poller. Watch mode is no longer preserved code: it is removed from the tree as part of this iteration. If an intraday-polling need ever appears, the implementation can be reconstructed from history (commit `ef80ba6`).

**Trade-off accepted.** The renamed operations break any external scripts that depended on the old command names. There are no known external consumers (this is still POC), so the rename cost is zero today. As the project matures past POC, locking in this naming schema before downstream consumers form is the right time to do it.
