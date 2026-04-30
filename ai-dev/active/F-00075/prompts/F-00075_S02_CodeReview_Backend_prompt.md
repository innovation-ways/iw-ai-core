# F-00075_S02_CodeReview_Backend_prompt

**Work Item**: F-00075 -- MiniMax Coding Plan usage from /coding_plan/remains (replace local SQLite estimate)
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

(Same policy as in S01. Do not run docker container/volume/network commands. Read-only `docker ps` / `docker logs` are allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md)

## ⛔ Migrations: agents generate, daemon applies

This work item touches no migrations. Do not run alembic.

## Input Files

- `ai-dev/active/F-00075/F-00075_Feature_Design.md`
- `ai-dev/active/F-00075/reports/F-00075_S01_Backend_report.md`
- The files changed by S01 (typically `orch/llm_usage.py`, possibly `tests/unit/test_llm_usage.py`, possibly `.env.example`).

## Output Files

- `ai-dev/active/F-00075/reports/F-00075_S02_CodeReview_Backend_report.md`

## Context

Per-agent code review of S01. Verify the backend slice meets the design doc and the project's conventions in `CLAUDE.md` / `orch/CLAUDE.md`.

## Requirements — Review Checklist

### Correctness vs design

- [ ] `_load_minimax_key()` reads `IW_MINIMAX_API_KEY` first, then `~/.local/share/opencode/auth.json`. Empty string is treated the same as unset.
- [ ] `_load_minimax_key()` never raises — file missing, permission denied, malformed JSON, missing key all return `None`.
- [ ] `_minimax_usage_remote()` uses `Authorization: Bearer {key}` and `Accept: application/json` headers exactly.
- [ ] Optional `IW_MINIMAX_GROUP_ID` is appended as `?GroupId=<value>` only when set.
- [ ] `httpx.get` is called synchronously with `timeout` ≤ 10 seconds.
- [ ] The `MiniMax-M*` row is selected by exact `model_name == "MiniMax-M*"` match (not a prefix or contains).
- [ ] `used = total - usage_count` (not the inverse — this is the documented gotcha).
- [ ] `pct` is `min(100, round(...))` — capped, integer.
- [ ] `_format_reset` returns `"Xh Ym"` for ≥1h, `"Ym"` for <1h, `None` for `<=0`.
- [ ] `_minimax_usage()` never raises and returns `{"block_pct": int, "block_reset": str | None}` for every code path.
- [ ] On missing key: `logger.warning` (one-time message), no HTTP call, returns `{0, None}`.
- [ ] On any remote failure: `logger.exception` is called once and returns `{0, None}`. No fallback to a SQLite path or any other local computation.
- [ ] The outer `except` for `_minimax_usage()` inside `get_llm_usage()` returns `{"block_pct": 0, "block_reset": None}` (two-key dict matching the new contract), not the legacy `{"block_pct": 0}`. The Claude outer wrapper must be unchanged.

### Removal of SQLite path

- [ ] `grep -nE 'sqlite3|_OPENCODE_DB|_FIVE_H_MS|_MINIMAX_5H_LIMIT|IW_MINIMAX_5H_LIMIT|opencode\.db' orch/llm_usage.py` returns zero matches. Run this and paste the result in your report.
- [ ] If `from pathlib import Path` was only used by the deleted `_OPENCODE_DB`, it has been removed too. Otherwise it is still needed (verify by grep).
- [ ] Module docstring is updated to reflect the new behavior. Claude paragraphs are unchanged.

### No regression for Claude

- [ ] `_claude_usage()`, `_run_ccusage()`, `_block_start()`, `_sum_jsonl_tokens()`, `_CLAUDE_5H_LIMIT`, `_CLAUDE_WEEKLY_LIMIT`, `_CLAUDE_BLOCK_ANCHOR_MIN` are byte-identical to `main` for the same inputs. If `_format_reset` was extracted and Claude was migrated to use it, run a quick differential: feed the same `remains_total_seconds` and confirm the produced strings match the previous Claude format exactly (same hour/minute pluralization, same separators).
- [ ] No new fields are required by the Claude template branch.

### Cache and side effects

- [ ] The 60s `_CACHE_TTL` / `_cache` / `_cache_lock` is reused. No new module-level cache was introduced.
- [ ] `_minimax_usage()` is invoked from `get_llm_usage()` exactly as before — no signature change.

### Security and secrets

- [ ] The API key is never logged. Specifically `logger.exception` does not include the key in any message format.
- [ ] No PII in error messages.
- [ ] Tests do not commit a real API key (the captured fixture is response-body-only).

### Code quality

- [ ] Type hints on all new functions: `-> str | None`, `-> dict[str, Any]`, `-> str | None`.
- [ ] `from __future__ import annotations` retained at the top of the module.
- [ ] No unused imports.
- [ ] No dead code from the deleted SQLite path.
- [ ] `make lint`, `make typecheck`, `make test-unit` all pass after the change. Re-run them as part of the review.

### Configuration documentation

- [ ] If `.env.example` exists, both `IW_MINIMAX_API_KEY` and `IW_MINIMAX_GROUP_ID` are documented as optional commented-out lines.

## Output

Write `ai-dev/active/F-00075/reports/F-00075_S02_CodeReview_Backend_report.md` containing:

- A pass/fail line for every checklist item above.
- A list of findings with severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`).
- For any `CRITICAL` or `HIGH`, recommend a fix.
- A final overall recommendation: `approve` or `request_changes`.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00075",
  "completion_status": "complete",
  "review_outcome": "approve|request_changes",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file": "", "line": 0, "description": ""}
  ],
  "tests_passed": true,
  "notes": ""
}
```
