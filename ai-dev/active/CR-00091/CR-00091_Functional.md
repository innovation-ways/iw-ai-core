# CR-00091 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item does not add a new database migration. It changes how future migrations are created and validated by the development pipeline.

## Why

When an AI agent generates a database migration, it records a pointer to the current chain tip at that moment. If other work lands on the main branch before this item finishes, the pointer becomes stale. The pipeline fixes it automatically just before merging — but by then the validation gate that checked the migration has already run against outdated data, giving a false sense of correctness. In one recent incident (CR-00086), an item stalled mid-workflow and the stale pointer went unnoticed until a human intervened manually. This change makes the "fix at merge time" contract explicit and testable from the start.

## What Changed (for the User)

- Agents generating a database migration now run a new pipeline command (`make migration-pending`) instead of invoking the Alembic tool directly. The generated file immediately contains a placeholder value (`"PENDING"`) instead of a specific revision identifier.
- The migration validation gate (`make migration-check`) automatically resolves the placeholder to the real chain tip before running its checks, so the validation always reflects the current state of the main branch.
- The pre-merge rebase step (which was already capable of resolving placeholder values) now has an explicit test proving this behaviour, preventing future regressions.
- Project documentation and the three agent-creation assistants are updated to teach the new convention, so all future items adopt it without manual guidance.

## How It Behaves

When an agent creates a new migration, it runs the pipeline command with a short description. The command generates the migration file and immediately replaces the parent-revision field with the word "PENDING". The agent commits the file as-is.

When the validation gate runs later in the same workflow, it looks for any migration files containing "PENDING", computes the actual current chain tip from all other migrations, replaces "PENDING" with that value, and then runs the full round-trip check (upgrade, schema comparison, downgrade, upgrade again). The validation result is always against a real, current state.

At merge time, the daemon's existing rebase step detects "PENDING" (which never matches any real revision identifier) and overwrites it with the true chain tip at that moment. The commit history shows a clean rebase entry, exactly as before.

If no migration files contain "PENDING", the validation gate and rebase step behave identically to today — no regressions for existing items.

## Out of Scope

- Enforcing that agents use `make migration-pending` — the existing direct Alembic invocation still works; adoption is by convention, not by validation.
- Changes to how the daemon handles real (non-PENDING) revision values — the rebase logic is unchanged in behaviour.
