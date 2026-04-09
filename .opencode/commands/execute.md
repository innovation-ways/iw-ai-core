---
description: Execute the workflow for a work item (e.g., /execute F123). Checks status via iw CLI and launches the orchestrator.
agent: orchestrator
---

Execute the workflow for the specified work item. Check item status via `iw item-status`, validate it is approved, move the design package from `ai-dev/design/active/` to `ai-dev/design/work/`, and execute all workflow steps defined in the manifest.
