# I-00116_S02_CodeReview_Backend_prompt

**Work Item**: I-00116
**Step**: S02
**Agent**: CodeReview (reviewing S01 — Backend)

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step makes no DB changes.

## Scope of review

ONLY review files changed by S01 — `orch/daemon/step_monitor.py`. The workflow manifest's `scope.allowed_paths` declares the item-level allowlist; per S05 of this same item, your diff scope is restricted to S01's files specifically. If you find changes outside that single file, flag them as CRITICAL scope violation.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00116 --json`
- **Design**: `ai-dev/active/I-00116/I-00116_Issue_Design.md`
- **S01 report**: `ai-dev/active/I-00116/reports/I-00116_S01_Backend_report.md`
- **The changed file**: `orch/daemon/step_monitor.py`
- **Reference**: I-00113's existing `_probe_for_child` logic in the same file

## Output Files

- Review report: `ai-dev/active/I-00116/reports/I-00116_S02_CodeReview_report.md`

## Review Checklist

| # | Check | How to verify |
|---|-------|---------------|
| 1 | `_try_recover_completed_review_step` exists with the exact signature from the design | grep the function definition |
| 2 | Helper is gated on `run.step_type in ('code_review', 'code_review_final')` | inspect the early-return |
| 3 | Report glob is anchored on BOTH `work_item_id` AND `step_id` | check the glob string for both components — `{run.work_item_id}_{run.step_id}_*_report.md` |
| 4 | mtime guard: `os.path.getmtime(report) > run.started_at.timestamp()` | a stale report from a prior run MUST NOT satisfy the guard |
| 5 | JSON parse extracts the first ` ```json ` fenced block, not the whole file | malformed report → returns False |
| 6 | Missing `verdict` or `mandatory_fix_count` → returns False (caller falls through to `_handle_crashed`) | defensive parsing |
| 7 | Verdict mapping: `pass` → completed; `fail` + `mandatory_fix_count>0` → needs_fix; else False | exact mapping per design |
| 8 | DaemonEvent emitted with type `step_run_recovered_from_report` AND `event_metadata` (NOT `metadata`) | CLAUDE.md critical rule |
| 9 | DaemonEvent payload includes work_item_id, step_id, step_run_id, report_path, report_mtime_iso, verdict, mandatory_fix_count | per design §3 |
| 10 | Wiring in `_check_step_health` invokes `_try_recover_completed_review_step` BEFORE `_handle_crashed`, only after `_probe_for_child` returns False | the order matters |
| 11 | `_probe_for_child` and `_handle_crashed` themselves are UNCHANGED | I-00113's contract and the original crash path remain intact |
| 12 | INFO log uses `%`-style placeholders (not f-string inside `logger.info(...)`) | grep for `logger.info(f"`)... should not appear in your diff |
| 13 | `datetime.now(UTC)` (not `datetime.utcnow()`) | grep |
| 14 | Non-code-review step types fall through to `_handle_crashed` unchanged | the helper's early return must keep them on the old path |

## Required Gates (pre-flight)

```bash
make lint
make format-check
```

Both MUST pass. If either fails on S01's edits, report it as a HIGH finding.

## Verdict Contract (REQUIRED in your report)

Your report MUST end with a ```` ```json ```` fenced block containing:

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00116",
  "step_reviewed": "S01",
  "verdict": "pass" | "fail",
  "findings": [
    {"severity": "CRITICAL"|"HIGH"|"MEDIUM"|"LOW", "file": "...", "issue": "..."}
  ],
  "mandatory_fix_count": <int>,
  "tests_passed": true | false,
  "test_summary": "..."
}
```

This JSON block IS what the I-00116 recovery path you are reviewing parses. Writing it incorrectly will defeat the very test of the system you are reviewing.

## Step Done Contract

After writing the report, call `iw step-done S02 --report ai-dev/active/I-00116/reports/I-00116_S02_CodeReview_report.md`. **DO NOT exit without calling `iw step-done`** — the loop bug this item exists to fix is *exactly* the result of forgetting this call. If you must exit on a blocker, call `iw step-fail` with the reason.
