---
description: Fix a failed work item by re-running the failed step with additional context about the failure.
---

# Fix Failed Item

Fix a failed work item by re-running the failed step.

## Usage

Provide the work item ID to fix.

## Workflow

1. **Get item status**:
   ```bash
   iw item-status {ID}
   ```
   Verify the item is in a failed state.

2. **Identify the failed step** from the item status output.

3. **Read the failure report** to understand what went wrong.

4. **Read the original prompt** for the failed step.

5. **Prepare enhanced context**:
   - Include the original prompt
   - Add the failure details and root cause
   - Add specific guidance on how to avoid the previous failure

6. **Re-run the failed step**:
   ```bash
   iw step-start {ID} --step S{NN}
   ```

7. **Dispatch the appropriate agent** with the enhanced context.

8. **Record the result**:
   ```bash
   # On success:
   iw step-done {ID} --step S{NN} --report-file {path}

   # On failure:
   iw step-fail {ID} --step S{NN} --error "{description}"
   ```

9. **If successful**, continue executing remaining steps in the workflow.

10. **Report** to the user:
    - Fix result (success/failure)
    - What was changed
    - Current item status
