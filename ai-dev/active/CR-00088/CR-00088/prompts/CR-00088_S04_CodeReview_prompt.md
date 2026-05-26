# CR-00088_S04_CodeReview_prompt

**Work Item**: CR-00088 -- Auto-merge — partial-allowlist semantics in Phase 1 dry-run
**Steps Being Reviewed**: S01 (backend-impl), S02 (backend-impl), S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

(Standard policy. This step touches no Docker.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This CR adds no migrations.)

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00088 --json`
- `ai-dev/active/CR-00088/CR-00088_CR_Design.md` — Design (READ AC1–AC5 in full)
- `ai-dev/active/CR-00088/CR-00088_Functional.md` — Functional summary (sanity-check it matches what shipped)
- `ai-dev/work/CR-00088/reports/CR-00088_S01_Backend_report.md`
- `ai-dev/work/CR-00088/reports/CR-00088_S02_Backend_report.md`
- `ai-dev/work/CR-00088/reports/CR-00088_S03_Tests_report.md`
- All files listed in S01–S03 reports' `files_changed`

## Output Files

- `ai-dev/work/CR-00088/reports/CR-00088_S04_CodeReview_report.md`

## Context

You are reviewing **three implementation steps** in a single pass. They share one cohesive concern (the allowlist gate going from all-or-nothing to partition); per-step reviews would duplicate work.

Read the design doc **before** running any gate. Read all three impl reports. Then review every file in their combined `files_changed`.

## Read the Design Document FIRST

The five Acceptance Criteria are the anchor. Carry them into the checklist below.

Key TDD/scope requirements to verify by path:

- `orch/daemon/auto_merge.py` MUST appear in S01's `files_changed` AND in S02's `files_changed` (S01 = partition logic + dataclass field; S02 = event metadata for ATTEMPTED + RESOLVED + FAILED).
- `tests/unit/test_auto_merge_classifier.py` MUST appear in S01's `files_changed`.
- `orch/daemon/merge_queue.py` MUST appear in S02's `files_changed`.
- `tests/integration/test_auto_merge_phase1.py` MUST appear in S02's `files_changed` (FOUR new RED-first integration tests + ONE tightened skip-event assertion).
- `tests/unit/test_auto_merge_invoke.py` MUST NOT appear in S02's `files_changed` — that file is for pure subprocess-mocked unit tests; the new DB-touching tests belong in integration. If the agent put them there anyway, that is a CRITICAL scope/architecture finding.
- `tests/integration/test_auto_merge_partial_allowlist.py` MUST appear in S03's `files_changed` (NEW file).
- `docs/research/R-00076-llm-automated-merge-resolution.md` MUST appear in S03's `files_changed`.
- `ai-dev/active/AUTO_MERGE_RESOLUTION.md` MUST appear in S03's `files_changed`.

Any missing (or any forbidden file present) → CRITICAL.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on all changed files:

```bash
make lint
make format-check
```

NEW violations (not pre-existing on `main`) in the changed files → each is a CRITICAL finding (`category: conventions`, exact code + message). Do not fix; report only.

## Review Checklist

### 1. S01 — Partition logic in `classify_conflicts`

- **`ClassificationResult.deferred_files: tuple[str, ...]` added with default `()`** — at the END of the field list so positional construction of existing tests does not break. Trailing default is non-negotiable.
- **Partition is a single linear pass** — one `for rel_path in conflict_files` loop, not two list comprehensions over the same input. Order preservation is a stated invariant.
- **Order preservation** — both `eligible_files` and `deferred_files` reflect the input ordering. If S01 sorted either tuple, that is a HIGH finding.
- **Empty-eligible branch keeps `skipped_reason="not_allowlisted"`** AND now populates `deferred_files=tuple(deferred_files)`. (Today's all-deferred case must remain visible as "skipped" — only the metadata grows.)
- **Non-empty eligible branch returns `skipped_reason=None`** with both tuples populated.
- **Refuse-list precedence unchanged** — refuse-list runs in step 1 (~line 397), before allowlist; the partition does not affect that ordering.
- **Docstring updated** for `classify_conflicts` step 6 to describe the partition.
- **Four new RED tests in `test_auto_merge_classifier.py`**: `test_partial_allowlist_returns_partition`, `test_all_deferred_keeps_skip_reason`, `test_refuselist_wins_over_partial_allowlist`, `test_deferred_files_default_empty`. Each test's RED state was either an `AssertionError` (wrong field values) or `TypeError` (unknown keyword) — recorded verbatim in S01 report's `tdd_red_evidence`.
- **Existing classifier tests tightened, not loosened** — e.g., `test_non_allowlisted_file` now also asserts `result.deferred_files`. Any test where assertion strength was REDUCED is a CRITICAL finding.

### 2. S02 — Event metadata thread-through

- **`attempt_resolution()` accepts `deferred_files: list[str] | None = None`** — trailing default preserves backward compat.
- **`EVENT_AUTO_RESOLUTION_ATTEMPTED` metadata** has both `allowlisted_files` (alias for `eligible_files`) AND `deferred_files`. `conflict_files` (the original key) is preserved unchanged — back-compat for any dashboard view reading it.
- **`EVENT_AUTO_RESOLVED` metadata** has `deferred_files`. The human-readable message string includes the deferred count when non-zero (e.g., "...; N file(s) deferred").
- **`EVENT_AUTO_RESOLUTION_FAILED` metadata** (the `if abstained_files or error_files:` branch in `attempt_resolution`, ~line 977) has `deferred_files`. This is the AC6 check — without it the operator misses the partial-allowlist context when the LLM abstains/errors. CRITICAL if missing.
- **`EVENT_AUTO_RESOLUTION_SKIPPED` metadata in `merge_queue.py`** now includes `deferred_files`. The existing `eligible_files` key (the full pre-classification list passed by the caller) is preserved unchanged.
- **`merge_queue.py` caller** of `attempt_resolution()` passes `deferred_files=list(_classification.deferred_files)`. If the kwarg is missing on the call site, that is a CRITICAL finding — the metadata in the events would silently fall back to `[]` even when partition data is available.
- **Four new RED integration tests in `tests/integration/test_auto_merge_phase1.py`** with plausible RED states (`KeyError` or `AssertionError` on metadata keys). They MUST use `event.event_metadata[...]` (NOT `event.metadata[...]` — SQLAlchemy reserves `metadata` on `DeclarativeBase`; using the wrong attribute raises `AttributeError`). The four tests cover ATTEMPTED, RESOLVED, FAILED, and default-empty cases respectively.
- **Tightened integration assertion in `test_auto_merge_phase1.py`** for the skipped-event metadata (`event_metadata["deferred_files"]` exact-list match). Not a new test; an extension.
- **No new tests in `tests/unit/test_auto_merge_invoke.py`** — that file is the home for pure subprocess-mocked unit tests; DB-touching tests must be integration. CRITICAL scope finding if violated.
- **No new event types introduced** — design forbids `merge_auto_partial` because the existing events carry the partition cleanly.
- **Phase ladder untouched** — `PHASE_TESTS_ONLY` (Phase 2) is still `raise ValueError` per the existing guard at ~line 855. S02 must NOT relax that guard. CRITICAL if it does.

### 3. S03 — Integration test + docs

- **`tests/integration/test_auto_merge_partial_allowlist.py` exists** as a NEW file (not a folded test in `test_auto_merge_phase1.py`).
- **Test reproduces the CR-00084 shape**: exactly 3 conflict files, one allowlisted (`docs/foo.md` or similar), two deferred (`Makefile`, `pyproject.toml`).
- **Uses the default `AutoMergeConfig`** (no override of `allowlist_patterns` or `refuselist_patterns`). The test exercises the real production config, not a tailored one — that is the whole point.
- **LLM is stubbed**, not called for real. `monkeypatch.setattr(auto_merge, "invoke_llm_for_file", ...)` or equivalent. CRITICAL if a real subprocess is launched.
- **Worktree-non-mutation assertion present**: a pre-call hash equals a post-call hash of `git ls-files | sort | xargs sha256sum`. Phase-1 invariant.
- **Work-item-still-failed assertion present**: `wi.status == "failed"`. Phase-1 behaviour.
- **Real testcontainer Postgres** (the existing `db_session` fixture). No DB mock. `psycopg2` URL replaced with `psycopg`. No duplicated `FTS_FUNCTION_SQL`.
- **`docs/research/R-00076-*.md`** has a new "Partial-allowlist semantics (CR-00088)" subsection (3–6 sentences, no more).
- **`ai-dev/active/AUTO_MERGE_RESOLUTION.md`** has the one-line tracker entry.
- **Assertions are strong** (per `skills/iw-ai-core-testing/SKILL.md`): exact list equality with order, not membership checks; exact dict-key reads, not `assert "x" in metadata`.

### 4. Cross-step: scope discipline

`git diff --name-only main..HEAD` matches the manifest's `scope.allowed_paths` list. Any file outside the allow-list (plus the implicit `ai-dev/active/CR-00088/**` and `ai-dev/work/CR-00088/**`) is a CRITICAL scope finding.

Expected file set (and nothing else):

- `orch/daemon/auto_merge.py`
- `orch/daemon/merge_queue.py`
- `tests/unit/test_auto_merge_classifier.py`
- `tests/integration/test_auto_merge_phase1.py`
- `tests/integration/test_auto_merge_partial_allowlist.py` (NEW)
- `docs/research/R-00076-llm-automated-merge-resolution.md`
- `ai-dev/active/AUTO_MERGE_RESOLUTION.md`
- `ai-dev/active/CR-00088/**` (implicit)
- `ai-dev/work/CR-00088/**` (implicit)

`tests/unit/test_auto_merge_invoke.py` is explicitly OUT — if it appears in the diff, raise a CRITICAL scope finding.

### 5. Architecture compliance

- No new event type registered. `EVENT_AUTO_*` constants block at the top of `auto_merge.py` is unchanged.
- No `from executor.*` imports.
- No new dataclass fields on `LLMCallResult` or `AutoMergeResult` (those carry single-file results — the partition lives at the classification layer).
- `DaemonEvent.metadata` field name in Python is `event_metadata` — verify any reflective test uses the Python name, not the SQL column name.
- `phase` config untouched. `executor/auto_merge.toml` untouched (or comment-only).
- `executor/worktree_commit.sh` untouched.

### 6. Backwards compatibility

- Existing tests that constructed `ClassificationResult(...)` without `deferred_files` still pass — the field has a default.
- Existing dashboard auto-merge event-detail view (any router under `dashboard/routers/auto_merge_*.py`) is unmodified and still renders — additive metadata keys are ignored by unknown consumers.
- The all-allowlisted case is byte-identical to today's behaviour (regression-test it by reading the S01 report's diff of `test_all_files_allowlisted`).

### 7. Security

- No user-controlled string flows into a subprocess, shell, or filesystem path. `fnmatch.fnmatchcase` is pure pattern matching; no glob expansion against the filesystem.
- No new prompt content sent to the LLM — `build_resolution_prompt` is unchanged, and only `eligible_files` reach it.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Scope violation, partition logic regression, missing required artefact, refuse-list precedence broken | Must fix before merge |
| **HIGH** | Significant bug, missing AC, order-preservation broken | Must fix before merge |
| **MEDIUM (fixable)** | Code quality, convention drift, weak assertion in new test | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement | Optional |
| **LOW** | Nitpick | Informational |

## Test Verification (NON-NEGOTIABLE)

Run targeted tests only:

```bash
uv run pytest tests/unit/test_auto_merge_classifier.py tests/integration/test_auto_merge_phase1.py tests/integration/test_auto_merge_partial_allowlist.py -v
```

Do NOT run `make test-integration` or `make test-unit` at large — that is S10/S11's job.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00088",
  "steps_reviewed": ["S01", "S02", "S03"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing|scope",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "partition_invariants_verified": true,
  "scope_violations": [],
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
- `partition_invariants_verified`: explicit boolean for refuse-list precedence + order preservation + Phase-1 worktree non-mutation. The single most important architectural check in this CR.
- `scope_violations`: any file in the diff outside the allow-list.
