# F-00060 S09 QV Fix Cycle 1/5

Quality gate S09 for work item F-00060 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 38 lint errors found - invalid module names, undefined imports (WorkItem/WorkItemType), line too long, print statements, Path usage issues, unused args

**Command output**:
```
...(truncated)...
tle="C", summary="C summary", functional_doc_content="CR-00003 content")
    |

E501 Line too long (114 > 100)
   --> tests/unit/test_qa_v2_relevance_filter_eval.py:137:101
    |
135 |         """Only IDs that are in BOTH mentioned_ids AND allowed_ids should emit."""
136 |         cr_b = MockWorkItem("CR-00002", title="B", summary="B summary", functional_doc_content="CR-00002 content")
137 |         cr_c = MockWorkItem("CR-00003", title="C", summary="C summary", functional_doc_content="CR-00003 content")
    |                                                                                                     ^^^^^^^^^^^^^^
138 |
139 |         bundle = EvidenceBundle(question="test")
    |

E501 Line too long (201 > 100)
   --> tests/unit/test_qa_v2_relevance_filter_eval.py:158:101
    |
156 | …
157 | …
158 | …cifically addresses the color aspect. We evaluated blue, green, and red before settling on the brand blue #0066CC.",
    |                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
159 | …
    |

E501 Line too long (112 > 100)
   --> tests/unit/test_qa_v2_relevance_filter_eval.py:178:101
    |
176 |         )
177 |         assert "brand blue #0066CC" in snippet, "Snippet should include full functional doc content"
178 |         assert snippet == item.functional_doc_content[:300], "Snippet must be first 300 chars of functional doc"
    |                                                                                                     ^^^^^^^^^^^^
    |

Found 38 errors.
No fixes available (6 hidden fixes can be enabled with the `--unsafe-fixes` option).
make: *** [Makefile:17: lint] Error 1
[0m
**Gate FAIL** — 38 lint errors found.
[0m$ [0mmkdir -p ai-dev/active/F-00060/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00060/reports/F-00060_S09_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00060 --step S09 --reason "38 lint errors found - invalid module names, undefined imports (WorkItem/WorkItemType), line too long, print statements, Path usage issues, unused args"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00060 step S09: 38 lint errors found - invalid module names, undefined imports (WorkItem/WorkItemType), line too long, print statements, Path usage issues, unused args
[0m
**FAIL** - 38 lint errors found, primarily in the F-00060 test files:
- `test_invariants_F00060.py` and `test_boundary_behavior_F00060.py`: invalid module names (snake_case required)
- F821 undefined `WorkItem`/`WorkItemType` in `test_invariants_F00060.py:186+`
- Multiple E501 line-too-long violations
- T201 print statements in `executor/scope_gate.py`
- PTH118/110/123 Path usage issues
- ARG005 unused lambda arguments

Report written to `ai-dev/active/F-00060/reports/F-00060_S09_QvGate_report.md`.

```


## Gate Command

The quality gate that failed runs:
```bash
make lint
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
