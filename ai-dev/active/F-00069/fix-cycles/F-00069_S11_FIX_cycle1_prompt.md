# F-00069 S11 QV Fix Cycle 1/5

Quality gate S11 for work item F-00069 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 7 unit tests failed: ELK frontmatter injection and purpose comment formatting broken in RAG mapgen/module_gen

**Unparseable output** (always surfaces):
  !  agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
  > build · MiniMax-M2.7
  $ uv run iw step-start F-00069 --step S11
  Started F-00069 step S11 (already in progress)
  $ make test-unit 2>&1
  ...output truncated...
  Full output saved to: /home/sergiog/.local/share/opencode/tool-output/tool_ddb8121c9001PTSge4aeIN21PL
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_test_run_emits_test_completed_on_success PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_test_run_emits_test_failed_on_failure PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_test_run_does_not_emit_quality_events PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_quality_run_emits_quality_started_on_begin PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_quality_run_emits_quality_completed_on_success PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_quality_run_emits_quality_failed_on_failure PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_quality_run_does_not_emit_test_events PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunAllureSkip::test_test_run_cleans_allure_results PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunAllureSkip::test_test_run_generates_allure_report PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunAllureSkip::test_quality_run_skips_allure_cleanup PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunAllureSkip::test_quality_run_skips_allure_report_generation PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunCommandRewrite::test_pytest_alluredir_equals_is_rewritten_to_per_run_dir PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunCommandRewrite::test_pytest_alluredir_space_separated_is_rewritten PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunCommandRewrite::test_pytest_alluredir_with_custom_base_dir_is_rewritten PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunCommandRewrite::test_make_command_gets_allure_results_env_prefix PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunCommandRewrite::test_command_without_allure_flag_or_make_is_unchanged PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunCommandRewrite::test_pytest_alluredir_takes_precedence_over_make_branch PASSED [ 98%]
  tests/unit/test_timing_middleware.py::TestQueryCountCtx::test_default_zero PASSED [ 98%]
  tests/unit/test_timing_middleware.py::TestQueryCountCtx::test_increment_and_get PASSED [ 98%]
  tests/unit/test_timing_middleware.py::TestQueryCountCtx::test_reset PASSED [ 98%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_instantiation_with_engine PASSED [ 98%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_default_threshold_is_500 PASSED [ 99%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_emits_warn_above_threshold PASSED [ 99%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_warn_log_contains_required_fields PASSED [ 99%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_debug_log_below_threshold PASSED [ 99%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_pool_status_in_log PASSED [ 99%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_does_not_swallow_upstream_exceptions PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_hit_returns_cached_value PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_miss_returns_none_for_missing_key PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_expired_key_returns_none PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_delete_removes_key PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_clear_removes_all_keys PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_concurrent_access_does_not_crash PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_stats_hit_miss PASSED   [ 99%]
  tests/unit/test_worktree_setup_context_copy.py::test_context_files_exist_in_worktree_after_copy PASSED [ 99%]
  tests/unit/test_worktree_setup_context_copy.py::test_copied_context_files_respect_exclude_patterns PASSED [ 99%]
  tests/unit/test_worktree_setup_context_copy.py::test_worktree_exclude_file_contains_correct_patterns PASSED [ 99%]
  tests/unit/test_worktree_setup_context_copy.py::test_copy_step_is_silent_when_active_dir_missing PASSED [ 99%]
  tests/unit/test_worktrees_caching.py::TestNavWorktreeBadgeCaching::test_badge_returns_from_cache_on_second_call_within_ttl PASSED [ 99%]
  tests/unit/test_worktrees_caching.py::TestNavWorktreeBadgeCaching::test_badge_returns_cached_value_after_expiry PASSED [ 99%]
  tests/unit/test_worktrees_caching.py::TestNavWorktreeBadgeCaching::test_cached_fn_provides_hit_miss_stats PASSED [ 99%]
  tests/unit/test_worktrees_caching.py::TestWorktreePageCaching::test_collect_worktrees_returns_same_value_from_cache PASSED [100%]
  _ TestBuildMermaidElkInjection.test_elk_frontmatter_injected_when_llm_omits_it _
  self = <tests.unit.rag.test_mapgen_mermaid.TestBuildMermaidElkInjection object at 0x75f536fff110>
  mock_config = <MagicMock id='129693112898416'>
      def test_elk_frontmatter_injected_when_llm_omits_it(self, mock_config):
          """When LLM returns mermaid block without ELK frontmatter, it is injected."""
          from orch.rag.mapgen import MapGenerator
          mock_response = MagicMock()
          mock_response.text = "```mermaid\ngraph TD\n  A[CLI] --> B[Daemon]\n  B --> C[DB]\n```"
          with patch("orch.rag.mapgen.Ollama") as mock_ollama_cls:
              mock_llm_instance = MagicMock()
              mock_llm_instance.complete.return_value = mock_response
              mock_ollama_cls.return_value = mock_llm_instance
              generator = MapGenerator()
              dsl, _purpose = generator._build_mermaid(
                  "- **CLI**: command interface\n- **Daemon**: background runner",
                  mock_config,
              )
  >       assert "layout: elk" in dsl, "ELK frontmatter must be injected when LLM omits it"
  E       AssertionError: ELK frontmatter must be injected when LLM omits it
  E       assert 'layout: elk' in 'graph TD\n  classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F\n  classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46\n  classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F\n  classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151\n  classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764\n  classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D\n\n\n  A[CLI] --> B[Daemon]\n  B --> C[DB]'
  tests/unit/rag/test_mapgen_mermaid.py:39: AssertionError
  _ TestBuildMermaidElkInjection.test_elk_frontmatter_not_duplicated_when_llm_includes_it _
  self = <tests.unit.rag.test_mapgen_mermaid.TestBuildMermaidElkInjection object at 0x75f536fff470>
  mock_config = <MagicMock id='129693112551760'>
      def test_elk_frontmatter_not_duplicated_when_llm_includes_it(self, mock_config):
          """When LLM already includes ELK frontmatter, it is not duplicated."""
          from orch.rag.mapgen import MapGenerator
          mock_response = MagicMock()
          mock_response.text = (
              "```mermaid\n---\nconfig:\n  layout: elk\n---\ngraph TD\n  A[CLI] --> B[Daemon]\n```"
          )
          with patch("orch.rag.mapgen.Ollama") as mock_ollama_cls:
              mock_llm_instance = MagicMock()
              mock_llm_instance.complete.return_value = mock_response
              mock_ollama_cls.return_value = mock_llm_instance
              generator = MapGenerator()
              dsl, _purpose = generator._build_mermaid(
                  "- **CLI**: command interface\n- **Daemon**: background runner",
                  mock_config,
              )
  >       assert dsl.count("layout: elk") == 1, "ELK frontmatter must not be duplicated"
  E       AssertionError: ELK frontmatter must not be duplicated
  E       assert 0 == 1
  E        +  where 0 = <built-in method count of str object at 0x75f487fbb7e0>('layout: elk')
  E        +    where <built-in method count of str object at 0x75f487fbb7e0> = 'graph TD\n  classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F\n  classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46\n  classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F\n  classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151\n  classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764\n  classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D\n\n\n  A[CLI] --> B[Daemon]'.count
  tests/unit/rag/test_mapgen_mermaid.py:62: AssertionError
  _____ TestBuildMermaidElkInjection.test_fallback_dsl_when_no_fenced_block ______
  self = <tests.unit.rag.test_mapgen_mermaid.TestBuildMermaidElkInjection object at 0x75f536fff7d0>
  mock_config = <MagicMock id='129693110126976'>
      def test_fallback_dsl_when_no_fenced_block(self, mock_config):
          """When LLM returns prose with no fenced mermaid block, fallback DSL is returned."""
          from orch.rag.mapgen import MapGenerator
          mock_response = MagicMock()
          mock_response.text = "The system has a CLI component and a Daemon component."
          with patch("orch.rag.mapgen.Ollama") as mock_ollama_cls:
              mock_llm_instance = MagicMock()
              mock_llm_instance.complete.return_value = mock_response
              mock_ollama_cls.return_value = mock_llm_instance
              generator = MapGenerator()
              dsl, _purpose = generator._build_mermaid(
                  "- **CLI**: command interface\n- **Daemon**: background runner",
                  mock_config,
              )
          assert "graph TD" in dsl, "Fallback DSL must contain 'graph TD'"
  >       assert "layout: elk" in dsl, "Fallback DSL must still get ELK frontmatter injected"
  E       AssertionError: Fallback DSL must still get ELK frontmatter injected
  E       assert 'layout: elk' in 'graph TD\n  classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F\n  classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46\n  classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F\n  classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151\n  classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764\n  classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D\n\n\n  A[System]'
  tests/unit/rag/test_mapgen_mermaid.py:83: AssertionError
  ________ TestBuildMermaid.test_build_mermaid_elk_frontmatter_preserved _________
  self = <unit.test_rag_mapgen.TestBuildMermaid object at 0x75f48c3aafc0>
  mock_config = <MagicMock id='129693090575568'>
          def test_build_mermaid_elk_frontmatter_preserved(self, mock_config):
              """Existing elk frontmatter injection logic is preserved."""
              llm_response = MagicMock()
              llm_response.text = """\
      ```mermaid
      graph TD
        A[System]
      ```
      ```purpose
      Overview.
      ```
      """
              gen = MapGenerator()
              with patch("orch.rag.mapgen.Ollama") as mock_ollama:
                  mock_llm_instance = MagicMock()
                  mock_llm_instance.complete.return_value = llm_response
                  mock_ollama.return_value = mock_llm_instance
                  dsl, _purpose = gen._build_mermaid("components answer", mock_config)
  >           assert "layout: elk" in dsl, f"DSL must contain 'layout: elk', got: {dsl}"
  E           AssertionError: DSL must contain 'layout: elk', got: graph TD
  E               classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F
  E               classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46
  E               classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F
  E               classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151
  E               classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764
  E               classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D
  E             
  E             
  E               A[System]
  E           assert 'layout: elk' in 'graph TD\n  classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F\n  classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46\n  classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F\n  classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151\n  classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764\n  classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D\n\n\n  A[System]'
  tests/unit/test_rag_mapgen.py:190: AssertionError
  ___ TestStoredContentFormat.test_stored_content_starts_with_purpose_comment ____
  self = <unit.test_rag_mapgen_diagram.TestStoredContentFormat object at 0x75f48c1e1ca0>
  mock_config = <MagicMock id='129693090512976'>
          def test_stored_content_starts_with_purpose_comment(self, mock_config):
              """The stored content starts with <!-- purpose: --> comment before DSL.
              This is the format stored by store_arch_diagram().
              """
              llm_response = MagicMock()
              llm_response.text = """\
      ```mermaid
      graph TD
        A[System]
      ```
      ```purpose
      This diagram shows the architecture.
      ```
      """
              gen = MapGenerator()
              with patch("orch.rag.mapgen.Ollama") as mock_ollama:
                  mock_llm_instance = MagicMock()
                  mock_llm_instance.complete.return_value = llm_response
                  mock_ollama.return_value = mock_llm_instance
                  dsl, purpose = gen._build_mermaid("components answer", mock_config)
              stored = f"<!-- purpose: {purpose} -->\n{dsl}"
              import re
  >           assert re.match(r"<!-- purpose: .+ -->\n---\nconfig:", stored), (
                  f"Stored content must match '<!-- purpose: ... -->\n---\nconfig:', got: {stored}"
              )
  E           AssertionError: Stored content must match '<!-- purpose: ... -->
  E             ---
  E             config:', got: <!-- purpose: This diagram shows the architecture. -->
  E             graph TD
  E               classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F
  E               classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46
  E               classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F
  E               classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151
  E               classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764
  E               classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D
  E             
  E             
  E               A[System]
  E           assert None
  E            +  where None = <function match at 0x75f53cf65800>('<!-- purpose: .+ -->\\n---\\nconfig:', '<!-- purpose: This diagram shows the architecture. -->\ngraph TD\n  classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F\n  classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46\n  classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F\n  classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151\n  classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764\n  classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D\n\n\n  A[System]')
  E            +    where <function match at 0x75f53cf65800> = <module 're' from '/usr/lib/python3.12/re/__init__.py'>.match
  tests/unit/test_rag_mapgen_diagram.py:292: AssertionError
  _ TestGenerateModuleDiagram.test_purpose_extracted_and_normalized_to_single_line _
  self = <unit.test_rag_module_gen.TestGenerateModuleDiagram object at 0x75f48c1e2450>
  mock_config = <MagicMock id='129693072424256'>
  mock_session = <MagicMock id='129693090562368'>
          def test_purpose_extracted_and_normalized_to_single_line(self, mock_config, mock_session):
              """Purpose is extracted from purpose block and normalized to a single line."""
              llm_response = MagicMock()
              llm_response.text = """\
      ```mermaid
      graph LR
        A[Controller]
      ```
      ```purpose
      This diagram shows the internal
      component structure of the module.
      ```
      """
              gen = ModuleGenerator()
              with (
                  patch("orch.rag.module_gen.Ollama") as mock_ollama,
                  patch.object(gen, "_make_slug", return_value="test-slug"),
                  patch("orch.rag.module_gen.DocService") as mock_doc_service_cls,
              ):
                  mock_llm_instance = MagicMock()
                  mock_llm_instance.complete.return_value = llm_response
                  mock_ollama.return_value = mock_llm_instance
                  mock_doc_service = MagicMock()
                  mock_doc_service_cls.return_value = mock_doc_service
                  mock_doc_service.get_doc.return_value = None
                  import asyncio
                  asyncio.run(
                      gen._generate_and_store_module_diagram(
                          project_id="test-project",
                          module_path="orch/rag",
                          module_name="orch.rag",
                          config=mock_config,
                          session=mock_session,
                          retrieved_nodes=["chunk1"],
                      )
                  )
                  create_call = mock_doc_service.create_doc.call_args
                  content = create_call[1]["content"]
                  purpose_match = content.split("---")[0] if "---" in content else ""
  >               assert "purpose:" in purpose_match, f"Purpose comment missing, got: {content[:200]}"
  E               AssertionError: Purpose comment missing, got: <!-- purpose: This diagram shows the internal component structure of the module. -->
  E                 graph LR
  E                   classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F
  E                   classDef data fill:#D1FAE5,stroke:#10B981,color
  E               assert 'purpose:' in ''
  tests/unit/test_rag_module_gen.py:109: AssertionError
  _ TestModuleDiagramPromptContent.test_module_diagram_prompt_elk_frontmatter_required _
  self = <unit.test_rag_module_gen_diagram.TestModuleDiagramPromptContent object at 0x75f48c1fcaa0>
  mock_config = <MagicMock id='129693113110160'>
  mock_session = <MagicMock id='129693090575376'>
          def test_module_diagram_prompt_elk_frontmatter_required(self, mock_config, mock_session):
              """Prompt requires YAML frontmatter with elk layout."""
              llm_response = MagicMock()
              llm_response.text = """\
      ```mermaid
      graph LR
        A[Controller]
      ```
      ```purpose
      Module structure.
      ```
      """
              gen = ModuleGenerator()
              with (
                  patch("orch.rag.module_gen.Ollama") as mock_ollama,
                  patch.object(gen, "_make_slug", return_value="test-slug"),
                  patch("orch.rag.module_gen.DocService") as mock_doc_service_cls,
              ):
                  mock_llm_instance = MagicMock()
                  mock_llm_instance.complete.return_value = llm_response
                  mock_ollama.return_value = mock_llm_instance
                  mock_doc_service = MagicMock()
                  mock_doc_service_cls.return_value = mock_doc_service
                  mock_doc_service.get_doc.return_value = None
                  import asyncio
                  asyncio.run(
                      gen._generate_and_store_module_diagram(
                          project_id="test-project",
                          module_path="orch/rag",
                          module_name="orch.rag",
                          config=mock_config,
                          session=mock_session,
                          retrieved_nodes=["chunk1"],
                      )
                  )
                  call_args = mock_llm_instance.complete.call_args
                  prompt = call_args[0][0]
  >               assert "layout: elk" in prompt, (
                      f"Prompt must require 'layout: elk' in frontmatter, got: {prompt[:300]}"
                  )
  E               AssertionError: Prompt must require 'layout: elk' in frontmatter, got: You are generating a Mermaid component diagram for the 'orch.rag' module.
  E                 
  E                 Code context:
  E                 chunk1
  E                 
  E                 Rules:
  E                 - Output ONLY a fenced ```mermaid block. No prose, no explanation.
  E                 - Use 'graph LR' direction (left-to-right).
  E                 - Maximum 12 nodes. Group minor items if needed.
  E                 - Node IDs: short alphanumeric (e.g.
  E               assert 'layout: elk' in "You are generating a Mermaid component diagram for the 'orch.rag' module.\n\nCode context:\nchunk1\n\nRules:\n- Output ONLY a fenced ```mermaid block. No prose, no explanation.\n- Use 'graph LR' direction (left-to-right).\n- Maximum 12 nodes. Group minor items if needed.\n- Node IDs: short alphanumeric (e.g., QA, IDX, CFG). Labels in [brackets].\n- Show the main internal components and their key dependencies.\n\nAfter the graph declaration, add this classDef block verbatim:\n  classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F\n  classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46\n  classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F\n  classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151\n  classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764\n  classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D\n\nClass assignment rules:\n- API handlers, controllers, routers → `class NodeID api`\n- Database models, repositories, data access layers → `class NodeID data`\n- Background jobs, daemon workers, pipeline stages → `class NodeID worker`\n- External API clients, third-party integrations → `class NodeID external`\n- Dashboard/UI components, frontend adapters → `class NodeID ui`\n- Core domain models, business logic services → `class NodeID core`\n\nStructural-elements-only instruction:\nShow only: controllers, API handlers, services, repositories, data access layers, integration adapters, core domain models.\nDo NOT show: utility classes, helpers, DTOs, config objects.\n\nAfter the diagram block, output a second fenced block:\n```purpose\n[One or two sentences describing what this diagram shows and when to refer to it.]\n```\n"
  tests/unit/test_rag_module_gen_diagram.py:300: AssertionError
  .venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: env
      self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")
  orch/db/models.py:175
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/orch/db/models.py:175: PytestCollectionWarning: cannot collect test class 'TestRunStatus' because it has a __init__ constructor (from: tests/unit/test_test_runner.py)
      class TestRunStatus(enum.Enum):
  tests/unit/daemon/test_batch_manager_worktree_hooks.py::TestTerminalTransitionComposeDown::test_terminal_transition_calls_compose_down
  tests/unit/test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/orch/db/safe_migrate.py:531: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context(live_db_url)
  tests/unit/test_code_qa_router_rerender.py: 1 warning
  tests/unit/test_qa_engine_hybrid_retrieval.py: 2 warnings
  tests/unit/test_qa_engine_render_cache.py: 4 warnings
  tests/unit/test_qa_v2_prompt_layout.py: 8 warnings
  tests/unit/test_qa_v2_relevance_filter_eval.py: 5 warnings
    <string>:9: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
  tests/unit/test_code_ui_routes.py::TestCodeIndexStream::test_sse_stream_returns_idle_when_no_runner_in_registry
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
      warnings.warn(
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_falls_back_when_module_filter_empty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_qa_engine.py:625: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_translates_dotted_module_path_to_filesystem_filter
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_qa_engine.py:723: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_when_module_filter_nonempty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_qa_engine.py:819: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_for_architecture_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_qa_engine.py:905: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_does_not_raise_when_env_false
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_safe_migrate.py:24: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_does_not_raise_when_env_absent
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_safe_migrate.py:28: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_raises_when_env_true
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_safe_migrate.py:33: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/orch/db/safe_migrate.py:593: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context(live_db_url)
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_when_agent_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_safe_migrate.py:190: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_against_per_worktree_db_when_per_worktree_flag_set
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_safe_migrate.py:200: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_even_with_per_worktree_flag
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_safe_migrate.py:213: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_when_only_per_worktree_flag_without_agent_context_is_irrelevant
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_safe_migrate.py:225: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_outside_agent_context_without_flag
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_safe_migrate.py:235: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[TRUE]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[True]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[1]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[yes]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[YES]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[true\n]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[ true]
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_safe_migrate_guards.py:47: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[None]
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_safe_migrate_guards.py:59: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_raises_only_for_exact_true
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00069/tests/unit/test_safe_migrate_guards.py:64: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  _______________ coverage: platform linux, python 3.12.3-final-0 ________________
  Name                                      Stmts   Miss Branch BrPart  Cover   Missing
  -------------------------------------------------------------------------------------
  dashboard/app.py                            117     45     20      0    53%   64-84, 125-127, 134-138, 141-163, 171, 179
  dashboard/dependencies.py                    21     14      2      0    30%   18-22, 26-38, 47-53
  dashboard/middlewares/alembic_guard.py       36      9      8      0    70%   67-70, 78-83
  dashboard/routers/_run_helpers.py            61     24     10      0    52%   24-27, 37-41, 88-112, 117-125, 149-156
  dashboard/routers/actions.py                397    306    108      1    19%   128-137, 142, 151-159, 191->193, 219-230, 258-290, 308-346, 364-380, 399-450, 468-492, 501-512, 531-678, 702-712, 736-757, 771-895, 913-962, 980-989, 1003-1012, 1030-1039, 1048-1134, 1197-1217, 1254-1264, 1278-1288, 1302-1312, 1326-1341
  dashboard/routers/batches.py                181    121     40      0    27%   89-92, 96-104, 108-112, 117-193, 197-236, 251-255, 277-336, 366-369, 388-392, 410-419, 439-444, 458-463
  dashboard/routers/code.py                   138    107     34      0    18%   41-44, 48, 52-56, 60-63, 72-87, 105-189, 212-240, 261-275, 295-328
  dashboard/routers/code_qa.py                179     54     40      4    67%   64-71, 108, 132-135, 172-193, 256-258, 285-322, 342-359, 389-390
  dashboard/routers/code_ui.py                211    121     54      2    38%   41-46, 82-85, 94-156, 176-181, 193-196, 205-250, 263-287, 323-336, 357-390, 429-431, 453, 462-509, 526
  dashboard/routers/containers.py              45     29     10      0    29%   36-47, 59-65, 94-98, 120-137
  dashboard/routers/coverage.py                18      8      2      0    50%   20-22, 31-35
  dashboard/routers/daemon_control.py          65     11     14      5    75%   51, 66, 94, 97->105, 101->97, 121-128
  dashboard/routers/docs.py                   528    440    132      0    13%   30-33, 42-51, 72-80, 99-134, 145-175, 185-246, 262-293, 312-316, 342-379, 384-431, 449-450, 468-483, 504-511, 525-536, 550-563, 578-589, 608-611, 625-644, 658-662, 675-683, 700-715, 737-764, 789-823, 849-852, 859-867, 876-898, 913-931, 945-957, 976-994, 1009-1015, 1035-1042, 1064-1072, 1093-1100, 1121-1129, 1149-1157, 1177-1189, 1212-1226, 1247-1254
  dashboard/routers/docs_global.py             51     38     26      0    17%   27-29, 50-97
  dashboard/routers/healthz.py                 13      5      2      0    53%   23-34
  dashboard/routers/items.py                  556    370    142      0    29%   176-177, 213-216, 275-323, 332-335, 339-347, 352-360, 366-462, 469-491, 500-508, 513-524, 528, 539-547, 551-559, 563-584, 599-600, 616-626, 631-643, 648-652, 656-666, 670-684, 710-757, 761-823, 828-878, 893-901, 926-934, 956-961, 979-994, 1012-1026, 1044-1062, 1079-1086, 1109-1133, 1143-1148, 1166-1171, 1189-1194, 1212-1217, 1234-1241, 1263-1301, 1313-1327
  dashboard/routers/jobs_ui.py                 81     65     16      0    16%   26-29, 43-83, 113-153, 178-192
  dashboard/routers/oss.py                    253    201     50      0    17%   46, 56-69, 78-184, 209-226, 244-252, 268-294, 307-320, 331-342, 353-376, 390-401, 412-415, 436-443, 458-505, 519-550, 565-582, 591-627, 640-683, 691-694
  dashboard/routers/project_dashboard.py       87     46      8      0    43%   82-85, 90-150, 154-162, 175, 190-191, 206-237, 251-259
  dashboard/routers/project_pages.py           95     35     26      7    60%   37-40, 63-109, 154->159, 155->154, 160->165, 166-170, 173-177, 186-189, 203-206, 227-230, 255-268
  dashboard/routers/projects.py               165    118     34      0    24%   73-126, 139-140, 151-153, 166-171, 176-193, 199-200, 213-253, 259-267, 279-365, 371-395
  dashboard/routers/quality.py                114     84     22      0    22%   43-45, 60-79, 97-101, 118-120, 137-160, 185-230, 242-287, 298-308
  dashboard/routers/research.py                88     66     28      0    19%   27-28, 39-42, 53-62, 86-96, 115-154, 168-200
  dashboard/routers/running.py                107     54     18      0    42%   91-129, 134-190, 195-226, 231-232, 245-249, 268-270, 283-289
  dashboard/routers/search.py                  61     36     14      0    33%   55-109, 127-130, 147-157
  dashboard/routers/sse.py                     78     55     16      0    24%   151-165, 180-275, 280-287, 300
  dashboard/routers/staleness.py              229    179     58      0    17%   80-83, 91-95, 102-108, 113-119, 124, 138-139, 153-166, 176, 198-209, 229-240, 258-268, 286-296, 314-324, 342-355, 384-411, 429-452, 470-493, 523-604
  dashboard/routers/system.py                 156     82     30      1    40%   103, 149-155, 160-190, 194-226, 231-278, 283-290, 295-304, 314-317, 331-334, 348-372
  dashboard/routers/tests.py                  163    112     40      0    25%   45-47, 64-66, 91-115, 133-137, 154-156, 172-174, 192-202, 221-244, 269-328, 339-347, 363-382, 404-409, 426-439, 444
  dashboard/routers/worktrees.py              388    301    126      0    17%   57-80, 99-104, 109-130, 135-140, 145-154, 159-164, 169-178, 186-208, 228-272, 277-289, 340-349, 362-379, 388-525, 541-550, 558-560, 573-575, 585-591, 613-711, 717-731, 745-785, 803-835, 849-906
  dashboard/services/coverage_service.py       96      5     14      2    94%   61-62, 92-93, 116->119, 126
  dashboard/services/oss_accepted.py           58      3     18      3    92%   49, 58->62, 60->59, 87, 92
  dashboard/services/oss_check_catalog.py      28      1      4      1    94%   25
  dashboard/services/oss_service.py           343    249    110      9    26%   49, 65-101, 105-121, 129-187, 195-227, 237-266, 277-319, 328-386, 391-417, 443, 445, 478, 484->487, 491-494, 497-498, 503-533, 543-549, 551, 562-584, 634, 652, 679-705, 725-738, 746-758
  dashboard/utils/batch_progress.py            15     10      4      0    26%   37-73
  dashboard/utils/markdown.py                  44     35     14      0    16%   33-39, 48-49, 53-88
  dashboard/utils/oss_copy.py                  18      3      0      0    83%   290, 301, 308
  dashboard/utils/project_onboarding.py        38      1     14      1    96%   45
  dashboard/utils/timing.py                    52      2      6      2    93%   34, 52, 86->92
  executor/scope_gate.py                       38     38     16      0     0%   25-80
  orch/active_files.py                         16     12      6      0    18%   15-48
  orch/archive/archiver.py                     62     12     28      6    76%   50, 54, 77->76, 79->76, 97-100, 104, 138-153
  orch/archive/batch_archiver.py              122     27     26      5    77%   69-70, 85, 103, 137, 201-203, 213-220, 229-236, 262-265
  orch/archive/extractor.py                    50      2     22      2    94%   88, 91
  orch/batch_planner.py                       297     46    112     16    81%   186->184, 198->191, 203-212, 235, 237-239, 241, 246->245, 327, 333, 338, 347, 352-362, 446->445, 494-497, 512-514, 602, 612->621, 629-647, 656-658
  orch/cli/batch_commands.py                  257    193     86      0    24%   103-105, 109-111, 115-117, 133-222, 242-362, 370-407, 415-464, 469-522, 530-553, 561-586
  orch/cli/daemon_commands.py                 108     40     22      6    63%   85-97, 115, 118, 140->138, 143, 148, 157-228
  orch/cli/db_commands.py                      59     47     12      0    17%   37-54, 63-96
  orch/cli/doc_commands.py                    246    103     92     10    52%   139->145, 141, 149-253, 305, 351, 356, 392, 405, 414, 444-445, 448-449, 461-469, 478-495, 498
  orch/cli/id_commands.py                      42     28      6      0    29%   40-61, 73-82, 96-118
  orch/cli/item_commands.py                   340    243    102      0    26%   139-160, 221-469, 477-521, 529-573, 599-631, 640-763, 802
  orch/cli/lock_commands.py                    79     57     18      0    23%   30-73, 81-114, 121-155
  orch/cli/main.py                             76     10      6      2    83%   59, 63-82
  orch/cli/merge_queue_commands.py             83     23     22      3    68%   84, 90, 100-129, 191-192
  orch/cli/migrations_commands.py             109     32     30      4    67%   86-87, 113-121, 130->132, 135->exit, 140, 179-225
  orch/cli/oss_commands.py                    212    165     68      0    17%   55-91, 100-188, 197-228, 236-249, 260-303, 312-413
  orch/cli/project_commands.py                 35     22      8      0    30%   37-83
  orch/cli/search_commands.py                  47     33     16      0    22%   40-103
  orch/cli/skills_commands.py                 111     92     30      0    13%   19-91, 98-152, 170-208
  orch/cli/step_commands.py                   346    253    124      0    24%   79-80, 137, 164-200, 219-271, 281-384, 409-493, 507-598, 612-699, 714-767, 782-855
  orch/cli/utils.py                            48      9     14      3    77%   47, 64-71, 107
  orch/cli/worktree_commands.py               136    116     58      0    10%   33-61, 66-75, 80-89, 98-125, 145-150, 154-156, 174-320
  orch/config.py                               67      8      2      0    88%   66-74
  orch/daemon/__main__.py                      17     17      2      0     0%   3-32
  orch/daemon/batch_manager.py                489    183    156     20    58%   90-99, 108-141, 145-148, 155, 176-267, 303-304, 365, 379-406, 422-440, 524-544, 578-587, 608-609, 622-687, 699-700, 709-723, 765-802, 854, 876->952, 888->891, 949, 954, 975-990, 1003, 1005, 1048, 1099-1102, 1106-1134, 1137, 1190->1193, 1287
  orch/daemon/batch_merge_hooks.py             28      3     10      2    87%   48-49, 53
  orch/daemon/browser_env.py                  175      7     38      3    95%   139, 173-174, 243->235, 322-328, 488-490
  orch/daemon/container_info.py               156    110     52      0    22%   37-46, 50-60, 85-87, 91-100, 104, 108, 112, 116-122, 127-200, 210-230, 234-264
  orch/daemon/doc_index_poller.py              89     64     20      3    26%   41-42, 49-58, 61-85, 89-147, 155-205, 222-230, 246-249, 252, 255
  orch/daemon/doc_job_poller.py                92      7     14      2    92%   66-67, 103-109, 139-140, 229
  orch/daemon/execution_report.py             265     55     88     13    76%   148-155, 195, 214->226, 227->235, 242, 247-249, 265, 291, 295-302, 310-341, 361-367, 404, 507, 546-559, 575-580
  orch/daemon/fix_cycle.py                    423    326    172      1    20%   98-102, 115-126, 146-162, 176-206, 215-232, 250-381, 399-412, 426-453, 463-489, 505-529, 548-586, 597-620, 627-629, 636-733, 745-764, 769-781, 792-814, 819-848, 853-879, 921-954, 959-969, 1033-1077, 1171-1233, 1242-1244, 1248-1252, 1264-1272, 1288
  orch/daemon/main.py                         324    149     82     15    49%   73-88, 135-139, 143-145, 150-171, 207, 238-239, 273-274, 276->286, 279-283, 316-319, 332-347, 361-401, 405-432, 455-458, 465-466, 490-509, 527, 531, 548-549, 553-556, 560-563, 574-575, 579-580, 589, 595-620, 632-633, 665-666
  orch/daemon/merge_queue.py                  114      9     28      3    92%   62-72, 254->258, 281->exit, 304-313
  orch/daemon/migration_pipeline.py           109     18     20      5    79%   98-100, 112-113, 133-146, 204-211, 245->251, 260, 263-266, 293->299, 303->306, 317->exit
  orch/daemon/migration_rebase.py             215     22     58      8    89%   153->152, 159, 167-168, 177, 201, 211, 227-229, 242, 264-266, 389, 421, 435-436, 494-495, 538-540
  orch/daemon/project_registry.py             139     30     30      3    79%   137-148, 185-186, 205-242, 266-267, 274-275, 292-293, 311->306
  orch/daemon/qv_baseline.py                  124     32     42      7    69%   95, 107, 117-146, 173->167, 206, 219, 246, 251
  orch/daemon/step_monitor.py                 169     16     46      7    87%   196-197, 264->266, 299->302, 343-370, 464->467, 470->472, 507->exit, 509->exit
  orch/daemon/worktree_compose.py             312     72     92     19    76%   127-131, 168, 240-252, 256, 259, 278, 282-286, 308-315, 319-324, 329-336, 357, 375-379, 402, 403->399, 467-468, 476, 483-489, 510, 522-523, 535-547, 569-618, 666-679, 705-741, 754-770
  orch/daemon/worktree_reaper.py               97     16     26      3    83%   76-78, 84, 87-89, 98->96, 104, 124-126, 192-193, 225-227
  orch/db/alembic_guard.py                     63     13     12      0    80%   65-74, 94-97
  orch/db/models.py                           647     12      8      0    97%   172, 520-522, 529-530, 537-538, 1812-1824
  orch/db/safe_migrate.py                     264     94     42      6    65%   206-207, 227-233, 238-240, 279-281, 301-302, 305-307, 318-342, 351-363, 373-404, 411-428, 461, 462->459, 465, 493-513, 539-555, 601-617
  orch/db/session.py                           53     22     12      0    60%   71-80, 85-91, 105-113, 124-132
  orch/diagram/install.py                      11      1      4      1    87%   18
  orch/diagram/render.py                       82     40     26      7    53%   24, 28-29, 33-34, 45, 49-50, 63-96, 106-129
  orch/doc_diff.py                             36      1     10      1    96%   77
  orch/doc_service.py                         414    130    184     38    65%   43-55, 64, 65->60, 74, 106, 110, 131->143, 166, 168->170, 171, 173, 175, 177, 178->180, 180->182, 183, 185, 189-209, 217-220, 237, 239, 241-244, 256-262, 291, 293, 296-297, 320, 349-350, 407-434, 445-451, 490, 507, 516->519, 520-528, 595, 617, 621, 623, 625, 648-649, 665-666, 676-684, 721, 738, 767-802, 863-869, 875-887, 891-901
  orch/evidences.py                            52     36     12      0    25%   28-31, 38-44, 49-55, 78-128
  orch/jobs/aggregator.py                     226     42     84      9    80%   146-153, 176->179, 227, 234-236, 304-323, 365-366, 558-579, 594, 597-599, 616, 632, 647-674, 707-713
  orch/oss/config_writer.py                    34      3      8      1    90%   51, 69-70
  orch/oss/fix_recipes/__init__.py             15      2      2      1    82%   13, 19
  orch/oss/fix_recipes/ci_cd.py               111     24     22      2    79%   14-22, 29-34, 275-307
  orch/oss/fix_recipes/community.py           236     32     70      9    85%   15-20, 31-32, 71, 143-144, 217-218, 300, 555-557, 601-602, 610-634, 645-663
  orch/oss/fix_recipes/contributor.py          53     16     16      3    67%   61-62, 70-94, 105-123
  orch/oss/fix_recipes/governance.py           35      3      6      1    90%   19-20, 58
  orch/oss/fix_recipes/hygiene.py             112     21     40      9    75%   35, 39, 41, 43, 86, 108->107, 136-151, 165, 187
  orch/oss/fix_recipes/internal_refs.py        21      2      4      2    84%   20, 27
  orch/oss/fix_recipes/license_check.py       116     37     34      6    66%   15-20, 31-32, 67-68, 107-108, 116-141, 152-171, 210-211
  orch/oss/fix_recipes/release.py              60      8     18      2    82%   83-92, 150-158
  orch/oss/fix_recipes/secrets.py              48      3     10      1    93%   19-20, 46
  orch/oss/persistence.py                      64     57     24      0     8%   27-102, 106-116, 120-135
  orch/oss/scanner.py                          94     78     18      0    14%   37-45, 72-162, 166-181
  orch/oss/tool_probe.py                       44      4      8      2    88%   47-48, 56, 59
  orch/rag/classifier.py                       26      0      8      2    94%   74->78, 75->74
  orch/rag/config.py                           29      0      2      1    97%   92->94
  orch/rag/doc_indexer.py                     190    190     52      0     0%   8-399
  orch/rag/doc_job.py                         102    102     24      0     0%   6-212
  orch/rag/evidence.py                         41      3     10      2    86%   56-57, 61
  orch/rag/git_log_resolver.py                 34      1     12      1    96%   62
  orch/rag/index_gen.py                       120      6     46      3    95%   37, 48, 82->81, 204-207
  orch/rag/indexer.py                         225    133     76      7    36%   82, 87-94, 96-103, 105-112, 123-133, 144-169, 177-225, 240-291, 301-326, 360-361, 367->373, 391-403, 405->411
  orch/rag/job.py                             183    159     44      0    11%   34-43, 47, 50, 53-170, 179-206, 217-233, 236-259, 267-268, 283-336, 346-366, 377-413
  orch/rag/mapgen.py                          115     66     20      0    39%   139-257, 261-270
  orch/rag/module_gen.py                      148      7     28      3    94%   77, 95->100, 96->95, 171-172, 390-394
  orch/rag/module_progress.py                  61     22     10      1    59%   41, 45-46, 76, 83, 87-88, 96-115
  orch/rag/parser.py                           84      4     36      2    95%   26-27, 106, 131
  orch/rag/qa.py                              334     90    140     12    71%   147-155, 171-173, 335, 353-409, 412-452, 455, 502-517, 561-580, 687->686, 703, 704->706, 715->714, 720->719, 743->742, 747->732
  orch/rag/symbol_gen.py                       72     56     22      0    17%   50-68, 71-91, 96-104, 107-111, 114-116, 119-120, 133-144
  orch/skills/init_project.py                  83      6     14      2    88%   27, 177-181
  orch/skills/sync.py                          83      5     30      4    92%   39, 54->58, 56-57, 89, 93
  orch/skills/sync_agents.py                   39     11      6      1    64%   38-50
  orch/staleness/alembic_check.py              95     14     32      5    85%   98->94, 124, 126, 227-229, 267-278, 287-294, 327->330
  orch/staleness/config.py                     85      1     32      1    98%   48
  orch/staleness/detection.py                 192     51     64     12    75%   41-45, 50-57, 65-66, 75-83, 106-107, 134, 142, 178-179, 194->198, 214, 236-238, 251, 277->275, 308-313, 319, 328-330, 351, 361-363, 390, 394-396, 402, 427->423, 430-431
  orch/staleness/git_lookup.py                 58     15     16      2    77%   78-83, 152-157, 172, 176-177
  orch/staleness/service.py                    94     14     24      1    87%   41-43, 140-145, 178-182, 245-247, 259-261
  orch/test_runner.py                         360    237     70      8    33%   47-48, 54-60, 78, 87->95, 128-162, 169, 185, 208-222, 238-452, 460-485, 495-526, 535-553, 563-570, 589, 628, 640-641, 657-679, 691-700
  orch/utils/log_capture.py                    33      4      8      1    88%   43-46, 58->60
  -------------------------------------------------------------------------------------
  TOTAL                                     17753   8070   4762    381    51%
  24 files skipped due to complete coverage.
  Coverage HTML written to dir tests/output/coverage/htmlcov
  Coverage XML written to file tests/output/coverage/coverage.xml
  Coverage JSON written to file tests/output/coverage/coverage.json
  Required test coverage of 46.0% reached. Total coverage: 51.09%
  make: *** [Makefile:38: test-unit] Error 1
  $ mkdir -p ai-dev/active/F-00069/reports
  (no output)
  ← Write ai-dev/active/F-00069/reports/F-00069_S11_QvGate_report.md
  Wrote file successfully.


## Gate Command

The quality gate that failed runs:
```bash
make test-unit
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
