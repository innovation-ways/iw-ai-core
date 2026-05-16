# F-00084 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This feature adds no database migrations.

## Why

When two parallel work items touch the same file, the merge queue hits a rebase conflict and parks the second item in a failed state that only an operator can recover. On 2026-05-16 this happened twice in one afternoon — both times for the same set of test files, with conflicts trivial enough that a human resolution took under a minute. We want the platform to start learning what those resolutions look like, with the long-term goal of letting it propose, verify, and eventually apply them on its own. This feature is the first step: plumbing plus a safe-by-construction observation mode that records what an AI would suggest, without ever changing anything.

## What Changed (for the User)

- A new operator-controlled setting picks a phase of behaviour for the auto-resolver. The default is "off"; an operator can flip it to "observe" once the new wiring has been verified.
- When the resolver is in "observe" mode, every merge-queue conflict that the platform deems safe to attempt produces a new audit record showing what the AI would have proposed for each conflicting file, what model was used, and how many tokens the attempt consumed. The record is visible in the dashboard's events view alongside the existing conflict notification.
- Some files are permanently off-limits: database migrations, secret-scanner configs, environment files, identity files, bootstrap scripts, lockfiles, and binaries are never sent to an AI. When one is in conflict, the audit record explicitly says it was skipped for safety and the existing operator workflow is unchanged.
- Today's manual flow is preserved exactly: the conflict notification still fires, the item still lands in the recoverable-failed state, and the existing "retry the merge" operator command still works.

## How It Behaves

When the platform tries to merge a completed work item and hits a conflict, it looks at the list of conflicting files. If every conflicting file is on the safe list (test files, documentation, item reports), the platform records that it will attempt an observation. It then asks the configured AI to propose a resolution for each file in turn, providing the common ancestor, both diverged versions, and recent context. The AI is told that if it is not confident, it should explicitly say so rather than guess. Whatever the AI returns — a full proposed file or an explicit refusal — is captured in an audit record and the merge attempt is then aborted just like today. No file in the worktree is touched and no commit is made. If any conflicting file is on the off-limits list, the platform skips the AI entirely, records a "skipped for safety" entry, and reverts to today's behaviour.

A safety net catches every other case: if the AI errors out, if the conflict region is too large, if too many files are in conflict at once, if a file is binary, or if the configuration is missing or malformed, the platform records the reason in the audit, falls back to today's behaviour, and never attempts a resolution. Operators advance from "off" to "observe" by editing the configuration and sending the daemon a reload signal — no restart needed.

## Out of Scope

- The resolver does not yet apply its proposals — that comes in a later change once two weeks of audit data confirm the proposals are correct.
- There is no dedicated audit-browsing page yet. The records are visible through the existing events view.
