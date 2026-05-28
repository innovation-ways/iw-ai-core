# CR-00093_S03_CodeReview_Final_prompt

**Work Item**: CR-00093 -- Register all test-enhancement Makefile suites as launchable dashboard cards
**Review Step**: S03 (Final Review)
**Implementation Steps Reviewed**: S01..S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker commands that change container/volume/network state. Testcontainers from pytest fixtures and read-only introspection are the only exceptions. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds NO migration. If the diff includes any file under `orch/db/migrations/versions/**`, that is a CRITICAL scope-creep finding.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00093 --json`.
- `ai-dev/active/CR-00093/CR-00093_CR_Design.md` — Design document (AC1–AC7 are the spine of this review).
- `ai-dev/work/CR-00093/reports/CR-00093_S01_Backend_report.md` — implementation report.
- `ai-dev/work/CR-00093/reports/CR-00093_S02_CodeReview_report.md` — per-agent review.
- `.iw-orch.json` and `ai-dev/work/TESTS_ENHANCEMENT.md` (the two modified files).

## Output Files

- `ai-dev/work/CR-00093/reports/CR-00093_S03_CodeReview_Final_report.md`.

## Context

Holistic cross-step review of the registry edit. S02 covered local correctness; S03 mechanically executes every AC and confirms the cross-step picture (S01 numeric anchors match S02's review).

## Read the Design Document FIRST

Specifically:
- AC1–AC7 — execute each mechanically.
- Impacted Paths = exactly 2 files.
- Notes — daemon-reload is operator's responsibility post-merge; the S11 qv-browser step runs against the isolated E2E stack so it sees the new cards without a SIGHUP.

## Pre-Review Lint & Format Gate

```bash
make lint
make format
```

## Scope Discipline — Implicitly Allowed Paths

`ai-dev/active/CR-00093/**`, `ai-dev/archive/CR-00093/**`, `ai-dev/work/CR-00093/**` are NOT scope creep.

### Directional scope diff

```bash
git diff main...HEAD --name-only
git status -s
```

Expected list (besides implicit allows): `.iw-orch.json`, `ai-dev/work/TESTS_ENHANCEMENT.md`. Anything else → CRITICAL.

## AC Execution Checklist

Execute every AC mechanically. Record commands and outputs verbatim in the report.

### AC1: test category count = 24

```bash
python -c "import json; print(len(json.load(open('.iw-orch.json'))['test_config']['categories']))"
```
Expected: `24`.

### AC2: quality category count = 13

```bash
python -c "import json; print(len(json.load(open('.iw-orch.json'))['quality_config']['categories']))"
```
Expected: `13`.

### AC3: every new category references a real Makefile target

```bash
python -c "
import json, re
d = json.load(open('.iw-orch.json'))
mf = open('Makefile').read()
missing = []
for block in ('test_config', 'quality_config'):
    for name, cfg in d[block]['categories'].items():
        m = re.match(r'^make\s+(\S+)', cfg['command'])
        if m and not re.search(rf'^{re.escape(m.group(1))}:', mf, re.MULTILINE):
            missing.append((block, name, m.group(1)))
if missing:
    print(f'MISSING: {missing}')
else:
    print('All make targets exist.')
"
```
Expected: `All make targets exist.` Any missing → CRITICAL.

### AC4: e2e_stack scoped correctly

```bash
python -c "
import json
d = json.load(open('.iw-orch.json'))
t_e2e = sorted([n for n, c in d['test_config']['categories'].items() if c.get('e2e_stack')])
q_e2e = [n for n, c in d['quality_config']['categories'].items() if c.get('e2e_stack')]
print(f'test_config e2e_stack: {t_e2e}')
print(f'quality_config e2e_stack: {q_e2e}')
assert t_e2e == ['e2e', 'e2e-smoke']
assert q_e2e == []
"
```

### AC5: existing entries byte-identical

```bash
python -c "
import json, subprocess
old = json.loads(subprocess.check_output(['git', 'show', 'main:.iw-orch.json']))
new = json.load(open('.iw-orch.json'))
for k in ('unit', 'integration', 'all'):
    assert old['test_config']['categories'][k] == new['test_config']['categories'][k], f'{k}: mutated'
for k in ('lint', 'format', 'typecheck', 'all-quality'):
    assert old['quality_config']['categories'][k] == new['quality_config']['categories'][k], f'{k}: mutated'
print('All 7 existing entries: byte-identical.')
"
```

### AC6: tracker rows present

```bash
grep -c "4.9 \| Dashboard launcher surface\|Dashboard launcher surface" ai-dev/work/TESTS_ENHANCEMENT.md
grep "CR-00093" ai-dev/work/TESTS_ENHANCEMENT.md | head
grep "v1.9 (2026-05-28)" ai-dev/work/TESTS_ENHANCEMENT.md
```

Expected: tracker row + changelog entry + header bump all present. Missing → HIGH.

### AC7: deferred to S11 (qv-browser)

AC7 is browser-verified by S11; S03 does not exercise it. Confirm S11 exists in the manifest and that the manifest's `scope.allowed_paths` matches the design Impacted Paths exactly.

```bash
python -c "
import json
m = json.load(open('ai-dev/active/CR-00093/workflow-manifest.json'))
paths = sorted(m['scope']['allowed_paths'])
expected = sorted(['.iw-orch.json', 'ai-dev/work/TESTS_ENHANCEMENT.md'])
assert paths == expected, f'scope mismatch: {paths} vs {expected}'
print(f'manifest scope: {paths}')
print(f'manifest steps: {[s[\"step\"] for s in m[\"steps\"]]}')
"
```

## Cross-Step Consistency Checks

1. **Numeric anchors**: S01 report's `test_categories_total=24` and `quality_categories_total=13` match the live JSON counts (AC1, AC2).
2. **Wave-style anchors don't apply** (single-impl-step CR), but:
3. **e2e_stack list**: S01 report's `e2e_stack_categories` matches the live JSON (AC4).
4. **Missing-target list**: S01 report's `missing_makefile_targets` is empty AND your AC3 check finds none.

## Re-run the test suites (NON-NEGOTIABLE)

```bash
make test-unit
uv run pytest tests/dashboard/test_route_contract_sweep.py -v --no-cov
```

Failure → CRITICAL.

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "CR-00093",
  "verdict": "pass|fail",
  "findings": [],
  "ac_execution": {
    "AC1_test_count_24": true,
    "AC2_quality_count_13": true,
    "AC3_all_make_targets_exist": true,
    "AC4_e2e_stack_scoped": true,
    "AC5_existing_byte_identical": true,
    "AC6_tracker_updated": true,
    "AC7_deferred_to_S11": true
  },
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
