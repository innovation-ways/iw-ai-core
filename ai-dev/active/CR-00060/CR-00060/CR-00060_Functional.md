# CR-00060 — Functional Design

## ⛔ Docker is off-limits

Standard policy. The one property test that needs a database reuses the existing test-container fixture; no new container management.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change adds, modifies, and removes no migrations.

## Why

The platform's most important lifecycles — what state a work item can move to, when a batch is complete, how many retry attempts are allowed, whether parsing a document and writing it back yields the same document, and whether two callers asking for the next ID at the same instant can ever get the same number — are today guarded only by example-based tests written by the same automated agent that wrote the implementation. Those tests prove the system behaves correctly on a handful of cases the author thought of; they do not prove the system behaves correctly across the space of cases nobody thought of. Property-based testing systematically explores that space and shrinks any failure down to the smallest input that reproduces it. This is the cheapest way to insure against a class of bugs we cannot easily write example tests for.

## What Changed (for the User)

Five new property-test modules now run as part of the normal merge gate, exercising the work-item lifecycle, the batch lifecycle, the retry-cap enforcement, the document parser round-trip, and the next-ID allocator. Three preset levels of thoroughness are configurable per run: a fast one used in the merge gate, a medium one used by developers locally, and a deep one available on demand for nightly or pre-release sweeps. Two new commands run the property tests at the medium and deep levels respectively. The existing test commands and the existing tests are unchanged. The testing strategy document and the agent-facing testing skill are updated to explain when and how to add new property tests; the enhancement plan and changelog record the change.

## How It Behaves

A developer working on any of the five guarded areas runs the test suite normally; the property tests are included alongside the example tests, using the fast preset by default. Each property test exercises its target across many auto-generated inputs and asserts an invariant — "a merged work item never moves back to in-progress", "no two concurrent ID allocations return the same number", "parsing a document and writing it back returns the same document". A failure is reported with the auto-shrunk smallest example that reproduces it, making bugs straightforward to file and fix. Developers wanting more thorough exploration can opt into the medium preset locally, or invoke the deep preset on-demand. The merge gate uses the fast preset with deterministic seeding, so failures are reproducible and not flaky. The deep preset is intentionally allowed to find bugs the fast preset misses — the value-add over example tests.

## Out of Scope

Wiring the deep preset into a scheduled nightly job, and adding property tests beyond the five named state-machine targets (e.g. for the RAG chunker or the staleness scoring), are explicitly deferred. Fixing any bug the deep preset surfaces during this change is also deferred to a separately filed incident — the property tests themselves go in cleanly first.
