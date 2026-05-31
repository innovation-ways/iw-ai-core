# I-00122_S04_CodeReview_prompt

**Work Item**: I-00122 — db-start guard against empty-DB displacement
**Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Read-only Docker introspection only. The tests under review must not invoke real
Docker — verify that.

## Input Files

- `uv run iw item-status I-00122 --json`.
- `ai-dev/active/I-00122/I-00122_Issue_Design.md`.
- `ai-dev/active/I-00122/reports/I-00122_S03_Tests_report.md`.
- `tests/unit/test_db_start_guard.py` (the new test file).

## Output Files

- `ai-dev/active/I-00122/reports/I-00122_S04_CodeReview_report.md`.

## Context

Review the S03 tests that lock the db-start guard behaviour. The central
question: do these tests actually fail against the *pre-fix* script and pass
against the *fixed* one — i.e. do they test the displacement, not just the exit
code?

## Review Checklist

Cite `file:line` for each:

1. **Semantic, not shape** — The reproduction test asserts the **specific
   absence** of a `compose`/`up -d db` call (the thing that creates the empty DB),
   not merely `returncode != 0`. The dev-machine test asserts the **specific
   presence** of that call. A test that only checks the exit code would pass even
   if the script refused for the wrong reason — flag that if present.
2. **Hermetic** — Uses a stub `docker` on `PATH`; never calls real Docker; no
   dependency on the live DB, port 5433, or testcontainers. Fast.
3. **db_ready control** — The up/down state of the DB is forced deterministically
   (closed port / throwaway listener / stubbed probe), not dependent on the host's
   actual 5433 state.
4. **Coverage** — All three cases present: (a) identity pinned + down → refuse;
   (b) no identity + down → bootstrap runs; (c) DB up → no-op. Edge: empty-string
   `IW_CORE_EXPECTED_INSTANCE_ID` treated as "not pinned" (matches the guard).
5. **Placement & conventions** — File is under `tests/unit/`, follows
   `tests/CLAUDE.md` conventions, no live-DB writes, no `importlib.reload`.
6. **Determinism** — No reliance on a random free port without handling the race;
   no flakiness from leftover containers (there are none — docker is stubbed).

## Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00122",
  "completion_status": "complete",
  "findings": [{"severity": "...", "file": "...", "issue": "...", "recommendation": "..."}],
  "approved": true,
  "notes": ""
}
```

Approve only if the reproduction test would genuinely have caught the original
displacement (asserts the compose-call absence), not just a non-zero exit.
