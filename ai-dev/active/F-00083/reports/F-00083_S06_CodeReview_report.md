# F-00083 S06 Code Review Report

## Summary

- Regression-guard: PASS
- Permission-block-match: PASS
- Scope-discipline: PASS
- Findings: CRITICAL=0 HIGH=1 MEDIUM=2 LOW=2

---

## CRITICAL Findings

None.

---

## HIGH Findings

### H1 — `Last-Event-ID` query-param/header mismatch breaks manual reconnect replay

**File**: `dashboard/static/chat_assistant/chat.js` line 174 vs `dashboard/routers/chat.py` line 235

**Evidence**:

`chat.js` (line 174) appends the replay id as a query parameter:
```js
url += '?last_event_id=' + encodeURIComponent(_lastSeenId);
```

`chat.py` (line 235) reads it from the HTTP header only:
```python
last_event_id = request.headers.get("Last-Event-ID")
```

**What is wrong**: `EventSource` sends `Last-Event-ID` as an HTTP request header **only** on its own internal auto-reconnect (connection-error retry). When `_connectStream()` is called manually — on tab navigation, session switch, or after `newSession()` — a brand-new `EventSource` is constructed. The browser has no previous `Last-Event-ID` state for a fresh `EventSource`, so it sends no header. The JS sets the query parameter as a workaround, but the router never reads `request.query_params["last_event_id"]`. The result: AC6 (tab-refresh reconnect with ring-buffer replay) does **not** work for the manually-triggered reconnect path. The integration tests pass because they send the header directly via `httpx`, bypassing this frontend-to-backend gap.

**Expected fix**: In `dashboard/routers/chat.py`, the `stream_session` endpoint must also read the query parameter as a fallback:
```python
last_event_id = (
    request.headers.get("Last-Event-ID")
    or request.query_params.get("last_event_id")
)
```

---

## MEDIUM Findings

### M1 — TDD RED evidence for S02 and S03 is ImportError / ModuleNotFoundError

**Files**: `ai-dev/active/F-00083/reports/F-00083_S02_Backend_report.md` (lines 13-14, 196-204), `ai-dev/active/F-00083/reports/F-00083_S03_Api_report.md` (lines 177-186)

**What is wrong**: The review prompt specifies that TDD RED evidence should be "a real failure type (AttributeError / AssertionError / TypeError), not ImportError." S01 correctly shows `AttributeError`. S02 shows `ImportError: cannot import name 'filters' from 'orch.chat'` and `ModuleNotFoundError: No module named 'orch.chat.opencode_client'`. S03 shows `ModuleNotFoundError: No module named 'dashboard.routers.chat'`. These are import-level failures that happen at test-collection time, not at test-execution time. They confirm the modules did not exist, but they do not prove the tests would have exercised the production logic. S02's report acknowledges this: "These are the canonical RED states for modules that don't exist yet — matches the RED-state convention adopted in S01." However S01's convention was an `AttributeError` at the class-attribute level, which is a more meaningful RED.

**Suggested fix**: For any future backend or API steps, write tests that import a stub/skeleton module first (so collection succeeds) and fail with `AttributeError` or `AssertionError` on the unimplemented method call. This is a documentation/process issue; no production code change needed for S07.

### M2 — `permission.reply` wire-field name unverified (`response` vs `reply`)

**Files**: `orch/chat/opencode_client.py` line 145, `ai-dev/active/F-00083/reports/F-00083_S02_Backend_report.md` (Issues section)

**What is wrong**: S02 captured from binary inspection that OpenCode's reply endpoint accepts a field named `reply`, but the prompt contract and the current implementation use `response`. The S02 report flags this as "MEDIUM-confidence gap" and S05 carries it forward. The integration tests only assert what the dashboard sends, not whether OpenCode accepts it. If the wire field is indeed `reply`, permission replies will silently fail (OpenCode may return 200 but ignore the unknown field, or return a 4xx). This gap is explicitly carried to S08 for resolution, which is appropriate — but it remains unresolved at S06 review time.

**Suggested fix**: Run a live spike against `opencode serve` with a model that actually emits `permission.asked`, capture the exact body format expected by OpenCode's `/session/{sid}/permissions/{rid}` endpoint, and update `OpencodeClient.reply_permission` if the field is `reply` not `response`. This can be deferred to S07 or S08.

---

## LOW Findings

### L1 — `_chipDismissed` persistence is session-scoped in memory only (no sessionStorage)

**File**: `dashboard/static/chat_assistant/chat.js` lines 29, 524-525

**What is wrong**: The design AC8 says "dismissing the chip removes it from any future prompts in this session." The JS `_chipDismissed` flag is a module-level `var` — it resets to `false` on every page navigation (each page reload creates a fresh JS context). This means the chip dismissal does NOT persist across navigations, contrary to the "for this session" wording. The "Currently viewing X" chip from `setContext` is re-injected on every page anyway (each page calls `setContext` on load), so the flag being reset is arguably acceptable — you get a fresh chip per page. However, if a user dismisses the chip on page A, navigates to page A again (same page), the chip reappears even though the user had dismissed it.

**Suggested fix**: Store `_chipDismissed` in `sessionStorage` keyed by `_tabId` + current page, or accept current behavior and update the AC8 wording to "dismissing the chip removes it for the current page view." LOW priority.

### L2 — `_opencode_root` uses env var `IW_CORE_REPO_ROOT` which is not documented in `.env.example`

**File**: `dashboard/routers/chat.py` lines 67-69

**What is wrong**: The `_OPENCODE_ROOT` module attribute falls back to `IW_CORE_REPO_ROOT` env var:
```python
_OPENCODE_ROOT: Path = Path(
    os.environ.get("IW_CORE_REPO_ROOT", Path(__file__).resolve().parents[3])
)
```
`IW_CORE_REPO_ROOT` is not documented in `.env.example` and not in `orch/config.py`. The default `parents[3]` logic should work for the standard layout (`dashboard/routers/chat.py` → `dashboard/routers/` → `dashboard/` → root), so the fallback is correct and this only matters if the repo is launched from an unexpected location. Low risk.

**Suggested fix**: Either remove the env-var override (the path calculation is correct) or document `IW_CORE_REPO_ROOT` in `.env.example` with a note that it's optional.

---

## Checklist Pass/Fail Table

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Regression guard — `git diff dashboard/templates/chat/ dashboard/static/chat/` | PASS | Zero diff; existing Code Q&A chat untouched |
| 2 | DOM id prefix — all new ids are `chat-assistant-*` | PASS | Grep confirms 30+ ids all prefixed `chat-assistant-` |
| 3 | Keybinding — Ctrl+/ for new panel; Cmd+\ for existing | PASS | `chat.js` line 785: `if (e.ctrlKey && e.key === '/')` |
| 4 | No new migrations / no model changes | PASS | `git diff orch/db/models.py orch/db/migrations/` — zero diff |
| 5 | Scope discipline — all files within manifest allowed paths | PASS | All 13 modified + 16 untracked files are within declared scope |
| 6 | Password security — no log/disk write/public-API return | PASS | Log reads `<redacted 32B token>`; password not in any router response |
| 7 | localhost bind — `--hostname 127.0.0.1` | PASS | `opencode_runtime.py` line 169: `"--hostname", "127.0.0.1"` |
| 8 | Permission block match | PASS | `.opencode/config.json` has `*:ask`, `read/glob/grep/webfetch/websearch:allow`, `external_directory:deny` |
| 9 | Health timeout 10s; restart cap 3 in 60s with CRITICAL log | PASS | `_HEALTH_TIMEOUT_SECONDS=10.0`, `_MAX_RESTARTS_PER_WINDOW=3`, `_RESTART_WINDOW_SECONDS=60.0`, CRITICAL log at line 302 |
| 10 | Relay ring buffer `deque(maxlen=256)` | PASS | `relay_manager.py` line 53: `deque(maxlen=buffer_size)` with `_DEFAULT_BUFFER_SIZE=256` |
| 11 | httpx.ReadError backoff 300ms → 3s | PASS | `_RECONNECT_BACKOFF_MIN=0.3`, `_RECONNECT_BACKOFF_MAX=3.0`, exponential backoff with `backoff * 2` |
| 12 | 8 endpoints present with correct paths/methods | PASS | All 9 endpoints present (design says 8 plus `/config` and `/skills` = 9 total as designed); SSE headers match `sse.py`; `/config` and `/skills` have 30s TTL cache; 503 gate on unhealthy runtime (config excluded) |
| 13a | Client-side dedup of message ids | PASS | `_seenIds` map at line 24, checked at line 218 |
| 13b | Gap detection on reconnect (last-seen-id vs first-received) | PASS (server-side); FAIL (client-to-server path) | Router returns gap event correctly; but JS passes `last_event_id` as query param while router reads header — see H1 |
| 13c | Context % polling stops within 5s of `session.idle` | PASS | `_stopContextPoll()` called in `session.idle` handler; poll interval is 5000ms |
| 13d | setContext wired in all 7 templates | PASS | All 7 templates listed in S04 report: item_detail, batch_detail, research_detail, research_library, docs_detail, docs_library, project_code |
| 14 | Chip removable + dismissal persists for session | PARTIAL | Dismissal flag resets on page reload (see L1); otherwise chip DOM wiring is correct |
| 14b | Send button disabled while stream active | PASS | `sendBtn.disabled = _streaming` at line 545 |
| 15 | Integration tests use testcontainer (not port 5433) | PASS | Tests use `db_session` testcontainer fixture; no port 5433 references in new test files |
| 15b | Assertion strength | PASS | S05 mutation-testing audit confirmed all 3 key mutations were caught |
| 16 | TDD RED evidence type (S01/S02/S03) | PARTIAL | S01 PASS (AttributeError); S02/S03 FAIL (ImportError/ModuleNotFoundError) — see M1 |
| 17 | No scope creep (Pi, /iw-debug, transcript DB, plan-only, R-00073 §14) | PASS | No references to Pi runtime, /iw-debug, DB migrations, or R-00073 §14 components |

---

## Conclusion

One HIGH finding must be fixed before merge: the `Last-Event-ID` query-param/header mismatch (H1) breaks AC6 (tab-refresh reconnect replay) for manually-triggered reconnects. The fix is a 1-line change in `dashboard/routers/chat.py` to also check `request.query_params.get("last_event_id")` as a fallback.

Two MEDIUM findings should be addressed in S07: the TDD RED evidence convention (process only, no code change) and the `permission.reply` wire-field name gap (should be validated against a running `opencode serve`).

All invariants pass: existing Code Q&A chat is untouched, no DB migrations, permission block matches R-00074 §5 verbatim, no password leakage, all DOM ids are correctly prefixed, keybinding uses Ctrl+/ (no collision), relay buffer is `deque(maxlen=256)`, health timeout is 10s, restart cap is 3/60s with CRITICAL log.
