# I-00111 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This change leaves migrations unchanged — no schema change involved.)

## Why

The dashboard exposes a machine-readable description of its own HTTP API so that the built-in interactive API browser, automated contract-checking tools, and any externally-generated client libraries can understand what endpoints exist and how to call them. Today that description page returns an error: anyone opening it in a browser, or any tool that fetches it, gets a server failure instead of a usable document. The breakage was discovered while wiring up a new nightly contract-checking job; that job had to install a temporary workaround to make any progress at all, and this work removes the underlying defect so the workaround can come out.

## What Changed (for the User)

- Opening the dashboard's API description URL now returns a complete, well-formed document instead of a server error.
- The dashboard's built-in interactive API browser page now loads and lists every endpoint, instead of showing an empty or error state.
- The nightly contract-fuzzing job now exercises the whole real API surface instead of a hand-filtered subset, so any new endpoint with the same class of defect is caught automatically.
- No user-visible change to any existing endpoint behaviour — only the description page and the interactive browser are affected. The fix is intentionally tiny so nothing else moves.

## How It Behaves

After this work ships, a fresh dashboard boot serves a valid API description on the first request and on every subsequent request, with no warm-up needed and no errors in the server logs. Tools that consume that description (the interactive browser, the nightly contract-fuzz job, and any externally-generated client library) get a complete picture of the API and can proceed normally. A new automated regression test asserts that the description endpoint returns a valid document with at least one route listed; if a future change ever re-introduces the same class of defect, the test fails before the change can land. The change is constrained to fixing the description-generation defect — no endpoint contracts, response shapes, or behaviours change, and the interactive browser presents the same content it always intended to.

## Out of Scope

- Adding or changing any actual API endpoint behaviour, response shape, or authentication.
- Expanding which endpoints the nightly contract-fuzz job targets — the allow-list of fuzzed endpoints is unchanged; only the underlying schema-loading path is restored.
