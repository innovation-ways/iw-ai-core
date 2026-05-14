# CR-00051 — Functional Design

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Leaves migrations unchanged.

## Why

The previous security work added a static-analysis gate to the per-item quality checks before the existing codebase had been audited against the new rules. As a result, every new feature, incident, and change request now fails the security gate on issues that pre-date the work — issues that have nothing to do with whatever the item was meant to deliver. One feature already had to skip the gate by hand to get merged. This change clears the backlog of pre-existing alerts in one focused pass so future work items can stop tripping over inherited findings.

## What Changed (for the User)

- Operators no longer have to skip the per-item security gate. Every new feature, incident, or change request from this point on runs the gate cleanly.
- The contributor handbook gains a short section explaining how to triage a new security alert when one does appear: when to fix it for real, and when to mark it as a documented false positive with a same-line reason.
- No dashboard page, button, or workflow looks or behaves differently. No data is migrated. No setting is renamed.

## How It Behaves

When the orchestration platform runs its automated quality checks against a work item, the security gate now passes on a clean baseline. If a contributor introduces code that triggers a new security alert, the gate fails for that item and that item only — the failure is now attributable to the new code, not to inherited noise. The contributor either fixes the underlying issue or, where the alert is a false positive, adds a same-line marker with a written explanation. Either way the per-item gate again becomes a meaningful signal.

The nightly full-repository security run continues to operate as before, unchanged.

## Out of Scope

- Migrating away from the older `# nosec` style markers that came from a previous static-analysis tool. Those markers stay in place; this work only adds new markers for the current tool, side-by-side with the old ones.
- Tightening the security ruleset, adding new rule packs, or running a different scanner. The configuration is unchanged.
