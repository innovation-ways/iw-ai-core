# CR-00049 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
DO NOT include file paths, class names, SQL, code fences, or implementation
steps. If you need to capture those, they belong in the technical design doc.
Keep the total body at most 500 words (the review skill blocks >500).
-->

## ⛔ Docker is off-limits

Standard policy. This work only touches tests, configuration, and documentation — no Docker changes.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work does not add, modify, or remove any database migrations.

## Why

The previous test-hygiene change shipped with a temporary fallback: the new test-order randomisation feature was installed but left switched off by default, because turning it on surfaced around fifty hidden failures the fallback agent could not resolve in time. The open follow-up was filed alongside it. This change finishes that cleanup — switching randomisation on by default so every future test run automatically shakes out hidden ordering bugs.

## What Changed (for the User)

- Test runs (locally and in the platform's per-item quality gates) now print a random seed at the top and execute test files in a different order every time, instead of always running them alphabetically.
- A small number of pre-existing tests that genuinely depend on running in a particular order are now openly marked as "order-dependent" and are allowed to be skipped under random order without failing the build. They were already broken under random order — they are now tracked rather than silently hidden.
- The internal testing notes, the testing strategy document, and the testing skill have been refreshed: the previous "switched off" notes become historical context, and the current state is "switched on by default, here is how to reproduce a failing seed."
- The follow-up entry tracking this cleanup is marked Done with counts of how many tests were repaired versus quarantined.

## How It Behaves

- A developer running local test commands gets a slightly different test order each run. The seed is printed up front and can be replayed by passing it back in.
- The platform's daemon exercises randomisation automatically when it runs the per-item gates. If a future change introduces a hidden ordering bug, it gets caught at gate time, not weeks later.
- Someone investigating a flake can ask for the old deterministic order on the command line for a single run — but the project default is randomised.
- Quarantined tests keep running under their original order; they are only skipped when a random seed would reshuffle them into a broken state, and they remain visible in the enhancement plan as smaller follow-ups.

## Out of Scope

- Eliminating every quarantine. Some tests are entangled with shared fixtures and need a larger refactor; those stay quarantined and listed as smaller follow-ups.
- Fixing the empty integration-tests gate — tracked separately and not blocking.
- Porting this change to sibling projects — each picks it up on its own next sync.
