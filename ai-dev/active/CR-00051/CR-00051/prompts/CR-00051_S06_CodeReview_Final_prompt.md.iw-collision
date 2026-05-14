# CR-00051_S06_CodeReview_Final_prompt

**Work Item**: CR-00051 — Semgrep baseline cleanup
**Step Being Reviewed**: S01 + S03 + S05 (cross-agent)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

This CR leaves migrations unchanged.

## Input Files

- **Runtime step state** (authoritative): `uv run iw item-status CR-00051 --json`.
- `ai-dev/active/CR-00051/CR-00051_CR_Design.md` — design doc.
- `ai-dev/active/CR-00051/CR-00051_Functional.md` — functional doc (sanity-check that the user-facing claim of "no behaviour change" holds).
- All step reports under `ai-dev/active/CR-00051/reports/`.
- All files in the union of S01, S03, and S05 `files_changed`.

## Output Files

- `ai-dev/active/CR-00051/reports/CR-00051_S06_CodeReview_Final_report.md`

## Context

This is the final cross-agent review before QV gates run. Per-step reviews (S02, S04) already verified each step's deliverable in isolation. Your job is to verify that **the whole CR coheres**: every AC (AC1–AC8) is met, every Invariant (I1–I4) is preserved, every test will pass against the just-applied suppressions + Makefile flag set, and no behavioural drift sneaked in.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Both must pass for the union of S01+S03+S05 `files_changed`.

## Review Checklist

### 1. Acceptance Criteria traceability matrix

Build a table in your review report:

| AC | Met by | Evidence |
|----|--------|----------|
| AC1 | S01+S03 | `make security-sast` exits 0 (run it now and record stdout tail) |
| AC2 | S01+S03 | Every `# nosemgrep` / `{# nosemgrep #}` carries a same-line rationale after `—` |
| AC3 | S01 | `# nosec B602` / `# noqa: S701` preserved on every annotated line |
| AC4 | S05 | Unit test asserts `write_button_attrs` macro emits exactly `""` for fresh and exactly the captured constant for stale; macro file unchanged from pre-CR state |
| AC5 | S01 (Makefile flag) | `make security-sast` includes `--exclude-rule generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var`; the macro is unchanged; AC4's test locks the constant-output rationale |
| AC6 | S01 | Triage section present in `docs/IW_AI_Core_Testing_Strategy.md` |
| AC7 | S05 | `tests/integration/test_security_sast_baseline.py` invokes semgrep with the four `--exclude-rule` flags and asserts 0 findings |
| AC8 | S01 | Comment block above `security-sast:` target lists all four excluded rules with rationale |

If any AC is not met, fail the review.

### 2. Invariants

- **I1**: For every line that previously carried `# nosec` or `# noqa`, both the original marker and the new `# nosemgrep` are present. Grep:
  ```bash
  rg "# nosec B602" orch/ dashboard/routers/
  rg "# noqa: S701" orch/daemon/worktree_compose.py
  ```
  Both grep counts must be ≥ their pre-CR values.
- **I2**: No new `| safe` filter has appeared. Grep the union of S03's `files_changed` for `| safe`. There should be exactly 16 matches (the pre-existing ones, one per file).
- **I3**: Tests use real Jinja2 rendering (no mocked env). Confirm by reading `tests/unit/test_db_guard_macro.py` — the env is `jinja2.Environment` with a real `FileSystemLoader`.
- **I4**: The four Makefile `--exclude-rule` flags exactly match the four-entry tuple `SEMGREP_EXCLUDE_RULES` in `tests/integration/test_security_sast_baseline.py`. Diff the two lists by inspection; any mismatch is **CRITICAL** (the test will silently pass against a different rule set than CI uses).

### 3. Behaviour drift sanity check

Run a dashboard import smoke check:
```bash
uv run python -c "from dashboard.app import app; print('import OK')"
```
Any error here is **CRITICAL**.

Render a known-good page through the test client (if cheap) to confirm Jinja templates parse:
```bash
uv run pytest tests/dashboard/ -k "queue or running or worktrees or batch_detail or project_code or research" -v 2>/dev/null | tail -20
```
This is best-effort — if no tests match, skip silently.

Verify `dashboard/templates/macros/db_guard.html` is byte-identical to its pre-CR state:
```bash
git diff main -- dashboard/templates/macros/db_guard.html
```
Output must be empty. Any non-empty diff is **CRITICAL** (S03 should NOT have touched the macro; if it did, AC4/AC5 reasoning is compromised).

### 4. Triage doc completeness

Read the new section in `docs/IW_AI_Core_Testing_Strategy.md`. It must:
- State that `# nosec` does not silence Semgrep.
- Note that in-macro `{# nosemgrep #}` does NOT propagate to call-site analyses.
- Show the Python (`# nosemgrep`), Jinja (`{# nosemgrep #}`), and Makefile (`--exclude-rule`) syntaxes.
- Enumerate the four legitimate reasons to suppress.
- Require a same-line rationale for per-line suppressions and a rationale comment block above the target for Makefile exclude flags.

A section missing any of these → **MEDIUM_FIXABLE**.

### 5. Test quality

For both new tests:
- Assertions are strong (`assert ==` not `assert is not None`).
- Skip reasons are clear and actionable.
- No fixture leakage (no `tmp_path` reuse across tests, no env vars left set).
- No reliance on `importlib.reload(orch.config)` (forbidden per `tests/CLAUDE.md`).
- The unit test does NOT modify, revert, or `git stash` `db_guard.html`. RED evidence was captured via the wrong-constant technique (see S05 prompt §3).

### 6. Scope discipline

Run `git diff --name-only main...HEAD` (or the equivalent for your worktree). The diff must be a strict subset of `workflow-manifest.json:scope.allowed_paths`. Any file outside that list is **CRITICAL**. In particular:
- `dashboard/templates/macros/db_guard.html` should NOT be in the diff. It is not in `scope.allowed_paths`. The test reads it but no agent edits it.
- None of the 12 `write_button_attrs(request)` caller files (other than `docs_detail.html` for the `:223` Class B annotation) should appear in the diff.

### 7. Self-assessment readiness

S15 will run the iw-item-analyze skill on this item. Verify that:
- Reports for S01, S03, S05 are present.
- Reports for the QV gates (S07–S14) will be generated by the daemon; not your concern here.
- The execution log is not littered with retried fix cycles for trivial reasons (if it is, note it — the self-assess will catch it but pre-empting helps).

## Test Verification (NON-NEGOTIABLE)

Run **all** of:
```bash
uv run pytest tests/unit/test_db_guard_macro.py -v
uv run pytest tests/integration/test_security_sast_baseline.py -v
make security-sast
```

All three must succeed (the integration test may skip if semgrep isn't installed; that's acceptable for this step — the `make security-sast` run is the authoritative check).

Record outputs in your report.

## Severity Levels

Standard table.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview_Final",
  "work_item": "CR-00051",
  "step_reviewed": "S01+S03+S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "all 3 gates passed: unit test (3 passed), integration test (1 passed or skipped), make security-sast (exit 0)",
  "notes": "Include the AC traceability table in the report body. Confirm db_guard.html is unchanged from main."
}
```
