# CR-00046 — Functional Design

## ⛔ Docker is off-limits

Standard policy applies. This change touches no container state. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. This change adds no database migration and modifies none.

## Why

Nearly all of this platform's tests are written by an AI agent. The testing rules we wrote down earlier this month say plainly: every test must be able to fail, and a test whose only assertion is "this isn't None", "this is a dict", or "this mock was called" is worthless. Until now those rules were guidance only — nothing in the build would stop a new vacuous test from landing. As the suite grows, drift back to those patterns is inevitable without an automated check. This change adds a small, fast static scanner that flags four classes of vacuous test and turns them into a build failure, with a one-line escape hatch for the rare case where a weak assertion really is the right thing.

## What Changed (for the User)

For people running or reviewing work on the dashboard:

- A new quality check runs on every pull request and inside the daemon's per-item gate sequence, alongside lint, format, and type-check. A new test with no assertion, only trivial-truth assertions ("not None"), only mock-called assertions, or an over-broad exception catch fails the gate with a clear message naming the test and the reason.
- Existing tests that match those patterns today are recorded in a baseline file so the gate does not break the build immediately. They are tracked as a known cleanup backlog.
- Adding a test to the baseline to silence the gate is explicitly the wrong fix. The right fix is to strengthen the test so it can actually fail when the code regresses.

## How It Behaves

The scanner walks every test file, looking only at functions whose name begins with "test_". For each one it asks four questions. Does the function contain any assertion at all? Are every one of its assertions trivially true regardless of what the code does? Are all of its assertions only checking that a mock was called, rather than checking behaviour around it? Does it catch a very broad exception class without constraining the message? If any answer is bad, the test is reported with its path, line, and a one-line explanation. The list is then compared against the baseline; the build fails only on entries not already there. A strict mode for ad-hoc runs ignores the baseline entirely. A short note in the testing standards explains the contract, and the testing skill agents read before writing tests now points at the gate, so the rules are no longer only advice.

## Out of Scope

- Cleaning up the existing baseline (the long tail of weak tests already in the suite) is deliberately a separate, larger follow-up — the goal of this change is the gate, not the cleanup.
- Other Phase-1 quality gates (coverage gates, randomised test order, secrets scanning, dead-code and dependency hygiene, Allure reporting, the curated smoke layer) are tracked as their own work items.
