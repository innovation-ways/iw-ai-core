# CR-00046 — Functional Design

## ⛔ Docker is off-limits

Standard policy applies. This change touches no container state. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. This change adds no database migration and modifies none.

## Why

Nearly all of this platform's tests are written by an AI agent. The testing rules we wrote down earlier this month say plainly: every test must be able to fail, and a test whose only assertion is "this isn't None" or "this is a dict" or "this mock was called" is worthless. But until now those rules were guidance only — there was nothing in the build that would actually stop a new vacuous test from landing. As the team grows the suite, drift back to those patterns is inevitable without an automated check. This change adds a small, fast static scanner that flags four classes of vacuous test and turns them into a build failure, with a one-line escape hatch for the rare case where a weak assertion is genuinely the right thing.

## What Changed (for the User)

For people running or reviewing work on the dashboard:

- A new quality check runs on every pull request and inside the daemon's per-item gate sequence, in addition to lint, format and type-check. If a new test is added that has no assertion, asserts only trivial truths (such as "the result is not None"), asserts only that a mock was called, or catches `Exception` too broadly, the gate fails with a clear message naming the test and the reason.
- Existing tests that today match one of those patterns are recorded in a baseline file so the gate does not break the build immediately. Those tests are tracked as a known cleanup backlog — they can fail the gate after they are improved, not before.
- Adding a test to the baseline to silence the gate is explicitly the wrong fix. The right fix is to strengthen the test so it can actually fail when the code regresses.

For people working on the platform itself, the rules already written into the testing standards are now backed by an automated check that is run locally by the standard quality target and remotely by both the daemon's quality gate sequence and the GitHub workflow that already runs on every push and pull request.

## How It Behaves

The scanner walks every test file under the tests folder, looking only at functions whose name begins with "test_". For each one, it asks four questions. Does the function contain any assertion at all? Are every one of its assertions trivially true regardless of what the code does? Are all of its assertions only checking that a mock was called, rather than checking the behaviour around the mock? Does it catch a very broad exception class without constraining the message? If any of those answers comes out badly, the test is reported with its path, its line, and a one-sentence explanation of which check failed. The scanner then compares its list of reports against the baseline file; the build fails only if a test is in the new list but not in the baseline. In strict mode (a flag for running it by hand) the baseline is ignored and every flagged test fails the run. A short note in the testing standards explains the contract, and the testing skill that agents read before writing tests now points at the gate so the rules are no longer only advice.

## Out of Scope

- Cleaning up the existing baseline (the long tail of weak tests already in the suite) is deliberately a separate, larger follow-up — the goal of this change is the gate, not the cleanup.
- Other Phase-1 quality gates (coverage gates, randomised test order, secrets scanning, dead-code and dependency hygiene, Allure reporting, the curated smoke layer) are tracked as their own work items.
