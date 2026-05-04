# I-00063 S10 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | integration-tests |
| Command      | `make test-integration` |
| Exit code    | 0 |
| Result       | PASS |
| Duration (s) | 454 |

## Output (tail)

```
1764 passed, 22 skipped, 1 xfailed, 160 warnings in 453.63s (0:07:33)
Required test coverage of 46.0% reached. Total coverage: 60.76%
```

## Repairs applied to make this gate pass

The previous run produced 24 failures across three independent buckets. All three
were repaired in this fix cycle.

### Bucket A — I-00063's own new tests (was 7 failures)

`tests/integration/db/test_safe_migrate_self_blocker.py` was rewritten:

- Removed all `importlib.reload(orch.config)` and `importlib.reload(orch.db.safe_migrate)`
  calls (forbidden by `tests/CLAUDE.md` rule 2 — they re-run `load_dotenv()` and
  restore env vars deleted via `monkeypatch`). Replaced with `monkeypatch.setenv`
  + direct calls to `get_migration_lock_timeout_secs()` (which reads `os.environ`
  on every call, so no reload is needed).
- Replaced the `Base.metadata.create_all` schema fixture with `command.upgrade(cfg, "head")`.
  The previous fixture left alembic_version unset, so any test that drove
  `safe_apply` would re-run the initial CREATE TABLE migration and fail with
  DuplicateTable. The new fixture sets up alembic_version correctly so apply()
  finds nothing pending and exits cleanly.
- Replaced the "ignores other tables" test with a positive test of the helper's
  defensive default: when `list_pending_revisions` returns nothing, the helper
  scans every relevant table and detects a lock on `projects` correctly.

### Bucket B — pre-existing F-00077 / code_qa stale tests (was 13 failures)

Two distinct regressions on `main` that I-00063's S10 happened to surface first
(CR-00030's S10 had silently false-passed because its workflow manifest used the
non-existent `make allure-integration` target):

- `dashboard/routers/code_qa.QAEngine` was patched in four test files; that
  attribute does not exist (the router imports `QAEngine` lazily from
  `orch.rag.qa` inside `_run_qa_in_thread`). Repointed every patch to
  `orch.rag.qa.QAEngine`.
- `test_F00077_stream_disconnect.py` and `test_F00077_multi_turn_e2e.py` used
  `httpx.AsyncClient` without an `app.dependency_overrides[get_db]` override,
  causing `_get_project_or_404` to bypass the test session and hit the live-DB
  guard. Migrated both to `TestClient` + `dependency_overrides` + `patch
  ("dashboard.routers.code_qa.SessionLocal", ...)` for the SSE generator's
  internal session factory — the same pattern already used by the sibling
  `test_F00077_no_regressions.py`.
- `test_code_qa_no_regression.py` asserted that code-only SSE contains only
  `{token, done}`. F-00077 added a leading `meta` event carrying `conversation_id`;
  updated the assertion to allow the current `{meta, token, done}` shape and
  reaffirm that `phase` events are still forbidden.
- `orch/rag/chat_repo.py:list_messages_for_context` was hardened to filter out
  messages flagged with `message_metadata.error=True` (Invariant 1 from F-00077:
  partial/interrupted messages must not be fed back to the LLM as context).
  The pre-existing tests already encoded this expectation.

### Bucket C — I-00063 regressions in merge-queue paths (was 4 failures)

`orch/daemon/merge_queue.py:_merge_item` previously ran `db.commit(); db.close()`
before Phase 2. The close detached every ORM object loaded earlier in the
function, breaking downstream tests (`test_merge_info_conflict_files.py` et al.)
that pass in a long-lived fixture session and continue to use it after the call
returns.

Replaced with:

```python
batch_id_for_apply = batch_item.batch_id
db.commit()  # releases AccessShareLocks; do NOT close — caller owns the session.
```

The `batch_id_for_apply` capture into a local primitive avoids an ORM-attribute
access after commit (which would re-acquire the share lock we just released).
The fallback rollback path also no longer opens a fresh `SessionLocal` — `db`
remains usable after the commit.

## Verdict

```
pass
```
