# CR-00045 — Functional Design

## ⛔ Docker is off-limits

Standard policy applies. This change touches no container state. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. This change adds no database migration and modifies none.

## Why

Nearly every line of code in this platform — production and tests — is written by an AI agent. The backend implementation agent is told to follow test-driven development: write the test first, watch it fail, then write the code that makes it pass. But nothing actually checks that the test was run and seen to fail before the code existed. In practice an agent can write the code first and the test afterwards, producing a test that confirms "what the code does" rather than "what it should do" — a test that will never catch a regression. This change closes that gap by making the failing-test step a required, recorded, and reviewed part of every backend implementation, as the final piece of the testing-enhancement effort's first phase.

## What Changed (for the User)

For people who run or review work items on the dashboard:

- Every backend implementation step's report now includes a short "RED evidence" entry — the name of the new test and the line showing it failing before the code was written — or, when the step legitimately adds no behavioural test (a pure refactor, a config or documentation change), a one-line note saying so and why.
- The self-assessment step now checks that this RED evidence is present and looks genuine (a real assertion failure, not a test that was broken on its own).
- The code-review step now confirms the RED evidence is there and reasons about whether each new test would actually have failed against the old code, flagging any that obviously would not.

For people working on the platform itself, the rules behind this — that a test must be able to fail, and that the failing run must be recorded — are written into the testing standards and are now backed by a small automated check, so they cannot quietly drift away.

## How It Behaves

When a backend implementation step runs, the agent first writes the new test, runs just that test (not the whole suite), and confirms it fails for the expected reason — because the behaviour does not exist yet, not because the test itself has a typo or a missing import. It records that failure in its report. Then it writes the implementation, makes the test pass, and reports as before. When the step is not the kind that adds new behaviour, the report says "not applicable" with a brief reason instead. Downstream, self-assessment and code-review treat a missing or implausible RED-evidence entry as something to flag. A small guard test keeps the wording of these rules in the agent and template documents from being removed by accident.

## Out of Scope

- Other implementation agents (database, API, frontend, pipeline, template) are not changed by this work — the new requirement is for the backend implementation agent.
- This does not introduce mutation testing or any new tooling; that comes later in the plan.
