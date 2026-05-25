# CR-00085_S04_CodeReview_Final_prompt

**Work Item**: CR-00085 -- DB-column documentation gate
**Review Step**: S04 (Final Review)
**Implementation Steps Reviewed**: S01..S02

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps`/`inspect`/`logs` permitted.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This work item adds no migration. Reject any migration file in `files_changed`.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00085 --json`.
- `ai-dev/work/CR-00085/CR-00085_CR_Design.md` — Design.
- `ai-dev/work/CR-00085/reports/CR-00085_S01_Backend_report.md` — S01.
- `ai-dev/work/CR-00085/reports/CR-00085_S02_Backend_report.md` — S02.
- `ai-dev/work/CR-00085/reports/CR-00085_S03_CodeReview_report.md` — S03 per-agent review.
- All files listed in S01 + S02 `files_changed`.

## Output Files

- `ai-dev/work/CR-00085/reports/CR-00085_S04_CodeReview_Final_report.md` — final review.

## Context

Cross-agent / global review of the complete CR-00085 implementation: S01 (scanner + baseline + RED-first test) plus S02 (Makefile + CI + docs + skill + tracker).

Read the design's Acceptance Criteria (AC1–AC8) and TDD Approach in full before opening any code. Cross-check every test the design names by behaviour against the union of S01's `files_changed`.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in changed files → CRITICAL `conventions` finding.

## Review Checklist

### 1. Completeness vs Design Document (AC1–AC8)

- **AC1** (Scanner detects undocumented columns) — execute `uv run python scripts/check_db_column_docs.py --baseline /dev/null` and assert exit 1 + at least one human-readable violation line.
- **AC2** (Scanner handles `DaemonEvent.event_metadata`) — execute the scanner full-strict and grep the output: `event_metadata` must NOT appear; `metadata` may.
- **AC3** (Baseline freezes today's debt) — execute `make check-column-docs` on the unchanged tree; exit 0; zero NEW violations.
- **AC4** (Baseline rejects new violations) — synthesize a temporary undocumented column by adding it ONLY in a worktree-local probe scratch file (do NOT commit), confirm the scanner flags it, revert the probe. Alternatively, reason from the test suite: `test_scanner_flags_new_undocumented_column_on_synthetic_mapper` provides equivalent evidence — accept it.
- **AC5** (Makefile + CI warn-first) — `make quality` exits 0 on unchanged tree; grep the Makefile for `check-column-docs.*\|\| true`; grep the GH workflow for `make check-column-docs || true`.
- **AC6** (RED-first test pins the contract) — `uv run pytest tests/orch/db/test_column_docs.py -v` shows all named tests passing.
- **AC7** (Docs / skill / tracker updates) — verify §5 row added, §9 row added/flipped, both skill copies updated and byte-identical, tracker §8 row 4.5 ✅, tracker §11 changelog entry present and citing the EXACT baseline entry count from S01's report, follow-up tracker row filed.
- **AC8** (Scope discipline) — `git diff main --name-only` matches the design's Impacted Paths verbatim; no `orch/db/models.py`, no `docs/IW_AI_Core_Database_Schema.md`, no migration file.

Each AC not satisfied is a CRITICAL finding. List all unsatisfied ACs in `missing_requirements`.

### 2. Cross-Agent Consistency (S01 ↔ S02)

- The baseline entry count cited in the tracker §11 changelog matches S01's `tdd_red_evidence` field VERBATIM. Mismatch is HIGH (drift between docs and reality).
- The Makefile target name (`check-column-docs`) matches what S02 added to `.PHONY`, the `quality` target, the GH workflow, the strategy doc §5, and the skill doc. ALL FIVE places must use the same name. Any drift is HIGH.
- The CR-ID citation (`CR-00085`) appears in every doc touched by S02 — strategy doc §5, strategy doc §9, skill section, tracker §8 row, tracker §11 changelog. Any place that says `CR-00084` or `CR-00086` is a typo CRITICAL.

### 3. Integration Points

- The scanner imports `from orch.db.models import Base` (or equivalent). Verify the import works at the same time as `make typecheck` passes (i.e. the scanner is importable from the project's normal venv).
- The `tests/orch/db/test_column_docs.py` file is discoverable by pytest (no missing `__init__.py`).

### 4. Test Coverage (Holistic)

- The five+ tests cover: empty-baseline RED, committed-baseline GREEN, reserved-name regression, synthetic-mapper composability, write-baseline roundtrip. Anything missing is CRITICAL.
- Diff-coverage gate (S11) — the new scanner code paths should be exercised by at least the empty-baseline RED test and the synthetic-mapper test. Spot-check that no major branch is uncovered.

### 5. Architecture Compliance

- The scanner lives under `scripts/`, consistent with `check_test_assertions.py`, `check_templates.py`, `arch_check.py`. Not under `orch/`.
- The baseline file lives under `orch/db/`, consistent with the implicit rule that baseline files live next to the thing they police (`tests/assertion_free_baseline.txt` next to `tests/`).
- The test file lives under `tests/orch/db/`, mirroring the production layout.

### 6. Security (Cross-Cutting)

- No hardcoded secrets, no network calls in the scanner.
- The scanner does NOT read from the database — it only inspects in-memory mapper declarations. Confirm by grepping the scanner for `engine`, `connect`, `session` — should be absent.
- The scanner does NOT make assumptions about live DB connectivity — verify by running it with `IW_CORE_DB_HOST=blocked` (or `unset IW_CORE_DB_HOST`); should still exit 0.

### 7. Burn-in policy correctness (CR-specific)

- Both surfaces (`make quality` AND `.github/workflows/test-quality.yml`) use `|| true`. ANY single surface that omits `|| true` is a CRITICAL finding — the burn-in policy must be uniform across surfaces (otherwise the GH job blocks while local dev doesn't, or vice versa).
- The follow-up CR (`CR-00085-followup-column-docs-gate-blocking`) is documented in BOTH the design's Notes section and the tracker's §8 follow-up row, so future operators know where to flip the gate.

## Test Verification (NON-NEGOTIABLE)

Run the unit suite (the QV S10 gate owns the integration suite — do NOT duplicate it here; running the full integration suite inside an `*-impl` step is forbidden, see I-00073/S03 lesson):

```bash
make test-unit
uv run pytest tests/orch/db/test_column_docs.py -v
```

Report results. If unit tests fail unrelated to CR-00085, note it but the CRITICAL bar applies only to failures this CR caused. Trust S10 (`qv-gate` integration-tests) for the integration suite.

## Severity Levels

Standard (CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW).

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-final-impl",
  "work_item": "CR-00085",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

`verdict`: `pass` if zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE. `cross_cutting: true` on findings spanning S01 and S02.
