# CR-00054_S08_CodeReview_Final_prompt

**Work Item**: CR-00054 -- Add OpenCode stub to worktree E2E stack
**Step**: S08
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only introspection allowed.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds NO migrations.

## Input Files

- All previous step reports (S01–S07)
- All files touched (limited to `scope.allowed_paths`)
- `ai-dev/active/CR-00054/CR-00054_CR_Design.md`
- `uv run iw item-status CR-00054 --json` for live step status

## Output Files

- `ai-dev/active/CR-00054/reports/CR-00054_S08_CodeReviewFinal_report.md`

## Context

You are the **final cross-agent reviewer** before QV gates kick in. Your scope is the integration of all S01–S07 changes:

1. The pieces fit together (stub script + Dockerfile shim path match; compose env var matches stub's port handling).
2. Scope discipline holds: `git diff --stat <base>...HEAD --name-only` lists ONLY files in `scope.allowed_paths` plus `ai-dev/active/CR-00054/**`.
3. The new integration test suite passes end-to-end when run locally: `uv run pytest tests/integration/test_e2e_opencode_stub.py -v`.
4. Pre-confirm what S15 (test-integration) will run. If a flaky test slipped in or an unrelated test is broken, surface it here as CRITICAL — that's the post-mortem learning from F-00079.
5. The stub's HTTP shapes match `orch/chat/opencode_client.py`'s expectations end-to-end. Trace one full flow: `OpencodeRuntime.start()` → `OpencodeClient.create_session()` → `OpencodeClient.stream_events()` → `OpencodeClient.reply_permission()` — each call must hit the stub correctly.
6. Dockerfile.e2e change does not introduce heavy RUN steps that push build time over ~3 min. Read the new layer(s); flag anything that fetches large binaries or installs heavy packages.

## Severities

Same as S06. CRITICAL = block; HIGH = block unless waived. Repeat findings from S06 only if they were not addressed in S07 (re-grade as CRITICAL if so).

## Required cross-checks

- `git diff --stat <merge-base>..HEAD --name-only` lists only allowed paths.
- `git diff <merge-base>..HEAD -- orch/chat/ dashboard/routers/chat.py dashboard/templates/chat_assistant/ dashboard/static/chat_assistant/` returns empty.
- `grep -n "OPENCODE_SERVER_PASSWORD" scripts/e2e_opencode_stub.py` — every reference is either reading from `os.environ` or comparing in basic-auth; none log the value.
- `make format-check` and `make type-check` pass locally for touched files.

## Result Contract

Same shape as S06.

```json
{
  "step": "S08",
  "agent": "code-review-final-impl",
  "work_item": "CR-00054",
  "completion_status": "complete",
  "findings": [],
  "blockers": [],
  "notes": "If S08 is clean, S09 is a no-op."
}
```
