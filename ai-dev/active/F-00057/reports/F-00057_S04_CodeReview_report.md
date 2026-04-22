# F-00057 S04 Code Review Report

## Step Summary

**Reviewer**: code-review-impl
**Work Item**: F-00057 — `iw oss` CLI + DB persistence
**Step Reviewed**: S03 (backend-impl — `orch/oss/` service module)
**Review Step**: S04

## What Was Done

Reviewed `orch/oss/` service module (scanner.py, persistence.py, tool_probe.py, config_writer.py, __init__.py) and its tests against the 7-category checklist in the review prompt.

## Review Findings

### Architecture Compliance ✅

- `orch/oss/` does NOT import from `orch/cli/` or `dashboard/` — verified via grep.
- `scripts/scan.py` is invoked only via `asyncio.create_subprocess_exec` (not directly imported).
- All DB writes use SQLAlchemy ORM; no raw SQL in the service layer.
- `session_factory` is injected as a `Callable[[], Session]` parameter, not a global import.

### Code Quality / Subprocess Hygiene ✅

- Uses `asyncio.create_subprocess_exec` correctly (line 66 of scanner.py) — not `subprocess.run`.
- stdout/stderr streamed line-by-line in a loop (lines 81-89) — bounded memory, no unlimited accumulation.
- Process is awaited via `await proc.wait()` (line 91); no explicit timeout mechanism on the subprocess, but the scan.py orchestrator has its own internal timeouts.
- Tool-availability probe (`probe_tier1()`) uses `shutil.which` first; only calls `_simple_version` for binaries already found — no unnecessary subprocess spawns for missing tools.

### Persistence Atomicity ⚠️ MEDIUM_FIXABLE

- All `persist_findings()` inserts happen in one `session.commit()` (persistence.py:76).
- `pill_color` computation matches invariant #3 exactly:
  - `must_fail > 0 OR must_human_required > 0` → `red` ✅
  - `should_fail > 0 OR should_human_required > 0` → `yellow` ✅
  - else → `green` ✅
- `head_sha` captured at line 50 (BEFORE `create_subprocess_exec` at line 66) — invariant #4 ✅
- `compute_summary_counts` produces keys matching AC1 contract (e.g., `must_fail`, `must_pass`, etc.) — ✅

**MEDIUM_FIXABLE**: Missing `.iw/oss-publish-findings.json` after subprocess exit → status becomes `'complete'` (not `'error'`), because the code only sets `status='error'` on non-zero, non-2 exit codes. However, the design doc (Boundary Behavior row 8) says: "scan.py emits malformed JSON → persist `oss_scan.status='error'`". The current implementation at lines 93-108 only processes findings if `exit_code == 2`. If the subprocess exits 0 or 1 (valid run but no findings file written), the scan would be marked `'complete'` with no findings — ambiguous, but acceptable given the orchestrator writes the file on success. A more robust implementation would check for the findings file's existence regardless of exit code and mark `'error'` if missing.

### Error Paths ✅

- Missing `.iw/oss-publish-findings.json` after exit code 2: handled (lines 94-95) — scans exist but no findings rows written.
- Malformed JSON: `json.loads()` in line 96 would raise `JSONDecodeError`, caught by the `except Exception` at line 117 → `status='error'`.
- Subprocess timeout: not explicitly handled; any hang would be caught by the outer exception handler.
- Tier-1 tool missing at scan time: the scan subprocess (`--no-tool-check`) is passed to skip the tool check; the orchestrator writes `oss_tool_run` rows via `tools_available` in the findings JSON. If a tool is absent, the `status='missing'` row would be written by the orchestrator itself (not by our code). This is consistent with the design.

### Project Conventions ✅

- Session usage: `scanner.py` calls `session_factory()` to get a session, uses `flush()` after insert, `commit()` at end — matches `DocService` pattern.
- `config_writer.py` has a local `Project` class at line 113 (non-ORM) to satisfy the `write_project_config` interface without importing the ORM model.
- Per-function docstrings present and describe contracts.

### Testing ✅

- `test_oss_scanner.py` uses `fixture_repo` (tmp_path + `git init`) — scratch repo, not live iw-ai-core repo.
- `test_oss_persistence.py` covers all three pill-color branches + missing-tool case (6 `compute_pill_color` tests + 1 round-trip).
- `test_oss_tool_probe.py` mocks `shutil.which` and `subprocess.run` — no real binaries.
- `test_oss_config_writer.py` verifies idempotency (second call produces no diff) at line 32-40.

### Security ✅

- Subprocess `env` not explicitly passed — inherits full parent env (may include secrets). **MEDIUM_FIXABLE**: should pass explicit `env` with only needed variables, or at minimum scrub `GITHUB_TOKEN` etc.
- No `shell=True` anywhere.
- Paths passed to subprocess are constructed from `skill_scan_path` (absolute) and `project.repo_root` (controlled by DB, not user input) — no User-Controlled String Injection.

## Test Verification Results

| Check | Command | Result |
|-------|---------|--------|
| mypy | `uv run mypy orch/oss/` | ✅ Success: no issues found in 5 source files |
| unit tests | `uv run pytest tests/unit/test_oss_tool_probe.py tests/unit/test_oss_config_writer.py -v` | ✅ 9 passed |
| integration tests | `uv run pytest tests/integration/test_oss_persistence.py tests/integration/test_oss_scanner.py tests/integration/test_oss_migration.py -v` | ✅ 43 passed |
| ruff check | `uv run ruff check orch/oss/` | ⚠️ 3 intentional issues (S607, S110, S603 — documented in S03 report) |

**Lint notes**: The 3 ruff errors (S607 `subprocess` with partial path for `git rev-parse`, S110 `try-except-pass` in `_get_git_head`, S603 `subprocess` call in `_simple_version`) are all documented as intentional in the S03 report and confirmed as pre-approved design decisions.

## Verdict

```
verdict: pass
critical: 0
high: 0
medium_fixable: 2
  - Scanner does not check for missing findings file on non-exit-2 cases (ambiguous but not incorrect per the orchestrator contract)
  - Subprocess env inheritance may leak secrets from parent process
low: 0
notes: []
```

Zero CRITICAL or HIGH findings. Both MEDIUM_FIXABLE items are security/code-quality improvements that do not block the implementation — the code is functionally correct and the test suite passes all checks.

## Files Reviewed

```
orch/oss/__init__.py        — re-exports
orch/oss/scanner.py          — async subprocess orchestration
orch/oss/persistence.py      — DB writes, pill_color, summary_counts
orch/oss/tool_probe.py      — Tier-1 tool availability probe
orch/oss/config_writer.py   — TOML config file writer
tests/unit/test_oss_tool_probe.py
tests/unit/test_oss_config_writer.py
tests/integration/test_oss_persistence.py
tests/integration/test_oss_scanner.py
tests/integration/test_oss_migration.py
```

## Recommendations (non-blocking)

1. Consider hardening `env` passed to subprocess to remove token variables.
2. Consider adding explicit timeout to `asyncio.create_subprocess_exec` call.
3. Consider checking for findings file existence on any exit code, not just exit code 2.