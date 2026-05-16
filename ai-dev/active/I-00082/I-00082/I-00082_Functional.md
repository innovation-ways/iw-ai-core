# I-00082 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This work
adds no Docker usage.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work leaves migrations unchanged.

## Why

Each work item declares a tight list of files it is allowed to touch.
Today, when a quality-validation gate fails and the platform retries the
fix automatically, the retry agent ignores that list. It either drifts
into unrelated edits that break previously-passing checks, or it silently
undoes operator fixes the operator just applied. Both outcomes deadlock
the item until a human steps in. CR-00053 spent roughly fourteen wasted
retry cycles on this single problem.

## What Changed (for the User)

- When the platform retries a failed quality check, it now respects the
  item's declared scope and refuses to make edits outside it.
- If a retry genuinely needs a fix outside the declared scope, the
  platform pauses and surfaces the situation to the operator with a clear
  one-line summary, instead of looping silently.
- Operator-applied edits to files outside the declared scope (a common
  carry-over fix for cross-item drift) are no longer silently reverted by
  the retry agent.
- Dashboard observers see a new line in the daemon log on every retry
  cycle showing how many edits stayed in scope and how many tried to leave
  it, so stuck items become trivial to triage.

## How It Behaves

When a retry runs and finishes, the platform compares the files the agent
touched against the item's declared scope. If every edit is in scope, the
retry proceeds normally — the rerun of the failing gate is the final word.
If any edit lies outside scope, the platform stops the retry, keeps the
agent's edits intact (does not auto-revert them), and marks the cycle as
needing operator review with a one-line note like "fix-cycle escalated:
agent edited 2 files outside scope". The operator then chooses to amend
the scope, accept the edits, or revert and retry.

The happy path — retries that stay within scope — is unchanged.

## Out of Scope

- The merge-time scope gate (which already exists and runs at the end) is
  unchanged; this work adds an earlier gate during fix cycles.
- Auto-amending the declared scope based on agent suggestions is not part
  of this work — every scope change is operator-driven.
