# CR-00059 — S02 Code Review Report

## Verdict

**NEEDS_FIX**

S01 landed the intended mutmut dependency/config/Makefile/doc scaffolding and passed `make lint` + `make format-check`, but there are blocking contract gaps in AC4/AC5 evidence quality and reproducibility.

---

## Findings

1. **CRITICAL · category: tests**  
   **File:** `tests/unit/test_mutmut_setup.py:52-73` (validated by command output)  
   **Description:** AC5 requires `uv run pytest tests/unit/test_mutmut_setup.py -v` to pass GREEN. It does not: pytest exits non-zero due to global coverage gate (`FAIL Required test coverage of 50.0% not reached. Total coverage: 3.01%`), even though both tests pass.  
   **Recommendation:** Make the test runnable under the exact AC command (e.g., adapt invocation contract or fixture/config so this targeted run is not coverage-failed). Update S01 evidence to show GREEN with the exact required command.

2. **HIGH · category: specification**  
   **File:** `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt:43-50`  
   **Description:** “Top 5 surviving mutants” is required as file:line + brief diff. Current table is five `n/a` placeholders, which is non-actionable for the follow-up queue.  
   **Recommendation:** Replace placeholder rows with real surviving mutant entries; if blocked, explicitly record blocker state and provide a concrete rerun plan + command adjustment that yields IDs/diffs.

3. **HIGH · category: specification**  
   **File:** `ai-dev/active/CR-00059/reports/CR-00059_S01_Backend_report.md:30-85` vs `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt:1-60`  
   **Description:** The inline measurement copy and canonical evidence are not byte-identical for the measurement portion (top-5 section content/format differs: “None captured …” vs 5 `n/a` rows).  
   **Recommendation:** Make the measurement section identical in both locations (single-source copy/paste).

4. **HIGH · category: correctness**  
   **File:** `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt:7-13`  
   **Description:** Mutation score is shown as `0.00%` with `Killed=0` and `Survived=0`; formula `K/(K+S)` has zero denominator, so score is mathematically undefined, not 0.00%.  
   **Recommendation:** Mark score as blocked/undefined for this run, and add explicit denominator note. If required by template, include both “reported score” and “formula applicability” fields.

---

## Checklist Results

- **Pre-review gates:** `make lint` ✅, `make format-check` ✅
- **AC1 (dep):** `mutmut>=2.5,<3.0` present ✅; `uv.lock` contains `name = "mutmut"` ✅; `uv run mutmut version` -> `2.5.1` ✅
- **AC2 ([tool.mutmut]):** `paths_to_mutate="orch/daemon/"`, `tests_dir="tests/"`, runner contains required args/paths ✅
- **AC3 (4 Make targets):** all `make -n mutation-*` parse ✅; missing-arg usage for `mutation-check`/`mutation-show` exits non-zero with usage ✅; uses `uv run mutmut` ✅
- **AC4 (spike table):** structure present ⚠️; blockers above (top-5 placeholders, undefined score, inline/evidence drift) ❌
- **AC5 (RED-first guard test):** file exists ✅; RED evidence in S01 report present ✅; required GREEN command currently fails coverage gate ❌
- **AC6 (strategy doc):** §5 mutation row on-demand ✅; §8 no longer says “not yet set up” ✅; references follow-up CR ✅; §9 flipped to ⚠️ ✅
- **AC7 (plan/changelog):** §6 item 2.1 is IN PROGRESS ✅; follow-up row added ✅; §11 new dated entry with spike numbers ✅
- **AC8 (scope):** no production code under `orch/daemon/`, no CI/workflow/skills/migration scope creep ✅
- **AC9 (QV chain):** not re-run end-to-end in this review (outside S02 command set) ℹ️

---

## Spike Measurement Audit (independent)

| Metric | Recorded | Re-derived / Check | Result |
|---|---:|---:|---|
| Total mutants | 0 | 0 | ✅ |
| Killed (K) | 0 | 0 | ✅ |
| Survived (S) | 0 | 0 | ✅ |
| Timeout | 0 | 0 | ✅ |
| Suspicious | 0 | 0 | ✅ |
| Mutation score | 0.00% | **undefined** (`K+S = 0`) | ❌ drift from strict formula applicability |
| Wall-clock | 0:17:17 | format valid (`h:mm:ss`) | ✅ |
| Modules covered | 25 of 25 + list | non-empty daemon list present | ✅ |

---

## Scope Audit (full file list)

From `git status --short` at review time:

- `Makefile` — **PASS** (impacted path)
- `ai-dev/work/TESTS_ENHANCEMENT.md` — **PASS**
- `docs/IW_AI_Core_Testing_Strategy.md` — **PASS**
- `pyproject.toml` — **PASS**
- `uv.lock` — **PASS**
- `tests/unit/test_mutmut_setup.py` — **PASS**
- `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt` — **PASS** (implicit `ai-dev/active/{ID}/**` scope)
- `ai-dev/active/CR-00059/reports/CR-00059_S01_Backend_report.md` — **PASS** (implicit scope)

No prohibited edits detected under `orch/`, `dashboard/`, `executor/`, `.github/workflows/`, `skills/`, `.claude/`, or Alembic migrations.

---

## Commands Run (S02)

- `uv run iw step-start CR-00059 --step S02`
- `make lint`
- `make format-check`
- `grep -n 'mutmut' pyproject.toml | grep -v '^#'`
- `uv run mutmut --version` (CLI rejected option)
- `uv run mutmut version`
- `python -c "import tomllib; ... ['tool']['mutmut']"`
- `make -n mutation-check MODULE=orch/daemon/auto_merge.py`
- `make -n mutation-audit`
- `make -n mutation-results`
- `make -n mutation-show ID=1`
- `make mutation-check` (usage path)
- `make mutation-show` (usage path)
- `ls -la tests/unit/test_mutmut_setup.py`
- `uv run pytest tests/unit/test_mutmut_setup.py -v`
- `wc -l orch/daemon/*.py`
- `make mutation-check MODULE=orch/daemon/container_info.py`

---

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00059",
  "reviewed_agent": "backend-impl",
  "verdict": "NEEDS_FIX",
  "mandatory_fix_count": 4,
  "findings_by_severity": {
    "critical": 1,
    "high": 3,
    "medium": 0,
    "low": 0,
    "info": 0
  },
  "top_3_blocking_findings": [
    "AC5 command `uv run pytest tests/unit/test_mutmut_setup.py -v` exits non-zero due to coverage gate",
    "Top-5 surviving mutants section contains placeholders/non-actionable entries",
    "Inline spike table and canonical evidence are not byte-identical"
  ],
  "findings": [
    {
      "severity": "CRITICAL",
      "category": "tests",
      "file": "tests/unit/test_mutmut_setup.py",
      "lines": "52-73",
      "description": "Required AC5 green command fails overall due coverage gate",
      "recommendation": "Ensure required command exits 0 and update evidence accordingly"
    },
    {
      "severity": "HIGH",
      "category": "specification",
      "file": "ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt",
      "lines": "43-50",
      "description": "Top 5 surviving mutants section contains n/a placeholders",
      "recommendation": "Provide real surviving mutant IDs/file:line/diff or explicit blocked rerun plan"
    },
    {
      "severity": "HIGH",
      "category": "specification",
      "file": "ai-dev/active/CR-00059/reports/CR-00059_S01_Backend_report.md",
      "lines": "30-85",
      "description": "Inline measurement section drifts from canonical evidence",
      "recommendation": "Make measurement portions byte-identical"
    },
    {
      "severity": "HIGH",
      "category": "correctness",
      "file": "ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt",
      "lines": "7-13",
      "description": "Score shown although K+S=0 (undefined denominator)",
      "recommendation": "Mark as undefined/blocked or rerun after runner adjustment"
    }
  ],
  "notes": "Scope boundaries respected; tooling/docs-only CR with no production code changes observed."
}
```
