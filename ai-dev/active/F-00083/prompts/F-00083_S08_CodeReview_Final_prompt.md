# F-00083_S08_CodeReview_Final_prompt

**Work Item**: F-00083 -- Dashboard AI Assistant — OpenCode-backed chat panel (v1)
**Step**: S08
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- `ai-dev/active/F-00083/F-00083_Feature_Design.md` — Design (the contract)
- All prior step reports under `ai-dev/work/F-00083/reports/`
- The current state of every file in `scope.allowed_paths`
- `dashboard/templates/chat/**` and `dashboard/static/chat/**` for the regression-guard cross-check

## Output Files

- `ai-dev/work/F-00083/reports/F-00083_S08_CodeReview_Final_report.md` — Cross-agent findings

## Required Independent Checks

1. **Regression guard**: `git diff --stat dashboard/templates/chat/ dashboard/static/chat/` against main. **Zero lines** is the required result. Any non-zero is **CRITICAL**. (Invariant 1)
2. **Permission block parity**: open `.opencode/config.json`, verify the `permission` block matches R-00074 §5 exactly (`"*": "ask"`, `read|glob|grep|webfetch|websearch: allow`, `external_directory: deny`). **CRITICAL** on deviation. (Invariant 3)
3. **Password security**: grep production code (not tests, not docs) for `OPENCODE_SERVER_PASSWORD|self\._password|runtime\.password`. Every match must be either: (a) the variable assignment, (b) the HTTP Basic auth header construction, or (c) a passthrough to subprocess env. **Zero matches in any logging or disk-write call.** **CRITICAL** on a log/disk hit. (Invariant 4)
4. **Independent targeted-test rerun**:
   ```bash
   uv run pytest tests/unit/test_chat_runtime.py tests/unit/test_chat_client.py tests/unit/test_chat_relay.py tests/unit/test_chat_filters.py tests/dashboard/test_chat_router.py tests/integration/test_chat_endpoint_session_lifecycle.py tests/integration/test_chat_endpoint_permission_flow.py tests/integration/test_chat_endpoint_reconnect.py -v
   ```
   All must pass. Failure here is **CRITICAL** — S07 should have caught it.
5. **Integration smoke (targeted)**: re-run only the F-00083 integration files independently — `uv run pytest tests/integration/test_chat_endpoint_session_lifecycle.py tests/integration/test_chat_endpoint_permission_flow.py tests/integration/test_chat_endpoint_reconnect.py -v`. Do NOT run `make test-integration` here — that is S15's job; running the full suite at this step duplicates the gate and historically triggers timeouts (I-00073). Surface any failure as **CRITICAL** so S09 can fix before S15.
6. **Scope discipline**: `git diff --stat HEAD --` (against the worktree base). Verify every modified file is in `scope.allowed_paths` from the manifest. Files outside are **CRITICAL** scope creep.
7. **CSS rebuild check**: if any new Tailwind classes were added to templates, verify `make css` was run AND `dashboard/static/styles.css` was committed with the change. Per `dashboard/CLAUDE.md`, alternative is appending plain CSS rules directly — note which path the implementer chose.
8. **Invariant cross-check**: for each of the 10 Invariants in the Design, write a one-line confirmation or finding.
9. **Boundary-row coverage**: cross-reference the Boundary Behavior table with S05's test coverage map. **HIGH** on any uncovered row.
10. **Ctrl+/ vs Cmd+\ collision**: spawn a headless browser test (`playwright-cli`) — open the dashboard's Projects page (which has no Code chat); press Ctrl+/ and verify the Dashboard AI Assistant toggles. Then open the Code view (which has Cmd+\); press Cmd+\ and verify the existing chat still toggles independently. **HIGH** on collision.
11. **S06/S07 follow-through**: every CRITICAL/HIGH from S06 either has a corresponding fix in S07 or is documented as contested with rationale. **CRITICAL** on a silently dropped CRITICAL.

## Output

Write the report at `ai-dev/work/F-00083/reports/F-00083_S08_CodeReview_Final_report.md`. Same severity scheme as S06. If clean, state "no CRITICAL/HIGH findings; S09 may be a no-op."

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-final-impl",
  "work_item": "F-00083",
  "completion_status": "complete",
  "files_changed": ["ai-dev/work/F-00083/reports/F-00083_S08_CodeReview_Final_report.md"],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "independent reruns: targeted unit+integration files OK (full suite deferred to S15)",
  "tdd_red_evidence": "n/a — final review step",
  "blockers": [],
  "notes": "Cross-agent findings: CRITICAL=X HIGH=Y. Regression-guard: PASS|FAIL. Permission-block: PASS|FAIL. Password-leak: PASS|FAIL. Targeted integration smoke: PASS|FAIL. Invariants 1–10: all PASS|<list of failures>."
}
```
