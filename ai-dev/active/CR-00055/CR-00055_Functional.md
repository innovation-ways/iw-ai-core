# CR-00055 — Functional Design

## ⛔ Docker is off-limits

Standard policy. The only Docker involved is the existing PostgreSQL testcontainer pytest already spins up; no new container management is introduced.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work touches no Alembic migrations.

## Why

The test suite runs in deterministic alphabetical order today, which hides test-order bugs — tests that accidentally depend on leftovers from earlier tests. The industry-standard fix is to randomise order on every run, but the first attempt (CR-00048) had to ship with randomisation off because the integration suite revealed too many leaks, and the second (CR-00049) was cancelled when the obvious fix (resetting the DB between every test) made the suite 3× slower. This work re-enables randomisation by default using a faster isolation technique that does not regress wall-clock.

## What Changed (for the User)

For anyone running the test suite (developers, daemon quality gates, GitHub Actions):

- Every `pytest` run now prints `Using --randomly-seed=<N>` at the top. Order is shuffled deterministically by that seed.
- If a test fails, the seed reproduces the exact failure: `pytest --randomly-seed=<N> ...`.
- Tests that fail only when randomised have been order-dependent all along — the team now finds these early instead of mysteriously months later.
- The `make test-integration` suite stays at roughly today's wall-clock (within about a minute).
- Three integration tests are temporarily quarantined as "known order-dependent"; they still run but their failure under random order doesn't break the build, and they're flagged for cleanup.

For agents and operators reading documentation, the four places that previously described `pytest-randomly` as "currently off-by-default" now describe it as "default-on" with reproduce and disable recipes.

## How It Behaves

Every test in the integration layer gets its own fresh, fully-migrated PostgreSQL database — created in ~25 ms via PostgreSQL's native database-cloning, used, then dropped. Nothing one test does can leak into another. Even when a test shells out to the `iw` command-line, the subprocess inherits the per-test database via environment variables and writes there, not into shared state.

Three migration round-trip tests are left as "known order-dependent" because they intentionally mutate schema state in ways per-test isolation cannot reach (they share a module-scoped database for performance). They pass in alphabetical order; under randomisation they may fail, and that failure is recorded as expected rather than blocking the build. A follow-up will eliminate the quarantine.

To reproduce a seeded run, pass the seed back: `pytest --randomly-seed=<N>`. To disable randomisation for one-off triage: prefix with `-p no:randomly`. Neither is needed day-to-day.

## Out of Scope

- Fixing the three quarantined tests at their root (scoping their shared database down to per-test). That is a follow-up; the quarantines are temporary.
- Re-enabling `pytest-randomly` for any other repo. This work only flips the iw-ai-core test suite.
