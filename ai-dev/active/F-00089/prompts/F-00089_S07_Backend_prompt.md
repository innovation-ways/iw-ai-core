# F-00089_S07_Backend_prompt

**Work Item**: F-00089 -- Daemon chaos / fault-injection test layer
**Step**: S07
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations involved in this step. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status F-00089 --json` — runtime step state.
- `ai-dev/work/F-00089/F-00089_Feature_Design.md` — Design document (AC7, AC8 first half, Invariants 9 + 10).
- S02..S06 reports + the test files they created (so you know exactly which tests `daemon-chaos-smoke` and `daemon-chaos-full` invoke).
- `Makefile` — existing test targets (study patterns of `test-unit`, `test-integration`, `allure-integration`).
- `.github/workflows/` — existing workflow patterns (`e2e.yml`, `test-quality.yml`).
- `skills/iw-workflow/SKILL.md` — canonical QV gate chain (currently 8 gates; you add the 9th).
- `.claude/skills/iw-workflow/SKILL.md` — mirror that `iw sync-skills --force iw-workflow` writes.

## Output Files

- `ai-dev/work/F-00089/reports/F-00089_S07_Backend_report.md` — Step report.

## Context

You are implementing **S07: wire-up** — Makefile targets, GH workflow, workflow-skill canonical-gate update. This step turns the test code from S01..S06 into a CI gate.

**Test-only scope.** No production code changes.

## Requirements

### 1. Makefile — two new targets

Add two targets to `Makefile`:

- `daemon-chaos-smoke` — runs **S02 + S03** only (fastest, broadest coverage). Command must invoke pytest with the two specific test files:
  ```
  uv run pytest tests/integration/daemon_chaos/test_worktree_setup_mid_failure.py \
                tests/integration/daemon_chaos/test_fix_cycle_cap_exhaustion.py -v
  ```
  Plus the determinism meta-test from S01 (`test_harness_is_deterministic.py`).
- `daemon-chaos-full` — runs **all five** scenario modules + the meta-test:
  ```
  uv run pytest tests/integration/daemon_chaos/ -v
  ```

Match the existing Makefile target style (use `.PHONY`, use `uv run pytest`, use the same `-v` flag pattern as `test-integration`). Add a short comment above each target explaining the intent.

### 2. GitHub Actions workflow

Create `.github/workflows/daemon-chaos.yml`:

- Triggers:
  - `pull_request` (any branch) → runs `make daemon-chaos-smoke` job. **Blocking** (must pass for PR merge).
  - `push` to `main` → same smoke job (catches any drift on the trunk).
  - `schedule: cron` (recommend nightly at 02:00 UTC) → runs `make daemon-chaos-full`. **Non-blocking**; results reported via existing Allure pipeline (model after `e2e.yml` or `test-quality.yml`).
  - `workflow_dispatch` (manual trigger) → runs `make daemon-chaos-full`.
- Job structure: one job per Makefile target (`daemon-chaos-smoke`, `daemon-chaos-full`); use `if:` conditions on triggers so only the right job fires per event type.
- Reuse the existing checkout + uv-sync + db-up steps from `e2e.yml` (or whatever pattern the most recent workflow uses — match by example, don't invent).
- Upload pytest output + (if available) Allure artifacts on failure.

### 3. Workflow skill — add the 9th canonical gate

Edit `skills/iw-workflow/SKILL.md`:

- In the "canonical QV gate chain" list (around line 141), add `daemon-chaos-smoke` as gate #9 (after `security-secrets`):
  ```
  9. `daemon-chaos-smoke` — `make daemon-chaos-smoke` (deterministic fault-injection smoke: worktree-setup-mid-failure + fix-cycle-cap-exhaustion; F-00089)
  ```
- In the JSON example block (around line 132), add the corresponding `qv-gate` entry as `S17` or wherever the canonical example places gate #9:
  ```json
  {"step": "S17", "agent": "qv-gate", "gate": "daemon-chaos-smoke", "command": "make daemon-chaos-smoke", "description": "QV: Daemon chaos smoke (S02 + S03 from F-00089)", "timeout": 900}
  ```
- Add a short paragraph below the existing `security-secrets` paragraph explaining the new gate (similar prose style — what it runs, why, with the F-00089 reference).

After editing the master copy, run:

```bash
uv run iw sync-skills --force iw-workflow
```

This writes the mirror at `.claude/skills/iw-workflow/SKILL.md`. **Both files** must appear in your `files_changed`. Verify byte-for-byte agreement with `diff skills/iw-workflow/SKILL.md .claude/skills/iw-workflow/SKILL.md`.

### 4. Critical — do NOT enforce the new gate on this Feature

The new `daemon-chaos-smoke` gate is now part of the canonical chain in `skills/iw-workflow/SKILL.md`. It applies to **future** work items, NOT to F-00089 itself (a gate cannot gate its own delivery). F-00089's own `workflow-manifest.json` (separately authored) uses only the existing 8 canonical gates. Verify this before reporting completion: open `ai-dev/active/F-00089/workflow-manifest.json` and confirm `daemon-chaos-smoke` does NOT appear in any `qv-gate` step.

### 5. Follow project conventions

Read `CLAUDE.md`. Match existing Makefile / workflow style exactly. Do NOT introduce new patterns.

## TDD Requirement

This step is **wire-up + skill text**, not behavioural code. Use `"n/a — wire-up step: Makefile targets, GH workflow YAML, skill text edit; no production behavioural logic"` in `tdd_red_evidence`.

You SHOULD still locally verify the Makefile targets work:

```bash
make daemon-chaos-smoke   # Must run S02 + S03 + meta-test, must exit 0
make daemon-chaos-full    # Must run all 5 scenarios + meta-test, must exit 0
```

If either fails, fix the Makefile target (not the tests).

You SHOULD validate the YAML syntax of the new workflow with `yamllint .github/workflows/daemon-chaos.yml` or `python -c "import yaml; yaml.safe_load(open('.github/workflows/daemon-chaos.yml'))"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — all must pass. (Lint may flag the new Makefile target if the project lints `Makefile`; check `make lint`'s scope.)

## Test Verification (NON-NEGOTIABLE)

Verify both Makefile targets exit 0:

```bash
make daemon-chaos-smoke
make daemon-chaos-full
```

Do NOT run other test suites. Do NOT report `tests_passed: true` unless both targets exit 0.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "Backend",
  "work_item": "F-00089",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "Makefile",
    ".github/workflows/daemon-chaos.yml",
    "skills/iw-workflow/SKILL.md",
    ".claude/skills/iw-workflow/SKILL.md"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "daemon-chaos-smoke: PASS, daemon-chaos-full: PASS",
  "tdd_red_evidence": "n/a — wire-up step: Makefile targets, GH workflow YAML, skill text edit; no production behavioural logic",
  "blockers": [],
  "notes": "Confirm both Makefile target invocations pass. Confirm diff(skills/iw-workflow/SKILL.md, .claude/skills/iw-workflow/SKILL.md) is empty. Confirm F-00089's own workflow-manifest.json does NOT include daemon-chaos-smoke."
}
```
