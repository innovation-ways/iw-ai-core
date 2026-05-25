# CR-00088 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

No migrations. The change only edits Python code, tests, and a research document.

## Why

When two work items in the same batch touch overlapping files, one of them often hits a rebase conflict at merge time. The platform already tries to resolve such conflicts using a language-model dry run, but only if every conflicted file is on a narrow allowlist. On 2026-05-25, a Change Request hit a conflict spanning three files — one was eligible, two were not — and the all-or-nothing rule meant the operator got no machine-proposed resolution for any of them. Testing-initiative Change Requests now land weekly and routinely overlap on a tracker file plus a build-config file, so the all-or-nothing rule kills resolution help most weeks.

## What Changed (for the User)

- Operators waiting on a stuck merge will now see, in the daemon event, two distinct lists: files the machine produced a proposed resolution for, and files it declined to touch.
- The proposed-resolutions list is non-empty whenever at least one conflicted file is eligible, even if other conflicted files are not. Today that list is always empty in the mixed case.
- Stuck merges that previously fell straight to "operator must rebase everything from scratch" will now arrive with the eligible subset pre-proposed; the operator only resolves the files the machine declined.
- Nothing is applied automatically here. The operator still owns the final rebase. The point is to give them a head start on the half the conflict the machine knows how to handle.

## How It Behaves

A merge enters the queue. The platform attempts to rebase the work item's branch onto the latest line of the main branch. If that rebase fails, the conflict files are listed.

The classifier walks the list and sorts each file into one of three buckets: refused outright (the file is on a defence-in-depth refuse list, for example a migration file), eligible (allowed to receive a proposed resolution), or deferred (not refused, not on the allowlist). If any file falls into the refused bucket, the whole attempt aborts — defence in depth still wins.

If at least one file is eligible, the machine is invoked for that subset; the proposed resolutions land in the daemon event for the operator to copy across. The deferred subset is recorded alongside so the operator knows exactly which files still need manual work.

If every file is deferred, the existing "skipped — not allowlisted" outcome stands; the deferred list is just rendered explicitly for clarity.

Phase stays at dry-run. The worktree is never modified. The merge still fails until the operator finishes the manual half. The win is that the operator's manual half is smaller and the machine's work is visible.

## Out of Scope

- This change does not flip the platform from dry-run to actually applying machine-proposed resolutions; that promotion is a separate follow-up Change Request, sequenced after this one.
- This change does not widen the allowlist. The same narrow set of patterns gates which files the machine will touch.
