# CR-00085_S03_CodeReview_prompt

**Work Item**: CR-00085 -- DB-column documentation gate
**Step Being Reviewed**: S01 (backend-impl) AND S02 (backend-impl)
**Review Step**: S03

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps`/`inspect`/`logs` permitted.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This work item adds no migration. Reject any migration file appearing in `files_changed`.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00085 --json`.
- `ai-dev/work/CR-00085/CR-00085_CR_Design.md` — Design.
- `ai-dev/work/CR-00085/reports/CR-00085_S01_Backend_report.md` — S01 report.
- `ai-dev/work/CR-00085/reports/CR-00085_S02_Backend_report.md` — S02 report.
- All files listed in S01+S02 `files_changed`.

## Output Files

- `ai-dev/work/CR-00085/reports/CR-00085_S03_CodeReview_report.md` — review report.

## Context

Per-agent code review of the two backend-impl steps that introduce the DB-column doc gate.

Read the design document **before** running gates and **before** opening any changed files. Specifically:

- Read the design's **Acceptance Criteria** in full — AC1–AC8 are all mandatory checks here.
- Read the design's **TDD Approach** — note the four+ test cases the design names by behaviour (`scanner_finds_undocumented_columns_against_empty_baseline`, `scanner_returns_zero_new_violations_against_committed_baseline`, `scanner_handles_daemon_event_metadata_rename`, `scanner_flags_new_undocumented_column_on_synthetic_mapper`, `write_baseline_roundtrips`). Cross-check that S01's `files_changed` includes `tests/orch/db/test_column_docs.py` and that each named test is present.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any NEW violation in files listed in S01/S02 `files_changed` is a **CRITICAL** finding (category: `conventions`).

## Review Checklist

### 1. S01 — scanner correctness (CRITICAL bars)

- **Scanner walks `Base.registry.mappers` → `mapper.local_table.columns`, NOT `cls.__dict__`.** If the scanner uses `vars(cls)` or `cls.__dict__` to walk columns, it will trip over `Base.metadata` and miss the `event_metadata` rename — that is a CRITICAL bug. Open the script and verify.
- **Scanner reports SQL column names** (`metadata`), not python attribute names (`event_metadata`). Run `uv run python scripts/check_db_column_docs.py --strict` and grep the output for `event_metadata` — that string must NOT appear; `metadata` may appear.
- **`doc=""` (empty string) is treated as missing.** Confirm `bool(col.doc)` semantics — an empty-string `doc=""` should be a violation.
- **Baseline file is sorted.** A deterministic-diff baseline makes future scrubs reviewable. Run `LC_ALL=C sort -c orch/db/column_docs_baseline.txt` (excluding header comments) — if it fails, that's a HIGH finding.
- **Baseline header is a clear "cleanup backlog not accept-list" warning** mirroring `tests/assertion_free_baseline.txt`. Missing or muted header → MEDIUM_FIXABLE.
- **CLI flags** — verify `--baseline`, `--write-baseline`, `--json`, `--strict` all work via a quick smoke run.
- **Exit codes** — exit 0 when zero new violations, exit 1 when new violations.

### 2. S01 — test correctness

- All five+ test cases named in the design's TDD Approach are present in `tests/orch/db/test_column_docs.py`. Missing any one is CRITICAL.
- The **RED-empty-baseline test** asserts `len(violations) > 0` AND names at least one specific known-undocumented column (e.g. `WorkItem.id`) — a `> 0` alone is too weak. If it's only `> 0`, that's a MEDIUM_FIXABLE finding.
- The **synthetic-mapper test** uses its own `MetaData` / `Base`, not `orch.db.models.Base`. Otherwise it pollutes the real registry.
- The **reserved-name regression test** asserts the SCANNER does not crash AND reports the SQL column name. If it only asserts existence of the SQL column (without invoking the scanner) it's a weakened version — MEDIUM_FIXABLE.
- The **write-baseline roundtrip** uses `tmp_path`, not the real baseline file.

### 3. S01 — TDD RED evidence

- `tdd_red_evidence` in the S01 report **must** contain the pre-implementation failure line (ImportError / ModuleNotFoundError) AND the post-implementation pass summary AND the exact baseline entry count.
- Confirm the baseline entry count claimed in the report matches `wc -l orch/db/column_docs_baseline.txt` minus the header-comment lines. Mismatch is a HIGH finding (the count flows downstream into the tracker changelog).
- Reason about whether the GREEN test would actually pass with the committed baseline — if the baseline misses any current undocumented column, the GREEN test will fail. Spot-check three random `Column(...)` declarations in `orch/db/models.py` that have no `doc=`; confirm their FQNs appear in the baseline.

### 4. S02 — Makefile wiring

- `check-column-docs` is in `.PHONY`. Missing → MEDIUM_FIXABLE.
- The `quality` target invokes `check-column-docs` via `|| true` (warn-first). If the `|| true` is missing — gate is BLOCKING — that's a CRITICAL finding (violates the design's burn-in policy AC5).
- The target command points at `orch/db/column_docs_baseline.txt`, not `/dev/null` or `--strict`.
- Style consistency: the new target's comment block follows the same shape as the `test-assertions` target's comment block.

### 5. S02 — CI wiring

- `.github/workflows/test-quality.yml`'s `lint-typecheck` job has exactly ONE new `- run: make check-column-docs || true` step.
- The `|| true` is present (warn-first). Missing → CRITICAL.
- No other job (`unit`, `integration`, `smoke`) has been touched.

### 6. S02 — docs / skill / tracker

- `docs/IW_AI_Core_Testing_Strategy.md` §5 has a new row for the gate; §9 has a new ✅ row for 4.5 (or 4.5 row flipped if it pre-existed). Cross-reference the gate command and the CR-ID exactly.
- `skills/iw-ai-core-testing/SKILL.md` AND `.claude/skills/iw-ai-core-testing/SKILL.md` BOTH gained the new section. Run `diff` between them and assert empty.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.5 is ✅ with CR-00085 + date; a new follow-up row is filed; §11 has a new dated changelog entry citing the exact baseline entry count.
- The baseline entry count cited in the tracker matches S01's `tdd_red_evidence` field verbatim.

### 7. Scope discipline

- `git diff main --stat` (or the merge-time scope gate's equivalent) lists ONLY files in the design's `Impacted Paths` list.
- `orch/db/models.py` is NOT in the diff. If it is, that's a CRITICAL scope violation.
- `docs/IW_AI_Core_Database_Schema.md` is NOT in the diff. If it is, CRITICAL.
- No file under `orch/db/migrations/versions/**` is in the diff. CRITICAL if so.

### 5a. TDD RED Evidence (Backend steps only)

S01 is a backend-impl behaviour step. Apply the 3-point checklist:

1. Confirm `tdd_red_evidence` is present and plausible (ImportError/ModuleNotFoundError, not a fixture / collection / syntax error).
2. Reason whether the RED-empty-baseline test would fail against the pre-implementation tree. The answer is "yes — the scanner module doesn't exist". Confirm this matches the evidence.
3. (Optional) Stash-recheck — risky in worktree, skip unless the gate-runner is comfortable.

S02 is wiring only; the `n/a — wiring only` form is acceptable.

## Test Verification (NON-NEGOTIABLE)

Run unit tests to confirm no regression beyond what the gate adds:

```bash
make test-unit
uv run pytest tests/orch/db/test_column_docs.py -v
```

If `make test-unit` fails on something unrelated to this CR, note it in the report and continue — only CR-00085-caused failures are CRITICAL findings.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability, scope violation | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-impl",
  "work_item": "CR-00085",
  "step_reviewed": "S01+S02",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict`: `pass` if zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE; else `fail`.
