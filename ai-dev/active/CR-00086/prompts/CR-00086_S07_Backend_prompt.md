# CR-00086_S07_Backend_prompt

**Work Item**: CR-00086 -- Self-dashboarding of test health
**Step**: S07
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Same policy. Read-only `docker ps/inspect/logs` plus `make` / `./ai-core.sh` targets only. The new CI workflow runs in GitHub-hosted Linux outside this worktree; you do not run it.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migration work here. You MUST NOT run `alembic upgrade/downgrade/stamp`. The docs update for `IW_AI_Core_Database_Schema.md` is documentation only — it does NOT regenerate any migration.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00086 --json`.
- `ai-dev/active/CR-00086/CR-00086_CR_Design.md` -- Design (read **Description**, **Desired Behavior**, AC6, Notes)
- `ai-dev/work/CR-00086/reports/CR-00086_S03_Backend_report.md` -- S03 report (the CLI command shape)
- `ai-dev/work/CR-00086/reports/CR-00086_S05_Frontend_report.md` -- S05 report (final column list to document)
- Existing workflows under `.github/workflows/` -- study one (e.g., the CI workflow) for project conventions on secrets, uv setup, action versions
- `docs/IW_AI_Core_Testing_Strategy.md` -- find where §10 should go
- `docs/IW_AI_Core_Database_Schema.md` -- find the table-listing convention
- `ai-dev/work/TESTS_ENHANCEMENT.md` -- find §8 row 4.6 and the header version block
- `skills/iw-ai-core-testing/SKILL.md` + `.claude/skills/iw-ai-core-testing/SKILL.md` -- mirror pair

## Output Files

- `ai-dev/work/CR-00086/reports/CR-00086_S07_Backend_report.md`
- `.github/workflows/test-health.yml` (new)
- `docs/IW_AI_Core_Testing_Strategy.md` (modified — new §10)
- `docs/IW_AI_Core_Database_Schema.md` (modified — new table DDL block)
- `ai-dev/work/TESTS_ENHANCEMENT.md` (modified — row 4.6 → DONE, v1.4 header)
- `skills/iw-ai-core-testing/SKILL.md` (modified — cross-reference paragraph)
- `.claude/skills/iw-ai-core-testing/SKILL.md` (mirrored via `iw sync-skills`)

## Context

You are implementing the **CI workflow + docs + skill + tracker** step of **CR-00086**. This step is doc-and-config heavy; NO production code changes. The CI workflow runs the `iw test-health-capture` command (built by S03) and uploads the printed JSON summary as an artefact.

Read `CLAUDE.md` and the existing workflows under `.github/workflows/` before starting.

## Requirements

### 1. .github/workflows/test-health.yml

**Persistence model (decided at design review)**: this workflow runs on a **self-hosted runner** with network access to the orchestration DB on port 5433. Snapshots are written to the live `test_health_snapshots` table — NOT to an ephemeral GH-Actions service-container Postgres. The pattern in `.github/workflows/test-quality.yml` (service container with hardcoded `iw/iw/iw_ai_core` env vars) is **explicitly rejected** for this workflow because its rows would disappear at runner exit, defeating the trend-over-time purpose.

Runner:

```yaml
runs-on: [self-hosted, iw-core]   # match the operator's self-hosted runner label
```

If the label `iw-core` does not exist in the operator's runner pool, ask before guessing — fall back to the default label the operator uses for IW-managed workflows (check existing workflows that already target a self-hosted runner, if any; otherwise raise a blocker so the operator can answer).

Triggers:

```yaml
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 3 * * *'   # 03:00 UTC nightly
  workflow_dispatch: {}    # allow manual trigger for debugging
```

Job steps:

1. `actions/checkout@v4` (pinned to a SHA per `.github/workflows/codeql.yml` style).
2. Set up Python (use the version from `pyproject.toml`, e.g. via `astral-sh/setup-uv@v3`).
3. `uv sync --frozen`.
4. Set the runtime DB env vars from GitHub secrets — `IW_CORE_DB_HOST`, `IW_CORE_DB_PORT`, `IW_CORE_DB_NAME`, `IW_CORE_DB_USER`, `IW_CORE_DB_PASSWORD` — sourced from `${{ secrets.IW_CORE_* }}`. **Do NOT** copy the inline `iw/iw/iw_ai_core` env-block from `test-quality.yml`: that pattern is correct for the ephemeral service-container workflows but is wrong here because it would point the capture at a throwaway DB. **Do NOT** add a `services: postgres:` block to this workflow.
5. Run `uv run iw test-health-capture --project iw-ai-core` and tee its stdout to `test-health-summary.json`.
6. Upload `test-health-summary.json` as a workflow artefact via `actions/upload-artifact@v4` (audit trail; the snapshots themselves live in the orch DB).

Concurrency: set `concurrency: { group: test-health, cancel-in-progress: false }` so concurrent on-push + cron runs queue rather than cancel.

**Operator prerequisite (call out in the report)**: the workflow will not run successfully until the operator (a) provisions a self-hosted runner with the chosen label, (b) creates the `IW_CORE_*` secrets in the repo settings, and (c) confirms the runner's network can reach the orch DB on port 5433. Document these prereqs in the §10 strategy doc you write below.

### 2. docs/IW_AI_Core_Testing_Strategy.md §10

Add a new top-level section `## 10. Self-dashboarding`. Cover:

- The four metrics surfaced (mutation_score, coverage_pct, flaky_test_count, assertion_baseline_size).
- Where the panel mounts (Tests view and Quality view, under the gates summary).
- Capture cadence (on push to main + nightly cron + manual `workflow_dispatch`).
- **Persistence model** (self-hosted runner reaches the live orch DB on port 5433 via the `IW_CORE_*` secrets; ephemeral service-container Postgres is explicitly out — explain why so future maintainers don't "fix" it back).
- Operator prerequisites (self-hosted runner labelled `iw-core` online; `IW_CORE_*` secrets configured; runner has network access to the orch DB).
- Idempotency contract (one row per `(project, metric, minute)`).
- Empty-state behaviour (per-metric placeholder + combined empty state).
- A link to CR-00086 design + manifest paths.
- A `last updated: 2026-05-24` line.

### 3. docs/IW_AI_Core_Database_Schema.md

Append a DDL block for `test_health_snapshots` in the same style as other tables in the file. Include columns, the FK, and the index. Cross-reference CR-00086.

### 4. ai-dev/work/TESTS_ENHANCEMENT.md

- §8 row 4.6: status `TODO` → `DONE`. Append the CR-00086 reference and date `2026-05-24`.
- Header version: bump to `v1.4`. Add a one-line release note (e.g., `v1.4 (2026-05-24): row 4.6 DONE — self-dashboarding panel ships in CR-00086`).
- Add a `§11` changelog entry dated 2026-05-24 with a two-line summary.

### 5. Skill cross-reference

In `skills/iw-ai-core-testing/SKILL.md`, find the section that lists the test-health metrics (or add one if absent), and add a paragraph:

> Live metric values are surfaced on the dashboard's Test Health panel (Tests and Quality pages for the iw-ai-core project). The panel reads from the `test_health_snapshots` table, populated by `iw test-health-capture` on every push to main and nightly. See CR-00086 for the design.

Run `uv run iw sync-skills` to mirror to `.claude/skills/iw-ai-core-testing/SKILL.md`. Commit BOTH copies (operator note from `feedback_skills_sync` memory).

## Project Conventions

- `CLAUDE.md`: no docker compose against the orch DB; never hardcode secrets.
- Existing workflow style — match it for action versions, secret references, and step ordering.
- Skill mirror: BOTH copies must land in the same commit.

## TDD Requirement

This step is doc + workflow + tracker + skill — no production behaviour is implemented. `tdd_red_evidence` MUST be `"n/a — workflow + docs + tracker + skill edits only, no production logic"`. Do NOT fabricate a behavioural test for this step.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck` — should be a no-op for this step (no .py changes)
3. `make lint` — must pass on any touched files (the workflow YAML is not linted by ruff, but check that no markdown-lint rules are broken on the docs).

Populate `preflight`. `typecheck` may be `skipped:no-code-changes` if no .py files changed.

## Test Verification (NON-NEGOTIABLE)

No new tests in this step. Sanity-check by running the existing skill-sync check:

```bash
diff -u skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md  # should be empty after sync-skills
```

If `diff` shows differences, re-run `iw sync-skills` and commit again.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "backend-impl",
  "work_item": "CR-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    ".github/workflows/test-health.yml",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "docs/IW_AI_Core_Database_Schema.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "skipped: workflow + docs + tracker + skill changes only",
  "tdd_red_evidence": "n/a — workflow + docs + tracker + skill edits only, no production logic",
  "blockers": [],
  "notes": ""
}
```
