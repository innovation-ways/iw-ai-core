# CR-00076 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures used by automated tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds no database change and no migration.

## Why

The platform has several hard-learned rules about how the database layer must behave — rules discovered the painful way through incidents that took worktrees down. They are written as warnings in the project guidelines but are not all verified by tests, so the next time someone violates one the failure surfaces at runtime inside a live worktree instead of being caught by the build. This work formalises the three most critical data-layer invariants as a consolidated test module so violations are caught by the suite.

## What Changed (for the User)

- A new group of automated checks now asserts three data-layer invariants on every change: that the full-text search trigger works for every searchable column; that the documented database version-skew failure is reproducible and pinned; and that the database identity pin accepts valid connections and refuses unexpected ones.
- A new single-command gate, `make data-layer-check`, runs these checks together with the existing migration round-trip tests — one place for operators to audit the data layer.
- If a new check uncovers a genuine pre-existing defect, it is recorded as a separate tracked bug — the build still passes and nothing is silently ignored.
- No visible change to the dashboard, the API, or any user-facing behaviour — purely a safety net for the data layer.

## How It Behaves

- On every work item, the three new test modules run as part of the standard integration suite. Each spins up a fresh, isolated test database, applies the schema, and verifies its invariant; a failure names the exact invariant that broke.
- The full-text search check inserts then updates a row for every searchable column and confirms the search index is refreshed by the database trigger. If a new searchable column is added without a trigger, the check catches it.
- The version-skew check reproduces the documented failure pattern — a database left at a migration version the checked-out code does not contain — and confirms the upgrade fails in the recognised way. This is the failure class that previously only surfaced when a worktree's startup sequence died.
- The identity check confirms the two-sided contract: when the database fingerprint matches the configured expectation the system proceeds; when it does not, the system refuses the connection.
- The new `make data-layer-check` command runs the three modules together with the existing migration round-trip tests. It is a convenience target — the modules already run in the regular integration suite — for operators who want the data-layer gate in isolation.

## Out of Scope

- Fixing any data-layer defect the new tests discover — those are tracked as separate incidents.
- Changing or replacing the existing migration round-trip tests or database identity tests — those remain untouched.
- Adding a new migration file, or adding a runtime guard that detects version skew — this work tests and reproduces, it does not introduce new behaviour.
