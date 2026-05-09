# CR-00041 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item adds no migrations and modifies no existing migrations.)

## Why

CR-00039 renamed two visual pill styles in the dashboard. The implementation work updated the templates and styling correctly, but a pre-existing test was still asserting the old style names. The code review caught the mismatch on a second pass, after a fix-cycle prompt explicitly pointed at the design's test-update notes. That round-trip cost roughly five to ten minutes for a problem that was knowable from the start. The trigger here is recurring: every time we rename a visual style in the dashboard, the implementation prompt should remind the agent to keep tests in sync.

## What Changed (for the User)

- The prompt that instructs implementation agents now contains a short, named reminder: when a design renames a visual style, the agent must search the test suite for the old name and update assertions to the new name before declaring its work complete.
- A small unit test guards the reminder from being silently removed or drifting between the two copies of the prompt template kept inside this project.
- No user-visible behaviour changes in the product itself. The dashboard, daemon, CLI, and database are all unchanged.

## How It Behaves

When an implementation agent reads its step prompt, it now sees the new reminder inside the existing test-verification section. If the design document instructs the agent to rename a visual style, the agent treats stale assertions as a failure to verify and updates them as part of the same step, rather than letting the next code-review step discover the gap. If a future change accidentally removes the reminder from one of the two prompt copies, the unit-test layer fails immediately, before the prompt template is ever shipped to a running agent.

If a change does not involve renaming a visual style, the reminder is a no-op — the agent reads it, recognises it does not apply, and proceeds normally.

## Out of Scope

- Generalising the reminder beyond visual style renames to cover other kinds of identifier renames. This is deliberate; broadening it before we have evidence of recurrence would dilute the trigger.
- Any changes to the dashboard, the daemon, the CLI, or the orchestration database.
