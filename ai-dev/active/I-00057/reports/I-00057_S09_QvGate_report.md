# I-00057 S09 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | unit-tests      |
| Command      | `make test-unit` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 55       |

## Output (tail)

```
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/unit/test_safe_migrate.py:28: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context()

tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_raises_when_env_true
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/unit/test_safe_migrate.py:33: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context()

tests/unit/test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/orch/db/safe_migrate.py:593: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context(live_db_url)

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_when_agent_context
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/unit/test_safe_migrate.py:190: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_against_per_worktree_db_when_per_worktree_flag_set
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/unit/test_safe_migrate.py:200: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_even_with_per_worktree_flag
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/unit/test_safe_migrate.py:213: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_when_only_per_worktree_flag_without_agent_context_is_irrelevant
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/unit/test_safe_migrate.py:225: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_outside_agent_context_without_flag
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/unit/test_safe_migrate.py:235: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")

tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[TRUE]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[True]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[1]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[yes]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[YES]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[true\n]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[ true]
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/unit/test_safe_migrate_guards.py:47: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context()

tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[None]
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/unit/test_safe_migrate_guards.py:59: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context()

tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_raises_only_for_exact_true
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/unit/test_safe_migrate_guards.py:64: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.12.3-final-0 ________________

Name                                      Stmts   Miss Branch BrPart  Cover   Missing
-------------------------------------------------------------------------------------
dashboard/app.py                            119     35     20      2    62%   68, 75-82, 127-129, 136-140, 143-165, 181
dashboard/dependencies.py                    21     10      2      0    48%   26-38, 47-53
dashboard/middlewares/alembic_guard.py       36      6      8      1    80%   70, 78-83
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
dashboard/routers/keep_alive.py              92     58      8      0    34%   47-52, 77-103, 117-125, 130-138, 143-147, 153-154, 160-172, 178-184, 190-203, 214-216
dashboard/routers/oss.py                    253    201     50      0    17%   46, 56-69, 78-184, 209-226, 244-252, 268-294, 307-320, 331-342, 353-376, 390-401, 412-415, 436-443, 458-505, 519-550, 565-582, 591-627, 640-683, 691-694
dashboard/routers/project_dashboard.py       87     46      8      0    43%   82-85, 90-150, 154-162, 175, 190-191, 206-237, 251-259
dashboard/routers/project_pages.py           95     35     26      7    60%   37-40, 63-109, 154->159, 155->154, 160->165, 166-170, 173-177, 186-189, 203-206, 227-230, 255-268
dashboard/routers/projects.py               165     92     34      1    41%   74, 139-140, 151-153, 166-171, 176-193, 199-200, 213-253, 259-267, 279-365
dashboard/routers/quality.py                114     84     22      0    22%   43-45, 60-79, 97-101, 118-120, 137-160, 185-230, 242-287, 298-308
dashboard/routers/research.py                88     66     28      0    19%   27-28, 39-42, 53-62, 86-96, 115-154, 168-200
dashboard/routers/running.py                107     54     18      0    42%   91-129, 134-190, 195-226, 231-232, 245-249, 268-270, 283-289
dashboard/routers/search.py                  61     36     14      0    33%   55-109, 127-130, 147-157
dashboard/routers/sse.py                     78     55     16      0    24%   151-165, 180-275, 280-287, 300
dashboard/routers/staleness.py              229    179     58      0    17%   80-83, 91-95, 102-108, 113-119, 124, 138-139, 153-166, 176, 198-209, 229-240, 258-268, 286-296, 314-324, 342-355, 384-411, 429-452, 470-493, 523-604
dashboard/routers/system.py                 156     82     30      1    40%   103, 149-155, 160-190, 194-226, 231-278, 283-290, 295-304, 314-317, 331-334, 348-372
dashboard/routers/tests.py                  163    112     40      0    25%   45-47, 64-66, 91-115, 133-137, 154-156, 172-174, 192-202, 221-244, 269-328, 339-347, 363-382, 404-409, 426-439, 444
dashboard/routers/usage.py                   18      9      4      0    41%   16-20, 25-28
dashboard/routers/worktrees.py              388    301    126      0    17%   57-80, 99-104, 109-130, 135-140, 145-154, 159-164, 169-178, 186-208, 228-272, 277-289, 340-349, 362-379, 388-525, 541-550, 558-560, 573-575, 585-591, 613-711, 717-731, 745-785, 803-835, 849-906
dashboard/services/coverage_service.py       96      5     14      2    94%   61-62, 92-93, 116->119, 126
dashboard/services/oss_accepted.py           58      3     18      3    92%   49, 58->62, 60->59, 87, 92
dashboard/services/oss_check_catalog.py      28      1      4      1    94%   25
dashboard/services/oss_service.py           343    249    110      9    26%   49, 65-101, 105-121, 129-187, 195-227, 237-266, 277-319, 328-386, 391-417, 443, 445, 478, 484->487, 491-494, 497-498, 503-533, 543-549, 551, 562-584, 634, 652, 679-705, 725-738, 746-758
dashboard/utils/batch_progress.py            15     10      4      0    26%   37-73
dashboard/utils/markdown.py                  44     35     14      0    16%   33-39, 48-49, 53-88
dashboard/utils/oss_copy.py                  18      3      0      0    83%   290, 301, 308
dashboard/utils/project_onboarding.py        38      1     14      1    96%   45
dashboard/utils/timing.py                    52      1      6      2    95%   52, 86->92
executor/scope_gate.py                       38     38     16      0     0%   25-80
orch/active_files.py                         16     12      6      0    18%   15-48
orch/archive/archiver.py                     62     12     28      6    76%   50, 54, 77->76, 79->76, 97-100, 104, 138-153
orch/archive/batch_archiver.py              122     27     26      5    77%   69-70, 85, 103, 137, 201-203, 213-220, 229-236, 262-265
orch/archive/extractor.py                    50      2     22      2    94%   88, 91
orch/batch_planner.py                       299     46    112     15    82%   191->189, 203->196, 208-217, 240, 242-244, 246, 332, 338, 343, 352, 357-367, 451->450, 499-502, 517-519, 607, 617->626, 634-652, 661-663
orch/cli/batch_commands.py                  257    193     86      0    24%   103-105, 109-111, 115-117, 133-222, 242-362, 370-407, 415-464, 469-522, 530-553, 561-586
orch/cli/daemon_commands.py                 108     40     22      6    63%   85-97, 115, 118, 140->138, 143, 148, 157-228
orch/cli/db_commands.py                      59     47     12      0    17%   37-54, 63-96
orch/cli/doc_commands.py                    246    103     92     10    52%   139->145, 141, 149-253, 305, 351, 356, 392, 405, 414, 444-445, 448-449, 461-469, 478-495, 498
orch/cli/id_commands.py                      42     28      6      0    29%   40-61, 73-82, 96-118
orch/cli/item_commands.py                   352    254    110      0    25%   140-161, 222-493, 501-545, 553-597, 623-655, 664-787, 826
orch/cli/lock_commands.py                    79     57     18      0    23%   30-73, 81-114, 121-155
orch/cli/main.py                             77     10      6      2    83%   64, 68-87
orch/cli/merge_queue_commands.py            124     58     36      3    48%   86, 92, 102-131, 193-194, 211-299
orch/cli/migrations_commands.py             109     32     30      4    67%   86-87, 113-121, 130->132, 135->exit, 140, 179-225
orch/cli/oss_commands.py                    212    165     68      0    17%   55-91, 100-188, 197-228, 236-249, 260-303, 312-413
orch/cli/project_commands.py                 35     22      8      0    30%   37-83
orch/cli/search_commands.py                  47     33     16      0    22%   40-103
orch/cli/skills_commands.py                 177    153     52      0    10%   19-91, 98-152, 163-245, 263-301
orch/cli/step_commands.py                   346    253    124      0    24%   79-80, 137, 164-200, 219-271, 281-384, 409-493, 507-598, 612-699, 714-767, 782-855
orch/cli/utils.py                            48      9     14      3    77%   47, 64-71, 107
orch/cli/worktree_commands.py               136    116     58      0    10%   33-61, 66-75, 80-89, 98-125, 145-150, 154-156, 174-320
orch/daemon/__main__.py                      17     17      2      0     0%   3-32
orch/daemon/batch_manager.py                518    177    158     20    61%   91-100, 109-142, 146-149, 156, 177-268, 304-305, 366, 380-407, 423-441, 525-545, 579-588, 609-610, 623-688, 700-701, 710-724, 766-803, 855, 877->962, 890->897, 955, 975, 999-1014, 1027, 1029, 1072, 1123->1129, 1126, 1132-1158, 1214->1217, 1311
orch/daemon/batch_merge_hooks.py             28      3     10      2    87%   48-49, 53
orch/daemon/browser_env.py                  192      8     46      5    95%   139, 173-174, 243->235, 322-328, 480->471, 485, 519-521
orch/daemon/container_info.py               156    110     52      0    22%   37-46, 50-60, 85-87, 91-100, 104, 108, 112, 116-122, 127-200, 210-230, 234-264
orch/daemon/doc_index_poller.py              89     64     20      3    26%   41-42, 49-58, 61-85, 89-147, 155-205, 222-230, 246-249, 252, 255
orch/daemon/doc_job_poller.py                92      7     14      2    92%   66-67, 103-109, 139-140, 229
orch/daemon/execution_report.py             265     55     88     13    76%   148-155, 195, 214->226, 227->235, 242, 247-249, 265, 291, 295-302, 310-341, 361-367, 404, 507, 546-559, 575-580
orch/daemon/fix_cycle.py                    465    309    192      4    32%   98-102, 115-126, 146-162, 176-206, 215-232, 250-381, 399-412, 426-453, 463-489, 505-529, 548-586, 606->609, 661-758, 770-789, 794-806, 817-839, 844-873, 878-904, 950->949, 992-993, 1036-1081, 1086-1096, 1197-1199, 1370-1432, 1441-1443, 1447-1451, 1463-1471, 1487
orch/daemon/keep_alive_poller.py             34     23      6      0    28%   46-54, 58-73, 82-91
orch/daemon/main.py                         335    156     86     16    49%   74-89, 136-140, 144-146, 151-172, 208, 241-242, 276-277, 279->289, 282-286, 319-322, 335-351, 365-405, 409-436, 459-462, 469-470, 494-513, 531, 535, 552-553, 557-560, 564-567, 578-579, 583-584, 588-593, 602, 608-633, 645-646, 678-679
orch/daemon/merge_queue.py                  114      9     28      3    92%   62-72, 254->258, 281->exit, 304-313
orch/daemon/migration_pipeline.py           109     18     20      5    79%   98-100, 112-113, 133-146, 204-211, 245->251, 260, 263-266, 293->299, 303->306, 317->exit
orch/daemon/migration_rebase.py             215     22     58      8    89%   153->152, 159, 167-168, 177, 201, 211, 227-229, 242, 264-266, 389, 421, 435-436, 494-495, 538-540
orch/daemon/project_registry.py             139     30     30      3    79%   137-148, 185-186, 205-242, 266-267, 274-275, 292-293, 311->306
orch/daemon/qv_baseline.py                  124     32     42      7    69%   95, 107, 117-146, 173->167, 206, 219, 246, 251
orch/daemon/step_monitor.py                 169     16     46      7    87%   196-197, 264->266, 299->302, 343-370, 464->467, 470->472, 507->exit, 509->exit
orch/daemon/worktree_compose.py             312     72     92     19    76%   127-131, 168, 240-252, 256, 259, 278, 282-286, 308-315, 319-324, 329-336, 357, 375-379, 402, 403->399, 467-468, 476, 483-489, 510, 522-523, 535-547, 569-618, 666-679, 705-741, 754-770
orch/daemon/worktree_reaper.py               97     16     26      3    83%   76-78, 84, 87-89, 98->96, 104, 124-126, 192-193, 225-227
orch/db/alembic_guard.py                     63     13     12      0    80%   65-74, 94-97
orch/db/models.py                           682     13     10      1    97%   174, 522-524, 531-532, 539-540, 1542, 1840-1852
orch/db/safe_migrate.py                     264     91     42      6    66%   206-207, 229-231, 238-240, 279-281, 301-302, 305-307, 318-342, 351-363, 373-404, 411-428, 461, 462->459, 465, 493-513, 539-555, 601-617
orch/db/session.py                           53     22     12      0    60%   71-80, 85-91, 105-113, 124-132
orch/design_doc_parser.py                   120      6     60      3    93%   58->50, 141->140, 178-182, 242
orch/diagram/install.py                      11      1      4      1    87%   18
orch/diagram/render.py                       82     40     26      7    53%   24, 28-29, 33-34, 45, 49-50, 63-96, 106-129
orch/doc_diff.py                             36      1     10      1    96%   77
orch/doc_service.py                         414    130    184     38    65%   43-55, 64, 65->60, 74, 106, 110, 131->143, 166, 168->170, 171, 173, 175, 177, 178->180, 180->182, 183, 185, 189-209, 217-220, 237, 239, 241-244, 256-262, 291, 293, 296-297, 320, 349-350, 407-434, 445-451, 490, 507, 516->519, 520-528, 595, 617, 621, 623, 625, 648-649, 665-666, 676-684, 721, 738, 767-802, 863-869, 875-887, 891-901
orch/evidences.py                            52     36     12      0    25%   28-31, 38-44, 49-55, 78-128
orch/jobs/aggregator.py                     226     42     84      9    80%   146-153, 176->179, 227, 234-236, 304-323, 365-366, 563-584, 599, 602-604, 621, 643, 658-685, 718-724
orch/keep_alive_service.py                   99     45     20      1    55%   58-67, 72-76, 86, 96-100, 105-110, 115-120, 151-153, 171, 193-203, 208, 237-240, 254-255
orch/llm_usage.py                           139     23     28      4    83%   72, 86-88, 91, 95, 116-127, 246-248, 252-254, 265-268
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
orch/rag/mapgen.py                          117     66     20      0    40%   147-265, 269-278
orch/rag/module_gen.py                      182     21     44      8    85%   98-101, 110-117, 124-125, 141, 144->148, 156->161, 157->156, 162->164, 167->169, 239-240, 470-474
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
orch/test_runner.py                         360    229     70     10    36%   47-48, 54-60, 78, 87->95, 128-162, 169, 185, 208-222, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 589, 628, 640-641, 657-679, 691-700
orch/utils/log_capture.py                    33      4      8      1    88%   43-46, 58->60
-------------------------------------------------------------------------------------
TOTAL                                     18549   8278   4984    406    52%

25 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 46.0% reached. Total coverage: 52.02%
===== 2254 passed, 2 skipped, 5 xfailed, 1 xpassed, 48 warnings in 51.49s ======
```

## Verdict

```
pass
```
