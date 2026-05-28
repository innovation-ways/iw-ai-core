# F-00091 S17 QV Fix Cycle 1/5

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

**New Failures**:
  [test] tests/dashboard/test_chat_context_pct_template.py::TestComposerDom::test_context_pct_element_exists
  [test] tests/dashboard/test_chat_context_pct_template.py::TestComposerDom::test_context_pct_starts_hidden
  [test] tests/dashboard/test_chat_context_pct_template.py::TestContextPctCss::test_crit_class_exists
  [test] tests/dashboard/test_chat_context_pct_template.py::TestContextPctCss::test_warn_class_exists
  [test] tests/dashboard/test_chat_context_pct_template.py::TestContextPctJsHelpers::test_refresh_context_pct_hides_on_falsy_tab_id
  [test] tests/dashboard/test_chat_history_restore.py::test_bootstrap_tabs_uses_last_active_at_fallback
  [test] tests/dashboard/test_chat_router_pi_context_pct.py::test_pi_tab_omits_context_pct_when_context_window_tokens_null
  [test] tests/dashboard/test_chat_router_pi_context_pct.py::test_pi_tab_omits_context_pct_when_no_token_usage
**Unparseable output** (always surfaces):
  uv run pytest tests/dashboard/ --ignore=tests/dashboard/browser --no-cov -v
  platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091/.venv/bin/python
  cachedir: .pytest_cache
  benchmark: 4.0.0 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
  hypothesis profile 'default'
  Using --randomly-seed=1506657373
  rootdir: /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00091
  configfile: pyproject.toml
  plugins: timeout-2.4.0, asyncio-1.3.0, cov-7.1.0, respx-0.22.0, xdist-3.8.0, allure-pytest-2.15.3, Faker-40.13.0, schemathesis-4.19.0, rerunfailures-15.1, benchmark-4.0.0, anyio-4.13.0, hypothesis-6.152.7, randomly-4.1.0
  asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
  collecting ... collected 1273 items / 2 deselected / 1271 selected
  _______________ test_bootstrap_tabs_uses_last_active_at_fallback _______________
      def test_bootstrap_tabs_uses_last_active_at_fallback() -> None:
          """`_bootstrapTabs` must select the most recently active tab when sessionStorage is cleared.
          Before the fix: `_activateTab(target ? target.id : _tabs[0].id)` always fell
          back to index 0 when the stored tab ID was stale or absent. After the fix the
          fallback must compare `last_active_at` timestamps across tabs and pick the highest.
          """
          js = CHAT_JS.read_text(encoding="utf-8")
          body = _extract_function_body(js, "_bootstrapTabs")
          assert body is not None, "_bootstrapTabs function not found in chat.js"
  >       assert body.count("last_active_at") >= 1, (
              "_bootstrapTabs must compare `last_active_at` timestamps to pick the "
              "most recently active tab when sessionStorage is cleared, "
              "instead of blindly falling back to _tabs[0]"
          )
  E       AssertionError: _bootstrapTabs must compare `last_active_at` timestamps to pick the most recently active tab when sessionStorage is cleared, instead of blindly falling back to _tabs[0]
  E       assert 0 >= 1
  E        +  where 0 = <built-in method count of str object at 0x376c75c0>('last_active_at')
  E        +    where <built-in method count of str object at 0x376c75c0> = 'function _bootstrapTabs() {\n    var projectId = _assistantProjectId();\n    if (!projectId) {\n      _tabs = [];\n      _activeTabId = null;\n      _renderEmptyNoTabs();\n      _setComposerEnabled(false);\n      return;\n    }\n    _fetchTabs(projectId, function (tabs) {\n      if (!tabs.length) {\n        // First load: retry once after 100ms (server may still be seeding the default tab)\n        setTimeout(function () {\n          _fetchTabs(projectId, function (tabs2) {\n            _tabs = tabs2;\n            _renderTabStrip();\n            if (_tabs.length) {\n              var lastActive2 = null;\n              try {\n                lastActive2 = localStorage.getItem(_activeTabKey(_assistantProjectId()));\n              } catch (_e) {\n                lastActive2 = null;\n              }\n              var target2 = lastActive2 && _tabs.find(function (t) { return t.id === lastActive2; });\n              if (!target2 && lastActive2) {\n                try {\n                  localStorage.removeItem(_activeTabKey(_assistantProjectId()));\n                } catch (_e2) {\n                  // ignore localStorage failures\n                }\n              }\n              _activateTab(target2 ? target2.id : _tabs[0].id);\n            } else {\n              _renderEmptyNoTabs();\n            }\n          });\n        }, 100);\n        return;\n      }\n      _tabs = tabs;\n      _renderTabStrip();\n      var lastActive = null;\n      try {\n        lastActive = localStorage.getItem(_activeTabKey(_assistantProjectId()));\n      } catch (_e) {\n        lastActive = null;\n      }\n      var target = lastActive && _tabs.find(function (t) { return t.id === lastActive; });\n      if (!target && lastActive) {\n        try {\n          localStorage.removeItem(_activeTabKey(_assistantProjectId()));\n        } catch (_e2) {\n          // ignore localStorage failures\n        }\n      }\n      _activateTab(target ? target.id : _tabs[0].id);\n    });\n  }\n\n'.count
  tests/dashboard/test_chat_history_restore.py:128: AssertionError
  ________ test_pi_tab_omits_context_pct_when_context_window_tokens_null _________
  pi_context_pct_app = (<starlette.testclient.TestClient object at 0x7ea6ca7ea210>, <MagicMock id='139255024828048'>, <MagicMock id='139254823243360'>, <sqlalchemy.orm.session.Session object at 0x7ea6d68dd5e0>)
  db_session = <sqlalchemy.orm.session.Session object at 0x7ea6d68dd5e0>
  test_project = <orch.db.models.Project object at 0x7ea6d6499460>
      def test_pi_tab_omits_context_pct_when_context_window_tokens_null(
          pi_context_pct_app: tuple[TestClient, Any, Any, Session],
          db_session: Session,
          test_project: Project,
      ) -> None:
  ...(1 lines omitted)...
  self = <tests.dashboard.test_chat_context_pct_template.TestComposerDom object at 0x7ea6ddf21670>
      def test_context_pct_element_exists(self):
          soup = BeautifulSoup(COMPOSER_HTML.read_text(encoding="utf-8"), "html.parser")
          el = soup.find(id="chat-assistant-context-pct")
          assert el is not None, "composer.html must contain #chat-assistant-context-pct"
  >       assert el.name == "span", f"#chat-assistant-context-pct must be a <span>, got <{el.name}>"
  E       AssertionError: #chat-assistant-context-pct must be a <span>, got <div>
  E       assert 'div' == 'span'
  E         
  E         - span
  E         + div
  tests/dashboard/test_chat_context_pct_template.py:50: AssertionError
  ___________________ TestContextPctCss.test_crit_class_exists ___________________
  self = <tests.dashboard.test_chat_context_pct_template.TestContextPctCss object at 0x7ea6ddf22b70>
      def test_crit_class_exists(self):
          body = _css_rule_body(
              CHAT_CSS.read_text(encoding="utf-8"), ".chat-assistant-context-pct.is-crit"
          )
  >       assert body is not None, (
              "chat.css must define a .chat-assistant-context-pct.is-crit rule "
              "for the >=90% destructive band"
          )
  E       AssertionError: chat.css must define a .chat-assistant-context-pct.is-crit rule for the >=90% destructive band
  E       assert None is not None
  tests/dashboard/test_chat_context_pct_template.py:115: AssertionError
  ___________________ TestContextPctCss.test_warn_class_exists ___________________
  self = <tests.dashboard.test_chat_context_pct_template.TestContextPctCss object at 0x7ea6ddf22750>
      def test_warn_class_exists(self):
          body = _css_rule_body(
              CHAT_CSS.read_text(encoding="utf-8"), ".chat-assistant-context-pct.is-warn"
          )
  >       assert body is not None, (
              "chat.css must define a .chat-assistant-context-pct.is-warn rule "
              "for the 70-89% amber/warning band"
          )
  E       AssertionError: chat.css must define a .chat-assistant-context-pct.is-warn rule for the 70-89% amber/warning band
  E       assert None is not None
  tests/dashboard/test_chat_context_pct_template.py:103: AssertionError
  = 17 failed, 1239 passed, 14 skipped, 2 deselected, 1 xfailed in 534.12s (0:08:54) =
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
