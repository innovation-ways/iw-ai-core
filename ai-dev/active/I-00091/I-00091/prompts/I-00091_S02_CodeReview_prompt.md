# I-00091_S02_CodeReview_prompt

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy — see `docs/IW_AI_Core_Agent_Constraints.md`. No docker
commands.

## ⛔ Migrations: agents generate, daemon applies

S01 should not have generated a migration. If it did, raise a CRITICAL
finding — the design explicitly excludes migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00091 --json`.
- `ai-dev/active/I-00091/I-00091_Issue_Design.md` — design document
- `ai-dev/active/I-00091/reports/I-00091_S01_Backend_report.md`
- All files listed in S01's `files_changed` (expect `orch/auto_merge_aggregator.py`
  and `tests/unit/test_auto_merge_config_resolution.py`)

## Output Files

- `ai-dev/active/I-00091/reports/I-00091_S02_CodeReview_report.md`

## Context

You are reviewing the backend half of the I-00091 fix: `ResolvedConfig`
gained two new per-axis source fields, and `resolve_project_config`
should now populate them correctly across the five layered scenarios
listed in the S01 prompt.

## Read the Design Document FIRST

Read `ai-dev/active/I-00091/I-00091_Issue_Design.md` in full before
opening any code. Pay particular attention to:

- **Root Cause Analysis → Defect A** — the exact bug shape S01 must fix.
- **Acceptance Criteria** — AC1, AC2, AC4 each constrain what
  `resolve_project_config` must report.
- **TDD Approach** — names the four unit-test cells; only one (phase-
  only) is expected to be added in S01 (the other three belong to S05).

Cross-check S01's report `files_changed` against the test files the
design names. Missing `tests/unit/test_auto_merge_config_resolution.py`
in `files_changed` is a CRITICAL finding only if S01 changed the
`ResolvedConfig` signature without updating any direct constructor call
in the test (the existing tests construct `ResolvedConfig` directly).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any new violation in S01's changed files → CRITICAL finding with
`category: conventions`.

## Review Checklist

### 1. Per-axis source semantics

- Verify `phase_source` is `"per_project_db"` IFF the DB row exists AND
  has a non-NULL `phase`.
- Verify `runtime_source` reflects the layer that ACTUALLY produced the
  returned `runtime_option_id` — particularly that the
  disabled-runtime fallthrough path resets `runtime_source` away from
  `"per_project_db"`.
- Verify the invalid-phase fallback (line 158-164 area) preserves the
  source of the invalid value so observability/warning logic still
  works.

### 2. Back-compat decision

- If S01 kept `.source` as a property: verify the docstring explains it
  is derived, and verify the chip template's existing rendering is not
  broken.
- If S01 removed `.source`: verify every grep hit
  (`grep -rn "config\.source"`) was updated.

### 3. ResolvedConfig dataclass shape

- All construction sites pass both new fields.
- `Literal` typing matches the existing pattern.
- `frozen=True` is preserved.

### 4. Tests

- The test added in S01 RED-evidence (phase-only override) actually
  exists in `files_changed`.
- It asserts on the new fields (`phase_source`, `runtime_source`), not
  just `phase`.
- No new tests for runtime-only / both / no-override appear here —
  those belong to S05; if S01 over-reached and wrote them, that is a
  MEDIUM (suggestion) finding only (it's harmless but blurs step
  ownership).

### 5. Code quality

- No silent broad excepts (the existing module uses `# noqa: BLE001`
  intentionally; new code should not add more).
- No new logger.warning that floods on every request.
- No `event_metadata` vs `metadata` confusion (this module uses neither
  directly, but if S01 added a new DaemonEvent emission, verify).

### 5a. TDD RED Evidence (behaviour-implementing steps only)

S01 is a behavioural Backend step. Verify:

1. The report's `tdd_red_evidence` field is present and shows a plausible
   `AttributeError` or `AssertionError` against the new test.
2. The named failing test exists at the cited path.
3. Reason about whether the test would have actually failed against
   pre-S01 code — i.e., whether the assertion targets the new field that
   didn't exist before. (It should: pre-S01 ResolvedConfig has no
   `phase_source` attribute, so an `AttributeError` is the expected
   shape.)

### 6. Security / Conventions

- No hardcoded credentials.
- Type hints match existing style.
- No imports of unused modules.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_auto_merge_config_resolution.py -v
```

Do NOT run the full suite — S12 owns that.

## Severity Levels

Same as the standard template (CRITICAL / HIGH / MEDIUM_FIXABLE /
MEDIUM_SUGGESTION / LOW).

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00091",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "",
      "suggestion": ""
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
