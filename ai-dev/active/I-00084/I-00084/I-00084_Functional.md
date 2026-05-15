# I-00084 — Functional Design

## ⛔ Docker is off-limits

Standard policy. No Docker usage.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migration impact.

## Why

This project runs entirely on a local machine — nothing is pushed to a
remote git server. One of the quality-coverage checks compares each
worktree's changes against a remote pointer, which never advances in this
setup. The result: every worktree silently sees every recently-merged
item as "its own diff", and the coverage check fails for reasons that
have nothing to do with the work item being checked. CR-00053's coverage
was reported as 75% but the real number on its actual changes was 92%.

## What Changed (for the User)

- The diff coverage number that operators see now reflects only the
  files the work item actually changed, not unrelated files from other
  recently-merged items.
- Worktrees created by the platform have their internal "remote main"
  pointer kept in sync with the local main branch, so all
  comparison-based tools (coverage, scope gates, future linters) get
  the right answer.
- Operators no longer need to run a manual `git fetch` workaround to
  get accurate diff-coverage numbers.

## How It Behaves

Every time the platform creates a working area for a new item, it
syncs the working area's "remote main" pointer to whatever the local
main branch currently points to. This is a single, fast, harmless
operation that runs once per worktree creation. The same sync runs as
a safety net at the top of the diff-coverage check itself.

The single-developer happy path (only one item ever in flight) is
unaffected, because in that case the pointer was already in sync.

## Out of Scope

- This work does not change anything about the actual remote (GitHub)
  setup. If someone ever does start pushing to GitHub, both the existing
  GitHub-based flow and this local-only sync continue to work side by
  side.
- This work does not change the diff-coverage threshold or the test
  suite.
