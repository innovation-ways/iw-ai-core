# CR-00090_S02_Frontend_prompt

**Work Item**: CR-00090 — Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var
**Step**: S02
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migration is required for this CR. Do not create or modify any Alembic
migration file.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00090 --json`
- `ai-dev/active/CR-00090/CR-00090_CR_Design.md` — Design document (authoritative spec)
- `ai-dev/active/CR-00090/reports/CR-00090_S01_Backend_report.md` — S01 result (confirms `_e2e_mode` global is injected)
- `dashboard/templates/base.html` — Main template with worktree-badge
- `dashboard/templates/fragments/staleness_dot.html` — Staleness dot fragment
- `dashboard/templates/pages/project_selector.html` — Project selector page
- `ai-dev/iw-config/worktree-compose.template.yml` — Worktree compose template

## Output Files

- `ai-dev/active/CR-00090/reports/CR-00090_S02_Frontend_report.md` — Step report

## Context

You are implementing the frontend/template and compose-template changes for CR-00090.

The S01 backend step added `get_e2e_mode()` to `orch/config.py` and injected `_e2e_mode`
as a Jinja2 global in `dashboard/app.py`. This step updates the three templates that use
the UA-based `_headless` detection and adds `IW_CORE_E2E_MODE: "true"` to the worktree
compose template.

## Requirements

### 1. Update `_headless` detection in all three templates

In each template listed below, find the line that sets `_headless` using the UA heuristic
and replace it with the OR-combined expression:

**Before** (in each template):
```jinja
{% set _headless = ('headlesschrome' in _ua) or ('playwright' in _ua) %}
```

**After** (in each template):
```jinja
{% set _headless = _e2e_mode or ('headlesschrome' in _ua) or ('playwright' in _ua) %}
```

Affected templates (read each file to find the exact line before editing):
- `dashboard/templates/base.html`
- `dashboard/templates/fragments/staleness_dot.html`
- `dashboard/templates/pages/project_selector.html`

**Critical**: The variable name `_headless` is PRESERVED — only the expression
changes. Other template code that uses `_headless` continues to work unchanged.
The `_e2e_mode` global was injected by S01; it is always available in every template
context without any per-route or per-template change.

### 2. Add `IW_CORE_E2E_MODE: "true"` to the worktree compose template

File: `ai-dev/iw-config/worktree-compose.template.yml`

Read the file to locate the `app` service's `environment:` block. Add the new variable
immediately after the existing `IW_CORE_DB_*` and related variables:

```yaml
      IW_CORE_E2E_MODE: "true"
```

Keep YAML indentation consistent with the surrounding entries. The value must be the
string `"true"` (quoted) so it is unambiguously a string in YAML. This affects all
future E2E containers launched by the daemon; currently-running containers are
unaffected until their next restart.

## Project Conventions

- **Plain CSS only** — no Tailwind recompile; do not touch `styles.css` (no CSS changes needed)
- **Jinja2 format filters** must use `%`-style: `"%dm%02ds"|format(m, s)` (enforced by `make lint`)
- **NEVER** use `agent-browser`; use `playwright-cli` exclusively for browser automation
- **NEVER** modify `.playwright/cli.config.json`
- Read `dashboard/CLAUDE.md` for template conventions

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift (Python only; Jinja2 templates are not reformatted)
2. `make typecheck` — must report zero errors in files you touched (Python only)
3. `make lint` — MUST pass, especially `scripts/check_templates.py` which validates Jinja2 format filters

## Test Verification (NON-NEGOTIABLE)

There are no new tests written in this step (S03 covers dashboard tests). Run the existing
unit tests to confirm no regressions:

```bash
uv run pytest tests/unit/ -v -q --no-cov
```

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "frontend-impl",
  "work_item": "CR-00090",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/base.html",
    "dashboard/templates/fragments/staleness_dot.html",
    "dashboard/templates/pages/project_selector.html",
    "ai-dev/iw-config/worktree-compose.template.yml"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — template/compose edits only, no production logic",
  "blockers": [],
  "notes": ""
}
```
