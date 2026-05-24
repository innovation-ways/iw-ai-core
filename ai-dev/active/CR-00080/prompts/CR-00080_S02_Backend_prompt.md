# CR-00080_S02_Backend_prompt

**Work Item**: CR-00080 -- Widen mutmut mutation-testing scope from `orch/daemon/` to all of `orch/`, run a second spike, and flip the mutation gate from informational to blocking
**Step**: S02
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy (see S01 prompt for the full text). This step does not need any container changes; if you find yourself reaching for `docker compose`, you are out of scope.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does not touch migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00080 --json`.
- `ai-dev/active/CR-00080/CR-00080_CR_Design.md` -- Design document (especially AC2 and AC3 — gate is nightly-only; AC3 has a viability guard you MUST apply BEFORE the threshold formula)
- `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt` -- S01's output. READ THIS FIRST — this is the data driving the viability decision.
- `ai-dev/work/CR-00080/reports/CR-00080_S01_Backend_report.md` -- S01 report
- Existing `.github/workflows/` directory layout (study any existing workflow file before writing yours)
- Earlier QV-gate / threshold precedents: `Makefile` `diff-coverage` (CR-00047), `security-secrets` (CR-00050)

## Output Files

If the AC3 viability guard PASSES:
- `.github/workflows/mutation.yml` -- new nightly blocking workflow
- `ai-dev/work/CR-00080/reports/CR-00080_S02_Backend_report.md` -- Step report

If the AC3 viability guard FAILS (S02 reports `completion_status: blocked`):
- `ai-dev/work/CR-00080/reports/CR-00080_S02_Backend_report.md` -- Step report ONLY (no workflow file is created)

You MUST NOT touch `skills/iw-workflow/SKILL.md` or `.claude/skills/iw-workflow/SKILL.md` in this step under any circumstance — the canonical QV chain is unchanged. mutmut lives on the nightly surface only.

## Context

You are implementing the second of three implementation steps for **Widen mutmut mutation-testing scope from `orch/daemon/` to all of `orch/`, run a second spike, and flip the mutation gate from informational to blocking**.

S01 measured the second spike. Your job has three parts in strict order:

1. **Apply the AC3 viability guard.** If it fails, STOP — report `blocked` and do not create the workflow file.
2. **Pick the blocking mutation-score threshold T** using the band-based margin rule.
3. **Wire the gate as `.github/workflows/mutation.yml`** — nightly schedule + workflow_dispatch, blocking on threshold breach.

Read the design document's **AC2** and **AC3** in full before starting — they encode the exact rules.

## Requirements

### 1. Read the spike measurements

Open `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt`. Record:
- `M` = measured mutation score (percent, integer or float)
- `K` = mutants killed + mutants survived (the "exercised" mutant count; do NOT count `timeout` or `skipped`)
- `partial?` = whether S01 reported a partial run

If the evidence file is missing or unreadable, STOP and raise a blocker (this means S01 did not complete; nothing for S02 to do).

### 2. Apply the AC3 viability guard FIRST

Before doing anything else, check:

- If `M < 20%` OR `K < 30`:
  - DO NOT create `.github/workflows/mutation.yml`.
  - DO NOT pick a threshold.
  - Report `completion_status: blocked` with these fields in the step report:
    - `viability: failed`
    - `measured_M: <value>`
    - `measured_K: <value>`
    - `reason: <"M below 20% floor" | "K below 30-mutant floor" | "both">`
    - `recommended_next_step: <verbatim suggestion to the operator — typically: "Expand test coverage in the most-mutated modules (see per-module breakdown in evidence file), then re-run this CR. Alternatively, run a longer manual spike (`make mutation-audit` outside the 3600s budget) to gather more data before re-running.">`
  - Stop here. Do not proceed to Requirement 3 or 4.

If `M >= 20%` AND `K >= 30`: proceed.

### 3. Choose the blocking mutation-score threshold T

Apply the band rule:

| Measured M band | margin | T |
|-----------------|--------|---|
| `M >= 70`       | 5      | `round_down(M) - 5` |
| `50 <= M < 70`  | 3      | `round_down(M) - 3` |
| `20 <= M < 50`  | 2      | `round_down(M) - 2` |

`round_down` is integer floor — for `M = 67.4%`, `round_down(M) = 67`, `T = 67 - 3 = 64`.

Record `T` (the integer percentage) in the step report.

### 4. Wire the gate as `.github/workflows/mutation.yml`

Create the file with this structure (top-of-file comment first, then the YAML):

```yaml
# CR-00080 nightly mutation-testing gate
#
# Threshold T=<N>% chosen at CR-00080 (measured M=<M>%, K=<K> exercised mutants,
# margin <margin> points per the CR-00047 ratchet pattern). Raise T over time as
# test coverage improves — see docs/IW_AI_Core_Testing_Strategy.md §8.
#
# This workflow runs `make mutation-audit` against the full `orch/` package once
# per day. The job fails (non-zero exit) when the measured mutation score drops
# below T. There is intentionally NO `continue-on-error: true` and NO `|| true`
# — the gate is blocking by design.

name: mutation
on:
  schedule:
    - cron: '0 6 * * *'   # 06:00 UTC daily
  workflow_dispatch: {}    # manual trigger for testing the workflow before nightly fires

permissions:
  contents: read

jobs:
  mutation-audit:
    runs-on: ubuntu-latest
    timeout-minutes: 240   # 4h ceiling; nightly cadence absorbs the cost
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      - name: Sync dependencies
        run: uv sync --frozen
      - name: Run mutation audit
        run: |
          set -o pipefail
          make mutation-audit | tee mutation-output.txt
      - name: Enforce threshold
        env:
          MUTATION_THRESHOLD: '<T>'
        run: |
          set -euo pipefail
          SCORE=$(python -c "
          import re, sys
          out = open('mutation-output.txt').read()
          # Parse 'Mutation score: NN%' lines (per-module + total).
          # The 'total' or final score is the one that matters; if multiple,
          # take the last 'Mutation score: <pct>%' line.
          m = re.findall(r'Mutation score:\\s*([0-9]+(?:\\.[0-9]+)?)\\s*%', out)
          if not m:
              sys.stderr.write('FATAL: no mutation score parsed from output\\n')
              sys.exit(2)
          print(int(float(m[-1])))
          ")
          echo "Measured mutation score: ${SCORE}% (threshold: ${MUTATION_THRESHOLD}%)"
          if [ "${SCORE}" -lt "${MUTATION_THRESHOLD}" ]; then
            echo "FAIL: mutation score ${SCORE}% below threshold ${MUTATION_THRESHOLD}%"
            exit 1
          fi
      - name: Upload audit output
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: mutation-output
          path: mutation-output.txt
          retention-days: 30
```

Substitute the bracketed values:
- `<N>` and `<T>` → the integer threshold from Requirement 3 (same number, used in two places).
- `<M>` → the measured mutation score from S01's evidence.
- `<K>` → the killed+survived count from S01's evidence.
- `<margin>` → 5 / 3 / 2 per the band.

The `set -o pipefail` line is required so a non-zero exit from `make mutation-audit` is not swallowed by `tee`.

Match the existing repo's GH workflow style if any workflow files already exist under `.github/workflows/` (check uv install action version, checkout action version, naming conventions). If no workflows exist, the structure above is canonical.

### 5. Validate the workflow YAML

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/mutation.yml'))"
```

Should print nothing (and exit 0). If `actionlint` happens to be installed in the worktree, also run:

```bash
actionlint .github/workflows/mutation.yml
```

After commit, optionally trigger the workflow manually (`gh workflow run mutation.yml`) and link the run ID in the step report. If `gh` is not available or the worktree lacks repo permissions, skip — S02's contract is "wire the gate", not "prove the gate works in the GH UI".

## Project Conventions

Read `CLAUDE.md`. Study any existing files under `.github/workflows/` before writing yours — match the action versions and naming style used there if present.

## TDD Requirement

This step is wiring + config — there is no new behavioural code to RED-first. Use `tdd_red_evidence: "n/a — gate-wiring + workflow YAML, no production logic"` in the result contract.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. **`make format`** — N/A for YAML edits; run anyway and confirm zero drift.
2. **`make typecheck`** — N/A; run anyway and confirm zero new errors.
3. **`make lint`** — must report zero errors.

## Test Verification (NON-NEGOTIABLE)

- YAML-validate the workflow YAML as described in Requirement 5.
- Do NOT run `make test-unit` or `make test-integration` — they are S10 / S11 QV gates.
- Do NOT run `make mutation-audit` here — it is S01's responsibility, and re-running it would burn budget for no new evidence.

## Subagent Result Contract

If viability PASSES and the gate is wired:

```json
{
  "step": "S02",
  "agent": "Backend",
  "work_item": "CR-00080",
  "completion_status": "complete",
  "files_changed": [
    ".github/workflows/mutation.yml"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "workflow YAML validated via yaml.safe_load (and actionlint if available)",
  "tdd_red_evidence": "n/a — gate-wiring + workflow YAML, no production logic",
  "blockers": [],
  "notes": "Viability guard PASSED (M=<value>%, K=<value>). Threshold T=<value>% (band: <M-band>, margin <N> points). Workflow created at .github/workflows/mutation.yml; nightly schedule 06:00 UTC + workflow_dispatch; blocking on score<T."
}
```

If viability FAILS:

```json
{
  "step": "S02",
  "agent": "Backend",
  "work_item": "CR-00080",
  "completion_status": "blocked",
  "files_changed": [],
  "preflight": {
    "format": "skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "no tests applicable — gate not wired",
  "tdd_red_evidence": "n/a — viability guard fired before any code changes",
  "blockers": [
    "AC3 viability guard failed: M=<value>%, K=<value>. <reason>. Recommended next step: <verbatim suggestion>."
  ],
  "notes": "Workflow file deliberately NOT created. The design's safety rail refuses to wire a meaningless threshold (T <= 0 or below the 20% floor). S03 will record the deferred state in tracker / strategy doc / skill instead of marking DONE."
}
```

- A `blocked` status here is the design's INTENDED outcome when the spike data is too thin — it is not a failure of the agent. The orchestrator should NOT auto-retry S02 in this case; the operator must address the recommended next step and re-run the whole CR.
