# CR-00054 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds no migrations and changes no database schema.

## Why

The Dashboard AI Assistant feature (F-00083) ships a chat panel backed by an OpenCode runtime. When the platform runs automated browser tests of that chat panel inside its per-feature isolated test environment, the environment does not include the OpenCode runtime — so the chat endpoint reports "OpenCode runtime unavailable" and the browser test cannot run. This CR adds a lightweight stand-in for the OpenCode runtime inside the test environment so future chat-related browser tests can actually exercise the chat UI from end to end.

## What Changed (for the User)

- Operators no longer have to manually skip the browser-verification step for chat-related work items because the underlying environment is "missing OpenCode" — the test environment now provides a stand-in.
- The dashboard inside the per-feature test environment becomes "ready" only once the chat endpoint also reports healthy, so flaky pre-flight failures disappear.
- The production dashboard behaviour is unchanged. End users browsing the real dashboard see exactly the same chat experience as before; they never interact with the stand-in.

## How It Behaves

- When the platform spins up a per-feature test environment, the dashboard inside it now has a small stand-in service available on its private network.
- The stand-in answers the same questions the real OpenCode runtime answers — what models are available, what sessions exist, what messages are in a session, what is happening right now on the live event stream.
- When the test sends a prompt through the chat UI, the stand-in produces a predictable, scripted reply: a short streamed message, a synthetic "the assistant wants permission to run a command" prompt, and a closing "I'm idle" signal. Tests can therefore reliably exercise the approval modal, the streaming UI, and the abort path without depending on a real language model.
- When the test closes or reloads its browser tab, the stand-in remembers the most recent events long enough for the chat UI's reconnect logic to catch up.
- If any future work needs richer agent behaviour than the stand-in offers, the testing strategy document explains how to extend its scripted reply set.

## Out of Scope

- This work does not change the production OpenCode integration, the chat router endpoints, the chat panel templates, or any of the existing chat tests at the code level.
- The stand-in is not a substitute for a real OpenCode runtime in any non-test environment. It exists only inside the platform's automated browser-verification environment.
