# CR-00087_S06_CodeReview_Final_prompt

**Work Item**: CR-00087 -- Auto-amend scope violations matching per-project allow-patterns
**Review Step**: S06 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

(Standard policy. See S01 prompt for full text. This step does not touch Docker.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This CR adds no migrations and you must not run `alembic upgrade`/`downgrade`/`stamp` against the live orch DB.)

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00087 --json`
- `ai-dev/active/CR-00087/CR-00087_CR_Design.md` — Design document (READ AC1..AC6 in full)
- `ai-dev/active/CR-00087/CR-00087_Functional.md` — Functional summary (sanity-check it still describes what shipped)
- All implementation step reports: `ai-dev/work/CR-00087/reports/CR-00087_S01_BackendImpl_report.md`, `_S02_BackendImpl_report.md`, `_S03_BackendImpl_report.md`, `_S04_TestsImpl_report.md`
- Per-agent review report: `ai-dev/work/CR-00087/reports/CR-00087_S05_CodeReview_report.md`
- All files listed in all implementation reports' `files_changed`

## Output Files

- `ai-dev/work/CR-00087/reports/CR-00087_S06_CodeReview_Final_report.md`

## Context

You are performing the **final cross-step review** of CR-00087. S05 reviewed all four impl steps in a single pass; your job is to catch issues that span steps and to verify the AC list end-to-end. The dominant cross-cutting concern in this CR is the **matcher-parity** chain: `_scope_match` was promoted to `scope_match`, then reused by both the violation detector inside `_complete_fix_cycle` and the auto-amend filter inside `should_auto_amend`. Any divergence between those two uses is a CRITICAL finding.

## Read the Design Document FIRST

Read ACs 1–6 in full. Carry every AC into your review as a first-class anchor — for each AC, record `PASS` or `FAIL` with the evidence (file + line or command output) that justifies the call.

Read the TDD section. Every test file the design names by path MUST appear in some impl report's `files_changed`:

- `tests/unit/daemon/test_project_registry_auto_amend_scope.py` — S01.
- `tests/unit/daemon/test_scope_amendment.py` — S02.
- `tests/unit/test_fix_cycle.py` — S03.
- `tests/integration/test_scope_amend_endpoints.py` — S04.

Missing → CRITICAL.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in changed files vs `main` → each one is a CRITICAL finding (`category: conventions`, exact violation code).

If a tool isn't available, STOP and raise a blocker.

## Review Checklist

### 1. AC walk-through (NON-NEGOTIABLE — explicit per-AC verdict)

For each of AC1..AC6 in the design doc, write a one-line PASS/FAIL with evidence.

- **AC1** (feature off by default): the S04 negative `test_complete_fix_cycle_does_not_auto_amend_when_feature_disabled` exists and passes. The default `auto_amend_allow_patterns == []` and `auto_amend_max_paths is None` for a config without the block. `git diff main -- .iw-orch.json` shows ONLY the commented-out `_auto_amend_scope_example` block.
- **AC2** (auto-amend fires when all match): the S04 positive test asserts BOTH events, manifest update, StepRun row, and step status transition. Run it targeted.
- **AC3** (partial match → no auto-amend): the S04 negative test for `orch/daemon/fix_cycle.py` mixed in with `tests/...` exists and passes.
- **AC4** (max_paths cap): the S04 negative test for 5 violations vs `max_paths=2` exists and passes.
- **AC5** (malformed config → off): the S01 unit-test matrix covers every malformed branch (non-dict, non-list, non-string entry, non-int max_paths, bool, negative).
- **AC6** (audit trail preserved): the S04 positive test asserts BOTH `scope_violation_escalation` AND `scope_auto_amended` events appear; payload includes `step_id`, `added_paths`, `manifests_updated`, `matched_patterns`.

### 2. Matcher-parity chain (the headline consistency check)

This is the cross-cutting failure mode most likely to slip past per-step review. Verify by reading **all three** sites and confirming they use the SAME matcher:

1. `orch/daemon/fix_cycle.py:scope_match` — the canonical implementation (was `_scope_match`).
2. `orch/daemon/fix_cycle.py:_complete_fix_cycle` — the violation detector. Inspect the comprehension that filters `agent_touched` paths against `allowed + implicit`. Confirm it calls `scope_match` (or the back-compat `_scope_match` alias pointing at the same function), NOT a separate matcher.
3. `orch/daemon/scope_amendment.py:should_auto_amend` — the auto-amend filter. Confirm it imports `scope_match` from `orch.daemon.fix_cycle` and uses it for every violation/pattern comparison.

Any of:
- `should_auto_amend` uses a different matcher (e.g. `_matches` from `scope_overlap.py`),
- `should_auto_amend` duplicates the body of `scope_match` instead of importing it,
- the rename was incomplete (still two functions doing the same job),

is a **CRITICAL** finding.

### 3. Backwards-compatibility chain (the second headline check)

Projects WITHOUT `auto_amend_scope` must see ZERO behavioural change. Verify all four ways the feature could leak in:

1. `ProjectConfig` defaults are `auto_amend_allow_patterns=[]` and `auto_amend_max_paths=None`.
2. `should_auto_amend([...], [], None)` returns `False` for ANY input (the `allow_patterns is non-empty` check is the first short-circuit).
3. `_try_auto_amend_after_escalation(project_config=None, ...)` short-circuits without DB or filesystem writes.
4. The S04 negative test `test_complete_fix_cycle_does_not_auto_amend_when_feature_disabled` exists and runs the full integration path with `auto_amend_allow_patterns=[]`, asserting no manifest write, no new StepRun, no `scope_auto_amended` event.

Any of the four failing or missing is a **CRITICAL** finding.

### 4. Atomicity & audit trail

- The `scope_violation_escalation` event is emitted and committed BEFORE the auto-amend block runs. The auto-amend's second commit does not roll back or supersede the escalation commit. Cross-check: an inspector reading `DaemonEvent` rows for an auto-amended cycle sees BOTH events in chronological order.
- The `scope_auto_amended` event payload contains all four required keys: `step_id`, `added_paths`, `manifests_updated`, `matched_patterns` — and `matched_patterns` is a snapshot list (`list(project_config.auto_amend_allow_patterns)`), not a live attribute reference.

### 5. Scope discipline

`git diff --name-only main..HEAD` matches `scope.allowed_paths` exactly. Files inside the allow-list but with surprising changes (e.g. `orch/daemon/scope_overlap.py` got an unintended edit while S02 was promoting `_scope_match`) are MEDIUM_FIXABLE; files outside the allow-list are CRITICAL.

### 6. Architecture compliance

- No `from orch` import in `executor/` — the executor scripts must stay self-contained (CLAUDE.md rule).
- `DaemonEvent.metadata` is `event_metadata` (SQLAlchemy reserves `metadata`) — verify the new event uses the right field name.
- No new dependency added to `pyproject.toml` — `git diff main -- pyproject.toml` should be empty.
- No new migration in `orch/db/migrations/versions/`.

### 7. Documentation & example coverage

- `docs/IW_AI_Core_Daemon_Design.md` has a new subsection (~10–20 lines) on the auto-amend pass. It states: (a) when auto-amend fires, (b) that BOTH events are emitted for audit, (c) that the feature is opt-in and default-off, (d) where to configure it. No surrounding rewrite.
- `.iw-orch.json` example block is named `_auto_amend_scope_example` so the parser ignores it. iw-ai-core itself does NOT enable auto-amend in this CR.
- `CR-00087_Functional.md` matches what shipped (sanity-check `What Changed` and `How It Behaves` against the actual implementation).

### 8. Test discipline

- All new tests assert on **strong identities** (`event.event_metadata["matched_patterns"] == [...]`), not weak `in` / `is not None` checks. Per `skills/iw-ai-core-testing/SKILL.md`.
- The matcher-parity test exists in `tests/unit/daemon/test_scope_amendment.py` (asserting `should_auto_amend([v], [p], None) == bool(scope_match(v, p))` for each pattern the project would realistically use). HIGH if missing — without it, future drift in `scope_match` would silently break auto-amend.

### 9. Security

- No hardcoded credentials anywhere in the diff (`grep -rn "sk-ant-\|password\s*=\|secret" `git diff --name-only main..HEAD``).
- No `.env` file committed.
- `auto_amend_allow_patterns` strings flow only into `fnmatch.fnmatch` and string-prefix checks — no shell, no subprocess, no path concatenation outside the deterministic manifest paths.

## Test Verification (NON-NEGOTIABLE)

1. Run the targeted unit tests:
   ```bash
   uv run pytest tests/unit/daemon/test_project_registry_auto_amend_scope.py tests/unit/daemon/test_scope_amendment.py tests/unit/test_fix_cycle.py -v
   ```
2. Run the **full unit suite** to catch any cross-module regression from the `_scope_match` → `scope_match` rename:
   ```bash
   make test-unit
   ```
3. Do NOT run `make test-integration` here — that is S11's job (it has its own timeout budget and will run anyway).

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, scope violation, matcher-skew (auto-amend uses a different matcher than violation detector), missing required artefact, backwards-incompat | Must fix before merge |
| **HIGH** | Significant bug, missing AC, matcher-parity test missing, audit trail incomplete | Must fix before merge |
| **MEDIUM (fixable)** | Code quality, missing edge case, convention drift | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-final-impl",
  "work_item": "CR-00087",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security|scope|backwards_compat",
      "file": "path/to/file",
      "line": 42,
      "description": "...",
      "suggestion": "...",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, integration pending S11",
  "missing_requirements": [],
  "ac_verdicts": {
    "AC1": "PASS|FAIL",
    "AC2": "PASS|FAIL",
    "AC3": "PASS|FAIL",
    "AC4": "PASS|FAIL",
    "AC5": "PASS|FAIL",
    "AC6": "PASS|FAIL"
  },
  "matcher_parity_verified": true,
  "backwards_compat_verified": true,
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE findings AND every AC is PASS.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
- `missing_requirements`: design requirements with no corresponding implementation. Each is automatically CRITICAL.
- `ac_verdicts`: explicit per-AC pass/fail dictionary — non-negotiable transparency.
- `matcher_parity_verified`: true iff `should_auto_amend` and the violation detector share `scope_match` (the single most important architectural invariant of this CR).
- `backwards_compat_verified`: true iff projects without `auto_amend_scope` provably see zero behavioural change (the S04 disabled-feature test passes).
