# CR-00050 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
DO NOT include file paths, class names, SQL, code fences, or implementation
steps. If you need to capture those, they belong in the technical design doc.
Keep the total body at most 500 words (the review skill blocks >500).
-->

## ⛔ Docker is off-limits

Standard policy. This work only touches configuration and documentation.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work does not add, modify, or remove any database migrations.

## Why

The project has dependency-vulnerability, Python-specific code, and infrastructure-config scanners — but **no secret scanner**. A contributor could accidentally commit a credential and nothing would catch it. There is also a placeholder for a broader static-analysis tool that does nothing today. This work adds secret scanning as a blocking gate on three surfaces and wires up the static-analysis tool in informational mode until we know its noise level.

## What Changed (for the User)

- A contributor who tries to commit a credential-shaped string — API key, password, internal email, private hostname — is stopped at commit time with a pointer to what was found.
- The continuous-integration workflow runs a secret scan on every push and pull request; results show in the security-findings view.
- The per-item merge pipeline includes a secret-scan gate as its eighth quality check, so anything the platform merges is automatically verified clean.
- The broader static-analysis tool runs on every change, surfacing findings without blocking merges yet — a follow-up flips it to blocking once the noise is triaged.
- The pre-existing findings on main — mostly example values in test fixtures — have been catalogued with a one-line note for each. Real-looking secrets, if any, are escalated rather than silently ignored.

## How It Behaves

- A developer's pre-commit hook gives immediate feedback on credential-shaped pastes. They investigate, rotate if real, or update the allowlist with a note if it's a known false positive.
- The continuous-integration secret-scan job runs on every push, pull request, and the existing weekly schedule. Findings upload to the security view; on private repositories that upload is automatically skipped until the repo is public — mirroring how the existing infrastructure-config scan handles the same caveat.
- The per-item merge pipeline runs the secret scan as its eighth gate. A work item with a leak cannot merge.
- The static-analysis tool runs on the same triggers with errors marked non-blocking. Findings appear in the security view but do not gate merges yet.

## Out of Scope

- Custom static-analysis rules — start with managed rule sets; add custom only if a pattern repeats.
- Container image scanning — no production image is built today.
- Rotating any genuinely-real secrets the initial scan finds — escalated as a separate incident-response action.
- Porting the new merge-gate to sibling projects — each picks it up on its own next sync.
