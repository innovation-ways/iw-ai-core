# CR-00087_S05_CodeReview_prompt

**Work Item**: CR-00087 -- Auto-amend scope violations matching per-project allow-patterns
**Steps Being Reviewed**: S01 (backend-impl), S02 (backend-impl), S03 (backend-impl), S04 (tests-impl)
**Review Step**: S05

---

## ⛔ Docker is off-limits

(Standard policy. See S01 prompt for full text. This step does not touch Docker.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This CR adds no migrations and you must not run `alembic upgrade`/`downgrade`/`stamp` against the live orch DB.)

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00087 --json`
- `ai-dev/active/CR-00087/CR-00087_CR_Design.md` — Design document (READ AC1–AC6 in full)
- `ai-dev/active/CR-00087/CR-00087_Functional.md` — Functional summary (sanity-check it still describes what shipped)
- `ai-dev/work/CR-00087/reports/CR-00087_S01_BackendImpl_report.md`
- `ai-dev/work/CR-00087/reports/CR-00087_S02_BackendImpl_report.md`
- `ai-dev/work/CR-00087/reports/CR-00087_S03_BackendImpl_report.md`
- `ai-dev/work/CR-00087/reports/CR-00087_S04_TestsImpl_report.md`
- All files listed in S01–S04 reports' `files_changed`

## Output Files

- `ai-dev/work/CR-00087/reports/CR-00087_S05_CodeReview_report.md`

## Context

You are reviewing **four implementation steps** (S01–S04) in a single pass. Per-step reviews would duplicate work because the steps share one cohesive concern (a per-project opt-in policy that escalates a fix-cycle's scope handling without changing the manual operator path).

Read the design document **before** the lint/format gate. Read all four impl reports. Then review every file in their combined `files_changed`.

## Read the Design Document FIRST

Read every AC in full. Carry the AC list into the review checklist below as the first-class anchor.

Key TDD-section requirements to verify by path:

- `orch/daemon/project_registry.py` MUST appear in S01's `files_changed`.
- `tests/unit/daemon/test_project_registry_auto_amend_scope.py` MUST appear in S01's `files_changed` (per-concern test file, NOT bundled into `test_project_registry.py`).
- `orch/daemon/scope_amendment.py` AND `orch/daemon/fix_cycle.py` MUST appear in S02's `files_changed` (S02 promotes `_scope_match` → `scope_match` AND adds `should_auto_amend`).
- `tests/unit/daemon/test_scope_amendment.py` MUST appear in S02's `files_changed`.
- `orch/daemon/fix_cycle.py`, `docs/IW_AI_Core_Daemon_Design.md`, `.iw-orch.json`, `tests/unit/test_fix_cycle.py` MUST appear in S03's `files_changed`.
- `tests/integration/test_scope_amend_endpoints.py` MUST appear in S04's `files_changed`.

Any missing → CRITICAL finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on all changed files:

```bash
make lint
make format
```

If either reports NEW violations in the changed files (not pre-existing on `main`), classify each as a CRITICAL finding (`category: conventions`, exact violation code + message). Fix nothing yourself — only report.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. S01 — Registry parsing

- **`ProjectConfig` fields**: `auto_amend_allow_patterns: list[str]` (default `[]`) and `auto_amend_max_paths: int | None` (default `None`) added next to the existing `overlap_*` fields (related per-project policy lives together).
- **`_parse_auto_amend_scope` helper**: signature `(project_id: str, raw: object) -> tuple[list[str], int | None]`. Style mirrors `_parse_overlap_gate` exactly (defensive logging, fallback-to-defaults on malformed input).
- **Malformed-input matrix**: every branch enumerated in the design's AC5 is exercised in tests (non-dict, non-list patterns, non-string pattern entries, non-int `max_paths`, `bool` `max_paths`, negative `max_paths`).
- **bool rejection**: `_parse_auto_amend_scope` explicitly rejects `True`/`False` for `max_paths` (bool is an int subtype in Python — the test for this must be present and pass).
- **Wired into `_build_project_config`**: the new helper is called after `_parse_overlap_gate` and the two fields are passed into the `ProjectConfig(...)` constructor.
- **Test file location**: `tests/unit/daemon/test_project_registry_auto_amend_scope.py` is a NEW per-concern file (not bundled into existing `test_project_registry.py` or `test_project_registry_overlap_gate.py`).
- **TDD RED evidence**: S01's report carries a plausible RED snippet (AttributeError on the missing dataclass field, or AssertionError on a default-value mismatch). NOT an ImportError or collection error.

### 2. S02 — `scope_match` promotion + `should_auto_amend` helper

- **`_scope_match` renamed to `scope_match`** in `orch/daemon/fix_cycle.py` (public name). The body is unchanged. If `_scope_match` is kept as an alias, the report says why (e.g. test file pins the old name).
- **All internal callers of `_scope_match` updated** to `scope_match` if the alias was dropped. `grep -rn "_scope_match" orch/ tests/` agrees with the report.
- **`should_auto_amend(violations, allow_patterns, max_paths) -> bool`** added to `orch/daemon/scope_amendment.py`.
- **Matcher reuse**: `should_auto_amend` imports `scope_match` from `orch.daemon.fix_cycle` (the same matcher the violation detector uses). It does NOT use `_matches` from `scope_overlap.py` and does NOT duplicate the matcher body — CRITICAL if it does.
- **Purity**: no logging, no side effects, no exceptions on bad input. Returns `False` for empty / non-list input rather than raising.
- **Test matrix**: every row from the S02 prompt's matrix is present and passes. The dedicated **matcher parity test** comparing `should_auto_amend` to `scope_match` is present.
- **TDD RED evidence**: a plausible RED snippet (AssertionError or NotImplementedError), not an ImportError.

### 3. S03 — `_complete_fix_cycle` integration

- **`_try_auto_amend_after_escalation` helper** extracted (S03 prompt mandates this for readability). Lives next to `_complete_fix_cycle` in `orch/daemon/fix_cycle.py`.
- **Hook placement**: the helper is invoked IMMEDIATELY BEFORE the `return  # Do NOT advance the step — operator must intervene` line in the escalation branch (~line 1151). The existing escalation commit is preserved unchanged.
- **`project_config is None` short-circuit**: when `project_config` is `None`, the helper returns immediately without DB or filesystem activity. The unit test for this short-circuit is present and passes.
- **New event `scope_auto_amended`**: emitted via the existing `_emit_event` helper (same one used for `scope_violation_escalation`) with payload `{step_id, cycle_number, added_paths, manifests_updated, matched_patterns}`. Matched patterns must be `list(project_config.auto_amend_allow_patterns)` at the time of decision (snapshot — do not pass the live attribute).
- **StepRun creation mirrors `dashboard/routers/actions.py:scope_amend_and_restart`**: `run_number = previous + 1`, `status = RunStatus.pending`, `command`/`worktree_path`/`cli_tool`/`timeout_secs` copied from the last run. Style may use either `db.scalar(select(...))` (preferred — modern SQLAlchemy 2.0) or `db.query(...).first()` (acceptable — match the file's surrounding style); flag either as LOW only.
- **Step transition**: `step.status = StepStatus.pending`, `started_at = None`, `completed_at = None`. WorkItem status flip from `failed → in_progress` mirrors `actions.py` lines 498–499.
- **INFO log**: a single INFO line summarising the auto-amend (`[<project_id>] Auto-amended scope for <item_id>/<step_id> cycle <n>: added <N> path(s) matching patterns <patterns>`). Not DEBUG.
- **Daemon Design doc updated** with a ~10–20 line subsection describing when auto-amend fires and the dual-event audit trail.
- **`.iw-orch.json` example block** added under `_auto_amend_scope_example` (key starts with underscore so the parser ignores it). No accidental enablement.
- **TDD RED evidence**: short-circuit test fails before the helper exists. Plausible RED.

### 4. S04 — Integration tests

- The four tests the design enumerates are present (positive, three negatives).
- **Real testcontainer Postgres** is used (the existing `db_session` fixture from `tests/conftest.py`). `psycopg2` URL is replaced with `psycopg`. `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` not duplicated.
- **No mocking of the DB** (`grep -E "MagicMock\(.*Session|mock.*db" tests/integration/test_scope_amend_endpoints.py` returns nothing in the new tests).
- **No mocking of `amend_allowed_paths` or `_emit_event`** — the integration tests must exercise real code paths.
- **Assertions are strong**: `event.event_metadata.get("matched_patterns") == [...]` not `assert "matched_patterns" in event.event_metadata`. Per `skills/iw-ai-core-testing/SKILL.md`.
- Test names map clearly to the design's ACs.

### 5. Cross-step: matcher parity

- The matcher used by `should_auto_amend` and the matcher used by the violation detector in `_complete_fix_cycle` are **the same function** (`scope_match`). Run a quick `grep -rn "from orch.daemon.fix_cycle import scope_match\|from orch.daemon.scope_amendment\|_scope_match\|_matches" orch/daemon/scope_amendment.py orch/daemon/fix_cycle.py` and confirm only one matcher implementation lives in the codebase for this concern.

### 6. Scope discipline

`git diff --name-only main..HEAD` matches the manifest's `scope.allowed_paths`. Files outside the allow-list are CRITICAL.

Expected files only:

- `orch/daemon/project_registry.py`
- `orch/daemon/scope_amendment.py`
- `orch/daemon/scope_overlap.py` (acceptable if S02 needed to touch it for cleanup — but typically should NOT be touched; flag any unexpected edits)
- `orch/daemon/fix_cycle.py`
- `docs/IW_AI_Core_Daemon_Design.md`
- `.iw-orch.json`
- `tests/unit/daemon/test_project_registry_auto_amend_scope.py` (NEW)
- `tests/unit/daemon/test_scope_amendment.py`
- `tests/unit/test_fix_cycle.py`
- `tests/integration/test_scope_amend_endpoints.py`
- `ai-dev/active/CR-00087/**` (always implicit)
- `ai-dev/work/CR-00087/**` (always implicit)

### 7. Architecture compliance

- No `from orch.daemon.scope_overlap import _matches` in `scope_amendment.py` (the design rejects this matcher choice — `scope_match` from `fix_cycle.py` is the canonical reuse).
- No new docker calls. No alembic migrations. No new DB columns.
- `DaemonEvent.metadata` (Python attribute) is `event_metadata` — verify the new `scope_auto_amended` event uses that field name.
- No `from executor.scope_gate import` (executor scripts must remain self-contained — CLAUDE.md rule).

### 8. Backwards compatibility

- Projects without `auto_amend_scope` in `.iw-orch.json` see ZERO behavioural change. The S04 negative test `test_complete_fix_cycle_does_not_auto_amend_when_feature_disabled` proves this.
- The manual operator endpoint `POST /…/scope/amend-and-restart/{step_id}` is unchanged (no edits to `dashboard/routers/actions.py`).

### 9. Security

- `auto_amend_scope` parser **rejects** `..` traversal, absolute paths, and shell metacharacters. (Actually — these are gitignore-style glob patterns matched against paths the agent touched; no shell or path traversal happens. But if the parser accepts any string, downstream `fnmatch` is safe by construction. Still, a malformed pattern like `../../etc/**` would not match any real-world violation path, so the security risk is bounded.) Flag any user-controlled string that ends up in a subprocess or file-path concatenation as CRITICAL.
- No path-injection: `amend_allowed_paths` writes only to the manifest files it locates by deterministic path construction; no shell.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, scope violation, matcher-skew (should_auto_amend uses a different matcher than the violation detector), missing required artefact | Must fix before merge |
| **HIGH** | Significant bug, missing AC, backwards-incompat for projects without the new config | Must fix before merge |
| **MEDIUM (fixable)** | Code quality, missing edge case, convention drift | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement | Optional |
| **LOW** | Nitpick | Informational |

## Test Verification (NON-NEGOTIABLE)

Run targeted tests only:

```bash
uv run pytest tests/unit/daemon/test_project_registry_auto_amend_scope.py tests/unit/daemon/test_scope_amendment.py tests/unit/test_fix_cycle.py -v
```

Do NOT run `make test-integration` — that is S11's job.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "CR-00087",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
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
  "matcher_parity_verified": true,
  "scope_violations": [],
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
- `matcher_parity_verified`: explicitly track whether `should_auto_amend` and the violation detector share the same matcher (the single most important architectural check in this CR).
- `scope_violations`: any file in the diff outside the allow-list.
