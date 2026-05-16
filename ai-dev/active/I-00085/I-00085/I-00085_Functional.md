# I-00085 — Functional Design

## ⛔ Docker is off-limits

Standard policy. No Docker usage.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migration impact.

## Why

A secret-scanner gate that runs as part of the quality checks reports
false alarms on cached files left behind by an earlier gate (the
type-check). This makes operators second-guess every secret-scan failure
and, more importantly, would block any work item whose run order is the
same as the standard sequence. CR-00053 hit this on its first manual
secret-scan attempt.

## What Changed (for the User)

- The secret-scan gate no longer flags cached tool data left behind by
  the type-check gate or other tool runs.
- Operators can run the standard gate sequence end-to-end without
  needing to clean cache directories between gates.
- Real secret detection is unaffected — a regression test pins this so
  the allowlist addition cannot accidentally hide a real secret.

## How It Behaves

The secret-scanner now ignores three additional cache directories
(`.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`). It already ignores
`__pycache__/` for the same reason. None of these directories are
checked into the repository, so excluding them from a working-tree scan
is consistent with their gitignored status.

If a real secret ever appears in the repository, the scanner still
reports it.

## Out of Scope

- This work does not change the secret-scanner's ruleset, threshold, or
  the gate's place in the standard sequence.
- This work does not address the broader question of gate ordering or
  cache cleanup; it is a targeted fix for one observed false-positive
  source.
