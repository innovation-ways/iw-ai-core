# F-00066 S13 Browser Verification Fix Cycle 1/3

The end-to-end browser verification for step S13 of work item F-00066 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# F-00066 S13 Browser Verification Report

**Work Item**: F-00066 — Proactive diagram rendering in QA chat
**Step**: S13
**Agent**: qv-browser
**Date**: 2026-04-29
**Base URL**: `http://localhost:9943`

---

## Environment Summary

| Item | Value |
|------|-------|
| mmdc available | **NO** (not installed) |
| LanceDB index present | **YES** — `~/.local/share/iw-ai-core/code-index/iw-ai-core/vectors/code_iw_ai_core.lance` |
| E2E stack | Isolated DB (ports 55559/55560), dashboard at 9943 |
| Project slug | `iw-ai-core` |

---

## Verification Results

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Mermaid diagram inline | **FAIL** | `F-00066_v1_mermaid_inline.png` | Stub returned plain text — no Mermaid blocks emitted, so server-side rendering was never triggered. No `<figure class="chat-diagram-figure">` present. |
| V2 | Download SVG link | **FAIL** | `F-00066_v2_download_link.png` | Same as V1 — stub response contained no diagram blocks, so V2 cannot be evaluated. Classified as `ENV_DATA_MISSING` (E2E stub limitation, not a code defect). |
| V3 | Client-side fallback | **FAIL** | `F-00066_v3_fallback.png` | Stub response contained no Mermaid blocks, so `upgradeAllMermaidBlocks` had nothing to render. |
| V4 | No regressions | **PASS** | `F-00066_v4_no_regressions.png` | Plain text question received a streaming text response with no errors. No console errors observed. |

---

## Analysis

### Why V1/V2/V3 Failed

The E2E stack uses `scripts/e2e_ollama_stub.py` which returns **deterministic stub responses** — plain text answers that do not contain any Mermaid fenced code blocks. The F-00066 feature (server-side Mermaid rendering via `mmdc`) is correctly implemented in:
- `dashboard/routers/code_qa.py` (SSE `image` events with base64 SVG)
- `dashboard/static/chat/render.js` (`onImage` handler, figure+caption, `data-iw-server-rendered` hiding)
- `dashboard/static/chat/stream.js` (SSE parsing, calls renderer methods)

However, because the stub LLM never emits ```mermaid blocks, the rendering pipeline was never invoked. The `<figure class="chat-diagram-figure">` element (AC1) and "Download SVG" link (AC2) cannot be verified in this environment.

### mmdc Absence

`mmdc` is not installed on this system (`MMDC_ABSENT`). Per the verification prompt: "Failure in V1/V2 due to mmdc absence with client-side fallback working is classified as `ENV_DATA_MISSING` (binary not installed), not a code defect."

However, the failure here is more fundamental — the stub doesn't emit Mermaid at all, so the server-side rendering path is never reached regardless of mmdc availability.

### V4 Pass

Plain text question "What is the purpose of the daemon?" received a streaming response with no console errors. The chat panel, module navigation, and code page all function correctly. No regressions introduced by F-00065 changes.

---

## Console Errors Observed

None.

---

## Screenshots

- `ai-dev/active/F-00066/evidences/post/F-00066_v1_mermaid_inline.png` — V1 (question submitted, stub response visible)
- `ai-dev/active/F-00066/evidences/post/F-00066_v2_download_link.png` — V2 (same response, no Download SVG link found)
- `ai-dev/active/F-00066/evidences/post/F-00066_v3_fallback.png` — V3 (fallback verification, no Mermaid blocks to upgrade)
- `ai-dev/active/F-00066/evidences/post/F-00066_v4_no_regressions.png` — V4 (plain text Q&A, no errors)

---

## Recommendation

The F-00066 code is correctly implemented. The E2E verification environment (stub LLM) does not generate Mermaid diagrams, making it impossible to verify the rendering pipeline end-to-end in-browser. 

To properly verify this feature, either:
1. Update the E2E stub to emit Mermaid blocks in responses, or
2. Run verification against a real Ollama instance with a model that generates diagrams

---

## JSON Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "F-00066",
  "overall_status": "fail",
  "base_url_used": "http://localhost:9943",
  "verifications": [
    {
      "id": "V1",
      "name": "Mermaid diagram inline",
      "status": "fail",
      "screenshot": "F-00066_v1_mermaid_inline.png",
      "notes": "E2E stub does not emit Mermaid blocks — rendering pipeline not invoked. Not a code defect."
    },
    {
      "id": "V2",
      "name": "Download SVG link",
      "status": "fail",
      "screenshot": "F-00066_v2_download_link.png",
      "notes": "ENV_DATA_MISSING: stub didn't emit diagrams, cannot evaluate. mmdc also absent."
    },
    {
      "id": "V3",
      "name": "Client-side fallback",
      "status": "fail",
      "screenshot": "F-00066_v3_fallback.png",
      "notes": "No Mermaid blocks in stub response, upgradeAllMermaidBlocks had nothing to render."
    },
    {
      "id": "V4",
      "name": "No regressions",
      "status": "pass",
      "screenshot": "F-00066_v4_no_regressions.png",
      "notes": "Plain text Q&A works correctly, no console errors."
    }
  ],
  "console_errors_observed": [],
  "screenshots": [
    "ai-dev/active/F-00066/evidences/post/F-00066_v1_mermaid_inline.png",
    "ai-dev/active/F-00066/evidences/post/F-00066_v2_download_link.png",
    "ai-dev/active/F-00066/evidences/post/F-00066_v3_fallback.png",
    "ai-dev/active/F-00066/evidences/post/F-00066_v4_no_regressions.png"
  ],
  "notes": "E2E stub limitation: scripts/e2e_ollama_stub.py does not generate Mermaid diagrams. Feature code is correctly implemented. V4 (no regressions) passes. V1/V2/V3 fail due to stub behavior, not code defects."
}
```

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/F-00066/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00066/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
