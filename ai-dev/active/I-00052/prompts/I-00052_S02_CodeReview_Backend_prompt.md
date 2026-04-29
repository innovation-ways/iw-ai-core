# I-00052_S02_CodeReview_Backend_prompt

**Work Item**: I-00052 — E2E dashboard container crash logs not captured — fix-cycle agents blind to startup failures
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md
Exception: `docker logs` (read-only) is allowed and is used by the new helper.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these two commands on the files listed in the
implementation report's `files_changed`. Fix nothing yourself — only report.

```bash
make lint          # ruff check — catches ARG001, F811, unused imports, etc.
make format        # ruff format --check — catches formatting drift
```

If either command reports NEW violations in the changed files, classify each one as
a **CRITICAL** finding with `"category": "conventions"`, `"file"`, `"line"`, and
`"description"` quoting the exact violation code.

## Input Files

- `ai-dev/active/I-00052/I-00052_Issue_Design.md` — bug description, acceptance criteria
- `ai-dev/active/I-00052/reports/I-00052_S01_Backend_report.md` — S01 report
- `orch/daemon/browser_env.py` — new `_capture_crashed_container_logs` helper
- `orch/daemon/batch_manager.py` — updated `error_msg` construction

## Output Files

- `ai-dev/active/I-00052/reports/I-00052_S02_CodeReview_Backend_report.md` — review report

## Review Checklist

### Correctness
- [ ] Regex `r"container\s+([\w\-]+)\s+exited\s+\(\d+\)"` correctly extracts container names from compose output — test mentally with `"dependency failed to start: container iw-ai-core-e2e-f00067-e2e-dashboard-1 exited (1)"`
- [ ] `dict.fromkeys()` used for deduplication (preserves order, unlike `set`)
- [ ] `subprocess.run` uses `["docker", "logs", name, "--tail", "50"]` (list form, not shell=True)
- [ ] Both `stdout` and `stderr` captured (`capture_output=True`) — `docker logs` writes to stderr by default
- [ ] `timeout=10` prevents the helper from blocking the failure-recording path
- [ ] Entire per-container block is inside `except Exception` — no raise possible
- [ ] Empty string returned when no names found or all calls fail (AC3 and AC2)
- [ ] `batch_manager.py` calls `browser_env._capture_crashed_container_logs(compose_output)` with the FULL compose output (not just `log_tail`)

### Safety
- [ ] No new `import` statements added to `browser_env.py` beyond what is already present (`subprocess` and `re` are already imported)
- [ ] `# noqa: S603` present on the `subprocess.run` call (list form, not shell — but ruff still flags it for subprocess use)
- [ ] `# noqa: BLE001` present on the bare `except Exception` (intentional broad catch for robustness)
- [ ] The helper does NOT call any other docker commands (only `docker logs`)

### Integration point
- [ ] `batch_manager.py` reads the FULL compose output into a variable before slicing the tail (not just `lines[-20:]`)
- [ ] `container_crash_logs` is appended at the end of `error_msg`, not inserted in the middle

### AC Verification
- [ ] AC1: crash logs will appear in `StepRun.error_message` when a container exits (1)
- [ ] AC2: safe fallback confirmed (except block, no re-raise)
- [ ] AC3: empty compose log → empty string, no subprocess spawned

## Severity Rubric

| Severity | Meaning |
|----------|---------|
| CRITICAL | Helper can raise (missing except), or `shell=True` used (security), or full compose output not passed (partial parse) |
| HIGH | Stdout-only capture (misses docker logs stderr), or no deduplication |
| MED | Missing noqa comments causing lint failures downstream |
| LOW | Minor naming nit |

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00052",
  "overall_status": "pass|fail",
  "mandatory_fix_count": 0,
  "findings": []
}
```

Then call:
```bash
uv run iw step-done I-00052 --step S02 \
  --report ai-dev/active/I-00052/reports/I-00052_S02_CodeReview_Backend_report.md
```
