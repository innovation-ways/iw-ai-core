# CR-00008 S13 QV Fix Cycle 1/5

Quality gate S13 for work item CR-00008 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 18 lint errors found across 6 files (SIM105, F541, I001, PTH118/120/100, E501, F401, S701, N802, N806, F841, S108)

**Command output**:
```
...(truncated)...
   content = licenses_path.read_text()
204 |         vendor_dir = Path(__file__).parent.parent.parent / "dashboard" / "static" / "vendor"
205 |         ACCEPTABLE_SPDX = {
    |         ^^^^^^^^^^^^^^^
206 |             "MIT",
207 |             "Apache-2.0",
    |

F841 Local variable `ACCEPTABLE_SPDX` is assigned to but never used
   --> tests/dashboard/test_chat_security.py:205:9
    |
203 |         content = licenses_path.read_text()
204 |         vendor_dir = Path(__file__).parent.parent.parent / "dashboard" / "static" / "vendor"
205 |         ACCEPTABLE_SPDX = {
    |         ^^^^^^^^^^^^^^^
206 |             "MIT",
207 |             "Apache-2.0",
    |
help: Remove assignment to unused variable `ACCEPTABLE_SPDX`

E501 Line too long (107 > 100)
   --> tests/dashboard/test_chat_security.py:244:101
    |
243 | class TestCodeQaRouteRegistered:
244 |     """AC3 — POST /api/projects/{project_id}/code/qa is registered and returns 501 for unknown projects."""
    |                                                                                                     ^^^^^^^
245 |
246 |     def test_code_qa_route_registered(self):
    |

S108 Probable insecure usage of temporary file or directory: "/tmp"
   --> tests/dashboard/test_code_qa_sse_wire.py:446:35
    |
444 |                         id="test-project",
445 |                         display_name="Test",
446 |                         repo_root="/tmp",
    |                                   ^^^^^^
447 |                         config={"code_understanding": {"index_path": str(index_base)}},
448 |                     )
    |

Found 18 errors.
[*] 3 fixable with the `--fix` option (2 hidden fixes can be enabled with the `--unsafe-fixes` option).
[0m
[0m$ [0mmkdir -p ai-dev/active/CR-00008/reports
[0m
[0m← [0mWrite ai-dev/active/CR-00008/reports/CR-00008_S13_QualityValidation_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00008 --step S13 --reason "18 lint errors found across 6 files (SIM105, F541, I001, PTH118/120/100, E501, F401, S701, N802, N806, F841, S108)"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00008 step S13: 18 lint errors found across 6 files (SIM105, F541, I001, PTH118/120/100, E501, F401, S701, N802, N806, F841, S108)
[0m
**FAIL** — 18 lint errors found across 6 files.

Key issues:
- `dashboard/routers/code.py:156` — SIM105: should use `contextlib.suppress(TimeoutError)`
- `tests/dashboard/browser/test_chat_mermaid.py` — f-string without placeholders, unsorted imports, `os.path` should be `Path`
- `tests/dashboard/test_chat_security.py` — Jinja2 `autoescape` not set (XSS risk), naming convention violations
- `tests/dashboard/test_chat_a11y.py` — unused import, long lines
- `tests/dashboard/test_code_qa_sse_wire.py:446` — insecure `/tmp` usage

3 errors are auto-fixable with `--fix`.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
