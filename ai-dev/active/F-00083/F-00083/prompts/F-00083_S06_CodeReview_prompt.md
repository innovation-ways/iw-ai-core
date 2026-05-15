# F-00083_S06_CodeReview_prompt

**Work Item**: F-00083 -- Dashboard AI Assistant — OpenCode-backed chat panel (v1)
**Step Being Reviewed**: S01 (backend-impl), S02 (backend-impl), S03 (api-impl), S04 (frontend-impl), S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- `ai-dev/active/F-00083/F-00083_Feature_Design.md` — Design (especially Invariants and Boundary Behavior)
- All five prior step reports
- All files listed across those reports' `files_changed`
- `dashboard/templates/chat/**` and `dashboard/static/chat/**` (the **existing** Code Q&A chat — must be untouched)

## Output Files

- `ai-dev/work/F-00083/reports/F-00083_S06_CodeReview_report.md` — Findings grouped by severity

## Review Checklist (CRITICAL findings block merge)

### Regression guard (HIGHEST priority — Invariant 1)
- **CRITICAL**: `git diff --stat dashboard/templates/chat/ dashboard/static/chat/` — must show **zero changes**. Any line touched in either directory is a CRITICAL regression-guard violation.
- **CRITICAL**: every new DOM id is prefixed `chat-assistant-`. Grep the new templates for `id="chat-` patterns that lack the `assistant-` qualifier. (Invariant 5)
- **CRITICAL**: Ctrl+/ keybinding does not collide with the existing Cmd+\. Check `dashboard/static/chat_assistant/chat.js` and the new base.html script.

### Scope discipline (Invariant 2)
- **CRITICAL**: zero new DB tables or migrations. Verify `orch/db/migrations/versions/**` and `orch/db/models.py` are unchanged. (This FR has no DB scope.)
- **CRITICAL**: `git diff --stat` shows no files outside `scope.allowed_paths` from the manifest.

### Security
- **CRITICAL**: grep production code (not tests) for `OPENCODE_SERVER_PASSWORD`, `_password`, `runtime.password`. Confirm no `logger.*(... password ...)`, no disk write, no return-from-public-API. (Invariant 4)
- **CRITICAL**: `opencode serve` is bound to `--hostname 127.0.0.1` (not `0.0.0.0`). Verify in `opencode_runtime.py`.

### Config layer (Invariant 3)
- **CRITICAL**: `.opencode/config.json`'s `permission` block exactly matches R-00074 §5 verbatim. Order doesn't matter; key/value semantics must:
  - `"*": "ask"`, `"read": "allow"`, `"glob": "allow"`, `"grep": "allow"`, `"webfetch": "allow"`, `"websearch": "allow"`, `"external_directory": "deny"`.
- **HIGH**: if `.opencode/config.json` had a pre-existing `permission` block and S04 silently overwrote it (no raised blocker in the report), that's a regression risk.

### Subprocess + relay
- **HIGH**: `OpencodeRuntime.start()` health-poll has a documented timeout (10 s) and clear error message on timeout.
- **HIGH**: `OpencodeRuntime` auto-restart cap is 3 in 60 s with CRITICAL log on exhaustion.
- **HIGH**: `RelayManager`'s ring buffer is exactly `deque(maxlen=256)` per session. (Invariant 7)
- **HIGH**: subscriber detach cleanup is verified by a unit test.
- **HIGH**: `httpx.ReadError` on the upstream pump triggers backoff retry (300 ms → 3 s) rather than killing the relay.

### API
- **HIGH**: every endpoint matches the design's contract row-for-row (8 endpoints documented in Design §API Changes).
- **HIGH**: `/api/chat/sessions/{sid}/stream` mirrors `dashboard/routers/sse.py`'s header set + disconnect check.
- **HIGH**: `/api/chat/config` and `/api/chat/skills` caches have TTL = 30 s.
- **HIGH**: when `runtime.health()` is False, all endpoints except `/api/chat/config` return 503.

### Frontend behaviour
- **HIGH**: client-side message-id dedup is implemented (set/array of recent ids; skip dupes).
- **HIGH**: gap detection is implemented (compare last-seen-id to first-received-id post-reconnect; render a warning).
- **HIGH**: context % polling stops within 5 s of `session.idle` (Invariant 9; well-bounded poll).
- **HIGH**: per-page `setContext` is wired in all 7 listed templates.
- **MEDIUM**: chip is removable; dismissal persists for the session (no chip on subsequent prompts in the same session).
- **MEDIUM**: Send button is disabled while a stream is active.

### Tests
- **HIGH**: every Boundary Behavior row in the Design has a corresponding test in S05 (cross-reference the table).
- **HIGH**: integration tests do not connect to the live DB (testcontainer only).
- **MEDIUM**: assertion strength — tests assert on specific values, not just "no exception raised."

### TDD evidence
- **HIGH**: S01/S02/S03 report a real `tdd_red_evidence` line with a failure type (`AttributeError`, `AssertionError`, `TypeError`), not an `ImportError` (which would indicate the test was broken, not RED).

### Scope creep
- **CRITICAL**: no work on Pi, no work on `/iw-debug` skill, no DB persistence of transcripts, no plan-only mode, no R-00073 §14 components. (Out-of-scope items per the Design.)

## Output

Write the review report at `ai-dev/work/F-00083/reports/F-00083_S06_CodeReview_report.md`. Group findings by severity. For each, name file + line and quote 1–3 lines of evidence. If clean, state "no CRITICAL/HIGH findings; S07 may be a no-op."

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00083",
  "completion_status": "complete",
  "files_changed": ["ai-dev/work/F-00083/reports/F-00083_S06_CodeReview_report.md"],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "review — no production code changed",
  "tdd_red_evidence": "n/a — review step",
  "blockers": [],
  "notes": "Findings count: CRITICAL=X HIGH=Y MEDIUM=Z LOW=W. Regression-guard: PASS|FAIL. Permission-block-match: PASS|FAIL. Scope-discipline: PASS|FAIL."
}
```
