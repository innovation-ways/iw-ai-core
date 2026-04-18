# CR-00008 S02 — Code Review of S01 (API wire format)

## Review Summary

Reviewed `dashboard/routers/code_qa.py` (232 lines) and `tests/dashboard/test_code_qa_sse_wire.py` (224 lines) against the CR-00008 design and S01 prompt checklist.

---

## Findings

### Finding 1: Test file — unused imports
- **Severity**: MEDIUM
- **File**: `tests/dashboard/test_code_qa_sse_wire.py:9,14,18`
- **Issue**: Three imports are unused: `asyncio` (line 9), `AsyncMock` from `unittest.mock` (line 14), and `router` from `dashboard.routers.code_qa` (line 18).
- **Recommended fix**: Remove the three unused imports.

---

### Finding 2: Test file — `zip()` without `strict=` parameter
- **Severity**: MEDIUM
- **File**: `tests/dashboard/test_code_qa_sse_wire.py:66`
- **Issue**: `zip(token_frames, tokens)` used without `strict=True`. If the two iterables ever have different lengths, Python's default zip behavior silently truncates to the shorter length, masking a mismatch.
- **Recommended fix**: Add `strict=True` (Python 3.10+). The `len(token_frames) == len(tokens)` assertion on the prior line would catch a mismatch anyway, but explicit `strict=True` is safer and documents intent.

---

### Finding 3: Test file — `db_session=None` violates type contract
- **Severity**: MEDIUM
- **File**: `tests/dashboard/test_code_qa_sse_wire.py:58,96,128,163`
- **Issue**: `_sse_generator`'s `db_session` parameter is typed as `Session` but is passed `None` in all four test invocations. Mypy correctly flags this: `Argument "db_session" to "_sse_generator" has incompatible type "None"; expected "Session"`.
- **Recommended fix**: Either (a) change the test to pass a real or mocked `Session` object, or (b) change the `_sse_generator` signature to `db_session: Session | None` if `None` is a valid no-op sentinel in the async context. The function body does not reference `db_session` at all, so the second option is low-risk for S01, but a reviewer of a future change must confirm.

---

### Finding 4: `_CitationTracker` receives token strings, not symbol IDs — citation hallucination risk
- **Severity**: HIGH
- **File**: `dashboard/routers/code_qa.py:159`
- **Issue**: `_CitationTracker.add(token)` is called with the raw LLM token string (e.g., `"first"`, `"##"`, `"Summary"`). The tracker's dictionary key is therefore the token's textual content, not a retrieved symbol identifier. For any unique token, `add()` returns a new index and a `citation` event is emitted with fabricated metadata (`label: "token:N"`, `snippet: token[:240]`).

  The S01 report states "zero citation events are emitted for MVP" because `QAEngine.answer_stream` has no citation hook. The test `test_citation_event_monotonic_if_any` passes for this reason only because `FakeEngine` yields short plain strings — the test's JSON parse + assertion would accept any `n` value (the assertion `n_values == list(range(1, len(n_values)+1))` passes because `1, 2, 3` equals `[1,2,3]` regardless of origin).

  If a future real engine yields multi-word tokens (e.g., `"The answer is..."`) or structured content, every unique token chunk would produce a spurious citation with a misleading `label` and a `snippet` that is just the token text itself, not a retrieved source snippet.

- **Recommended fix**: Gate citation emission behind a flag that is set only when a real retrieved-symbol integration point is found in the engine. E.g., add `if citation_tracker and has_real_citations:` before emitting. For S01 MVP, the cleanest fix is to simply not call `citation_tracker.add(token)` at all, and emit zero citation events as the report promises. The tracker class can remain in the module for future use without being invoked.

---

### Finding 5: Dead `ThreadPoolExecutor` variable
- **Severity**: LOW
- **File**: `dashboard/routers/code_qa.py:127,171`
- **Issue**: `executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)` is created on line 127, used on line 171 for `executor.shutdown(...)`, but no work is ever submitted to it. The threading is done entirely in the daemon-thread + `loop.run_forever()` pattern inside `_run_qa_in_thread`. The executor is dead code.
- **Recommended fix**: Remove `executor` and the `shutdown()` call. If a thread pool is eventually needed for parallel work (e.g., concurrent engine warmup), it should be added intentionally.

---

### Finding 6: Missing docstring on `_sse_generator`
- **Severity**: LOW
- **File**: `dashboard/routers/code_qa.py:113`
- **Issue**: `_sse_generator` has no docstring. Given the complexity of the threading model (daemon thread + queue + `loop.run_in_executor`), a brief docstring explaining the error-surface contract (which exceptions can bubble out, and under what conditions the generator yields `error` vs raises) would aid future maintainers.
- **Recommended fix**: Add a docstring. At minimum document: (1) that `ConnectionRefusedError` and `OSError` from the engine are caught and yielded as `event: error`; (2) that citation events are best-effort and depend on engine integration.

---

## Quality Checks

| Check | Result |
|-------|--------|
| `uv run ruff check dashboard/routers/code_qa.py` | ✅ Pass |
| `uv run mypy dashboard/routers/code_qa.py` | ✅ Pass |
| `uv run ruff check tests/dashboard/test_code_qa_sse_wire.py` | ❌ 4 errors (3 unused imports, 1 B905) |
| `uv run mypy tests/dashboard/test_code_qa_sse_wire.py` | ❌ 4 errors (db_session None type) |
| `uv run pytest tests/dashboard/test_code_qa_sse_wire.py -v` | ✅ 8 passed |

---

## Wire-Format Contract Checklist

| Requirement | Status |
|-------------|--------|
| Every frame has `event:` + `data:` + `\n\n` terminator | ✅ |
| `token` events use `{"b64": "..."}` | ✅ |
| Base64 round-trips via `b64encode(utf8).decode("ascii")` | ✅ |
| `citation` events carry `n`, `label`, `url`, `snippet` | ✅ (but see Finding 4) |
| `done` events carry `{"ok": true}` | ✅ |
| `error` events carry `{"message": "..."}` | ✅ |
| Exactly one terminal event (`done` XOR `error`) | ✅ |
| `ConnectionRefusedError`/`OSError` → `error` then return | ✅ |
| Request body shape unchanged; headers preserved | ✅ |
| Multipart stub returns 501 + exact detail string | ✅ |
| No multipart body persisted to disk/memory | ✅ |
| Citations deferred if no engine hook (no hallucination) | ⚠️ **FAIL** — see Finding 4 |
| Module ≤ 250 lines | ✅ (232 lines) |
| No `asyncio.run(...)` in request path | ✅ |

---

## Verdict

- **Gating issues (CRITICAL+HIGH)**: 1 (Finding 4 — citation hallucination risk)
- **Non-gating issues (MEDIUM+LOW)**: 5 (Findings 1, 2, 3, 5, 6)
- **Ready for next step**: **no**

The S01 implementation passes the wire-format framing and encoding checks but introduces a HIGH-severity citation hallucination issue: every unique token string triggers a fabricated citation event with a fake `label` and a `snippet` that is just the token text itself. This contradicts the S01 report's explicit promise of "zero citation events for MVP" and creates a risk that a future real deployment would surface spurious citations to end users. S02 must fix this before S03 (frontend) is started, as the frontend is expected to consume real citation events.

The five MEDIUM/LOW issues (unused imports, `zip` strictness, type safety on `db_session`, dead executor, missing docstring) should also be cleaned up in S02's fix cycle.
