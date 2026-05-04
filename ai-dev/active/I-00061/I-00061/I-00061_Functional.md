# I-00061 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item adds no migrations.)

## Why

When a design author lists a quality-validation gate that cannot run in the
target project — for example, asking for a frontend type-check on a project
that has no frontend, or running a Makefile target that does not exist — the
orchestrator launches it anyway, watches it fail, and burns five fix-cycle
attempts trying to "repair" what was never repairable. The work item then
parks until a human notices and skips the broken gate by hand. F-00076
recently lost five gates and roughly an hour of compute to this exact pattern.
The goal of this work is to recognise an unrunnable gate before it runs and
silently route around it.

## What Changed (for the User)

- Approving a work item now quietly drops any quality gate that obviously
  cannot run in the project. The operator sees no extra prompt — approval
  still succeeds the same way.
- Approving a batch performs the same check across every item in the batch,
  so a gate that was fine when an item was first approved but has since
  become unrunnable (the project drifted, a Makefile target was removed) is
  also handled.
- Skipped gates are recorded in the audit trail with the gate name, the
  reason it was unrunnable, and which command produced the verdict, so the
  operator can grep the event log to understand exactly what was skipped and
  why.
- Real, runnable gates are not affected. If a gate looks valid, it runs as
  before.

## How It Behaves

When the operator approves a work item, the system inspects every quality
gate attached to the item. For each gate it asks a small, conservative
question: "Could this command actually run here?" The check is purely
structural — it looks at the command shape (does the Makefile have this
target, does this directory exist, is this binary on the PATH) and returns
yes or no. It does not execute the command.

Gates that fail the check are silently marked skipped, with the reason and
command captured in the audit trail. Gates that pass — or that the system
cannot confidently classify — are left untouched and will run as normal
during execution.

The same check runs again when a batch is approved, in case the project
state changed between the two approvals. Both checks share one source of
truth, so they always agree on what counts as a phantom gate.

If, in a rare case, a gate is mis-skipped (for example, an earlier step in
the same item was supposed to add a missing Makefile target), the operator
can manually un-skip the gate and re-run it.

## Out of Scope

- Updating the design-creation skills to enforce the precheck — that is a
  separate doc change.
- Skipping non-quality-validation steps (implementation, code review, etc.) —
  those are not phantom-prone in the same way.
- Adding an explicit per-step opt-out flag for the rare "earlier step adds
  the target" case. That is a future enhancement if the rare case starts
  happening regularly.
