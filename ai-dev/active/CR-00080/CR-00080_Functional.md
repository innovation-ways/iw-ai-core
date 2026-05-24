# CR-00080 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change adds, modifies, or removes zero migrations.

## Why

Mutation testing — a technique that intentionally breaks one line of production code at a time and asks "did any test notice?" — was wired up earlier as a manual tool measuring only the daemon subsystem. The intent was always to widen it to the whole backend and turn it into a blocking gate. The first attempt also discovered a configuration bug: the coverage-floor check was firing before any mutated code could run, so the spike produced zero mutants and zero useful numbers. This work item fixes that bug, widens scope to the whole backend, measures real numbers in a second spike, then flips the gate from informational to blocking so a regression in test sensitivity actually fails the build.

## What Changed (for the User)

- Engineers and operators get a real mutation score for the backend instead of a "not measured yet" placeholder.
- The mutation gate is now blocking, so a change that weakens behavioural test coverage is caught automatically rather than slipping through.
- The gate runs as a nightly automated check. Per-change enforcement was considered and rejected because the measured cost is too high for a per-batch gate; a future diff-scoped optimisation could revisit that.
- A safety rail refuses to wire a meaningless threshold: if the spike produces too little signal, the gate is deliberately not wired and the operator is told what to do next.
- Tracker, strategy doc, and the testing skill are updated so anyone reading them knows the gate is on, the chosen threshold, and the ratchet rule.

## How It Behaves

After this ships, the nightly automated check runs the full mutation audit against the backend and compares the measured mutation score to a threshold set a few points below the original spike measurement (mirroring the diff-coverage ratchet pattern already in use). If a future change deletes a test, weakens an assertion, or adds untested branches, the surviving-mutant count rises, the mutation score drops, and the nightly check fails. Engineers see a clear failure with a pointer to the audit output so they can identify the surviving mutant and add the missing assertion.

The threshold is documented as a ratchet — once an item lifts the score above the floor for a sustained period, the floor is raised so quality only moves in one direction.

## Out of Scope

- Production code changes. Only test-tooling configuration, gate wiring, documentation, and tracker entries change.
- Adding new tests to chase a higher mutation score. The score this change measures is the score we have; future work items lift it.
- Mutation testing for the dashboard, executor, or CLI layers. This change widens scope from the daemon to the whole backend orchestration package only; broader scope is a future follow-up.
