# CR-00093_S02_CodeReview_prompt

**Work Item**: CR-00093 -- Register all test-enhancement Makefile suites as launchable dashboard cards
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker commands that change container/volume/network state. Testcontainers from pytest fixtures and read-only introspection are the only exceptions. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds NO migration. If the diff includes any file under `orch/db/migrations/versions/**`, that is a CRITICAL scope-creep finding.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00093 --json`.
- `ai-dev/active/CR-00093/CR-00093_CR_Design.md` — Design document (especially AC1–AC7, Impact Analysis, Notes).
- `ai-dev/work/CR-00093/reports/CR-00093_S01_Backend_report.md` — S01's report.
- `.iw-orch.json` (modified) and `ai-dev/work/TESTS_ENHANCEMENT.md` (modified).
- `Makefile` — for cross-checking the `command` field of every new category.

## Output Files

- `ai-dev/work/CR-00093/reports/CR-00093_S02_CodeReview_report.md`.

## Context

You are reviewing S01's edit to `.iw-orch.json` + tracker. The CR is config-only — no Python edits expected. The review focuses on JSON shape conformance, completeness of the 30 new entries, Makefile-target existence, `e2e_stack` scoping, and the absence of unintended changes to existing 7 entries.

## Read the Design Document FIRST

Specifically:
- AC1–AC7 — each is a mandatory check, exercised below.
- Notes → heavy-suite labels live in the description field, not the label prefix.
- Notes → sibling projects out of scope.
- Impacted Paths — exactly two files (plus implicit `ai-dev/active/CR-00093/**` and `ai-dev/work/CR-00093/**`).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

The CR touches no Python; both should pass without movement.

## Scope Discipline — Implicitly Allowed Paths

`ai-dev/active/CR-00093/**`, `ai-dev/archive/CR-00093/**`, `ai-dev/work/CR-00093/**` are NOT scope creep.

### Directional scope diff

```bash
git diff main...HEAD --name-only
git status -s
```

Expected list (besides implicit allows): exactly `.iw-orch.json` and `ai-dev/work/TESTS_ENHANCEMENT.md`. ANYTHING else → CRITICAL. Specifically:
- No file under `orch/db/migrations/versions/` → required.
- No file under `dashboard/` or `orch/` → required (no Python edit needed for this CR).
- No file under `tests/` → required (no new tests).
- No file under `Makefile` → required (every target already exists).

## Review Checklist

### 1. JSON parses + counts (AC1, AC2)

```bash
python -c "
import json
d = json.load(open('.iw-orch.json'))
t = d['test_config']['categories']
q = d['quality_config']['categories']
print(f'test_config.categories: {len(t)} ({sorted(t.keys())})')
print(f'quality_config.categories: {len(q)} ({sorted(q.keys())})')
assert len(t) == 24, f'expected 24 test categories, got {len(t)}'
assert len(q) == 13, f'expected 13 quality categories, got {len(q)}'
"
```

Wrong count → CRITICAL. JSON parse failure → CRITICAL.

### 2. Existing entries byte-identical (AC5)

```bash
# Compare every existing entry's fields against main.
git show main:.iw-orch.json | python -c "
import json, sys
old = json.load(sys.stdin)['test_config']['categories']
new = json.load(open('.iw-orch.json'))['test_config']['categories']
for k in ('unit', 'integration', 'all'):
    assert old[k] == new[k], f'{k} test entry mutated:\n  old={old[k]}\n  new={new[k]}'
print('test_config existing 3 entries: byte-identical')
"
git show main:.iw-orch.json | python -c "
import json, sys
old = json.load(sys.stdin)['quality_config']['categories']
new = json.load(open('.iw-orch.json'))['quality_config']['categories']
for k in ('lint', 'format', 'typecheck', 'all-quality'):
    assert old[k] == new[k], f'{k} quality entry mutated:\n  old={old[k]}\n  new={new[k]}'
print('quality_config existing 4 entries: byte-identical')
"
```

Any mutation of an existing entry → CRITICAL.

### 3. Every new category references a real Makefile target (AC3)

```bash
python -c "
import json, re
d = json.load(open('.iw-orch.json'))
all_cats = list(d['test_config']['categories'].items()) + list(d['quality_config']['categories'].items())
makefile = open('Makefile').read()
missing = []
for name, cfg in all_cats:
    cmd = cfg['command']
    # Extract 'make <target>' invocations
    targets = re.findall(r'^make\s+(\S+)', cmd) or re.findall(r'\bmake\s+(\S+)', cmd)
    for t in targets:
        if not re.search(rf'^{re.escape(t)}:', makefile, re.MULTILINE):
            missing.append((name, t))
    # Some commands are direct (uv run pytest ...) — skip them.
if missing:
    print(f'MISSING TARGETS: {missing}')
else:
    print('All Makefile targets present.')
"
```

Any missing target → CRITICAL.

### 4. `e2e_stack` flag scoping (AC4)

```bash
python -c "
import json
d = json.load(open('.iw-orch.json'))
t = d['test_config']['categories']
q = d['quality_config']['categories']
e2e_in_test = sorted([n for n, c in t.items() if c.get('e2e_stack')])
e2e_in_quality = [n for n, c in q.items() if c.get('e2e_stack')]
assert e2e_in_test == ['e2e', 'e2e-smoke'], f'unexpected: {e2e_in_test}'
assert e2e_in_quality == [], f'e2e_stack on quality category: {e2e_in_quality}'
print('e2e_stack correctly scoped to test_config: e2e + e2e-smoke')
"
```

Wrong scope → CRITICAL.

### 5. Required fields present on every new entry

```bash
python -c "
import json
d = json.load(open('.iw-orch.json'))
for block in ('test_config', 'quality_config'):
    for name, cfg in d[block]['categories'].items():
        for field in ('label', 'command', 'description', 'group'):
            assert field in cfg, f'{block}.{name}: missing {field}'
print('All required fields present.')
"
```

Missing field → CRITICAL.

### 6. Group taxonomy (AC scope)

Confirm the new entries use exactly these groups (no typos, no surprises):
- Test groups: `backend` (11 new), `quality` (1 new), `e2e` (2 new), `perf` (4 new), `chaos` (2 new), `visual` (1 new). Plus existing `backend` (unit, integration) and `suites` (all).
- Quality groups: `docs` (1 new), `security` (3 new), `coverage` (3 new), `hygiene` (2 new). Plus existing `style` (lint, format, typecheck) and `suites` (all-quality).

Any unexpected group name → MEDIUM_FIXABLE (rename to a canonical group).

### 7. `bundle` flag scoping

Only the existing `all` and `all-quality` should have `bundle: true`. Spot-check no new entry carries it.

```bash
python -c "
import json
d = json.load(open('.iw-orch.json'))
bundles = []
for block in ('test_config', 'quality_config'):
    for name, cfg in d[block]['categories'].items():
        if cfg.get('bundle'):
            bundles.append(f'{block}.{name}')
assert sorted(bundles) == ['quality_config.all-quality', 'test_config.all'], f'unexpected bundles: {bundles}'
print('bundle scoped to: all + all-quality')
"
```

### 8. Tracker entries (AC6)

- `ai-dev/work/TESTS_ENHANCEMENT.md` §8: new row added (item 4.9 or similar) referencing CR-00093 + DONE + 2026-05-28.
- §11: new top changelog entry dated 2026-05-28 mentioning CR-00093, 21 test + 9 quality categories, e2e_stack scope, daemon-reload operator note.
- Header version bumped (v1.8 → v1.9).

Missing → HIGH (MEDIUM_FIXABLE if present but wording diverges materially from design).

### 9. Heavy-suite labels carry wall-clock hint

Spot-check `mutation-audit` and `daemon-chaos-full`:
- The wall-clock hint (`~1h`, `~minutes`) appears in either the `label` field or the `description` field (design Notes allow either; description is preferred).
- `description` mentions intended cadence (`nightly CI`, `nightly-class`).

Missing hint → MEDIUM_FIXABLE.

## Test Verification (NON-NEGOTIABLE)

Run the dashboard-route-contract sweep to confirm no regression on the Tests / Quality pages:

```bash
uv run pytest tests/dashboard/test_route_contract_sweep.py -v --no-cov
```

Any failure → CRITICAL.

## Severity Levels

Standard (CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW).

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00093",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
