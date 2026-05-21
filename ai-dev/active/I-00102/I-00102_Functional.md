# I-00102 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item adds one migration (a new optional column on the work items table). The agent writes the migration; the daemon applies it.

## Why

Operators routinely iterate on a work item's design package — adding or reordering steps, renaming prompts — between the moment they first register the item and the moment they approve it for execution. Today, the very first register call freezes the step layout in the database, and every subsequent edit on disk is silently ignored. When the operator finally approves the item and lets the daemon run it, the daemon picks up the stale layout and fails — sometimes loudly, sometimes after burning thirty minutes of compute on the wrong instructions. The trigger for this change is a real-world failure where one work item ran a quality-gate test command for thirty minutes when it should have been running a self-assessment. The goal is to make approval the authoritative freeze point so iteration between register and approve "just works".

## What Changed (for the User)

- When you edit a work item's design after first registering it, the **approve** action now notices the change automatically and updates the recorded steps to match what is on disk. No new command to learn; no manual re-register step.
- The dashboard's events stream gains a new `manifest_refreshed` row whenever this happens, so you can audit which approvals quietly rebuilt the step list.
- Approve still refuses to run for items that are not in draft status, so an in-flight or completed item is never rebuilt out from under you.

## How It Behaves

Normal happy path: register a work item; iterate on the design; approve. If the design has changed since register, approve will silently rebuild the step list from the current files, record an audit event, and proceed. If the design has not changed, approve runs as it does today with no extra noise.

Edge cases:

- If approve cannot find the workflow manifest at the expected path (the operator deleted or renamed the design folder), approve refuses with an explicit error rather than guessing.
- If the work item is no longer in draft (it was already approved, or it is running, or it is done), no rebuild is attempted; the existing status guard rejects approve with the same message it does today.
- Existing work items registered before this change have no recorded design fingerprint. On their next approve, the system treats that as "the design may have drifted" and rebuilds from the current files, then stores the fingerprint. This is safe because by definition a draft item has not yet executed any steps.

## Out of Scope

- This change does not touch the daemon's behaviour during step execution. A companion daemon-side fix already ensures that if a stale step somehow slips past approval, the daemon fails fast with a clear error instead of running the wrong instructions.
- No new operator-facing CLI flag is added. Iteration after approval, or rebuilding a non-draft work item, remains unsupported.
