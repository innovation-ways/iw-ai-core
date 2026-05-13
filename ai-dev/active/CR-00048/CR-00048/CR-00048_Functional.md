# CR-00048 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change adds no migration and modifies none.

## Why

The test suite has three quiet weaknesses. Tests always run in the same order, so when one test leaves state behind that affects another, the failure only shows up "sometimes in CI" instead of every run. A mistyped test marker (the labels that group or skip tests) is only a warning, so a typo can silently mislabel or skip a test. And nothing watches for dead code or dependency drift (packages declared but unused, or used but not declared) — both accumulate over time. There is also a known instance of the first weakness: two tests pass everywhere except inside an automated-agent workspace, because an environment variable from that workspace leaks into the test. This change closes all four.

## What Changed (for the User)

For people running or reviewing work on the dashboard:

- Test runs now use a randomized order each time, with the seed printed at the top so any failure is reproducible. The suite was made robust to this — any secretly order-dependent test was fixed, or (if too many) quarantined and tracked as a backlog. Cross-test pollution now surfaces immediately, not intermittently.
- Mistyped or unregistered test markers are now an error, not a warning.
- The build also runs a dead-code scan and a dependency-hygiene check. These are informational for now — they print findings but do not fail the build; a later change turns them into hard gates once the noise is triaged.
- The two tests that failed only inside an automated-agent workspace now pass everywhere.

The testing standards and the testing skill agents read before writing tests now document how to reproduce a randomized failure and disable randomization.

## How It Behaves

Every test run picks a random order for files, classes, and functions, seeds the relevant randomness from one per-run seed, and prints it. To reproduce a failure you re-run with that seed; to debug without randomization you pass an option that turns it off. A mistyped marker makes the run fail fast with a message naming the unknown marker. The dead-code scan and the dependency check run as part of the standard quality target and the pull-request workflow, list what they find, and let the run continue. The two agent-context tests now explicitly control the environment variable that used to leak in, so they behave identically inside an agent workspace and on a developer machine.

## Out of Scope

- Turning the dead-code and dependency checks into hard gates is deliberately a later change — this one only adds them in informational mode.
- Actually deleting any dead code the scan flags is a separate effort.
- The separate, already-known no-op test gate and the existing weak-test-backlog cleanup are tracked as their own work items.
- If the random-order cleanup is larger than fits here, the remaining tests are quarantined and tracked rather than fixed — and, as a last resort, randomization is added but left off by default until a follow-up flips it on.
