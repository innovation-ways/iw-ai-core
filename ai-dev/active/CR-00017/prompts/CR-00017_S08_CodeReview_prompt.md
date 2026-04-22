# CR-00017_S08_CodeReview_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step Being Reviewed**: S07 (backend-impl — CLIs)
**Review Step**: S08

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md`
- `ai-dev/active/CR-00017/reports/CR-00017_S07_Backend_report.md`
- All files in S07's `files_changed`

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S08_CodeReview_report.md`

## Review Checklist

### 1. Exit-code discipline (CRITICAL)
- Canonical codes (0/2/3/4/5/1) match the design exactly.
- No expected failure mode leaks a Python traceback to stdout — they emit a formatted error and exit with the right code.
- `1` is reserved for unexpected paths only — anything the spec calls out must map to 2/3/4/5.

### 2. Ack flag enforcement
- `iw migrations apply` refuses without `--i-am-operator` before any safe_migrate call.
- `iw merge-queue unfreeze` refuses without `--ack "<non-empty>"` before any state change.
- Both guards fire before `IW_CORE_AGENT_CONTEXT` check is even relevant.

### 3. Agent-context refusal
- Both dangerous commands check `IW_CORE_AGENT_CONTEXT` early.
- The safe commands (`list-pending`, `dry-run`, `status`) do NOT have the agent-context check.

### 4. Output formats
- `--json` produces valid JSON (test by `json.loads`ing the output).
- Human-readable output is consistent with existing `iw` CLI style.

### 5. Session hygiene
- Any DB read (e.g. `status` reading the log table) closes the session in a `finally`.
- No leaked cursors.

### 6. Registration
- Both groups registered in `orch/cli/__init__.py`.
- `uv run iw --help` actually shows them (S07 report should evidence this).

### 7. Test coverage
- CliRunner tests for every documented exit code.
- Tests mock `safe_migrate` / `migration_pipeline` — no live-DB or real testcontainer for these unit tests.
- Fresh env fixture ensures `IW_CORE_AGENT_CONTEXT` doesn't leak between tests (use `monkeypatch.delenv(..., raising=False)` in setup).

### 8. Project conventions
- click decorators match existing style.
- Error messages use existing `print_err`-style helpers if there are CLI equivalents.

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW. Fix in place.

## Subagent Result Contract

Standard code-review JSON.

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S08
uv run iw step-done CR-00017 --step S08 --report ai-dev/active/CR-00017/reports/CR-00017_S08_CodeReview_report.md
```
