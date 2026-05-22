# CR-00075 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures used by automated tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds no database change and no migration.

## Why

The project already runs security scanners over code and secrets — but their output is advisory; they are not asserted tests that fail a build. A previous outage (incident I-00041) was caused by a safety guard that silently stopped working, and nothing in the test suite pinned it. Other classes of security risk — unauthorized access to protected pages, the document system reading files it should refuse, a safety switch being bypassed — also have no regression net. This work creates one: an organised package of asserted security tests that fail the build when a protection breaks.

## What Changed (for the User)

- A new set of asserted security tests now runs automatically on every change alongside the existing integration tests. If a safety guard stops working or a protected endpoint starts leaking data, the build fails immediately — not after a human notices something is wrong.
- Operators and reviewers get a clear signal: a security regression is named by the exact failing test and the exact protection that broke.
- A new convenience command makes it easy to run only the security tests in isolation during development, without touching the existing scanner commands.
- No visible change to the dashboard or any user-facing behaviour — this is purely a safety net. Nothing about how pages look or behave changes.

## How It Behaves

- On every work item and pull request, the security tests run as part of the normal integration-test suite against a fresh isolated test database. A protection that no longer fires causes a test to fail and names the broken guard.
- If a security test discovers a genuine vulnerability that has no fix yet — a real path that bypasses a guard — the test is written as a documented reproduction, marked as an expected failure with a tracking ticket, and flagged to the operator as a blocker. The fix is a separate tracked ticket, so the safety net stays honest without forcing unrelated fixes into this change.
- The live-DB safety guard is tested by simulating what a live-database connection URL looks like, never by actually connecting to the live database — so the test itself cannot trigger the outage it guards against.
- Authorization tests send requests deliberately missing or mismatching credentials and assert the response is a refusal, never data and never a server error.
- Document-render tests feed the pipeline deliberately malicious inputs and assert the pipeline refuses to act on them.
- Agent-context tests assert that the flag that restricts agents from running operator-only commands is effective and cannot be trivially bypassed.

## Out of Scope

- Fixing any vulnerability the tests discover — those are tracked as separate high-priority tickets.
- Changing how the existing scanner commands work or what they report — the new asserted tests are a different mechanism running alongside the scanners, not a replacement.
