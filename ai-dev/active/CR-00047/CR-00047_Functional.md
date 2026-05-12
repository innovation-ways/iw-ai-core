# CR-00047 — Functional Design

## ⛔ Docker is off-limits

Standard policy applies. This change touches no container state. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. This change adds no database migration and modifies none.

## Why

The build already measures test coverage, including the harder-to-fool branch coverage, and there is already a rule that fails the build when coverage drops too low. But that floor is set so far below the codebase's actual coverage that the suite could lose roughly a third of its coverage before the build noticed. And separately, nothing checks that *newly added or changed* lines are covered — an agent can touch a file, leave its new code untested, and no gate complains as long as the overall number stays above the very low floor. This change raises the floor to just below where coverage actually is today, writes down the rule that the floor only ratchets upward, and adds a gate that fails when new or changed lines are not well covered.

## What Changed (for the User)

For people running or reviewing work on the dashboard:

- The "overall coverage too low" gate now fails much earlier — it sits just below today's real coverage, with a small cushion, and the testing standards record that the floor is only ever raised, never lowered.
- A new "diff coverage" check runs in the daemon's per-item gate sequence (and on every pull request) and fails if the lines a change adds or modifies are not covered to a high bar (around ninety percent of changed lines). So a change that adds untested code is caught even when the overall coverage number barely moves.
- The diff-coverage gate that runs inside the daemon builds its own complete picture of coverage (both the fast tests and the slower database-backed ones) before judging the change, so it gives an honest answer regardless of how the other gates are wired.
- A small housekeeping fix to the coverage configuration ensures coverage reports line up correctly when the build runs in a temporary workspace rather than the main checkout.

For people working on the platform itself, the relevant testing standards and the testing skill that agents read before writing tests now mention both the raised floor and the new diff-coverage gate, so the expectation is explicit rather than implied.

## How It Behaves

When a change is being merged, after the test gates run, the diff-coverage gate runs the full test suite, builds a combined coverage report, asks "which lines does this change add or modify, and how many of them are covered?", and fails the change if too few are. On a pull request, an equivalent check runs against the lines the pull request changes. On a push straight to the main branch (where there is no "diff" to measure) the pull-request check simply does not run. Independently, every test run still ends by checking the overall coverage against the floor; that floor is now meaningful rather than nominal, so a change that quietly deletes a swathe of tested code, or adds a large untested module, will fail the build. Developers can run the diff-coverage check locally before pushing.

## Out of Scope

- Fixing the separate, already-known issue where one of the daemon's test gates is currently a no-op is deliberately a different work item.
- Other Phase-1 quality gates (randomised test order, secrets scanning, dead-code and dependency hygiene, reporting dashboards, the curated smoke layer) and the cleanup of the existing weak-test backlog are tracked as their own work items.
- Capturing coverage from subprocesses (the command-line tool and the daemon's child processes) is noted as a known limitation but not addressed here.
