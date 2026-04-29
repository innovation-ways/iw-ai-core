# F-00065 S13 QvBrowser Report

## What was done

- Ran browser verification for F-00065 (Diagram display in code view) against the E2E stack at `http://localhost:9919`
- Logged in as `dev@example.local`
- Verified V1–V5 per the step instructions
- Captured 4 screenshots and wrote a detailed report to `reports/F-00065_S13_BrowserVerification_Report.md`

## Files created

- `ai-dev/active/F-00065/reports/F-00065_S13_BrowserVerification_Report.md`
- `ai-dev/active/F-00065/evidences/post/F-00065_v1_arch_diagram.png`
- `ai-dev/active/F-00065/evidences/post/F-00065_v2_module_diagram.png`
- `ai-dev/active/F-00065/evidences/post/F-00065_v3_empty_state.png`
- `ai-dev/active/F-00065/evidences/post/F-00065_v5_no_regressions.png`

## Test results

| Verification | Result |
|-------------|--------|
| V1: Architecture diagram visible | FAIL |
| V2: Module diagram visible | FAIL |
| V3: Empty state for no diagram | PASS |
| V4: Mermaid blocks render correctly | SKIP |
| V5: No regressions | PASS |

## Issues found

**V1 / V2: `pre[data-lang="mermaid"]` not rendered — code defect**

The fragment `code_architecture_diagram.html` uses `pre[data-lang="mermaid"]` format, but `iwRenderMermaid` in `components/libs/mermaid.html` queries `.mermaid:not([data-processed])` — a selector for `div.mermaid` format. The correct function `window.iwChat.upgradeMermaidBlock` (in `chat/mermaid.js:244`) handles `pre[data-lang="mermaid"]` but is never called for architecture diagram fragments.

**Root cause files:**
- `dashboard/templates/components/libs/mermaid.html:8` — wrong selector
- `dashboard/templates/fragments/code_architecture_diagram.html:16` — calls `iwRenderMermaid` instead of `upgradeAllMermaidBlocks`
- `dashboard/templates/base.html:231-232` — htmx handler calls wrong function

**V2 (RAG module not visible):** The E2E seed only has `orch/daemon/` and `dashboard/` modules. The `diagram-module-rag` fixture row exists but the RAG module doesn't appear in the architecture map, so it can't be clicked in the UI. This is an environment issue, not a code defect.