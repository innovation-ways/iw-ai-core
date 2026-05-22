# CR-00073 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures used by automated tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds no database change and no migration.

## Why

The command-line tool that agents use to record results, allocate identifiers,
and register work is the platform's most critical bridge — every agent call
passes through it. Today there is no systematic check that each command does
exactly what its documentation says: the right exit code, the right output, the
right database effect. Gaps between what the tool actually does and what its
specification claims go undetected until a human notices. This
work closes both gaps — a per-command check that the contract holds, and a check
that the tool and its specification stay in sync.

## What Changed (for the User)

- The build now automatically verifies that each high-priority command exits
  with the correct code, prints the expected output, and writes exactly the
  expected data. A regression in any of these fails the build and names the
  command that broke.
- A new check detects when a command exists in the tool but is missing from the
  specification, or is in the specification but has been silently removed from
  the tool. Both directions of drift are caught automatically.
- Any pre-existing drift found when this work ships is recorded in a visible,
  auditable list with an explanatory note, so it is not lost. From then on, only
  new drift triggers a failure.
- Reviewers get earlier, clearer signals: a contract regression is named by the
  exact command and assertion that failed, not discovered later as a confusing
  agent failure in the field.
- No visible change to the tool itself — this is purely a safety net; behaviour
  does not change.

## How It Behaves

- On every work item and pull request, the contract tests load a fresh isolated
  test database, then exercise each high-priority command in turn. A command
  that exits with the wrong code, prints unexpected output, or leaves the
  database in a different state than its documentation promises fails the build
  immediately, naming the failing command.
- A separate check reads the specification and the tool's actual command list
  and compares them. Any command present in one but not the other is reported.
  Commands already flagged as known discrepancies — each with a tracking note —
  are skipped, so only newly introduced gaps raise an alert.
- For the identifier-allocation command, the check also verifies that
  simultaneous calls never produce duplicate identifiers — a property hard to
  test manually but critical for correctness.
- If a contract test surfaces a real bug in the tool, the bug is recorded as a
  separate tracking ticket and the test is marked as a known expected failure
  until it is fixed, keeping the safety net honest without forcing unrelated
  fixes into this change.

## Out of Scope

- Fixing any CLI bug the new tests discover — those are tracked separately as
  their own tickets.
- Adding contract coverage for every command in the tool in this change —
  priority commands are covered first; additional commands are follow-up work.
