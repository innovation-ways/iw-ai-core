# F-00089_S10_CodeReview_Final_prompt

**Work Item**: F-00089 -- Daemon chaos / fault-injection test layer
**Review Step**: S10 (Final Review)
**Implementation Steps Reviewed**: S01..S08
**Per-Agent Review**: S09

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations involved. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status F-00089 --json` — runtime step state.
- `ai-dev/work/F-00089/F-00089_Feature_Design.md` — Design document (read in full).
- All implementation step reports: `ai-dev/work/F-00089/reports/F-00089_S0[1-8]_Backend_report.md`.
- S09 per-agent review report: `ai-dev/work/F-00089/reports/F-00089_S09_CodeReview_report.md`.
- All files in all `files_changed` arrays.

## Output Files

- `ai-dev/work/F-00089/reports/F-00089_S10_CodeReview_Final_report.md` — Final review report.

## Context

You are performing the **final cross-step review** of all implementation work for F-00089. S09 already covered each step in isolation; your job is the cross-cutting picture — does the harness API agree across all six users? Do the docs cross-link correctly? Is the smoke subset truly the same in Makefile, GH workflow, strategy doc, and skill? Is the test layer truly invisible to production?

This step's mandate is "catch what per-step review couldn't". The pattern that bit CR-00076 (per-step "looks fine", composition "context-overflowed") and I-00075 (per-step "render path correct", new fixture exercised an unreviewed branch in a shared template) is the prior to look for here.

## Read the Design Document FIRST

Read the design doc before opening code:

- AC1..AC8 — every criterion is mandatory.
- Invariants 1..10 — verify each one is enforced (not just believed).
- TDD Approach — verify every named test file appears in some step's `files_changed`. Missing entries = CRITICAL.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any new violation = CRITICAL.

## Review Checklist

### 1. Completeness vs design (CRITICAL per missing)

- Every AC has at least one test that exercises it. Walk AC1 → AC8 and name the test(s) that prove each.
- Every Invariant is either tested or enforced by infrastructure (the merge-time scope gate, the live-DB guard test, etc.). Walk Invariant 1 → 10 and name the enforcement.
- Every Boundary Behavior row has a test. Walk the table; any missing row = CRITICAL.

### 2. Harness API agreement across all consumers (CRITICAL per mismatch)

Open all of these and diff the hook lists:

- `tests/integration/daemon_chaos/harness.py` (module docstring).
- All five scenario test modules (which hooks they actually call).
- `skills/iw-workflow/SKILL.md` (S07 — gate-canon update mentions the smoke subset).
- `skills/iw-ai-core-testing/SKILL.md` (S08 — new harness section).
- `docs/IW_AI_Core_Testing_Strategy.md` (S08 — Layer 9 entry).

All five must reference the same hook names, the same signature shapes, the same smoke subset (S02 + S03). Any drift = CRITICAL.

### 3. Test-only scope (CRITICAL per row)

- `git diff main` against `orch/**`, `dashboard/**`, `executor/**`, `orch/db/migrations/**` must be EMPTY (Invariants 1 + 4).
- All scenario tests that use `xfail` use `strict=True` and reference a filed Incident ID (Invariant 5).

### 4. Cross-doc consistency (HIGH per drift)

- The smoke subset (S02 + S03) is named identically in Makefile, GH workflow, strategy doc, testing skill, workflow skill.
- The tracker (`ai-dev/work/TESTS_ENHANCEMENT.md`) §8 row 4.3 status, the v1.4 header date, and the §11 changelog entry agree with what S07/S08 actually shipped.
- The daemon-design doc's cross-link to the new test layer is concrete (file paths or Layer 9 reference), not handwave.

### 5. The new gate is NOT on F-00089's own manifest (CRITICAL)

Open `ai-dev/active/F-00089/workflow-manifest.json` and grep for `daemon-chaos-smoke`. It must NOT appear in any `qv-gate` step. Invariant 10. CRITICAL if it does.

### 6. The new gate IS on the canonical chain in the workflow skill (CRITICAL)

Open `skills/iw-workflow/SKILL.md`. The canonical QV gate chain list must now contain 9 gates, with `daemon-chaos-smoke` as #9. The JSON example block must include a corresponding `qv-gate` entry. CRITICAL if missing — the whole point of this Feature's wire-up step (S07) was this update.

### 7. Skill sync byte-for-byte (HIGH per mismatch)

- `diff skills/iw-workflow/SKILL.md .claude/skills/iw-workflow/SKILL.md` = empty.
- `diff -r skills/iw-ai-core-testing/ .claude/skills/iw-ai-core-testing/` = empty.

### 8. Determinism meta-test exists and runs clean (HIGH)

`tests/integration/daemon_chaos/test_harness_is_deterministic.py` must exist (S01 deliverable). Run it 10 times; assert the same result. If it's flaky, that's HIGH — the whole layer's value depends on this canary.

### 9. CR-00060 cross-link is honoured (MEDIUM)

S03 (fix-cycle cap exhaustion) is the runtime complement to CR-00060 / P2-CR-B. Verify the test file's docstring or a code comment cross-links to CR-00060. MEDIUM if missing.

### 10. I-00075 / I-00076 cross-link is honoured (MEDIUM)

S06 (migration-rebase failure) pins the I-00075/76 failure mode. Verify the test file cross-links to those Incidents. MEDIUM if missing.

### 11. Security (CRITICAL per row)

- No hardcoded secrets / credentials anywhere in the new code.
- No tests use real network calls or real external services.

## Test Verification (NON-NEGOTIABLE)

Run the **full** unit + integration suites:

```bash
make test-unit
make test-integration
```

Plus the chaos-specific smoke + full targets:

```bash
make daemon-chaos-smoke
make daemon-chaos-full
```

Report exact results. If `make test-integration` fails because of an unrelated pre-existing flake, note it but classify it MEDIUM (not CRITICAL) — unless the failure traces back to a chaos-test fixture leak.

## Severity Levels

Same table as S09. Add one row:

- **CRITICAL** also includes: missing AC coverage, missing Invariant enforcement, harness-API drift across multiple docs, new gate appearing on F-00089's own manifest, new gate missing from the canonical chain in the workflow skill.

## Review Result Contract

```json
{
  "step": "S10",
  "agent": "CodeReview_Final",
  "work_item": "F-00089",
  "steps_reviewed": ["S01","S02","S03","S04","S05","S06","S07","S08"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit, Y integration, Z chaos-smoke, W chaos-full — all passed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `cross_cutting: true` for any finding that spans multiple steps (most of yours).
