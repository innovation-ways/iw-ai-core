# I00108_S05_CodeReview_Final_prompt

**Work Item**: I-00108 -- `iw doc-update` new-doc without `--tier`/`--editorial-category` should be exit 2 usage error, not exit 3 TypeError
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Standard policy. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migration in this item. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00108 --json`.
- `ai-dev/active/I-00108/I-00108_Issue_Design.md` -- Design document.
- `ai-dev/active/I-00108/I-00108_Functional.md` -- Functional summary.
- All step reports:
  - `ai-dev/active/I-00108/reports/I-00108_S01_Backend_report.md`
  - `ai-dev/active/I-00108/reports/I-00108_S02_CodeReview_report.md`
  - `ai-dev/active/I-00108/reports/I-00108_S03_Tests_report.md`
  - `ai-dev/active/I-00108/reports/I-00108_S04_CodeReview_report.md`
- All files listed in any implementation report's `files_changed` (expected union: `orch/cli/doc_commands.py`, `tests/integration/cli/test_doc_update_contract.py`).

## Output Files

- `ai-dev/active/I-00108/reports/I-00108_S05_CodeReview_Final_report.md` -- Final review report.

## Context

You are performing the final cross-agent review of all implementation work for **I-00108**. Per-agent reviews (S02, S04) have already covered their respective steps; your job is to catch the integration concerns they could not — scope discipline across both files, AC end-to-end coverage, and a clean final test run.

## Read the Design Document FIRST

- `## Acceptance Criteria` — AC1 (exit 2 + clear stderr + no row created) and AC2 (xfail removed, both regression tests green). EVERY criterion must be covered end-to-end by the combined work of S01 + S03.
- `## TDD Approach` — the reproduction test (now GREEN, marker removed) plus the two new regression tests are the full test surface.

## Pre-Review Lint, Format, and Assertion Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
make test-assertions
```

If any reports NEW violations or trips the assertion scanner, classify each as a **CRITICAL** finding.

## Review Checklist

### 1. Completeness vs Design Document

- **AC1 covered**: confirm `orch/cli/doc_commands.py` has the pre-check; manually trace the code path for the new-doc-without-tier case → it reaches `output_error(ctx, ..., 2)` before any `DocService.create_doc()` call.
- **AC2 covered**: confirm the xfail marker is REMOVED from `test_doc_update_new_doc_without_tier_is_clean_usage_error`; confirm both new tests (`test_doc_update_existing_doc_update_without_tier_succeeds` and `test_doc_update_new_doc_with_tier_and_category_succeeds`) exist.
- No TODO / FIXME / placeholder comments in any changed file.

### 2. Scope integrity (CRITICAL)

```bash
git diff origin/main -- orch/ dashboard/ executor/ scripts/ | head -1
```

The diff for `orch/` MUST contain ONLY `orch/cli/doc_commands.py`. Any other file under `orch/`, or any file under `dashboard/` / `executor/` / `scripts/`, is a **CRITICAL** scope-creep finding.

```bash
git diff origin/main --stat
```

The combined diff must be limited to:
- `orch/cli/doc_commands.py`
- `tests/integration/cli/test_doc_update_contract.py`
- The `ai-dev/active/I-00108/` package itself (design, manifest, prompts, reports).

Any other modified file is a HIGH finding (scope expansion).

### 3. Update path still optional (cross-step consistency)

- S01's pre-check fires ONLY when `existing is None`. S03's `test_doc_update_existing_doc_update_without_tier_succeeds` pins this. Verify:
  - The S03 test seeds an existing doc, then runs `doc-update` without `--tier`/`--editorial-category`, and asserts exit 0.
  - The S01 pre-check guards on `existing is None` (or the equivalent `svc.get_doc(...) is None`), NOT just on `tier is None` — otherwise the update path would also be refused, contradicting S03's regression test.
- A mismatch here (pre-check fires too broadly, regression test passes by accident) is a CRITICAL cross-cutting finding.

### 4. Reproduction test was actually flipped GREEN

- `test_doc_update_new_doc_without_tier_is_clean_usage_error` no longer has `@pytest.mark.xfail`.
- Its assertions remain: `result.exit_code == 2` and `"tier" in result.stderr.lower()` (the contract pinned by CR-00073). If S03 weakened or removed assertions, HIGH.
- If `@pytest.mark.xfail` is still present, CRITICAL: the test cannot record as a normal pass.

### 5. Architecture / convention compliance

- S01's change is contained to the `doc_update` callback in `orch/cli/doc_commands.py`. No edit to `orch/doc_service.py` (the service-layer `create_doc` signature is intentional). No new abstractions.
- The pre-check uses `output_error(ctx, msg, 2)` (consistent with the existing exit-1/exit-2/exit-3 paths in the same file).
- The error message contains the substring `"tier"` (lowercase substring; the contract test asserts on it).
- S03's tests are in-process via `CliRunner` (not subprocess via `iw_subprocess`) — matches the style of the existing 5 `test_doc_update_*` tests.

### 6. Security (cross-cutting)

- No new attack surface. The pre-check refuses input before any service-layer call; the refused input is not echoed back to stderr (only the message + flag names are emitted). Verify the error message does NOT echo the user-supplied `doc_id` through any unescaped log path that could pollute terminals.

### 7. Test files appear in `files_changed`

The design doc's §File Manifest test row (`tests/integration/cli/test_doc_update_contract.py`) MUST appear in S03's `files_changed`. Missing → CRITICAL.

### 8. No format/style regressions

`make format-check` and `make lint` must report clean across both changed files. The S02 / S04 reviews already checked their respective steps; you re-run holistically.

## Test Verification (NON-NEGOTIABLE)

Run **targeted** tests for the contract suite and one cross-check of the broader CLI contract layer to catch any cross-file regression:

```bash
uv run pytest tests/integration/cli/test_doc_update_contract.py -v --no-cov 2>&1 | tail -25
uv run pytest tests/integration/cli/ tests/integration/test_cli_spec_conformance.py --no-cov -q 2>&1 | tail -10
```

Expected:
- `test_doc_update_contract.py`: 8 passed, 0 failed, 0 xfailed.
- `tests/integration/cli/ + test_cli_spec_conformance.py`: matches the pre-merge baseline from CR-00073 (50 passed + 1 xfailed for CR-00073's own files) **minus** the 1 xfail that S03 just removed, **plus** the 2 new regression tests → expect **52 passed, 0 xfailed**. Any new failure here is a CRITICAL cross-file regression.

Do NOT run `make test-unit`, `make test-integration`, or `make test-cli-contract` — those are S06–S13 QV gates and re-running them here duplicates work and risks a step timeout.

## Severity Levels

- **CRITICAL** — fix or merge will be blocked.
- **HIGH** — must fix before merge.
- **MEDIUM_FIXABLE** — should fix this cycle.
- **MEDIUM_SUGGESTION** — defer if tight.
- **LOW** — nit / style.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00108",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": false
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "8 passed (doc-update contract); 52 passed (full cli/ + conformance)",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
- `missing_requirements`: list any AC1..AC2 with no corresponding implementation. Each missing requirement is automatically a CRITICAL finding.
- `cross_cutting: true` on any finding spanning S01's code change and S03's tests (especially the update-path pre-check guard from §3 above).
