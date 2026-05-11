# CR-00045 — Functional Design

## ⛔ Docker is off-limits

Standard policy applies. This change touches no container state. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. This change adds no database migration and modifies none.

## Why

Nearly every line of code in this platform — production and tests — is written by an AI agent. The backend implementation agent is told to follow test-driven development: write the test first, watch it fail, then write the code that makes it pass. But nothing checks that the test was actually run and seen to fail before the code existed. An agent can write the code first and the test afterwards, producing a test that confirms "what the code does" rather than "what it should do" — one that will never catch a regression. This change closes that gap by making the failing-test step a required, recorded, and reviewed part of backend implementation.

## What Changed (for the User)

For people who run or review work items on the dashboard:

- Every backend implementation step's report now includes a short "RED evidence" entry — the new test's name and the line showing it failing before the code was written — or, when the step legitimately adds no behavioural test, a one-line note saying so and why.
- The self-assessment step now checks that this RED evidence is present and looks genuine — a real assertion failure, not a test that was broken on its own.
- The code-review step now confirms it is there and reasons about whether each new test would actually have failed against the old code, flagging any that obviously would not.

For people working on the platform, the rules behind this — a test must be able to fail, and the failing run must be recorded — are now in the testing standards and backed by an automated check, so they can't quietly drift away.

## How It Behaves

When a backend implementation step runs, the agent first writes the new test, runs just that test (not the whole suite), and confirms it fails for the expected reason — because the behaviour doesn't exist yet, not because the test has a typo or a missing import. It records that failure, then writes the implementation, makes the test pass, and reports as before. When the step adds no new behaviour, the report says "not applicable" with a brief reason. Downstream, self-assessment and code-review treat a missing or implausible RED-evidence entry as something to flag. Dedicated coverage steps that add tests after the code already exists are exempt. A small guard test keeps the wording of these rules in the agent and template documents from being removed by accident.

## Out of Scope

- Other implementation agents (database, API, frontend, pipeline, template) are not changed by this work — the new requirement is for the backend implementation agent.
- This does not introduce mutation testing or any new tooling; that comes later in the plan.
