# F-00091 S17 QV Fix Cycle 2/5

Quality gate S17 for work item F-00091 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  dashboard/templates/chat_assistant/panel.html
  dashboard/templates/chat_assistant/composer.html
  dashboard/static/chat_assistant/chat.js
  dashboard/static/chat_assistant/chat.css
  dashboard/static/styles.css
  dashboard/routers/chat.py
  dashboard/routers/projects.py
  orch/chat/context_usage.py
  orch/db/migrations/versions/**
  tests/dashboard/**
  tests/integration/**
  tests/unit/**

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/F-00091/**
  ai-dev/archive/F-00091/**
  ai-dev/work/F-00091/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091/ai-dev/active/F-00091/F-00091_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: frontend-tests failed: exit=2

**Unparseable output** (always surfaces):
  uv run pytest tests/dashboard/ --ignore=tests/dashboard/browser --no-cov -v
  platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091/.venv/bin/python
  cachedir: .pytest_cache
  benchmark: 4.0.0 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
  hypothesis profile 'default'
  Using --randomly-seed=2663012135
  rootdir: /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091
  configfile: pyproject.toml
  plugins: timeout-2.4.0, asyncio-1.3.0, cov-7.1.0, respx-0.22.0, xdist-3.8.0, allure-pytest-2.15.3, Faker-40.13.0, schemathesis-4.19.0, rerunfailures-15.1, benchmark-4.0.0, anyio-4.13.0, hypothesis-6.152.7, randomly-4.1.0
  asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
  collecting ... collected 1273 items / 2 deselected / 1271 selected
  ________ TestStalenessDotUpToDate.test_grey_dot_has_hx_swap_outer_html _________
  self = <tests.dashboard.test_staleness_templates.TestStalenessDotUpToDate object at 0x7e5c6fb8b5c0>
  tmpl = <Template 'fragments/staleness_dot.html'>
      def test_grey_dot_has_hx_swap_outer_html(self, tmpl):
          proj = type("P", (), {"id": "iw-ai-core"})()
  >       html = tmpl.render(staleness=_up_to_date_result(), project=proj)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  tests/dashboard/test_staleness_templates.py:373: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  .venv/lib/python3.12/site-packages/jinja2/environment.py:1295: in render
      self.environment.handle_exception()
  .venv/lib/python3.12/site-packages/jinja2/environment.py:942: in handle_exception
      raise rewrite_traceback_stack(source=source)
  dashboard/templates/fragments/staleness_dot.html:2: in top-level template code
      {% set _ua = (request.headers.get('user-agent', '')|lower) %}
      ^^^^^^^^^^^^^^^^^^^^^^^^^
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  self = <jinja2.environment.Environment object at 0x7e5c6fe73d10>
  obj = Undefined, attribute = 'headers'
      def getattr(self, obj: t.Any, attribute: str) -> t.Any:
          """Get an item or attribute of an object but prefer the attribute.
          Unlike :meth:`getitem` the attribute *must* be a string.
          """
          try:
  >           return getattr(obj, attribute)
                     ^^^^^^^^^^^^^^^^^^^^^^^
  E           jinja2.exceptions.UndefinedError: 'request' is undefined
  .venv/lib/python3.12/site-packages/jinja2/environment.py:490: UndefinedError
  ________ TestStalenessDotUpToDate.test_renders_grey_dot_when_up_to_date ________
  ...(1 lines omitted)...
      def getattr(self, obj: t.Any, attribute: str) -> t.Any:
          """Get an item or attribute of an object but prefer the attribute.
          Unlike :meth:`getitem` the attribute *must* be a string.
          """
          try:
  >           return getattr(obj, attribute)
                     ^^^^^^^^^^^^^^^^^^^^^^^
  E           jinja2.exceptions.UndefinedError: 'request' is undefined
  .venv/lib/python3.12/site-packages/jinja2/environment.py:490: UndefinedError
  _______ TestStalenessDotNotRunning.test_not_running_renders_grey_not_red _______
  self = <tests.dashboard.test_staleness_templates.TestStalenessDotNotRunning object at 0x7e5c6fb8a270>
  tmpl = <Template 'fragments/staleness_dot.html'>
      def test_not_running_renders_grey_not_red(self, tmpl):
          """not_running does NOT contribute to is_stale — grey dot only."""
          proj = type("P", (), {"id": "iw-ai-core"})()
  >       html = tmpl.render(staleness=_not_running_result(), project=proj)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  tests/dashboard/test_staleness_templates.py:412: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  .venv/lib/python3.12/site-packages/jinja2/environment.py:1295: in render
      self.environment.handle_exception()
  .venv/lib/python3.12/site-packages/jinja2/environment.py:942: in handle_exception
      raise rewrite_traceback_stack(source=source)
  dashboard/templates/fragments/staleness_dot.html:2: in top-level template code
      {% set _ua = (request.headers.get('user-agent', '')|lower) %}
      ^^^^^^^^^^^^^^^^^^^^^^^^^
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  self = <jinja2.environment.Environment object at 0x7e5c6fb19190>
  obj = Undefined, attribute = 'headers'
      def getattr(self, obj: t.Any, attribute: str) -> t.Any:
          """Get an item or attribute of an object but prefer the attribute.
          Unlike :meth:`getitem` the attribute *must* be a string.
          """
          try:
  >           return getattr(obj, attribute)
                     ^^^^^^^^^^^^^^^^^^^^^^^
  E           jinja2.exceptions.UndefinedError: 'request' is undefined
  .venv/lib/python3.12/site-packages/jinja2/environment.py:490: UndefinedError
  = 9 failed, 1247 passed, 14 skipped, 2 deselected, 1 xfailed in 287.37s (0:04:47) =
  make: *** [Makefile:144: test-dashboard] Error 1


## Gate Command

The quality gate that failed runs:
```bash
make test-frontend
```

After applying fixes, re-run this command to verify the issues are resolved.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Skim the section that covers this step's scope; quote-of-the-doc lives in this prompt when available.
2. **Diff your target file(s) against the spec** — list deviations explicitly before editing.
3. **Apply the minimum patch** to align code with the spec; the reported errors should resolve as a side effect of that alignment.
4. **If the errors disagree with the spec, the spec wins.** Note the disagreement in your output rather than silently following the errors.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.
5. **Post-edit cross-gate check (MANDATORY before exit).** When the
   failing gate is NOT lint/format, your edits may still introduce a
   new ruff violation that the next review run trips on. Before exiting,
   run `make format-check` and `make lint` and resolve any NEW violation
   your edits introduced (`uv run ruff format <file>` for format issues;
   targeted edit for lint). Diagnosed 2026-05-25 from CR-00082 S04's
   ping-pong between fix cycles where each agent re-broke the gate the
   previous one fixed.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
