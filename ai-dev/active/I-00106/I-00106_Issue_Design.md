# I-00106: Agent Session Log modal renders oldest-first — newest activity buried at the bottom

**Type**: Issue
**Severity**: Low
**Created**: 2026-05-22
**Reported By**: sergio (dashboard usability observation)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item adds no migration** — it is a pure presentation-layer fix. No schema, model, or data change.

## Description

On the item detail page, the steps table has a **Logs** column; clicking the icon in that column opens the **Agent Session Log** modal (feature CR-00065). That modal renders the agent runtime/session log in pure chronological order — the *oldest* message is pinned at the top and the *newest* activity sits at the bottom. For long or live-running steps the reader must scroll all the way down to find the latest turn, and the modal's 3-second live poll keeps appending new content below the fold. This makes the log hard to follow.

## Project Context

Read the project's `CLAUDE.md` and the layer guides (`orch/CLAUDE.md`, `dashboard/CLAUDE.md`) for architecture, conventions, and hard rules. Relevant notes for this fix:

- `orch/daemon/session_reader.py` (`read_session_content`) is the canonical parser that turns a pi `.jsonl` session file — or a claude/opencode log dump — into a flat list of segment dicts. It is consumed only by the dashboard router `item_session_log` in `dashboard/routers/items.py`.
- `orch/` code MUST NOT import from `dashboard/` — the new helper lives in `orch/` and stays self-contained.
- The "Logs" **tab** (a different surface from the "Logs" **column**) already reverses log lines via `_reverse_log` in `dashboard/routers/items.py`; it is explicitly **out of scope** here.
- Fragment templates under `dashboard/templates/fragments/` MUST NOT extend `base.html`.

## Browser Evidence

Pre-fix evidence captured against the live dashboard at `http://iw-dev-01:9900/project/iw-ai-core/item/CR-00076`, opening the Agent Session Log modal for step **S03 / run #1** (a `pi` run):

- `evidences/pre/I-00106-bug-evidence.png` — screenshot of the open modal. The first (top) segment is the agent's very first action, `tool bash: {"command": "uv run iw step-start CR-00076 --step S03"}`, immediately followed by its first `thinking` block. The newest activity is off-screen at the bottom, reachable only by scrolling.
- `evidences/pre/I-00106-bug-snapshot.yml` — accessible-DOM snapshot of the same modal, confirming the chronological (oldest-first) segment order structurally.

## Steps to Reproduce

1. Open the dashboard and navigate to any completed or running work item's detail page (e.g. `/project/iw-ai-core/item/CR-00076`).
2. In the **Steps** table, find a step that ran an agent (a `pi`, `claude`, or `opencode` run) and click the icon in its **Logs** column.
3. Observe the **Agent Session Log** modal that opens.

**Expected**: The newest agent turn is at the **top** of the modal; the oldest turn is at the bottom. Within a single turn the natural order is preserved (thinking → tool call → tool result → assistant reply).

**Actual**: The oldest segment is at the top and the newest at the bottom. The reader has to scroll to the bottom to see the latest activity, and each 3-second live poll appends new content below the current view.

## Browser Verification Script

Reproduce the bug (and, after the fix, confirm it) with `playwright-cli`:

```bash
playwright-cli kill-all
playwright-cli open "<dashboard-base-url>/project/iw-ai-core/item/CR-00076"
playwright-cli snapshot                       # locate the "View logs for step S03" button ref
playwright-cli click <logs-button-ref>        # opens the Agent Session Log modal
playwright-cli snapshot                       # inspect modal segment order
playwright-cli screenshot                     # capture evidence
```

Pre-fix: the first in-modal segment is the agent's `step-start` command. Post-fix: the first segment belongs to the agent's most recent turn.

## Root Cause Analysis

The Agent Session Log modal renders segments in the exact order `read_session_content` produced them, and that order is strictly chronological.

1. **Parser builds segments oldest-first.** `orch/daemon/session_reader.py:_render_pi_jsonl` (lines 72-94) reads the session `.jsonl` file top to bottom and calls `_process_pi_object` for each line; `_process_pi_object` / `_process_assistant_content_item` only ever `segments.append(...)` (e.g. lines 102, 118, 126-128, 146, 171, 189, 204, 217). The pi-without-session-file fallback (`read_session_content`, lines 296-302) does the same. Result: `segments[0]` is the oldest event, `segments[-1]` the newest.

2. **Router passes the list through untouched.** `dashboard/routers/items.py:item_session_log` (lines 2192-2281) calls `raw_segments = read_session_content(run)` (line 2255), assigns `segments = raw_segments` (line 2256), and renders the template with `{"segments": segments, ...}` (lines 2268-2281). No reordering happens.

3. **Template iterates the flat list as-is.** `dashboard/templates/fragments/session_log_popup_content.html:21` iterates `{% for seg in segments %}` in list order, so the oldest segment renders first (top) and the newest last (bottom).

Nothing in the chain reverses the order. The fix is to interpose a turn-aware reversal between the parser output and the template.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/session_reader.py` | Produces a flat chronological segment list; no turn-aware newest-first grouping helper exists |
| `dashboard/routers/items.py` (`item_session_log`) | Passes `segments` straight to the template; must apply the new helper and pass `turns` instead |
| `dashboard/templates/fragments/session_log_popup_content.html` | Iterates a flat `segments` list oldest-first; must iterate `turns` newest-first with a separator between turns |
| Tests (unit + dashboard) | No test guards segment/turn ordering in the modal; needs a reproduction test plus regression coverage of the grouping helper |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add a pure, tested turn-grouping helper to `orch/daemon/session_reader.py` that groups the flat chronological segment list into turns and returns them newest-first, preserving within-turn order. | — |
| S02 | code-review-impl | Review S01 (backend) | — |
| S03 | frontend-impl | Wire `item_session_log` to apply the helper; update `session_log_popup_content.html` to iterate `turns` newest-first with a divider between turns. | — |
| S04 | code-review-impl | Review S03 (frontend) | — |
| S05 | tests-impl | Reproduction test + regression tests for the helper and the modal render order. | — |
| S06 | code-review-impl | Review S05 (tests) | — |
| S07 | code-review-final-impl | Cross-cutting final review of S01..S06 | — |
| S08..S15 | qv-gate | lint, format-check, type-check, arch-check, security-sast, unit-tests, frontend-tests, integration-tests | — |
| S16 | qv-browser | End-to-end browser verification — open the modal, confirm newest turn on top, no regressions | — |
| S17 | self-assess-impl | Post-execution self-assessment (project has `self_assess = true`) | — |

Agent slugs: `backend-impl`, `frontend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration. Pure presentation-layer change.

### Code Changes

- **Files to modify**:
  - `orch/daemon/session_reader.py` — add the turn-grouping helper (S01).
  - `dashboard/routers/items.py` — `item_session_log` applies the helper, passes `turns` to the template (S03).
  - `dashboard/templates/fragments/session_log_popup_content.html` — iterate `turns` newest-first with a turn divider (S03).
- **New test files**:
  - `tests/unit/test_session_reader.py` — *existing* file; S05 appends helper tests to it.
  - `tests/dashboard/test_session_log_modal_ordering.py` — new dashboard render-order test file.
- **Nature of change**: Additive — a new pure helper plus a re-ordering pass at the view boundary. No parser semantics change; `read_session_content` still returns chronological segments for any other caller.

### The turn-grouping helper (S01 contract)

Add a pure function to `orch/daemon/session_reader.py` — suggested name `group_into_turns_newest_first(segments)`:

```python
def group_into_turns_newest_first(
    segments: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Group a chronological flat segment list into agent turns, newest turn first."""
```

**Turn definition.** A *turn* is a contiguous run of segments. The turn is terminated by:

- an `assistant` segment that is **not** immediately followed by another `assistant` segment (consecutive `assistant` segments — e.g. a pi message whose `content` list has multiple `text` items — stay in the **same** turn); or
- an `error` segment (always terminates its turn).

Segments accumulated after the last terminator (no assistant reply yet — common while a step is still running) form a **final in-progress turn**.

**Special segments.**

- A `compaction` segment is emitted as its **own single-segment turn** so it keeps acting as a visual separator. Flush the in-progress turn before it.
- A `log` segment (the claude/opencode whole-dump fallback; `read_session_content` returns exactly one) is emitted as its own turn, and its `text` has its **lines reversed** (newest line on top) so it is consistent with the `_reverse_log` behaviour already used by the Logs tab. Add a small private line-reverse helper inside `session_reader.py` — do **not** import `dashboard/`.

**Ordering.** Group turns in chronological order, then reverse the list of turns so the newest turn is first. Each turn keeps its internal chronological order. Return `list[list[dict]]`. Empty input returns `[]`. The helper MUST NOT mutate the input segments (return new dicts where text is rewritten).

### The router + template change (S03 contract)

- `dashboard/routers/items.py:item_session_log` — after `raw_segments = read_session_content(run)`, call `group_into_turns_newest_first(raw_segments)` and pass the result to the template as `turns` (replacing the `segments` context key). The error-fallback branch (lines 2258-2265) must also produce a `turns`-shaped value (a single turn containing the one error segment). Import the helper from `orch.daemon.session_reader` alongside the existing `read_session_content` import.
- `dashboard/templates/fragments/session_log_popup_content.html` — change the guard and loop to iterate `turns`: an outer `{% for turn in turns %}` and an inner `{% for seg in turn %}` reusing the existing per-segment rendering verbatim. Between turns (every turn except the first) render a thin divider using existing Tailwind utility classes already present in this file (e.g. `border-t border-border`) — do **not** introduce a new CSS class or require a `make css` rebuild. The header block, the `is_live` polling wrapper, and the empty-state `{% else %}` branch are preserved.

## File Manifest

All files for this work item live under `ai-dev/active/I-00106/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00106_Issue_Design.md` | Design | This document |
| `I-00106_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00106_S01_Backend_prompt.md` | Prompt | S01 turn-grouping helper |
| `prompts/I-00106_S02_CodeReview_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00106_S03_Frontend_prompt.md` | Prompt | S03 router + template change |
| `prompts/I-00106_S04_CodeReview_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00106_S05_Tests_prompt.md` | Prompt | S05 reproduction + regression tests |
| `prompts/I-00106_S06_CodeReview_prompt.md` | Prompt | S06 review of S05 |
| `prompts/I-00106_S07_CodeReview_Final_prompt.md` | Prompt | S07 cross-agent final review |
| `prompts/I-00106_S16_BrowserVerification_prompt.md` | Prompt | S16 browser verification |
| `prompts/I-00106_S17_SelfAssess_prompt.md` | Prompt | S17 self-assessment |
| `evidences/pre/I-00106-bug-evidence.png` | Evidence | Pre-fix screenshot of the modal rendering oldest-first |
| `evidences/pre/I-00106-bug-snapshot.yml` | Evidence | Pre-fix accessibility snapshot of the modal |

Reports are created during execution in `ai-dev/active/I-00106/reports/`.

## Test to Reproduce

Test-file location: `tests/dashboard/test_session_log_modal_ordering.py`. This is a **dashboard** test — it drives the `item_session_log` route through a FastAPI `TestClient`. Copy the proven pattern from `tests/dashboard/test_items_session_log.py`, the existing test file for this exact route: a **file-local** `client` fixture plus the `_make_project` / `_make_pi_jsonl` seed helpers. Note `tests/dashboard/conftest.py` does **not** define `client` or any factory — it only re-exports the testcontainer DB fixtures (`db_session`, `test_project`) from `tests/integration/conftest.py`; the file-local `client` fixture depends on `db_session`, and that dependency is the reason route-driving tests belong under `tests/dashboard/` (I-00067 lesson). The test reproduces the bug end-to-end: pre-fix the route renders segments oldest-first, so the newest turn's text appears *after* the oldest in the response HTML; post-fix the order flips.

```python
def test_i00106_session_log_modal_renders_newest_turn_first(client, ...):
    """Reproduction: the Agent Session Log modal must render the newest agent
    turn ABOVE the oldest turn.

    Fails before the fix: the route renders read_session_content() output
    chronologically, so the oldest turn's marker appears first in the HTML.
    """
    # Seed a pi StepRun whose log_content is a JSONL session with TWO distinct
    # turns: an OLD turn (assistant reply text "OLDEST_TURN_MARKER") followed by
    # a NEW turn (assistant reply text "NEWEST_TURN_MARKER").
    ...
    resp = client.get(f"/project/{project_id}/item/{item_id}/step/{step_id}/session-log")
    assert resp.status_code == 200
    html = resp.text
    # Semantic ordering assertion — specific markers, not shape
    assert "NEWEST_TURN_MARKER" in html and "OLDEST_TURN_MARKER" in html
    assert html.index("NEWEST_TURN_MARKER") < html.index("OLDEST_TURN_MARKER"), (
        "I-00106 bug: newest turn must render above the oldest turn"
    )
```

## Acceptance Criteria

### AC1: Bug is fixed — newest turn renders first

```
Given a step run whose agent session log contains multiple turns
When the Agent Session Log modal is opened from the steps-table "Logs" column
Then the newest turn renders at the TOP of the modal and the oldest turn at the bottom,
     and within every turn the segment order is unchanged
     (thinking -> tool call -> tool result -> assistant reply)
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests/dashboard/test_session_log_modal_ordering.py::test_i00106_session_log_modal_renders_newest_turn_first passes,
     and the unit tests for group_into_turns_newest_first in tests/unit/test_session_reader.py pass
```

### AC3: Within-turn order is preserved

```
Given an agent turn made of a thinking segment, a tool call, a tool result, and an assistant reply
When that turn is grouped by group_into_turns_newest_first
Then the four segments appear in that exact chronological order inside the turn
     (only the order of turns relative to each other is reversed, never the order within a turn)
```

### AC4: In-progress trailing turn and special segments

```
Given a still-running step whose session log ends with thinking + tool segments and no assistant reply
When the modal is rendered
Then those trailing segments form a single in-progress turn shown at the TOP;
And a compaction marker renders as its own standalone separator turn between the turns around it;
And a claude/opencode single-"log" segment renders with its text lines reversed (newest line on top)
```

### AC5: No empty-state or live-poll regression

```
Given a step run with no readable session content
When the modal is opened
Then the existing empty-state message still renders (no template exception);
And for a live (running/stalled) step the 3-second htmx poll still refreshes the modal body,
     now showing the newest turn at the top on every refresh
```

## Regression Prevention

- The unit tests pin the contract of `group_into_turns_newest_first`: turn order is reversed, within-turn order is preserved, the in-progress trailing turn surfaces first, `compaction` is a standalone turn, `error` terminates a turn, consecutive `assistant` segments stay in one turn, and a lone `log` segment gets line-reversed. Any future refactor of the helper that breaks newest-first ordering or within-turn order fails these tests.
- The dashboard render-order test pins the end-to-end behaviour at the route boundary, so a future change that drops the helper call in `item_session_log` (reverting to chronological order) is caught immediately.
- Keeping the reversal in a single named pure helper — rather than scattering `reversed(...)` in the router or template — means there is exactly one place to test and one place that can regress.

## Dependencies

- **Depends on**: CR-00065 (introduced the Agent Session Log viewer, `session_reader.py`, and the modal this fix re-orders)
- **Blocks**: None

## Impacted Paths

- `orch/daemon/session_reader.py`
- `dashboard/routers/items.py`
- `dashboard/templates/fragments/session_log_popup_content.html`
- `tests/unit/test_session_reader.py`
- `tests/dashboard/test_session_log_modal_ordering.py`

## TDD Approach

- **Reproducing test**: `tests/dashboard/test_session_log_modal_ordering.py::test_i00106_session_log_modal_renders_newest_turn_first` — fails before the fix (oldest turn renders first), passes after.
- **Unit tests** (file: `tests/unit/test_session_reader.py`, appended to the existing suite — `group_into_turns_newest_first` imported from `orch.daemon.session_reader`, exercised with hand-built synthetic segment lists, no files needed):
  - `test_group_turns_reverses_turn_order` — two complete turns; assert the result has the newest turn at index 0 and the oldest last.
  - `test_group_turns_preserves_within_turn_order` — one turn of thinking/tool_call/tool_result/assistant; assert the four segments keep their exact order inside the turn.
  - `test_group_turns_in_progress_trailing_turn_first` — segments ending with thinking + tool_call and no assistant reply; assert the trailing turn is its own turn and is first in the result.
  - `test_group_turns_compaction_is_standalone_turn` — a `compaction` segment between two turns; assert it is a single-segment turn in the correct position.
  - `test_group_turns_error_terminates_turn` — a turn ending in an `error` segment; assert the error closes that turn and a following turn is separate.
  - `test_group_turns_consecutive_assistant_segments_stay_in_one_turn` — two adjacent `assistant` segments; assert they land in the same turn, not two.
  - `test_group_turns_log_segment_lines_reversed` — a single `log` segment with multi-line text; assert the returned segment's text lines are reversed and the input dict is not mutated.
  - `test_group_turns_empty_input_returns_empty_list` — `[]` in, `[]` out.
- **Dashboard tests** (file: `tests/dashboard/test_session_log_modal_ordering.py`, uses the `client` fixture):
  - `test_i00106_session_log_modal_renders_newest_turn_first` — reproduction (above): assert `html.index("NEWEST_TURN_MARKER") < html.index("OLDEST_TURN_MARKER")`.
  - `test_session_log_modal_empty_state_still_renders` — a step run with no session content; assert HTTP 200 and the existing empty-state copy is present (no template exception).

**Assertion strength** — assert specific marker text and concrete index ordering, never shape-only checks like "the response contains some segments". See the S05 prompt's semantic-correctness warning.

## Notes

- Severity is **Low**: this is a readability/UX fix. No data is lost, no value is rendered incorrectly — only the *order* of correct content changes. Decision recorded 2026-05-22.
- Scope decision (user, 2026-05-22): **only** the Agent Session Log modal (the steps-table "Logs" column). The "Logs" **tab** already reverses log lines via `_reverse_log` and is intentionally untouched.
- Reversal granularity decision (user, 2026-05-22): reverse **by turn** — flip the order of turns, preserve each turn's internal sequence — not a flat reversal of every segment (which would place a tool result above its own tool call).
- The turn-boundary rule ("a turn ends at an `assistant` segment not followed by another `assistant`, or at an `error`") is a heuristic over the pi JSONL event stream. The common pi pattern is one trailing `assistant` text per turn, so it groups cleanly; the consecutive-`assistant` rule covers multi-`text` messages. This is presentation-only — a mis-placed boundary is a cosmetic imperfection, never a correctness defect.
- No scroll-preservation JavaScript is added: with newest-first ordering the latest turn is at the top, which is where an `innerHTML` poll swap already lands. Preserving mid-scroll position across the 3 s live poll is explicitly out of scope.
