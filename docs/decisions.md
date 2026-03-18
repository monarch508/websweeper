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
