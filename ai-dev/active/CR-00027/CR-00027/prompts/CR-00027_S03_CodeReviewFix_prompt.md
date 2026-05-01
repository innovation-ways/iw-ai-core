# CR-00027 — S03: Code Review Fix

## Context

You are fixing CRITICAL and HIGH findings from the S02 code review of CR-00027: Dashboard Sidebar Nav — Collapsible Section Headers.

Read the S02 review report from the item's report artifacts before starting.

The only file changed in this CR is `dashboard/templates/base.html`. After any fix, run `make css` to regenerate `dashboard/static/styles.css`, then run `make lint` to verify no lint errors.

Architecture reference: `CLAUDE.md` and `dashboard/CLAUDE.md`.

## Instructions

1. Read the S02 code review findings
2. For each CRITICAL or HIGH finding, apply the minimal fix to `dashboard/templates/base.html`
3. Re-run `make css` after template changes
4. Re-run `make lint` and confirm it passes
5. Do NOT fix MEDIUM/LOW/INFO findings unless they are trivially safe
6. Do NOT refactor beyond what is needed to address the finding

If there are no CRITICAL or HIGH findings, state "No fixes required" and exit.
