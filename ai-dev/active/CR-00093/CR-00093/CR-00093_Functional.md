# CR-00093 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This work item adds NO migration. The dashboard launcher reads its category list from a per-project config file at the project root; only the contents of that file change.

## Why

A multi-phase initiative shipped over twenty new test suites and quality gates — smoke, end-to-end browser journeys, property-based tests, performance budgets, daemon chaos scenarios, visual regression, mutation analysis, secret scanning, dead-code checks, and several more. Each one works correctly from the command line and runs automatically in continuous integration, but none of them appear on the dashboard's Tests and Quality launcher pages. An operator who wants to trigger a one-off run has to shell into the project root and type the right command instead of clicking a button. This work item closes that last-mile gap so every suite the team built becomes discoverable and launchable from the browser.

## What Changed (for the User)

- The Tests page now shows twenty-one new launcher cards organised into clear groups: backend suites (smoke, properties, quarantine, flake detection, CLI contract, cross-project isolation, security module, data-layer, route sweep, contract fuzz), browser end-to-end (smoke and full), performance (overall plus per-area splits for daemon, retrieval, and dashboard routes), chaos (smoke and full), visual regression, and assertion-quality. The existing unit, integration, and "run all" cards stay where they were.
- The Quality page gains nine new cards across four new groups: documentation (column-doc coverage), security (secret scanner, static-analysis, dependency audit), coverage (diff coverage, mutation check, full mutation audit), and hygiene (dead-code finder, dependency-cleanliness check). The existing lint, format, type-check, and "run all quality" cards stay where they were.
- The two longest-running suites — full mutation audit and full daemon chaos — carry a wall-clock hint in their description so the operator knows what to expect before clicking.
- The two end-to-end browser suites are mutually exclusive: launching one while the other is running surfaces a warning rather than colliding on the shared browser-test ports.
- For every new card, clicking it produces a run row in the Runs tab and (where the suite produces them) results in the Results tab — the same experience as the existing cards.

## How It Behaves

When an operator opens the dashboard, picks a project, and goes to the Tests or Quality page, they see every suite the project supports — grouped by area, each with a short description. Clicking a card starts a background run, surfaces a live log, and records the outcome in the Runs tab. If two end-to-end browser suites are launched in quick succession, the second shows a warning that the browser-test stack is already in use. For long-running suites the description tells the operator up-front roughly how long to expect. Everything that worked before continues to work exactly as before; the change is purely additive.

## Out of Scope

- Other managed projects (the shared dashboard reads each project's own config; siblings can adopt the pattern when ready).
- Promoting any new gate to "blocks every pull request" status — a separate per-gate decision that lives in other work items.
