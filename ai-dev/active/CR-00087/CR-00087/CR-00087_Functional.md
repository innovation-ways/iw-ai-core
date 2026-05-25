# CR-00087 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This change leaves migrations unchanged.)

## Why

When an automated fix-cycle agent edits a file the work item did not declare as in-scope, the orchestrator pauses the item and asks the operator to either confirm the path is allowed or revert the agent's edits. Most of these prompts are for routine paths — companion test files, small documentation touches, work-item artefacts — and the operator approves them without thinking. The click adds friction without exercising real judgment. This change lets each project pre-bless a small set of safe path patterns so routine cases resolve automatically and only genuinely surprising edits escalate to a human.

## What Changed (for the User)

- A project can declare a list of pre-approved path patterns plus an optional safety cap on how many files one auto-confirm may cover.
- When a fix-cycle's out-of-scope edits fall entirely within the pre-approved patterns, the work item resumes on its own without waiting for a human.
- When even one edit falls outside those patterns, the work item still pauses and the existing manual buttons appear exactly as they do today.
- The event feed records the original scope-violation signal AND a new auto-amend signal, so operators can see both the cause and the action.
- Existing projects see no behaviour change until they add the new configuration block.

## How It Behaves

When a fix-cycle agent edits a file outside the work item's declared scope, the orchestrator checks the project's pre-approved patterns. If every edited file matches a pattern and the count stays within the safety cap, the orchestrator records the violation, adds the files to the work item's allowed list (in both the working copy and the design-time copy), records that it auto-confirmed, and lets the work item move on. The yellow "scope blocked" badge does not appear in this case.

If even one edit falls outside the patterns, or the total exceeds the cap, the orchestrator behaves exactly as it does today: the badge appears, the work item waits, and the operator decides whether to approve or revert.

Malformed configuration (wrong shape, wrong types) is treated as if the feature were turned off — the orchestrator logs a warning and falls back to the manual flow.

## Out of Scope

- The "Revert" action remains manual. Reverting an agent's edits rewrites the working copy, which is destructive enough that a human should always make that call.
- The fix-cycle agent is not re-launched. The orchestrator keeps the agent's edits exactly as the manual confirm does today.
