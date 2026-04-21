# F-00057_S04_CodeReview_prompt

**Work Item**: F-00057
**Step Being Reviewed**: S03 (backend-impl — `orch/oss/` service module)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/F-00057/F-00057_Feature_Design.md`
- `ai-dev/active/F-00057/reports/F-00057_S03_Backend_report.md`
- Files listed in S03 report (`orch/oss/*.py`, tests)

## Output Files

- `ai-dev/active/F-00057/reports/F-00057_S04_CodeReview_report.md`

## Context

Review S03's backend service module. Focus: subprocess hygiene, DB write atomicity, correctness of `pill_color` computation, error paths.

## Review Checklist

### 1. Architecture Compliance

- `orch/oss/` does NOT import from `orch/cli/` or `dashboard/` (one-way layer dependencies).
- Does NOT touch `scripts/scan.py` directly — invokes via subprocess only.
- ORM used throughout; no raw SQL in service layer.
- Session factory is INJECTED, not imported as a global, so tests can swap it.

### 2. Code Quality / Subprocess hygiene

- `asyncio.create_subprocess_exec` used — not `subprocess.run` (would block the event loop).
- stdout/stderr bounded (don't hold unlimited output in memory — 2KB truncation per `oss_tool_run.output_summary`).
- On subprocess cancellation (task cancel), the child process is terminated cleanly.
- Timeout on subprocess invocation (bounded duration).
- Tool-availability probe does not invoke subprocesses for tools that `shutil.which` already reports missing.

### 3. Persistence atomicity

- All inserts for a single scan happen in one transaction; no partial-state leak if an insert mid-way fails.
- `pill_color` computation matches invariant #3 exactly:
  - `must_fail > 0 OR must_human_required > 0` → `red`
  - else `should_fail > 0 OR should_human_required > 0` → `yellow`
  - else → `green`
- `head_sha` captured BEFORE subprocess start (invariant #4).
- `compute_summary_counts` keys match the dashboard contract in AC1.

### 4. Error paths

- Missing `.iw/oss-publish-findings.json` after subprocess exit → `oss_scan.status='error'` with clear message.
- Malformed JSON → same.
- Subprocess times out → same.
- Tier-1 tool genuinely missing at scan time → `oss_tool_run.status='missing'` persisted; scan continues (does NOT abort).

### 5. Project Conventions

- Match `orch/doc_service.py` (or similar existing service) for session usage / naming.
- Per-function docstrings describe contract.

### 6. Testing

- `tests/integration/test_oss_scanner.py` uses a scratch git repo fixture (tmp_path + `git init`), not the live iw-ai-core repo.
- `tests/integration/test_oss_persistence.py` covers all three pill-color branches + missing-tool case.
- Unit tests for `tool_probe.probe_tier1` mock `shutil.which` — no real binaries touched.
- Unit test for `config_writer.write_project_config` verifies idempotency (second call produces no diff).

### 7. Security

- Subprocess `env` is controlled — inherits but does not leak secrets from the parent process beyond what's needed.
- No `shell=True` anywhere.
- Paths passed to subprocess are absolute, not user-controlled strings.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass.
2. `make test-integration` — pass.
3. `make lint` — pass.
4. `uv run mypy orch/oss/` — pass.

## Review Result Contract

Standard JSON shape. `verdict: pass` only if zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
