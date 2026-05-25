# CR-00082_S03_Backend_prompt

**Work Item**: CR-00082 -- Visual-regression test layer for rendered HTML and PDF documents
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

(Standard policy — see S01 prompt for full text. Docs / skill / tracker / CI yaml only in this step.)

## ⛔ Migrations: agents generate, daemon applies

This CR adds no migrations. You MUST NOT add any file under
`orch/db/migrations/versions/**`.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00082 --json`
- `ai-dev/work/CR-00082/CR-00082_CR_Design.md` — Design document (read AC5, AC7 carefully)
- `ai-dev/work/CR-00082/reports/CR-00082_S01_Backend_report.md` and `CR-00082_S02_Backend_report.md` — for the final make-target list to wire into CI
- `docs/IW_AI_Core_Testing_Strategy.md` — find §2 (Layers), §5 (gates), §9 (status matrix)
- `skills/iw-ai-core-testing/SKILL.md` and `.claude/skills/iw-ai-core-testing/SKILL.md` — the master copy + the synced copy
- `ai-dev/work/TESTS_ENHANCEMENT.md` — find §8 row 4.1 and the v1.x header block

## Output Files

- `ai-dev/work/CR-00082/reports/CR-00082_S03_Backend_report.md` — Step report

## Context

You are implementing the **CI workflow + documentation + skill + tracker updates** for CR-00082.

S01 + S02 shipped the test module + baselines + make targets. Your job is to:

1. Wire the new `make visual-regression` target into a new GitHub Actions workflow.
2. Update the testing-strategy doc to reflect the new layer.
3. Update the testing skill to document the patterns and baseline-management rules.
4. Update the tracker.

## Requirements

### 1. Create `.github/workflows/visual-regression.yml`

The workflow must include all three triggers required by AC5:

1. **Cron** — nightly (e.g., `0 3 * * *`, or match the cadence of other nightly workflows in `.github/workflows/`).
2. **`workflow_dispatch`** — ad-hoc manual run.
3. **`pull_request` with `paths` filter** — fires on changes to:
   - `dashboard/static/styles.css`
   - `dashboard/templates/pdf/**`
   - `dashboard/templates/components/doc_*`
   - `doc-system/**`

The job:

1. Checks out the repo.
2. Installs `uv` (match the version-pin pattern used by other workflows under `.github/workflows/`).
3. Runs `uv sync --all-groups` (or whatever the project's standard install command is — read another workflow).
4. Installs the system `pdftoppm` binary (poppler-utils on Ubuntu; the runner image likely already has it — confirm, and `apt-get install -y poppler-utils` only if not).
5. Installs `playwright-cli` per the project's pattern (or reuses the same pattern used by `make test-e2e` / `make test-browser` workflows — read existing CI to find the exact recipe).
6. Runs `make visual-regression`.
7. On failure, uploads `tests/output/visual-diff/**` as a job artefact so a reviewer can download and inspect the `*-diff.png` files.

**Burn-in policy**: ship the workflow with the job step's `continue-on-error: true` for the first calendar week post-merge. Add an inline `# BURN-IN: flip to continue-on-error: false after <date>` comment naming the flip date (2026-06-01). This keeps the early nightly noise from blocking PRs while the baselines settle.

### 2. Update `docs/IW_AI_Core_Testing_Strategy.md`

- **§2** — add a "Layer 8 — visual regression" subsection (model it on the existing Layer N subsections). Describe: what it covers (HTML doc views + PDF exports), how it runs (`make visual-regression`), where the baselines live (`tests/visual/baselines/`), what the failure artefacts look like (`tests/output/visual-diff/*-diff.png`), and why it is NOT a daemon QV gate (wall-clock cost).
- **§5** — add a new gate row for `make visual-regression` (CI-only, nightly + path-filtered, not in `make check`).
- **§9** — flip the "visual regression" row from ❌ to ✅, citing CR-00082 + 2026-05-24.

### 3. Update `skills/iw-ai-core-testing/SKILL.md`

Add a new section titled e.g. "Visual regression — patterns and baseline-management rules". Cover:

- When to add a new baseline (every new editorial category that ships in `doc-system/`).
- How to update a baseline intentionally (review-gated PR that touches `tests/visual/baselines/**`).
- The forbidden auto-accept pattern (never bake "if diff > threshold, overwrite baseline" into the test).
- The Playwright CLI rules (link back to `CLAUDE.md`).
- Pixel-tolerance discipline (one shared constant; do NOT inflate per-test).

After editing the master copy, run:

```bash
uv run iw sync-skills --force iw-ai-core-testing
```

to mirror the master copy into `.claude/skills/iw-ai-core-testing/` and every project's `.claude/skills/` per project policy. Confirm the sync wrote to both `skills/iw-ai-core-testing/` (no-op) and `.claude/skills/iw-ai-core-testing/` (updated). Record the sync output in the report `notes`.

### 4. Update `ai-dev/work/TESTS_ENHANCEMENT.md`

- §8 row 4.1 — flip status from TODO to DONE; add a "CR-00082 / 2026-05-24 / 4-PDF + 4-HTML baselines, nightly + path-filtered CI, blocking after 1-week burn-in" notes column.
- Add a new v1.4 header entry dated 2026-05-24 summarising the visual-regression delivery and pointing at CR-00082.

## Project Conventions

Read `CLAUDE.md` and the existing files under `.github/workflows/` for CI patterns. Match the style of neighbouring workflows (yaml indentation, action versions, uv install recipe).

For the skill edit, match the style of existing sections in `skills/iw-ai-core-testing/SKILL.md`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. **`make format`**
2. **`make typecheck`** — N/A here (only yaml + markdown changes); record as `skipped:no-code-changes`.
3. **`make lint`** — must pass (the project's lint chain includes `scripts/check_templates.py` for Jinja2; yaml changes do not trigger it but run it anyway).

## Test Verification (NON-NEGOTIABLE)

Targeted runs only — no new behavioural test is added in this step. Verify the prior steps' targets still pass:

```bash
make visual-regression
```

Do NOT run `make test-unit` or `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00082",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    ".github/workflows/visual-regression.yml",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "skipped:no-code-changes",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "make visual-regression: PASS",
  "tdd_red_evidence": "n/a — CI yaml + docs + skill + tracker edits only, no behavioural production logic",
  "blockers": [],
  "notes": "iw sync-skills output: <copy here>. Burn-in flip date: 2026-06-01."
}
```
