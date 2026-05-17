# I-00087_S02_CodeReview_Frontend_prompt

**Work Item**: I-00087 — AI Assistant chat panel does not render model responses
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute any Docker container/volume/network management command. Allowed: testcontainers via pytest fixtures, read-only `docker ps/inspect/logs`, and `./ai-core.sh`/`make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade`, `alembic downgrade`, or `alembic stamp` against the live orchestration DB. This step does not involve migrations.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00087 --json`
- `ai-dev/active/I-00087/I-00087_Issue_Design.md` — the spec
- `ai-dev/active/I-00087/reports/I-00087_S01_Frontend_report.md` — what S01 did
- `dashboard/static/chat_assistant/chat.js` — the only file S01 changed
- `orch/chat/filters.py` — `INTERESTING_EVENTS` must match what S01 registered
- `.opencode/node_modules/@opencode-ai/sdk/dist/gen/types.gen.d.ts` — canonical opencode wire shapes

## Output Files

- `ai-dev/active/I-00087/reports/I-00087_S02_CodeReview_report.md` — review report

## Context

You are reviewing the frontend fix for I-00087. The bug is wire-protocol drift: `chat.js` listened for event names opencode does not emit, and read payload keys that do not exist on the actual `properties.*` wire shape. S01 rewrote the listener registration, the `_handleEvent` payload extraction, and `_loadHistory`.

## Read the Design Document FIRST

Read `ai-dev/active/I-00087/I-00087_Issue_Design.md` in full before opening `chat.js`:

- **Acceptance Criteria** — every criterion is a mandatory check.
- **Concrete event handling table** (in the design's "Code Changes" section) — every row is a contract S01 must satisfy.
- **Session continuity invariants** — the design explicitly names six invariants the fix MUST NOT regress; S01's report should contain a grep audit. Verify the audit.
- **TDD Approach** — the test file is named `tests/dashboard/test_chat_panel_event_protocol.py`. S03 writes it; S01 does not. Confirm S01's report claims `tdd_red_evidence` as `"n/a — production fix only; dedicated tests-impl step (S03)…"` per the prompt.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run these on the files in S01's `files_changed` (should be only `dashboard/static/chat_assistant/chat.js`):

```bash
make lint
make format-check
```

If either reports NEW violations in `chat.js` (not present on `main` pre-S01), file each as a **CRITICAL** finding with `category: "conventions"`, the file, line, and the exact tool message.

`make lint` for this project runs `node --check` on the JS files; a syntax error here will block downstream. Failure here is your single biggest catch.

## Review Checklist

### 1. Wire-protocol alignment (PRIMARY FOCUS)

Open `chat.js` and locate the `namedEvents` array (was at line 187-191 pre-fix). Cross-check against `INTERESTING_EVENTS` in `orch/chat/filters.py`:

- Every name in `INTERESTING_EVENTS` MUST appear in `namedEvents`. Missing names → CRITICAL.
- The relay-synthesised events `gap`, `reconnecting`, `error` MUST remain present. Removing them → CRITICAL.
- Extra opencode event names (e.g., `message.updated`, `message.part.removed`, `session.status`) are FINE — these were called out in the design table.

Then locate `_handleEvent`. For each event type the design table mentions, verify:

- **`message.part.updated`** — handler reads `properties.delta` AND `properties.part`. If it only reads one, that's a HIGH finding (will miss either streaming chunks or finalised text).
- **`message.updated`** — handler reads `properties.info` and inspects `info.role`, `info.time.completed`, `info.error`. Missing the error branch is MEDIUM_FIXABLE.
- **`tool.execute.before/after`** — handler renders SOMETHING visible (even a one-liner). If S01 added no rendering for tools, that's a HIGH finding — AC3 in the design fails.
- **`permission.updated`** — handler shows the modal. The `_replyPermission` flow at the bottom of `chat.js` must still work (URL still resolves to `/api/chat/sessions/{sid}/permissions/{rid}`). MEDIUM_FIXABLE if the rid extraction is wrong but the modal still renders; HIGH if the modal never fires.
- **`session.idle`** — preserved with the previous `permission_denied` / `aborted` sub-cases.

### 2. History reload

Locate `_loadHistory`. Verify:

- Iterates `data.messages` and reads `entry.info` (not `m.role` directly).
- Extracts text from `entry.parts` via filter+map on `type === 'text'`. If the implementer used `parts[0].text` they will miss multi-part messages — MEDIUM_FIXABLE.
- Passes `entry.info.id` as the dedup key when rendering assistant messages — required to avoid double-rendering after a reconnect (MEDIUM_FIXABLE if missing).

### 3. Session-continuity invariants

S01's report MUST contain a grep audit confirming these six markers still appear in `chat.js`:

1. `'iw-chat-session-' + _tabId`
2. `last_event_id=`
3. `_loadHistory(`
4. `sessionStorage.removeItem`
5. `switchSession`
6. `_renderChip` or `chat-assistant-chip`

If any is missing from the audit OR not in the actual file, that is a HIGH finding (regresses an explicit user requirement: session continuity).

### 4. Code Quality

- The `properties` vs `data` asymmetry MUST be documented in a comment at the top of `_handleEvent` (per the prompt).
- The new `namedEvents` array MUST have a comment pointing to `orch/chat/filters.py:INTERESTING_EVENTS`.
- No new dependencies (vanilla JS only — match the existing file style).

### 5. Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Key checks:
- No `navigator.clipboard.writeText` direct calls (use `window.iwClipboard.copy`).
- No Tailwind class invention without `make css` — but this step should not touch templates at all.

### 6. Security

- No hardcoded credentials or session IDs.
- The handler must NOT `eval()` or `innerHTML`-inject untrusted text. Existing `_escHtml` is used everywhere — confirm S01 used it for any new tool-name rendering (HIGH if not).

### 7. Testing

Per the prompt, S01 does NOT write tests — that is S03's job. The S01 report should reflect this with `tdd_red_evidence: "n/a — …"`. Do not penalise S01 for the absence of new tests — penalise S03 if it cuts corners.

Run the existing chat tests to confirm no regression in router/client coverage:

```bash
uv run pytest tests/dashboard/test_chat_router.py tests/unit/test_chat_client.py -v --no-cov
```

All 52 should pass (they did before S01 — S01's frontend-only changes cannot affect them).

### 5a. TDD RED Evidence — N/A for this step

S01 is a `frontend-impl` step, but the design explicitly assigns test authorship to S03 (`tests-impl`). The contract requires `tdd_red_evidence` to use `"n/a — <reason>"`; verify the reason given is the prompt's recommended phrasing.

## Severity Levels

| Severity | Meaning | Action Required |
|---|---|---|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00087",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "dashboard/static/chat_assistant/chat.js",
      "line": 0,
      "description": "",
      "suggestion": ""
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "52 passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
