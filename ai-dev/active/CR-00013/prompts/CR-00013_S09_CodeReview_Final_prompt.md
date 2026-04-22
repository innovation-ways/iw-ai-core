# CR-00013_S09_CodeReview_Final_prompt

**Work Item**: CR-00013 -- Dashboard navigation performance — eliminate multi-second hangs between pages
**Review Step**: S09 (final cross-layer review)
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/CR-00013/CR-00013_CR_Design.md` — Design
- All step reports in `ai-dev/active/CR-00013/reports/` from S01 through S08
- All files changed across the CR (union of every `files_changed` list)

## Output Files

- `ai-dev/active/CR-00013/reports/CR-00013_S09_CodeReview_Final_report.md` — final review

## Context

You are doing the final cross-layer sanity check on CR-00013 before QV gates. Per-agent reviews (S02, S04, S06, S08) already validated each slice. Your job is to verify the slices compose correctly and cover AC1–AC8 end-to-end.

## Review Focus

### 1. Integration Correctness

- The request-timing middleware (S01) correctly counts queries for the rewritten N+1 routes (S03). Verify by reading both: the middleware's query counter must attribute queries to the in-flight request regardless of which router handles it.
- The TTL cache (S01) and the N+1 fixes (S03) don't step on each other. The cached badge endpoint still uses bulk queries, not loops (even though it runs rarely after caching).
- The prebuilt CSS (S05) covers all Tailwind classes used in templates modified or added by S01/S03 (none expected, but verify).
- The `{% block head %}` lazy-load pattern (S05) works with htmx fragment swaps used by actions in S01/S03 routers.

### 2. AC Coverage

Walk AC1–AC8:

- **AC1**: `nav_worktree_badge` latency + zero subprocess on cache hit — S01 implementation + S07 `test_nav_worktree_badge_cache.py`.
- **AC2**: pool config + env overrides — S01 + S07 `test_db_pool_config.py`.
- **AC3**: bounded queries on 5 routes — S03 + 5 query-count tests.
- **AC4**: subprocess cache on `_git_branch_and_stats` and `/worktrees` — S01 + tests.
- **AC5**: async sleep in daemon_control — S01 + S07 `test_daemon_control_async.py`.
- **AC6**: Tailwind prebuilt + lazy libs + self-hosted font — S05 + S07 render tests.
- **AC7**: WARN log above threshold — S01 + S07 middleware tests.
- **AC8**: visual parity — deferred to S15 browser verification.

Any AC without an implementation + test pairing is a HIGH finding.

### 3. No Regressions on Adjacent Routes

- Check that routers not in scope (actions, sse, search, docs, quality, tests, jobs_ui, code_ui, research) are unchanged.
- SSE router (`routers/sse.py`) still works with the resized pool; its 5-second poll still opens a short-lived session per fetch.
- Templates not in scope (fragments, components not touched by S05) still render.

### 4. CLAUDE.md Consistency

- `dashboard/CLAUDE.md` updated to document the new build step.
- No stale references elsewhere to "no build step" or "Tailwind CDN".
- `orch/CLAUDE.md` mentions of pool-related env vars match `.env.example`.

### 5. Observability First

- The timing middleware is registered early enough in `create_app()` to wrap all subsequent routes (but after `StaticFiles` mounting, which shouldn't be measured the same way).
- Pool-status logging doesn't accidentally hold a DB connection during its own execution.

### 6. Security & Safety

- No secrets logged by the middleware.
- Env-var defaults are safe for production.
- No blocking calls re-introduced in async handlers.

### 7. Documentation

- Design doc accurately reflects the final implementation (small drift is OK; material changes must be noted in the report).
- `.env.example` documents the new vars.
- Any new dependency (Tailwind CLI) is recorded in the appropriate lockfile.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — clean.
2. `make test-integration` — clean.
3. `make quality` — clean.
4. `make css` — clean.

## Severity Levels

| Severity | Action |
|----------|--------|
| **CRITICAL** | Must fix before merge |
| **HIGH** | Must fix before merge |
| **MEDIUM (fixable)** | Should fix |
| **MEDIUM (suggestion)** | Optional |
| **LOW** | Informational |

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-final",
  "work_item": "CR-00013",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "ac_coverage": {
    "AC1": "covered|missing",
    "AC2": "covered|missing",
    "AC3": "covered|missing",
    "AC4": "covered|missing",
    "AC5": "covered|missing",
    "AC6": "covered|missing",
    "AC7": "covered|missing",
    "AC8": "deferred-to-S15"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
