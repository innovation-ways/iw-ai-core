# I-00061 S09 QvGate Report

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
tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_raises_when_env_true
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00061/tests/unit/test_safe_migrate.py:33: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context()

tests/unit/test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00061/orch/db/safe_migrate.py:593: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context(live_db_url)

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_when_agent_context
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00061/tests/unit/test_safe_migrate.py:190: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_against_per_worktree_db_when_per_worktree_flag_set
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00061/tests/unit/test_safe_migrate.py:200: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_even_with_per_worktree_flag
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00061/tests/unit/test_safe_migrate.py:213: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_when_only_per_worktree_flag_without_agent_context_is_irrelevant
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00061/tests/unit/test_safe_migrate.py:225: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_outside_agent_context_without_flag
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00061/tests/unit/test_safe_migrate.py:235: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")

tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[TRUE]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[True]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[1]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[yes]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[YES]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[true\n]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[ true]
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00061/tests/unit/test_safe_migrate_guards.py:47: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context()

tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[None]
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00061/tests/unit/test_safe_migrate_guards.py:59: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context()

tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_raises_only_for_exact_true
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00061/tests/unit/test_safe_migrate_guards.py:64: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
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
dashboard/routers/actions.py                468    370    140      1    17%   143-152, 157, 166-174, 206->208, 234-245, 273-305, 323-361, 379-395, 414-465, 483-507, 516-527, 546-693, 717-727, 751-772, 786-910, 939-1000, 1021-1059, 1077-1086, 1100-1109, 1127-1136, 1158-1255, 1268-1354, 1417-1437, 1474-1484, 1498-1508, 1522-1532, 1546-1561, 1616-1634
dashboard/routers/batches.py                231    162     58      0    24%   84-90, 124-170, 174-177, 181-189, 193-197, 207-284, 288-327, 342-346, 368-440, 470-473, 492-505, 523-541, 561-566, 580-585
dashboard/routers/code.py                   148    115     36      0    18%   41-44, 48, 52-56, 60-63, 72-87, 109-124, 138-222, 245-273, 294-308, 328-361
dashboard/routers/code_qa.py                179     54     40      4    67%   64-71, 108, 132-135, 172-193, 256-258, 285-322, 342-359, 389-390
dashboard/routers/code_ui.py                214    123     54      2    38%   42-47, 83-88, 97-159, 179-184, 196-199, 208-253, 266-290, 326-339, 360-393, 432-434, 456, 465-512, 529
dashboard/routers/containers.py              45     29     10      0    29%   36-47, 59-65, 94-98, 120-137
dashboard/routers/coverage.py                18      8      2      0    50%   20-22, 31-35
dashboard/routers/daemon_control.py          65     11     14      5    75%   51, 66, 94, 97->105, 101->97, 121-128
dashboard/routers/docs.py                   528    440    132      0    13%   30-33, 42-51, 72-80, 99-134, 145-175, 185-246, 262-293, 312-316, 342-379, 384-431, 449-450, 468-483, 504-511, 525-536, 550-563, 578-589, 608-611, 625-644, 658-662, 675-683, 700-715, 737-764, 789-823, 849-852, 859-867, 876-898, 913-931, 945-957, 976-994, 1009-1015, 1035-1042, 1064-1072, 1093-1100, 1121-1129, 1149-1157, 1177-1189, 1212-1226, 1247-1254
dashboard/routers/docs_global.py             51     38     26      0    17%   27-29, 50-97
dashboard/routers/healthz.py                 13      5      2      0    53%   23-34
dashboard/routers/items.py                  563    361    146      2    32%   177-178, 214-217, 276-324, 333-336, 340-348, 353-361, 367-463, 470-492, 501-509, 514-525, 529, 543, 552-568, 577-594, 621-622, 638-648, 653-665, 670-674, 678-688, 692-706, 732-779, 783-845, 850-900, 915-923, 948-956, 978-983, 1001-1016, 1034-1048, 1066-1084, 1101-1108, 1131-1155, 1165-1170, 1188-1193, 1211-1216, 1234-1239, 1256-1263, 1285-1323, 1335-1349
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
dashboard/routers/sse.py                     78     55     16      0    24%   153-167, 182-277, 282-289, 302
dashboard/routers/staleness.py              229    179     58      0    17%   80-83, 91-95, 102-108, 113-119, 124, 138-139, 153-166, 176, 198-209, 229-240, 258-268, 286-296, 314-324, 342-355, 384-411, 429-452, 470-493, 523-604
dashboard/routers/system.py                 156     82     30      1    40%   103, 149-155, 160-190, 194-226, 231-278, 283-290, 295-304, 314-317, 331-334, 348-372
dashboard/routers/tests.py                  163    112     40      0    25%   45-47, 64-66, 91-115, 133-137, 154-156, 172-174, 192-202, 221-244, 269-328, 339-347, 363-382, 404-409, 426-439, 444
dashboard/routers/usage.py                   18      9      4      0    41%   16-20, 25-28
dashboard/routers/worktrees.py              391    303    126      0    17%   58-81, 100-105, 110-131, 136-141, 146-155, 160-165, 170-179, 187-209, 229-273, 278-290, 343-352, 365-382, 391-541, 557-566, 574-576, 589-591, 601-607, 629-727, 733-747, 761-801, 819-851, 865-922
dashboard/services/coverage_service.py       96      5     14      2    94%   61-62, 92-93, 116->119, 126
dashboard/services/oss_accepted.py           58      3     18      3    92%   49, 58->62, 60->59, 87, 92
dashboard/services/oss_check_catalog.py      28      1      4      1    94%   25
dashboard/services/oss_service.py           397    265    144     15    33%   50, 66-102, 106-122, 130-188, 196-228, 238-267, 278-320, 329-387, 392-418, 444, 446, 479, 485->488, 492-495, 498-499, 504-534, 544-550, 552, 563-585, 635, 653, 680-727, 764, 767-768, 771-772, 803, 807-808, 819->823, 827, 836->839, 844-857, 865-877
dashboard/utils/batch_progress.py            15     10      4      0    26%   37-73
dashboard/utils/markdown.py                  77     34     30      0    55%   35-41, 50-51, 55-88
dashboard/utils/oss_copy.py                  18      3      0      0    83%   290, 301, 308
dashboard/utils/project_onboarding.py        38      1     14      1    96%   45
dashboard/utils/timing.py                    52      1      6      2    95%   52, 86->92
executor/scope_gate.py                       38     38     16      0     0%   25-80
orch/active_files.py                         16     12      6      0    18%   15-48
orch/archive/archiver.py                     62     12     28      6    76%   50, 54, 77->76, 79->76, 97-100, 104, 138-153
orch/archive/batch_archiver.py              150     33     38      9    76%   70-71, 86, 104, 149, 207, 217-218, 223->226, 257-262, 273-276, 286-293, 302-309, 335-338
orch/archive/extractor.py                    50      2     22      2    94%   88, 91
orch/batch_planner.py                       305     38    116     17    86%   200->198, 212->205, 224, 226, 231->229, 255, 257-259, 261, 347, 353, 358, 367, 372-382, 466->465, 514-517, 532-534, 622, 632->641, 649-667, 676-678
orch/cli/batch_commands.py                  268    203     92      0    23%   104-106, 110-112, 116-118, 134-225, 245-365, 373-435, 443-492, 497-550, 558-581, 589-614
orch/cli/daemon_commands.py                 108     40     22      6    63%   85-97, 115, 118, 140->138, 143, 148, 157-228
orch/cli/db_commands.py                      59     47     12      0    17%   37-54, 63-96
orch/cli/doc_commands.py                    246    103     92     10    52%   139->145, 141, 149-253, 305, 351, 356, 392, 405, 414, 444-445, 448-449, 461-469, 478-495, 498
orch/cli/id_commands.py                      42     28      6      0    29%   40-61, 73-82, 96-118
orch/cli/item_commands.py                   374    275    118      0    24%   142-163, 224-529, 537-590, 598-642, 668-700, 709-832, 871
orch/cli/lock_commands.py                    79     57     18      0    23%   30-73, 81-114, 121-155
orch/cli/main.py                             77     10      6      2    83%   64, 68-87
orch/cli/merge_queue_commands.py            125     59     36      3    48%   86, 92, 102-131, 193-194, 211-303
orch/cli/migrations_commands.py             109     32     30      4    67%   86-87, 113-121, 130->132, 135->exit, 140, 179-225
orch/cli/oss_commands.py                    212    165     68      0    17%   55-91, 100-188, 197-228, 236-249, 260-303, 312-413
orch/cli/project_commands.py                 35     22      8      0    30%   37-83
orch/cli/search_commands.py                  47     33     16      0    22%   40-103
orch/cli/skills_commands.py                 177    153     52      0    10%   19-91, 98-152, 163-245, 263-301
orch/cli/step_commands.py                   376    281    148      0    22%   79-80, 140, 167-203, 222-274, 302-434, 470-579, 593-684, 698-785, 800-853, 868-941
orch/cli/utils.py                            48      9     14      3    77%   47, 64-71, 107
orch/cli/worktree_commands.py               136    116     58      0    10%   33-61, 66-75, 80-89, 98-125, 145-150, 154-156, 174-320
orch/daemon/__main__.py                      17     17      2      0     0%   3-32
orch/daemon/batch_manager.py                545    188    172     25    61%   100-109, 118-151, 155-158, 165, 186-277, 344-345, 394, 395->420, 402-418, 428->384, 437, 449, 463-507, 523-541, 625-645, 679-688, 709-710, 723-788, 800-801, 810-824, 866-903, 955, 977->1062, 990->997, 1055, 1075, 1099-1114, 1127, 1129, 1173, 1224->1230, 1227, 1233-1259, 1315->1318, 1412
orch/daemon/batch_merge_hooks.py             28      3     10      2    87%   48-49, 53
orch/daemon/browser_env.py                  192      8     46      5    95%   139, 173-174, 243->235, 322-328, 480->471, 485, 519-521
orch/daemon/container_info.py               156    110     52      0    22%   37-46, 50-60, 85-87, 91-100, 104, 108, 112, 116-122, 127-200, 210-230, 234-264
orch/daemon/doc_index_poller.py              89     64     20      3    26%   41-42, 49-58, 61-85, 89-147, 155-205, 222-230, 246-249, 252, 255
orch/daemon/doc_job_poller.py                93      7     14      2    92%   70-71, 107-113, 143-144, 233
orch/daemon/execution_report.py             339     68    120     11    77%   167-169, 292, 311->323, 324->332, 362, 388, 414, 458-464, 501, 517-518, 614, 637-683, 703-716, 732-737
orch/daemon/fix_cycle.py                    468    312    194      4    32%   98-102, 115-126, 149-169, 183-213, 222-239, 257-388, 406-419, 433-460, 470-496, 512-536, 555-593, 613->616, 668-765, 777-796, 801-813, 824-846, 851-880, 885-911, 957->956, 999-1000, 1043-1088, 1093-1103, 1204-1206, 1377-1439, 1448-1450, 1454-1458, 1470-1478, 1494
orch/daemon/keep_alive_poller.py             34     23      6      0    28%   46-54, 58-73, 82-91
orch/daemon/main.py                         335    153     86     16    50%   74-89, 136-140, 144-146, 151-172, 208, 241-242, 276-277, 279->289, 282-286, 319-322, 335-351, 365-405, 409-436, 468-470, 494-513, 531, 535, 552-553, 557-560, 564-567, 578-579, 583-584, 588-593, 602, 608-633, 645-646, 678-679
orch/daemon/merge_queue.py                  133     13     34      5    89%   73-83, 265-266, 285->289, 312->exit, 333-334, 349-358
orch/daemon/migration_pipeline.py           109     18     20      5    79%   98-100, 112-113, 133-146, 204-211, 245->251, 260, 263-266, 293->299, 303->306, 317->exit
orch/daemon/migration_rebase.py             215     22     58      8    89%   157->156, 163, 171-172, 181, 205, 215, 231-233, 246, 268-270, 393, 425, 439-440, 498-499, 542-544
orch/daemon/project_registry.py             147     32     32      4    79%   133-138, 164-175, 212-213, 232-269, 293-294, 301-302, 319-320, 338->333
orch/daemon/qv_baseline.py                  124     32     42      7    69%   95, 107, 117-146, 173->167, 206, 219, 246, 251
orch/daemon/scope_overlap.py                 70      3     42      3    95%   56, 58, 60
orch/daemon/step_monitor.py                 169     16     46      7    87%   196-197, 264->266, 299->302, 343-370, 464->467, 470->472, 507->exit, 509->exit
orch/daemon/worktree_compose.py             312     72     92     19    76%   127-131, 168, 240-252, 256, 259, 278, 282-286, 308-315, 319-324, 329-336, 357, 375-379, 402, 403->399, 467-468, 476, 483-489, 510, 522-523, 535-547, 569-618, 666-679, 705-741, 754-770
orch/daemon/worktree_reaper.py               97     16     26      3    83%   76-78, 84, 87-89, 98->96, 104, 124-126, 192-193, 225-227
orch/db/alembic_guard.py                     63     13     12      0    80%   65-74, 94-97
orch/db/models.py                           692     13     12      3    97%   177, 538-540, 548, 555-556, 1409, 1582, 1880-1892
orch/db/safe_migrate.py                     264     91     42      6    66%   206-207, 229-231, 238-240, 279-281, 301-302, 305-307, 318-342, 351-363, 373-404, 411-428, 461, 462->459, 465, 493-513, 539-555, 601-617
orch/db/session.py                           53     22     12      0    60%   71-80, 85-91, 105-113, 124-132
orch/design_doc_parser.py                   175      6     88      4    95%   76->79, 154->146, 237->236, 274-278, 338
orch/diagram/install.py                      11      1      4      1    87%   18
orch/diagram/render.py                       82     40     26      7    53%   24, 28-29, 33-34, 45, 49-50, 63-96, 106-129
orch/doc_diff.py                             36      1     10      1    96%   77
orch/doc_service.py                         414    130    184     38    65%   43-55, 64, 65->60, 74, 106, 110, 131->143, 166, 168->170, 171, 173, 175, 177, 178->180, 180->182, 183, 185, 189-209, 217-220, 237, 239, 241-244, 256-262, 291, 293, 296-297, 320, 349-350, 407-434, 445-451, 490, 507, 516->519, 520-528, 595, 617, 621, 623, 625, 648-649, 665-666, 676-684, 721, 738, 767-802, 863-869, 875-887, 891-901
orch/evidences.py                            52     36     12      0    25%   28-31, 38-44, 49-55, 78-128
orch/jobs/aggregator.py                     230     42     86     10    80%   146-153, 176->179, 227, 234-236, 304-323, 365-366, 573-594, 611->613, 614, 617-619, 636, 658, 673-700, 733-739
orch/keep_alive_service.py                   99     45     20      1    55%   58-67, 72-76, 86, 96-100, 105-110, 115-120, 151-153, 171, 193-203, 208, 237-240, 254-255
orch/llm_usage.py                           127      9     32      0    94%   227-229, 233-235, 246-249
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
orch/qv_gate_validator.py                   122     31     52      4    75%   51, 69, 93-94, 109, 127, 274-337
orch/rag/classifier.py                       26      0      8      2    94%   74->78, 75->74
orch/rag/config.py                           29      0      2      1    97%   92->94
orch/rag/doc_indexer.py                     190    190     52      0     0%   8-399
orch/rag/doc_job.py                         102    102     24      0     0%   6-212
orch/rag/evidence.py                         41      3     10      2    86%   56-57, 61
orch/rag/git_log_resolver.py                 34      1     12      1    96%   62
orch/rag/index_gen.py                       120      6     46      3    95%   37, 48, 82->81, 204-207
orch/rag/indexer.py                         225    133     76      7    36%   82, 87-94, 96-103, 105-112, 123-133, 144-169, 177-225, 240-291, 301-326, 360-361, 367->373, 391-403, 405->411
orch/rag/job.py                             183    159     44      0    11%   34-43, 47, 50, 53-170, 179-206, 217-233, 236-259, 267-268, 283-336, 346-366, 377-413
orch/rag/mapgen.py                          127     71     30      1    41%   147-273, 277-286, 390
orch/rag/module_gen.py                      182     21     44      8    85%   98-101, 110-117, 124-125, 141, 144->148, 156->161, 157->156, 162->164, 167->169, 239-240, 470-474
orch/rag/module_progress.py                  61     22     10      1    59%   41, 45-46, 76, 83, 87-88, 96-115
orch/rag/parser.py                           84      4     36      2    95%   26-27, 106, 131
orch/rag/qa.py                              334     90    140     12    71%   147-155, 171-173, 335, 353-409, 412-452, 455, 502-517, 561-580, 687->686, 703, 704->706, 715->714, 720->719, 743->742, 747->732
orch/rag/symbol_gen.py                       72     56     22      0    17%   50-68, 71-91, 96-104, 107-111, 114-116, 119-120, 133-144
orch/self_assess.py                          98     13     42     13    81%   79, 84, 88, 92, 97, 102, 113, 123, 127, 131, 138, 142, 198
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
TOTAL                                     19367   8527   5382    447    53%

25 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 46.0% reached. Total coverage: 52.80%
===== 2524 passed, 2 skipped, 5 xfailed, 1 xpassed, 48 warnings in 51.48s ======
```

## Verdict

```
pass
```
