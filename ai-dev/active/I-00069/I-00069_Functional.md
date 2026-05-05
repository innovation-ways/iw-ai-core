# I-00069 — Functional Design

## Why

Engineers running the dashboard test suite see a scary-looking ERROR
log line plus a Python traceback at the start of nearly every run. The
condition it reports is in fact the safety guard doing its job — refusing
to let test code touch the production orchestration database — but the
output is visually indistinguishable from a real failure. This was
flagged in I-00067's self-assessment as a recurring source of confusion
during triage.

## What Changed (for the User)

- Engineers running dashboard tests no longer see an ERROR-level log
  entry plus traceback for the expected production-database refusal.
- The refusal is now reported as a single low-noise debug line under the
  test context, leaving genuine startup failures as the only ERROR
  entries in test output.
- Outside the test context, behaviour is unchanged: real boot problems
  still surface loudly, with a traceback, just as before.

## How It Behaves

When the dashboard starts up, it performs a quick check to confirm the
orchestration database schema is at the expected version. In production
or local development, this check is meaningful and any failure is logged
at ERROR. Inside the automated test environment, the same check is
deliberately blocked by a safety guard so that tests cannot accidentally
talk to the production database. After this fix, the dashboard
recognises that this specific refusal is the expected, intended outcome
under tests and demotes it to a quiet debug-level note. Any other
exception coming out of the same check is still treated as a genuine
problem and logged at the loud level, so unexpected errors remain
visible.

## Out of Scope

- Changing the safety guard itself, which already behaves correctly.
- Changing the daemon's startup probe, where a similar failure would
  still be a genuine problem and is treated as such.
