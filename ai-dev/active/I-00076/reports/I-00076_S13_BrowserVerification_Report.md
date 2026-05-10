# I-00076 S13 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9959`
- **E2E user:** `dev@example.local`
- **Target item:** `I-99003` (synthetic fixture seeded by `001_editable_step_item.py`)
- **Target step:** `S01` (status: `failed`)
- **Option applied:** id=5 (`claude` / `claude-opus-4-7`, "Claude Code / Opus 4.7")

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | **pass** | null | — | No dangling DOM refs on overview/history/batches; only `favicon.ico` 404 in console (harmless) |
| V1 | Editable-step `<select>` renders corrected markup | **pass** | null | `I-00076_v1_select_markup.png` | HTML has `hx-disabled-elt="this"`, no `this.disabled`, no `htmx.trigger`, `name="option_id"` present, `hx-patch` correct |
| V2 | Selecting an option fires exactly one successful PATCH | **pass** | null | `I-00076_v2_select_applied.png` | Selected option 5; UI updated to show "Claude Code" in CLI column; no JS/HTMX errors in console |
| V3 | Override persisted (DB confirmation) | **pass** | null | `I-00076_v3_override_persisted.png` | `workflow_steps.agent_runtime_option_id = 5`; exactly 1 `runtime_override_changed` event with `new_option_id: 5` |
| V4 | No regressions on adjacent overview-tab flows | **pass** | null | `I-00076_v4_no_regressions.png` | Batches page renders correctly; console clean (only `favicon.ico` 404); step pipeline strip, restart/skip buttons, bulk apply control all present |

## Console / Network Errors
- `favicon.ico:0` → 404 — present on every page load; cosmetic only, not a JS error or HTMX failure.

## No Regressions Observed
- Batches page (`/project/iw-ai-core/batches`) renders the `e2e-I-00076` batch correctly (status: `executing`).
- History page (`/project/iw-ai-core/history`) shows three items (I-00001, F-00055, CR-00001) without errors.
- The step pipeline strip, restart (↻) / skip (⏭) buttons, and "Apply to remaining steps" bulk control on the Overview tab are all present and not throwing.
- No new console errors introduced by the fix.

## Screenshots Captured
- `ai-dev/active/I-00076/evidences/post/I-00076_v1_select_markup.png`
- `ai-dev/active/I-00076/evidences/post/I-00076_v2_select_applied.png`
- `ai-dev/active/I-00076/evidences/post/I-00076_v3_override_persisted.png`
- `ai-dev/active/I-00076/evidences/post/I-00076_v4_no_regressions.png`

## Root Cause (on failure only)
N/A — all verifications passed.

## DB Evidence (V3)

**`workflow_steps` query:**
```
 work_item_id | step_id | agent_runtime_option_id
--------------+---------+-------------------------
 I-99003      | S01     |                       5
```

**`daemon_events` query (runtime_override_changed):**
```
 id | entity_id |        event_type        |                        metadata
----+-----------+--------------------------+-------------------------------------------------------------------------------------------------------------------------------
  1 | I-99003   | runtime_override_changed | {"actor": "dashboard", "scope": "step", "item_id": "I-99003", "step_ids": ["S01"], "new_option_id": 5, "old_option_id": null}
```

Exactly 1 event, `new_option_id: 5` (not `null`), confirming the fix is working end-to-end.