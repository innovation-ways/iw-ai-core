---
description: Analyze a failed work item to determine root cause of failure and recommend next steps.
---

# Analyze Failed Item

Analyze a failed work item to determine the root cause and recommend next steps.

## Usage

Provide the work item ID to analyze.

## Workflow

1. **Get item status**:
   ```bash
   iw item-status {ID}
   ```

2. **Read the design document** at `ai-dev/design/work/{ID}/design.md` to understand what was being implemented.

3. **Read the workflow manifest** at `ai-dev/design/work/{ID}/manifest.json` to understand which step failed.

4. **Read the step reports** to find error details:
   - Check `ai-dev/design/work/{ID}/reports/` for any generated reports
   - Look for error messages, stack traces, and failure descriptions

5. **Investigate the codebase**:
   - Read the files that were being modified
   - Check git log for recent changes
   - Run tests to see current state of failures

6. **Determine root cause**:
   - Was it a code error in the implementation?
   - Was it a test failure?
   - Was it a design issue?
   - Was it an environment/tooling issue?

7. **Report to user**:
   - Work item ID and title
   - Which step failed and which agent was running
   - Root cause analysis
   - Recommended next steps:
     - Re-run the failed step (`/fix_item`)
     - Modify the design and re-execute
     - Manual intervention needed
