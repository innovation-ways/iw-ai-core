# CR-00047 — Functional Design

## ⛔ Docker is off-limits

Standard policy applies. This change touches no container state. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. This change adds no database migration and modifies none.

## Why

The build already measures test coverage, including the harder-to-fool branch coverage, and a rule already fails the build when coverage drops too low. But that floor sits so far below the codebase's actual coverage that the suite could lose roughly a third of its coverage before the build noticed. Separately, nothing checks that *newly added or changed* lines are covered — an agent can touch a file, leave its new code untested, and no gate complains as long as the overall number stays above the very low floor. This change raises the floor to just below where coverage actually is today, writes down the rule that the floor only ratchets upward, and adds a gate that fails when new or changed lines are not well covered.

## What Changed (for the User)

For people running or reviewing work on the dashboard:

- The "overall coverage too low" gate now fails much earlier — it sits just below today's real coverage with a small cushion, and the standards record that the floor only ever rises, never falls.
- A new "diff coverage" check runs in the daemon's per-item gate sequence and on every pull request; it fails when the lines a change adds or modifies are not covered to a high bar (about ninety percent), so untested new code is caught even when the overall number barely moves.
- A small housekeeping fix makes coverage reports line up correctly when the build runs in a temporary workspace rather than the main checkout.
- The testing standards and the skill agents consult before writing tests now mention the raised floor and the new gate.

## How It Behaves

When a change is merged, after the test gates run, the diff-coverage gate runs the test suite, builds a combined coverage picture (the fast tests and the slower database-backed ones), and fails the change if too few of its added or modified lines are covered. On a pull request an equivalent check runs against the lines that request changes; on a push straight to main — where there is no diff — it does not run. Independently, every test run still ends by checking overall coverage against the floor, which is now meaningful: deleting a swathe of tested code, or adding a large untested module, fails the build. Developers can run the diff-coverage check locally before pushing.

## Out of Scope

- Fixing the separate, already-known issue where one of the daemon's test gates is currently a no-op is deliberately a different work item.
- Other Phase-1 quality gates (randomised test order, secrets scanning, dead-code and dependency hygiene, reporting dashboards, the curated smoke layer) and cleanup of the existing weak-test backlog are tracked as their own work items.
- Capturing coverage from subprocesses (the command-line tool and the daemon's child processes) is noted as a known limitation but not addressed here.
