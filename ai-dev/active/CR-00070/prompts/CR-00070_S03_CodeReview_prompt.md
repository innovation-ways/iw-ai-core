# CR-00070_S03_CodeReview_prompt

**Work Item**: CR-00070 -- Show Resolved Agent + Model Instead of "Inherit" in Step Runtime Dropdowns
**Steps Being Reviewed**: S01 (backend-impl), S02 (frontend-impl)
**Review Step**: S03

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR introduces no migration. If any reviewed step added an Alembic
revision under `orch/db/migrations/versions/**`, that contradicts the design
— raise it as a CRITICAL finding.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00070 --json`.
- `ai-dev/active/CR-00070/CR-00070_CR_Design.md` -- Design document
- `ai-dev/work/CR-00070/reports/CR-00070_S01_Backend_report.md` -- S01 report
- `ai-dev/work/CR-00070/reports/CR-00070_S02_Frontend_report.md` -- S02 report
- All files listed in those reports' `files_changed`

## Output Files

- `ai-dev/work/CR-00070/reports/CR-00070_S03_CodeReview_report.md` -- Review report

## Context

You are reviewing the implementation work done in S01 (backend-impl) and S02
(frontend-impl) for **CR-00070**. The CR replaces the `— inherit —` label in
the runtime-override dropdowns with the resolved agent + model suffixed
`(inherited)`.

Read the design document to understand what was intended. Read both
implementation reports to understand what was done. Then review all changed
files.

## Read the Design Document FIRST

Read `ai-dev/active/CR-00070/CR-00070_CR_Design.md` **before** running the
lint/format gate and **before** opening any changed files. Specifically:

- Read `## Acceptance Criteria` (AC1–AC6) in full — every criterion is a
  mandatory check.
- Read `## TDD Approach` in full — note every test file named by path; the
  resolver tests must exist in `tests/integration/` and the template tests in
  `tests/dashboard/test_runtime_override_templates.py`. A design-named test
  file missing from any `files_changed` is a **CRITICAL** finding.
- Verify the three render paths (`items.py::item_detail`,
  `items.py::item_tab_overview`, `runtime_overrides.py::_render_steps_fragment`)
  were ALL wired — AC6 requires the relabel to appear via every path. A
  missed path is a CRITICAL/HIGH finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these on the changed files. Fix nothing — only
report.

```bash
make lint
make format
```

Any NEW violation in the changed files (not present on `main` before this
work) is a **CRITICAL** finding with `"category": "conventions"`, the
`file`/`line` from the tool output, and the exact violation code quoted.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Architecture Compliance

- `resolve_inherited_runtime()` lives in `orch/agent_runtime/resolver.py` and
  is exported from `orch/agent_runtime/__init__.py`. Business logic stays in
  `orch/`, routers stay thin (`dashboard/CLAUDE.md`).
- `resolve_runtime()` itself is **not** modified — only wrapped. Confirm.
- The three render paths reuse one shared dashboard helper, not triplicated
  logic.

### 2. Code Quality & Correctness

- `resolve_inherited_runtime()` skips the step-override branch (passes a
  no-step-override sentinel) so it answers "what does an un-overridden step
  inherit". An item-level override must still be honoured (AC3).
- It returns `None` on the empty-catalogue case rather than letting
  `resolve_runtime()`'s `RuntimeError` escape (AC5). A render path that can
  500 the steps table is a CRITICAL finding.
- The template falls back to a neutral `— inherit —` when
  `inherited_runtime_label` is falsy — no ` (inherited)` with an empty model.
- The `<select>` `value=""`, `name`, and htmx attributes are unchanged — the
  inherit/clear mechanism (AC4) must still work.
- The bulk dropdown non-empty options now use `display_name` (consistent with
  the per-step list).

### 3. Project Conventions

- Read `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`. Naming, imports,
  SQLAlchemy 2.0 style, fragment-template rules.

### 4. Security

- No hardcoded secrets. `display_name` is operator-controlled catalogue data
  rendered through Jinja2 autoescaping — confirm no `|safe` was added.

### 5. Testing

- Resolver tests cover: no override → default; item override → that option;
  empty catalogue → `None`.
- Template/render tests cover all three render paths and the fallback case.
- Tests assert on behaviour and would fail if the production code regressed.

### 5a. TDD RED Evidence

S01 (backend-impl) is behaviour-implementing — confirm its report's
`tdd_red_evidence` records a plausible RED run (`AssertionError` /
`AttributeError`, not an import/collection error). For at least one new
behavioural test, reason about whether it would fail against pre-change code;
a test that passes without the new code is a HIGH finding. S02 is a
template/test step — `"n/a — ..."` or a template-render RED is acceptable.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review, run the targeted tests for this CR and report
results accurately:

```bash
uv run pytest tests/dashboard/test_runtime_override_templates.py -v
```

(The resolver integration tests also run under `make test-integration` at the
S07 QV gate — you need not run the full suite here.)

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Breaks functionality, data loss, security | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, arch violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality, missing edge case, convention | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement | Optional |
| **LOW** | Nitpick, style | Informational |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview",
  "work_item": "CR-00070",
  "step_reviewed": "S01,S02",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL, zero HIGH, and zero MEDIUM(fixable)
  findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM(fixable).
