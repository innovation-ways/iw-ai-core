# F-00084 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This feature adds no database migrations.

## Why

When two parallel work items touch the same file, the merge queue parks the second item in a failed state that only an operator can recover. On 2026-05-16 this happened twice in one afternoon for the same test files, with conflicts trivial enough that a human resolution took under a minute. We want the platform to start learning what those resolutions look like, with the long-term goal of letting it propose, verify, and eventually apply them on its own. This feature is the first step: plumbing plus a safe-by-construction observation mode that records what an AI would suggest, without ever changing anything.

## What Changed (for the User)

- A new operator-controlled setting picks a phase of behaviour for the auto-resolver. The default is "off"; an operator can flip it to "observe" once the wiring has been verified.
- In "observe" mode, every merge-queue conflict the platform deems safe to attempt produces a new audit record: what the AI would have proposed for each file, which model was used, and how many tokens were consumed. The record is visible in the dashboard's events view alongside the existing conflict notification.
- Some files are permanently off-limits: database migrations, secret-scanner configs, environment files, identity files, bootstrap scripts, lockfiles, and binaries. When one is in conflict, the record says it was skipped for safety and the operator workflow is unchanged.
- The manual flow is preserved: the conflict notification still fires, the item still lands in the recoverable-failed state, and the existing "retry the merge" operator command still works.

## How It Behaves

When the platform hits a merge conflict, it inspects the conflicting files. If every file is on the safe list (test files, documentation, item reports), it records that it will attempt an observation, then asks the configured AI to propose a resolution for each file in turn — supplying the common ancestor, both diverged versions, and recent context. The AI is told to say so explicitly if it is not confident rather than guess. Whatever the AI returns — a full proposed file or an explicit refusal — is captured in the audit record, and the merge attempt is aborted just like today. Nothing in the worktree is touched and no commit is made. If any conflicting file is on the off-limits list, the AI is skipped entirely, a "skipped for safety" entry is recorded, and today's behaviour applies.

A safety net catches every other case: an AI error, an oversized conflict region, too many files in conflict, a binary file, or a missing or malformed configuration — the reason is recorded and the platform falls back to today's behaviour. Operators advance from "off" to "observe" by editing the configuration and sending a reload signal — no restart needed.

## Out of Scope

- The resolver does not yet apply its proposals — that comes once audit data confirms the proposals are correct.
- There is no dedicated audit-browsing page yet; records appear in the existing events view.
