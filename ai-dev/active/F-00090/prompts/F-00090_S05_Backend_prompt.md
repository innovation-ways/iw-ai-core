# F-00090_S05_Backend_prompt

**Work Item**: F-00090 -- Regression-rate tracking
**Step**: S05
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy applies. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

This step leaves migrations unchanged.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00090 --json`.
- `ai-dev/active/F-00090/F-00090_Feature_Design.md` — AC8.
- `ai-dev/active/F-00090/reports/F-00090_S02_Backend_report.md` — the `regression_link_service` you'll call.
- `scripts/backfill_functional_doc.py` and `scripts/e2e_seed.py` — for backfill script style conventions.
- `docs/IW_AI_Core_Testing_Strategy.md` — §10 gains a new section.
- `docs/IW_AI_Core_Database_Schema.md` and `docs/IW_AI_Core_Dashboard_Design.md` — incremental doc updates.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.7 — flip TODO → DONE at v1.4.
- `skills/iw-ai-core-testing/` — add a cross-reference to the regression KPI.

## Output Files

- `ai-dev/active/F-00090/reports/F-00090_S05_Backend_report.md` — step report.
- New: `scripts/backfill_regression_classification.py`
- Modified: `docs/IW_AI_Core_Testing_Strategy.md`
- Modified: `docs/IW_AI_Core_Database_Schema.md` (only if S01 didn't cover everything — extend, don't duplicate)
- Modified: `docs/IW_AI_Core_Dashboard_Design.md`
- Modified: `ai-dev/work/TESTS_ENHANCEMENT.md`
- Modified: `skills/iw-ai-core-testing/SKILL.md` (and the `.claude/skills/iw-ai-core-testing/SKILL.md` mirror)

## Context

You are wrapping up F-00090 with the **backfill script + docs + tracker + skill** updates. None of these are CI-gated; the backfill is operator-run.

Read the design first. Read `CLAUDE.md`.

## Requirements

### 1. Backfill script — `scripts/backfill_regression_classification.py`

A standalone Python script (not a CLI subcommand) that:

- Accepts `--project PROJECT_ID` (required) and optional `--dry-run`.
- Opens a session via `orch.db.session.SessionLocal()`.
- Selects every Incident in the project with `regression_classification IS NULL`.
- For each, calls `regression_link_service.suggest_introducer(...)` and writes the top suggestion **as a comment line to stdout** plus (when not `--dry-run`) **logs the suggestion** — but **does NOT classify automatically**. Operator confirmation is required via the UI or the CLI `--accept` flag (Invariant 3).
- Prints a summary line: `Processed N incidents; M had suggestions; 0 classifications persisted (operator triage required)`.
- Idempotent: re-running yields the same suggestions; no DB writes when `--dry-run`; even without `--dry-run`, the script does not write `WorkItem` rows (it only emits suggestions).
- Exits 0 on success.

Use `argparse` (match `scripts/backfill_functional_doc.py` style). Add a top-of-file docstring describing the operator-run workflow and warning that this is NOT a CI step.

### 2. Documentation updates

**`docs/IW_AI_Core_Testing_Strategy.md`** — add a new `## 10. Regression-rate KPI` section (or extend §10 if it already exists) explaining: the rationale (throughput-without-regressions is misleading), how classifications are recorded (operator + heuristic), how the KPI is computed (weekly merges vs weekly regressions), and the rate-guard rule (0.0 when merges=0). Reference F-00090.

**`docs/IW_AI_Core_Dashboard_Design.md`** — describe the new Quality KPIs section, the dedicated `/project/{id}/quality-kpis` route, the regression badge on Batches/History, and the htmx classification form on the Incident detail page. Cross-reference F-00090.

**`docs/IW_AI_Core_Database_Schema.md`** — if S01 added a stub, extend it with the operator-vs-heuristic semantics for `classified_by`, the ENUM values explained, and a worked example. If S01 already did this, skip — do not duplicate.

### 3. Tracker update — `ai-dev/work/TESTS_ENHANCEMENT.md`

Find §8 row 4.7 ("Regression-rate tracking"). Flip the status from TODO → DONE and bump the tracker version line to v1.4 (or the next semver step matching the file's convention). Add a one-line note: `Delivered by F-00090 — operator-curated classification + heuristic + dashboard KPI section`.

### 4. Skill cross-reference + sync

**`skills/iw-ai-core-testing/SKILL.md`** — add a one-paragraph cross-reference under the existing "Test red-flag checklist" or similar section pointing readers at the new regression-rate KPI as part of the broader "quality signals you should look at" picture. Mirror the edit into `.claude/skills/iw-ai-core-testing/SKILL.md` (the project-local copy).

After editing, run:

```bash
uv run iw sync-skills
```

To propagate the master copy to the project worktree. This is the canonical sync command. Capture its output in your report.

### 5. RED-first discipline

This step adds no new behavioural tests (the backfill script is operator-run and the docs are doc edits). Use:

`tdd_red_evidence: "n/a — backfill script + docs + skill + tracker only; no production logic with behavioural tests"`

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Key constraints:

- **MUST** ensure `.env` and `.iw/` are in every managed project's `.gitignore` — not relevant here (no new project) but you'll see this rule.
- **MUST** propagate skill edits to the master copy AND project-local copies; the `iw sync-skills` command is the bridge.
- Tracker updates use the existing TESTS_ENHANCEMENT.md row/version conventions — read the file first.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — applies to the new script.
2. `make typecheck` — applies to the new script.
3. `make lint` — applies to the new script.

(Docs and tracker are markdown — they don't trip type/format gates, but `scripts/check_templates.py` runs as part of `make lint` and may surface markdown issues. Address any it reports.)

## Test Verification (NON-NEGOTIABLE)

The backfill script has no dedicated unit test (operator-run, file-side-effect-free). Verify by running it in `--dry-run` against a fresh testcontainer (use the same pattern as `scripts/e2e_seed.py` tests if one exists; otherwise a smoke run with `--dry-run --project test_project` against the testcontainer is acceptable). Capture exit code 0.

Do NOT run the full unit / integration suites.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "backend-impl",
  "work_item": "F-00090",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "scripts/backfill_regression_classification.py",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "docs/IW_AI_Core_Dashboard_Design.md",
    "docs/IW_AI_Core_Database_Schema.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "backfill smoke (dry-run): exit 0; iw sync-skills: OK",
  "tdd_red_evidence": "n/a — backfill script + docs + skill + tracker only; no production logic with behavioural tests",
  "blockers": [],
  "notes": ""
}
```
