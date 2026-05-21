# CR-00070_S01_Backend_prompt

**Work Item**: CR-00070 -- Show Resolved Agent + Model Instead of "Inherit" in Step Runtime Dropdowns
**Step**: S01
**Agent**: backend-impl

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

This CR introduces **no migration** and **no schema change**. You MUST NOT
create an Alembic revision. If you believe a schema change is needed, STOP
and raise a blocker — it would contradict the design.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00070 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/CR-00070/CR-00070_CR_Design.md` -- Design document (authoritative spec)
- `ai-dev/active/CR-00070/CR-00070_Functional.md` -- Functional summary

## Output Files

- `ai-dev/work/CR-00070/reports/CR-00070_S01_Backend_report.md` -- Step report

## Context

You are implementing the backend half of **CR-00070**. The work-item steps
table currently renders `— inherit —` as the empty option of every runtime
`<select>`, which hides the agent + model a step will actually run. Your job
is to compute the *effective inherited runtime* and surface its display name
to the template so the empty option can be relabelled (S02 does the template
edit; you supply the data it needs).

Read `ai-dev/active/CR-00070/CR-00070_CR_Design.md` in full first — the
**Current Behavior**, **Desired Behavior**, **Backend / Resolver Changes**,
and **Acceptance Criteria** sections are the authoritative spec. Then read
`CLAUDE.md`, `orch/CLAUDE.md`, and `dashboard/CLAUDE.md` for conventions.

## Requirements

### 1. Add `resolve_inherited_runtime()` to `orch/agent_runtime/resolver.py`

Add a new public helper that computes the runtime option a step would
**inherit** when it carries no step-level override:

- Signature: `resolve_inherited_runtime(session, *, item, project) -> AgentRuntimeOption | None`.
- It must delegate to the existing `resolve_runtime()` so the result matches
  exactly what the daemon resolves for a step with no step-level override.
  Pass a no-step-override sentinel as the `step` argument — an object whose
  `agent_runtime_option_id` attribute is `None` (so `resolve_runtime()`'s
  step-override branch is skipped and the cascade falls to item override →
  `projects.toml` lookup → catalogue default).
- It MUST return `None` instead of letting `resolve_runtime()`'s `RuntimeError`
  ("unreachable" branch — no resolvable option, empty catalogue) escape. Catch
  that `RuntimeError` and return `None`. Rationale: a dashboard render must
  degrade gracefully, never 500 the steps table (AC5).
- Do NOT modify `resolve_runtime()` itself or its cascade behaviour.
- Add a concise docstring explaining it answers "what does an un-overridden
  step inherit" and why it returns `None` on the empty-catalogue case.

Export `resolve_inherited_runtime` from `orch/agent_runtime/__init__.py`
alongside the existing `resolve_runtime` export.

### 2. Wire the three dashboard render paths to pass `inherited_runtime_label`

`dashboard/templates/fragments/item_steps_table.html` is rendered by three
code paths. Each currently builds a `runtime_options` context list. Each must
additionally compute and pass a new context variable
`inherited_runtime_label` — the resolved option's `display_name` string, or
`None` when nothing resolves.

The three paths:
1. `dashboard/routers/items.py::item_detail` (full item page).
2. `dashboard/routers/items.py::item_tab_overview` (htmx overview-tab fragment).
3. `dashboard/routers/runtime_overrides.py::_render_steps_fragment` (PATCH-response fragment).

For each path:
- Load the project's `ProjectConfig` the same way the daemon's resolution
  source works — via `orch.daemon.project_registry.load_projects_toml(...)`
  keyed by `project_id` (see the existing precedent in
  `dashboard/routers/project_pages.py`, which already does
  `load_projects_toml(load_config().projects_toml).get(project_id)`).
  A `None` `ProjectConfig` (project absent from `projects.toml`) is acceptable
  — `resolve_runtime()` tolerates a `None`/attribute-less project and falls
  through to the catalogue default.
- Load the `WorkItem` (two of the three paths already have it in scope).
- Call `resolve_inherited_runtime(db, item=<work item>, project=<ProjectConfig or None>)`.
- Pass `inherited_runtime_label` (the resolved `display_name`, or `None`)
  into the `item_steps_table.html` template context.

**Do not triplicate the logic.** Factor a single small helper (e.g. in
`dashboard/routers/items.py` or a shared dashboard util) that takes
`(db, project_id, item)` and returns the label string or `None`, and call it
from all three paths. Keep routers thin (see `dashboard/CLAUDE.md`).

The inherited value is identical for every per-step dropdown within one item,
so compute it **once per render**, not per step.

### 3. Tests (TDD — see below)

Write the resolver tests and the dashboard-context tests described in the
design doc's **TDD Approach** section. The S02 frontend step adds the
template-rendering assertions; your tests cover the resolver helper and that
each render path puts a correct `inherited_runtime_label` into the response.

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `dashboard/CLAUDE.md` for:

- Architecture patterns and layer boundaries (business logic in `orch/`,
  routers stay thin).
- SQLAlchemy 2.0 sync style, Click/CLI patterns.
- Test organization, fixtures, and the strict DB-isolation rules in
  `tests/CLAUDE.md` (testcontainers only, never the live DB).

Follow all rules there exactly. When in doubt, match existing code — the
existing `resolve_runtime()` and the three render paths are your reference.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write failing tests first. Then run a *targeted* run only
   (`uv run pytest tests/integration/test_<x>.py -v`). Confirm the failure
   is an `AssertionError`/`AttributeError` from missing implementation — not
   an `ImportError`/`SyntaxError`/collection error. Capture the failing line(s).
2. **GREEN**: Minimal implementation to make tests pass.
3. **REFACTOR**: Improve structure while keeping tests green.

Test guidance (also see the design doc TDD section):
- `resolve_inherited_runtime()` needs seeded `agent_runtime_options` rows, so
  its tests belong in `tests/integration/` (a DB is required). Cover: no
  item-level override → catalogue/`projects.toml` default; item-level
  override set → returns the item-override option; empty catalogue → returns
  `None` (no raise).
- Render-path tests can extend `tests/dashboard/test_runtime_override_templates.py`
  — assert each of the three responses carries the resolved `display_name`
  for the inherited option, and that an item-level override changes it.

Do not skip the RED phase. Tests must exist before implementation code.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run these in order and fix
any issues in files you touched:

1. **`make format`** — auto-fixes formatting drift; inspect the diff and re-stage.
2. **`make typecheck`** — zero errors involving files you touched.
3. **`make lint`** — zero errors.

Record each in the `preflight` object of your result contract. If a tool is
unavailable, STOP and raise a blocker — do not silently skip.

## Test Verification (NON-NEGOTIABLE)

After implementation, verify your own changes — but **DO NOT run the full
test suite**. Run only the targeted tests you wrote/modified:

```bash
uv run pytest tests/integration/test_<your_resolver_test>.py tests/dashboard/test_runtime_override_templates.py -v
```

`make test-integration` is the S07 QV gate's job — do not run it here.
Do not report `tests_passed: true` unless your targeted tests pass with zero
failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00070",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/integration/test_x.py::test_foo — AssertionError: ...  // captured RED run",
  "blockers": [],
  "notes": ""
}
```

- `tdd_red_evidence`: **Required** — record the test id(s) and a 1–3 line
  snippet of the RED run output.
- `completion_status`: `complete` only when all deliverables are done and
  targeted tests pass.
