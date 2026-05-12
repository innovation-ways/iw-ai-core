# CR-00048 — Functional Design

## ⛔ Docker is off-limits

Standard policy applies. This change touches no container state. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. This change adds no database migration and modifies none.

## Why

The test suite has three quiet weaknesses. First, tests always run in the same order, so when one test accidentally leaves state behind that affects another, the failure only shows up "sometimes in CI" instead of on every run — which makes it slippery to catch and fix. Second, a mistyped test marker (the little labels that group or skip tests) is only a warning, so a typo can silently mislabel or skip a test without anyone noticing. Third, nothing watches for dead code or for dependency drift (packages declared but unused, or used but not declared) — both accumulate over time. There is also a concrete, known instance of the first weakness: two tests pass everywhere except inside an automated-agent workspace, because an environment variable from that workspace leaks into the test. This change closes all four.

## What Changed (for the User)

For people running or reviewing work on the dashboard:

- Test runs now use a randomized order each time, with the random seed printed at the top so any failure is reproducible. The suite has been made robust to this — any test that was secretly order-dependent has been fixed, or (if there were too many to fix at once) clearly quarantined and tracked as a backlog. As a result, accidental cross-test pollution surfaces immediately rather than intermittently.
- Mistyped or unregistered test markers are now an error, not a warning, so they get caught at once.
- The build now also runs a dead-code scan and a dependency-hygiene check. For now these are informational only — they print findings but do not fail the build; a later change will turn them into hard gates once the noise has been triaged.
- The two tests that failed only inside an automated-agent workspace now pass everywhere, because the test no longer lets the workspace's environment leak in.

For people working on the platform itself, the testing standards and the testing skill that agents read before writing tests now document how to reproduce a randomized failure and how to temporarily disable randomization.

## How It Behaves

Every test run picks a random order for files, classes, and functions, seeds the relevant randomness sources from a single per-run seed, and prints that seed. To reproduce a failure you re-run with that seed; to debug without randomization you pass an option that turns it off. If a mistyped marker is used, the run fails fast with a clear message naming the unknown marker. The dead-code scan and the dependency check run as part of the standard quality target and in the pull-request workflow, list whatever they find, and let the run continue regardless. The two agent-context tests now explicitly control the environment variable that used to leak in, so they behave identically inside an agent workspace and on a developer machine.

## Out of Scope

- Turning the dead-code and dependency checks into hard gates is deliberately a later change — this one only adds them in informational mode.
- Actually deleting any dead code the scan flags is a separate effort.
- Fixing the separate, already-known issue where one of the daemon's test gates is currently a no-op, and the cleanup of the existing weak-test backlog, are tracked as their own work items.
- If the random-order cleanup turns out to be larger than fits in one change, the remaining order-dependent tests are quarantined and tracked rather than fixed here — and, as a last resort only, randomization is added but left off by default until a follow-up flips it on.
