# I-00108 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item leaves migrations unchanged.)

## Why

The `iw doc-update` command is the only way for agents and operators to create or update a project documentation record from the command line. When the caller targets a brand-new document and forgets two of the required fields, the command currently crashes with an opaque "Database error" message and a misleading exit code. The error reads as a transient database failure, when in reality the caller simply forgot to supply two required pieces of information. This bug was surfaced by the new CLI contract test layer that shipped in the same release; the contract test pins the desired behaviour today via a strict expected-failure marker.

## What Changed (for the User)

- When a caller asks to create a brand-new documentation record but does not supply the document's automation tier and editorial category, the command now refuses the request with a clear, actionable message that names the two missing pieces of information.
- The refusal uses the exit code that callers and orchestrators reserve for "the caller made a usage mistake" — so a downstream script that distinguishes "retryable database error" from "fix your invocation and try again" now sees the correct signal.
- No documentation record is created on the rejected call. Nothing changes in the database.
- Updates to documents that already exist are not affected — the command still accepts a partial update where only the changed fields are provided.

## How It Behaves

When `iw doc-update` runs, it first looks up whether a documentation record already exists for the supplied project and document identifier:

- If a record exists, the command treats the call as an update: any fields the caller provided are applied, and everything else stays as it was. The two fields at the heart of this incident remain optional in this path.
- If no record exists, the command treats the call as a new-document creation. Creation requires the document's automation tier and editorial category. If either is missing, the command stops immediately, prints a clear message naming both fields, and returns the usage-error exit code. If both are supplied, the document is created normally and the command emits its usual success output.

The happy path for both updates and creations is unchanged. Only the new-doc-with-missing-required-fields path is improved: previously it surfaced a confusing internal type error labelled as a database failure; now it surfaces a clear usage error that tells the caller exactly what to add to their command.

## Out of Scope

- This change does not make the two fields mandatory at the parser layer. Doing so would break legitimate update calls that supply neither.
- This change does not introduce any new validation primitives or restructure the command. It is a single, narrow refusal in the new-document branch.
