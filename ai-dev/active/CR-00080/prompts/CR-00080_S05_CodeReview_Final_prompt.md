# CR-00080_S05_CodeReview_Final_prompt

**Work Item**: CR-00080 -- Widen mutmut mutation-testing scope from `orch/daemon/` to all of `orch/`, run a second spike, and flip the mutation gate from informational to blocking
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Standard policy. This final review does not require container changes.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. Verify no migrations were added (no files under `orch/db/migrations/versions/**`).

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00080 --json`.
- `ai-dev/active/CR-00080/CR-00080_CR_Design.md` -- Design document
- `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt`
- All step reports under `ai-dev/work/CR-00080/reports/`
- All files modified by S01..S03 (collected from the three `files_changed` lists)

## Output Files

- `ai-dev/work/CR-00080/reports/CR-00080_S05_CodeReview_Final_report.md`

## Context

You are performing the global cross-agent review. S04 already reviewed each implementation step in isolation. Your job is to verify the whole-CR shape: that all five acceptance criteria are satisfied end-to-end (or correctly deferred when S02's viability guard fires), that the threshold and gate state are internally consistent across every surface they appear on, and that there is no scope creep or hidden coupling — particularly that the canonical QV chain in `skills/iw-workflow/SKILL.md` is untouched.

## Review Checklist

### 1. AC1 end-to-end: scope widened and spike completed

- `pyproject.toml` `paths_to_mutate = "orch/"` (read the actual file).
- Cov-fail-under bug is fixed (verify by reading the runner string).
- `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt` exists, is non-empty, and contains the required fields (wall-clock, mutants generated > 0, killed, surviving, mutation score, per-module breakdown). If the file says `[PARTIAL — terminated at ...]`, that is acceptable per the design's Notes (S01 budget rule).
- `tests/unit/test_mutmut_setup.py` asserts the new `"orch/"` scope.

### 2. AC2 end-to-end: gate runs as a blocking nightly GH workflow (or is deferred)

**Branch on S02's `completion_status` from the report:**

**If `complete` (gate wired):**
- `.github/workflows/mutation.yml` exists and is valid YAML.
- Triggers include `schedule: - cron: '0 6 * * *'` AND `workflow_dispatch: {}`.
- Has `permissions: contents: read`.
- The threshold step uses `set -euo pipefail` and exits 1 on `SCORE < T`.
- NO `continue-on-error: true`. NO `|| true`. NO `if: failure()` swallowing the threshold step.
- `set -o pipefail` is set on the `make mutation-audit | tee ...` line.

**If `blocked` (gate deferred):**
- `.github/workflows/mutation.yml` does NOT exist.
- The S02 report documents `viability: failed` with measured M, K, reason, and recommended next step.

**Both:** `skills/iw-workflow/SKILL.md` is UNCHANGED (`git diff origin/main..HEAD -- skills/iw-workflow/SKILL.md .claude/skills/iw-workflow/SKILL.md` is empty). Any modification is a CRITICAL scope violation — mutmut lives on the nightly surface only.

### 3. AC3 end-to-end: viability guard + threshold formula

- Read `M` and `K` from the evidence file.
- **Viability guard verdict** must match S02's status:
  - `M >= 20%` AND `K >= 30` → S02 MUST be `complete`. If S02 is `blocked` here, that is a CRITICAL finding (gate should have been wired).
  - `M < 20%` OR `K < 30` → S02 MUST be `blocked`. If S02 is `complete` here, that is a CRITICAL finding (gate should have been deferred).
- **Threshold T** (only when S02 is `complete`):
  - Read `T` from `.github/workflows/mutation.yml`.
  - Confirm `T = round_down(M) − margin`, margin = 5 (M>=70), 3 (50<=M<70), 2 (20<=M<50).
  - The same `T` integer must appear in: workflow YAML, strategy doc §5 + §8, tracker §9 gate matrix + §11 changelog, skill mutmut section. Mismatch is a HIGH finding.

### 4. AC4 end-to-end: tracker + strategy + skill reflect the correct state

**Viable path (S02 complete):**

Run `grep -n "P2-CR-A-followup-mutation-block" ai-dev/work/TESTS_ENHANCEMENT.md` — every match must say DONE (CR-00080), no IN PROGRESS or TODO references remaining. Same for "item 2.1" / "Adopt mutation testing in CI" / "item 4.8" / "Tighten mutation gate to blocking".

`docs/IW_AI_Core_Testing_Strategy.md` §5 / §8 / §9 must be internally consistent with the tracker on "nightly GH workflow", threshold T, and the spike numbers.

`skills/iw-ai-core-testing/SKILL.md` mutmut section must reflect widened scope + nightly blocking gate. The historical "Earlier behaviour (CR-00059)" note should be preserved (HIGH finding if silently removed — mirror CR-00049 precedent).

**Blocked path (S02 blocked):**

Tracker entries for `P2-CR-A-followup-mutation-block` / item 2.1 / item 4.8 stay IN PROGRESS (or OPEN for 4.8) with the CR-00080 deferred annotation explaining M, K, and the recommended next step. `docs/IW_AI_Core_Testing_Strategy.md` §8 ends with the deferred state. Skill mutmut section says "config widened, gate wiring deferred". The deferred-state phrasing must be consistent across all surfaces.

**Both paths:** `.claude/skills/iw-ai-core-testing/SKILL.md` ↔ master byte-equality verified by `diff` (zero output).

### 5. AC5 end-to-end: no out-of-scope files

Run `git diff origin/main..HEAD --name-only`. Cross-check every entry against `workflow-manifest.json:scope.allowed_paths`. Every modified file must match one of the listed globs OR be under `ai-dev/active/CR-00080/**` OR `ai-dev/archive/CR-00080/**` (implicit allowance).

Especially verify:
- Zero files under `orch/` (except those listed — none in this CR's scope).
- Zero files under `dashboard/`.
- Zero files under `executor/`.
- Zero files under `orch/db/migrations/versions/**`.
- Zero modification to `skills/iw-workflow/SKILL.md` or `.claude/skills/iw-workflow/SKILL.md` (these were deliberately removed from `scope.allowed_paths` because the canonical QV chain is unchanged).
- No new dependencies in `pyproject.toml` `dependencies` (verify by `git diff origin/main..HEAD -- pyproject.toml` and reading only the `dependencies` array — the `[tool.mutmut]` change is allowed).

### 6. Cross-surface consistency audit

**If S02 is `complete`:** Grep for "nightly GH workflow" (canonical phrasing) and the threshold integer T across all touched files:

```bash
grep -rn "nightly GH workflow" docs/IW_AI_Core_Testing_Strategy.md ai-dev/work/TESTS_ENHANCEMENT.md skills/iw-ai-core-testing/SKILL.md
grep -rn "<T-value>" docs/IW_AI_Core_Testing_Strategy.md ai-dev/work/TESTS_ENHANCEMENT.md skills/iw-ai-core-testing/SKILL.md .github/workflows/mutation.yml
```

Every match must agree. Naming drift (e.g., "GitHub Actions nightly" in one place, "nightly workflow" in another) is a MEDIUM(fixable) finding — "nightly GH workflow" is the canonical phrasing.

**If S02 is `blocked`:** Grep for the measured M and K values, and the recommended-next-step phrasing, across the strategy doc / tracker / skill. Drift in M / K / next-step wording across surfaces is a HIGH finding.

### 7. RED-first audit (S01 only)

S01's `tdd_red_evidence` must record an actual `AssertionError`, not `ImportError` / collection error / fixture error. S02 and S03 must use `"n/a — …"` (wiring / docs steps).

### 8. Tests verification

Run the project's unit test command to confirm no regression:

```bash
uv run pytest tests/unit/test_mutmut_setup.py -v
```

(Per the design: a one-file targeted run. Full-suite verification is owned by S10 / S11 QV gates.)

## Severity Levels

Same as S04. A "pass" verdict requires zero CRITICAL + zero HIGH + zero MEDIUM(fixable).

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "CR-00080",
  "step_reviewed": "S01..S04",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "1 passed (test_mutmut_setup.py); cross-surface grep confirms surface + threshold consistent",
  "notes": ""
}
```
