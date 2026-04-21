# F-00057_S09_CodeReview_Final_prompt

**Work Item**: F-00057 — `iw oss` CLI + DB persistence
**Step**: S09
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/F-00057/F-00057_Feature_Design.md`
- All prior reports in `ai-dev/active/F-00057/reports/`:
  - `F-00057_S01_Database_report.md`
  - `F-00057_S02_CodeReview_report.md`
  - `F-00057_S03_Backend_report.md`
  - `F-00057_S04_CodeReview_report.md`
  - `F-00057_S05_Backend_report.md`
  - `F-00057_S06_CodeReview_report.md`
  - `F-00057_S07_Tests_report.md`
  - `F-00057_S08_CodeReview_report.md`

## Output Files

- `ai-dev/active/F-00057/reports/F-00057_S09_CodeReview_Final_report.md`

## Context

You are performing the **global cross-step review** for F-00057. Each prior step has been reviewed in isolation; your job is to verify that the layers compose correctly, that the design's acceptance criteria are fully met, and that no regressions were introduced elsewhere in the codebase.

## Review Checklist

### 1. Cross-layer consistency

- **ORM model names match the migration enum names** exactly (`ossscan_status`, etc.) — a mismatch will surface only at runtime.
- **Service module uses the ORM columns** with the right types (e.g., `head_sha: str | None`, not `str`).
- **CLI's `--json` output shape** matches the `summary_json` rolled up in `oss_scan` and the AC1 contract.
- **`pill_color` computed in `persistence.py` matches** what the CLI returns in `status --json` (single source of truth — should be the same function).
- **`head_sha` captured in scanner** appears in the CLI's `status --json` output verbatim.
- **Enable → Scan → Status flow** is end-to-end coherent: enable writes flag, scan reads flag, status reads persistence.

### 2. Acceptance-criteria coverage

Walk each AC (AC1 through AC6) and verify a specific test exists:

- **AC1** (scan persists + status JSON): `test_oss_cli.py::test_oss_status_json_shape` or similar.
- **AC2** (install --dry-run): `test_oss_cli.py::test_oss_install_dry_run_lists_missing`.
- **AC3** (install runs script): covered by integration or documented as manual (streaming subprocess is hard to test without a live installer — flag if only documented, not executed).
- **AC4** (enable flips flag + writes toml, idempotent): `test_oss_cli.py::test_oss_enable_writes_config_and_flips_flag`.
- **AC5** (stale detection): `test_oss_freshness.py::test_stale_detection_after_commit`.
- **AC6** (help discoverability): `test_oss_cli.py` or manual verification.

Any AC without a corresponding test is a CRITICAL finding.

### 3. No regressions elsewhere

- Run `make test-unit` — all existing unit tests pass.
- Run `make test-integration` — all existing integration tests pass.
- Grep for new imports of `orch.oss` or `scripts.scan` from unexpected places (dashboard, daemon) — none should exist.
- `orch/cli/main.py` only has the `oss` group added; no other groups were touched.

### 4. Design-doc file manifest alignment

- Every file listed in the design doc's *File Manifest* has been created or modified.
- No files were created that aren't listed (would indicate scope creep).

### 5. TDD evidence

- Each implementation step's tests were (per reports) red-before-green. Flag if any report omits this.

### 6. CLAUDE.md compliance

- Testcontainer-only tests ✓.
- No `importlib.reload(orch.config)` ✓.
- Dialect URL replace applied where needed ✓.
- `DaemonEvent.metadata` rule respected (not directly applicable here but confirms awareness of SQLAlchemy reserved names).

### 7. Code hygiene

- No debug prints left in `orch/oss/*.py`.
- No commented-out code.
- Type hints present on all public functions.
- `make lint` + `uv run mypy orch/` both clean.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass.
2. `make test-integration` — pass.
3. `make lint` — pass.
4. `uv run ruff format --check .` — pass.
5. `uv run mypy orch/` — pass.
6. `uv run iw oss --help` — all 7 subcommands listed.

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-final-impl",
  "work_item": "F-00057",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "acceptance_criteria_coverage": {
    "AC1": "covered by test_...",
    "AC2": "covered by test_...",
    "AC3": "covered by test_... (or 'manually documented — see notes')",
    "AC4": "covered by test_...",
    "AC5": "covered by test_...",
    "AC6": "covered by test_..."
  },
  "notes": ""
}
```

Only `verdict: pass` when: zero CRITICAL + HIGH + MEDIUM_FIXABLE findings AND every AC has a corresponding test or documented manual coverage.
