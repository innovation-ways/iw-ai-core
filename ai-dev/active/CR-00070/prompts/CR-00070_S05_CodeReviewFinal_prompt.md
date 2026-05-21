# CR-00070_S05_CodeReview_Final_prompt

**Work Item**: CR-00070 -- Show Resolved Agent + Model Instead of "Inherit" in Step Runtime Dropdowns
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S02 (plus any S04 fixes)

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

This CR introduces no migration. An Alembic revision in any changed-file set
contradicts the design — flag it CRITICAL.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00070 --json`.
- `ai-dev/active/CR-00070/CR-00070_CR_Design.md` -- Design document
- All implementation step reports: `ai-dev/work/CR-00070/reports/CR-00070_S01_*`, `CR-00070_S02_*`
- The per-agent review report: `ai-dev/work/CR-00070/reports/CR-00070_S03_CodeReview_report.md`
- Any fix report: `ai-dev/work/CR-00070/reports/CR-00070_S04_CodeReview_FIX_report.md`
- All files listed in the implementation reports' `files_changed`

## Output Files

- `ai-dev/work/CR-00070/reports/CR-00070_S05_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation
work for **CR-00070**. Per-agent review (S03) and any fixes (S04) are done;
your job is to catch cross-cutting issues — how the backend resolver helper,
the three router render paths, and the template edit fit together as one
coherent change.

Read the design document to understand the full intended scope. Read all
implementation and review reports. Then review all changed files holistically.

## Read the Design Document FIRST

Read `ai-dev/active/CR-00070/CR-00070_CR_Design.md` **before** the lint gate
and **before** opening code:

- Read `## Acceptance Criteria` (AC1–AC6) in full — every criterion is a
  mandatory check.
- Read `## TDD Approach` in full — cross-check every test file it names by
  path against the `files_changed` of ALL implementation reports. A named
  test file appearing nowhere is a **CRITICAL** finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any NEW violation in the changed files is a **CRITICAL** finding with
`"category": "conventions"`. If a command is unavailable, STOP and raise a
blocker.

## Review Checklist

### 1. Completeness vs Design Document

- All of AC1–AC6 are satisfied by the combined work.
- The `(inherited)` relabel reaches the UI through **all three** render
  paths: `items.py::item_detail`, `items.py::item_tab_overview`,
  `runtime_overrides.py::_render_steps_fragment` (AC6). A missed path is
  CRITICAL.
- No TODOs / placeholder implementations.

### 2. Cross-Agent Consistency

- The `inherited_runtime_label` context variable name is identical between
  what S01's routers pass and what S02's template consumes. A name mismatch
  silently yields the fallback label everywhere — verify by reading both
  sides, not by trusting the reports.
- The shared dashboard helper introduced by S01 is genuinely shared by all
  three paths (no copy-paste drift).

### 3. Integration Points

- `resolve_inherited_runtime()` is imported/used correctly; `resolve_runtime()`
  is unchanged; the `orch/agent_runtime/__init__.py` export is correct.
- `load_projects_toml()` usage matches the existing precedent and tolerates a
  project absent from `projects.toml` (returns `None` → catalogue default).

### 4. Test Coverage (Holistic)

- Resolver tests AND template/render tests both exist and exercise the
  integration points (the render paths actually emit the resolved label).
- The empty-catalogue fallback (AC5) is covered end-to-end.
- Any pre-existing test asserting on the literal `— inherit —` string was
  updated (the design's **Updated tests** note).

### 5. Architecture Compliance

- Read `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`. Layer boundaries
  respected; routers stay thin.

### 6. Security (Cross-Cutting)

- No hardcoded secrets. `display_name` rendered through Jinja2 autoescaping;
  no `|safe` added.

## Test Verification (NON-NEGOTIABLE)

Run the **targeted** tests for this CR and report results accurately:

```bash
uv run pytest <CR-00070 resolver integration test> tests/dashboard/test_runtime_override_templates.py -v
```

(Use the resolver integration test file named in S01's report.) Do **NOT**
run `make test-integration` here — the full `tests/integration` +
`tests/dashboard` suite is the **S07 QV gate's** job; running it again in this
review step duplicates that gate and risks the I-00073 timeout pattern. If the
targeted tests fail, that is a CRITICAL finding.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Breaks functionality, data loss, security, missing requirement | Must fix before merge |
| **HIGH** | Significant bug, integration failure, arch violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality, missing edge case, convention | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement | Optional |
| **LOW** | Nitpick, style | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "CR-00070",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X targeted tests passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL, zero HIGH, zero MEDIUM(fixable).
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM(fixable).
- `missing_requirements`: each is automatically a CRITICAL finding.
