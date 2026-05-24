# CR-00080_S04_CodeReview_prompt

**Work Item**: CR-00080 -- Widen mutmut mutation-testing scope from `orch/daemon/` to all of `orch/`, run a second spike, and flip the mutation gate from informational to blocking
**Steps Being Reviewed**: S01 (Backend — spike + scope widen) + S02 (Backend — gate wiring) + S03 (Backend — docs + tracker + skill sync)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy. This review does not require any container changes.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. There are no migrations in this CR; verify that S01..S03 did NOT add any (no files under `orch/db/migrations/versions/**`).

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00080 --json`.
- `ai-dev/active/CR-00080/CR-00080_CR_Design.md` -- Design document (read AC1..AC5 in full BEFORE opening any changed file)
- `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt` -- S01's spike output
- `ai-dev/work/CR-00080/reports/CR-00080_S01_Backend_report.md`
- `ai-dev/work/CR-00080/reports/CR-00080_S02_Backend_report.md`
- `ai-dev/work/CR-00080/reports/CR-00080_S03_Backend_report.md`
- All files listed in each report's `files_changed`

## Output Files

- `ai-dev/work/CR-00080/reports/CR-00080_S04_CodeReview_report.md`

## Context

You are performing a single per-agent review covering all three Backend implementation steps (S01, S02, S03). Read the design document first — every Acceptance Criterion is a mandatory check.

## Read the Design Document FIRST

- Read AC1..AC5 in full.
- Write down every file the design lists in the File Manifest and Impacted Paths section.
- Cross-check against the three implementation reports' `files_changed` lists. If the design names a file that no report mentions, that is a CRITICAL finding (unless the file is `.github/workflows/mutation.yml` and S02 reported `blocked` — per AC3 the viability guard refuses to wire the gate when spike data is too thin, and an absent file in that case is correct, not a finding).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Fix nothing yourself — only report. Any NEW violation in S01..S03's changed files vs. `main` is a CRITICAL finding with `"category": "conventions"`.

## Review Checklist

### 1. S01 — Spike + scope widen

- **Cov-fail-under fix lands**: `pyproject.toml` `[tool.mutmut].runner` and/or `Makefile` `mutation-check` + `mutation-audit` recipes pass `--cov-fail-under=0` (or document the equivalent override). Verify by reading the actual runner string.
- **Scope widened**: `pyproject.toml` `paths_to_mutate = "orch/"` (NOT `"orch/daemon/"`).
- **Makefile audit loop widened**: `find orch/ -name "*.py" -not -name "__init__.py" -not -path "*/__pycache__/*" -not -path "*/migrations/*"`. Migrations excluded is a hard requirement (no useful mutation testing on alembic revision files).
- **Guard test updated**: `tests/unit/test_mutmut_setup.py` asserts `"orch/"`. The S01 report's `tdd_red_evidence` records `AssertionError: assert 'orch/daemon/' == 'orch/'` (or equivalent) — confirm plausibility.
- **Evidence file exists**: `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt` is present and contains: total wall-clock, mutants generated, killed, surviving, mutation score, per-module breakdown. A `[PARTIAL — terminated at ...]` prefix is acceptable if S01 reported `partial` status.
- **Comment block rewritten**: the comment above `[tool.mutmut]` in `pyproject.toml` cites CR-00080 (not "CR-00059, P2-CR-A-followup-...").

### 2. S02 — Gate wiring (nightly GH workflow only) + viability guard

**First, branch on S02's `completion_status`** (read the report):

- If `complete`: the viability guard PASSED, the workflow file MUST exist, and the threshold MUST follow the band rule. Apply the "viable" checks below.
- If `blocked`: the viability guard FAILED, the workflow file MUST NOT exist, and the step report MUST document the measured M / K and a recommended next step. Apply the "blocked" checks below.

**Viable path checks:**

- **Viability guard correctly applied**: read `M` and `K` from the evidence file. Confirm `M >= 20%` AND `K >= 30`. A `complete` status with `M < 20%` OR `K < 30` is a CRITICAL finding (the guard should have fired).
- **Threshold T per AC3 band rule**: T = round_down(M) − margin, where margin = 5 (M>=70), 3 (50<=M<70), 2 (20<=M<50). Compute T from the evidence's M; compare to the value embedded in `.github/workflows/mutation.yml`. Any mismatch is a CRITICAL finding.
- **Workflow file exists at `.github/workflows/mutation.yml`**: confirm by reading. Must contain:
  - `schedule: - cron: '0 6 * * *'` AND `workflow_dispatch: {}` triggers.
  - `permissions: contents: read` (minimal).
  - A threshold-enforcement step that exits non-zero on `SCORE < T`.
  - `set -o pipefail` on the `make mutation-audit | tee ...` line (otherwise the audit's non-zero exit is swallowed).
  - **NO** `continue-on-error: true`. **NO** `|| true`. **NO** `if: failure()` swallowing the threshold step. Any one of these is a CRITICAL finding.
- **Workflow YAML validity**: run `python -c "import yaml; yaml.safe_load(open('.github/workflows/mutation.yml'))"` — must succeed (no output).
- **Top-of-file comment cites T, M, K, margin** per the design's AC3 documentation requirement.

**Blocked path checks:**

- **Viability guard correctly fired**: read `M` and `K` from the evidence file. Confirm `M < 20%` OR `K < 30`. A `blocked` status with M>=20% AND K>=30 is a CRITICAL finding (the guard should have passed and the workflow should have been wired).
- **Workflow file does NOT exist**: `ls .github/workflows/mutation.yml` MUST fail. A `blocked` status with the workflow file present is a CRITICAL finding.
- **Step report documents the deferred state**: must include measured M, K, the reason, and a recommended next step. Missing any of these is a HIGH finding.

**Both paths:**

- **`skills/iw-workflow/SKILL.md` UNCHANGED**: run `git diff origin/main..HEAD -- skills/iw-workflow/SKILL.md .claude/skills/iw-workflow/SKILL.md`. Output MUST be empty. The canonical QV chain is out of scope for this CR; any modification is a CRITICAL scope violation.

### 3. S03 — Docs / tracker / skill

**Branch on S02's outcome** (S03 should have followed the same branch):

**Viable path:**
- **Strategy doc**: §5 gate-table row updated to "blocking nightly GH workflow, T=<N>%", §8 mutation-testing section rewritten to second-spike narrative (with M, K, T, viability guard, ratchet rule), §9 gap row closed.
- **Tracker**: §5 `P2-CR-A-followup-mutation-block` → DONE (CR-00080), §6 item 2.1 → DONE, §8 item 4.8 → DONE, §9 gate matrix updated, §10 mutation-cost question answered with W + per-mutant cost, §11 changelog entry dated 2026-05-24.
- **Skill**: `skills/iw-ai-core-testing/SKILL.md` mutmut section reflects widened scope + nightly blocking gate + threshold T. Historical "Earlier behaviour (CR-00059)" note preserved (mirror CR-00049 pattern).
- **Cross-surface consistency**: "nightly GH workflow" and threshold T appear identically across strategy doc, tracker, skill, and `.github/workflows/mutation.yml`. Inconsistency is a HIGH finding (`category: conventions`).

**Blocked path:**
- **Strategy doc**: §5 row marked DEFERRED with M / K / next step, §8 rewritten but ending with the deferred state, §9 gap row stays open with the CR-00080 annotation.
- **Tracker**: §5 / §6 / §8 entries stay IN PROGRESS with the deferred annotation; §10 mutation-cost question answered (even with partial data) but with the deferred-wiring conclusion; §11 changelog records the attempt.
- **Skill**: mutmut section reflects "config widened, gate wiring deferred"; historical CR-00059 breadcrumb preserved.
- **Cross-surface consistency**: deferred-state phrasing + M / K / recommended-next-step appear identically across strategy doc §8, tracker §5/§6/§8/§10/§11, and skill. Inconsistency is a HIGH finding.

**Both paths:**
- `.claude/skills/iw-ai-core-testing/SKILL.md` byte-identical to master (verify by `diff` — must be empty).
- `skills/iw-workflow/SKILL.md` and `.claude/skills/iw-workflow/SKILL.md` UNCHANGED (re-verify here; any touch is a CRITICAL scope violation).

### 4. Scope compliance (CRITICAL — AC5)

Run `git diff origin/main..HEAD --name-only` and verify every modified file is in the manifest's `scope.allowed_paths`. Any file outside the list is a CRITICAL finding. Particularly check:

- NO files under `orch/` except those listed.
- NO files under `dashboard/` / `executor/`.
- NO files under `orch/db/migrations/versions/**`.
- NO modification to `skills/iw-workflow/SKILL.md` or `.claude/skills/iw-workflow/SKILL.md` — these were intentionally removed from `scope.allowed_paths` because the canonical QV chain is unchanged by this CR.

### 5. TDD RED Evidence (S01 only — Backend behaviour-implementing)

S02 and S03 add no behavioural tests → expect `tdd_red_evidence: "n/a — …"` in their reports. That is correct, NOT a finding.

S01 adds a test assertion change. Verify:
1. The `tdd_red_evidence` field shows `AssertionError` (not `ImportError`, not collection error).
2. Reason: would the new assertion fail against pre-change `pyproject.toml`? Yes — the assertion compares against `"orch/"` while the pre-change value was `"orch/daemon/"`. Plausible RED.

### 6. Architecture compliance

- No new production code outside `orch/daemon/` — confirmed by scope check.
- No new dependencies (verify `pyproject.toml` `dependencies` list unchanged — only the `[tool.mutmut].paths_to_mutate` value changed).
- Skill sync ran with `--force` (per CR-00049 precedent for project-override skills).

## Test Verification (NON-NEGOTIABLE)

1. Run `uv run pytest tests/unit/test_mutmut_setup.py -v` — must pass with the widened assertion.
2. Run `diff skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md` — must be empty.
3. Run `git diff origin/main..HEAD -- skills/iw-workflow/SKILL.md .claude/skills/iw-workflow/SKILL.md` — must be empty (this CR does NOT touch the canonical QV chain).
4. If S02 reported `complete`: `python -c "import yaml; yaml.safe_load(open('.github/workflows/mutation.yml'))"` — must succeed.
5. If S02 reported `blocked`: verify `.github/workflows/mutation.yml` does NOT exist.

Do NOT run `make test-unit` or `make test-integration` — those are S10 / S11 QV gates.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, scope violation, gate not blocking | Must fix before merge |
| **HIGH** | Surface/threshold inconsistency across files, missing tracker update | Must fix before merge |
| **MEDIUM (fixable)** | Convention violation, missing comment, stale historical note | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Better wording for the threshold rule | Optional |
| **LOW** | Nitpick | Informational only |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00080",
  "step_reviewed": "S01+S02+S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "1 passed (test_mutmut_setup.py); diffs empty (skill sync verified)",
  "notes": ""
}
```

- `verdict: pass` iff zero CRITICAL + zero HIGH + zero MEDIUM(fixable) findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM(fixable) total.
