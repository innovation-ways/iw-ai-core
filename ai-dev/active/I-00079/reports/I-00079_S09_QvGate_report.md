# I-00079 S09 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | unit-tests      |
| Command      | `make test-unit` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 68       |

## Output (tail)

```

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_against_per_worktree_db_when_per_worktree_flag_set
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00079/tests/unit/test_safe_migrate.py:200: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_even_with_per_worktree_flag
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00079/tests/unit/test_safe_migrate.py:213: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_when_only_per_worktree_flag_without_agent_context_is_irrelevant
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00079/tests/unit/test_safe_migrate.py:225: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")

tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_outside_agent_context_without_flag
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00079/tests/unit/test_safe_migrate.py:235: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")

tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[TRUE]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[True]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[1]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[yes]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[YES]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[true\n]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[ true]
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00079/tests/unit/test_safe_migrate_guards.py:47: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context()

tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[]
tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[None]
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00079/tests/unit/test_safe_migrate_guards.py:59: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context()

tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_raises_only_for_exact_true
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00079/tests/unit/test_safe_migrate_guards.py:64: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.12.3-final-0 ________________

Name                                       Stmts   Miss Branch BrPart  Cover   Missing
--------------------------------------------------------------------------------------
dashboard/app.py                             170     55     32      4    59%   78-83, 90-103, 156-157, 174, 186-188, 195-199, 202-224, 240, 248-258, 272-293
dashboard/dependencies.py                     27     14      4      0    42%   34-40, 44-56, 65-71
dashboard/middlewares/alembic_guard.py        36      6      8      1    80%   70, 78-83
dashboard/routers/_run_helpers.py             61     24     10      0    52%   24-27, 37-41, 88-112, 117-125, 149-156
dashboard/routers/actions.py                 502    400    148      1    16%   152-161, 166, 175-183, 215->217, 243-254, 282-314, 332-370, 388-404, 423-474, 492-516, 525-536, 555-720, 744-754, 778-799, 813-937, 961-1022, 1043-1081, 1105-1115, 1133-1142, 1156-1165, 1183-1192, 1214-1311, 1324-1410, 1473-1493, 1530-1540, 1554-1564, 1578-1588, 1602-1617, 1672-1690, 1710-1731
dashboard/routers/batches.py                 263    186     66      0    23%   94-100, 136-182, 186-189, 193-201, 205-209, 219-344, 355-382, 386-428, 443-447, 469-541, 571-574, 593-606, 624-642, 662-667, 681-686
dashboard/routers/code.py                    148    115     36      0    18%   41-44, 48, 52-56, 60-63, 72-87, 109-124, 138-222, 245-273, 294-308, 328-361
dashboard/routers/code_qa.py                 236     97     54      6    56%   67-74, 114, 138-141, 181-202, 277-300, 328-399, 405->443, 410-441, 464-507, 537-538
dashboard/routers/code_ui.py                 214    123     54      2    38%   42-47, 83-88, 97-159, 179-184, 196-199, 208-253, 266-290, 326-339, 360-393, 432-434, 456, 465-512, 529
dashboard/routers/containers.py               45     29     10      0    29%   36-47, 59-65, 94-98, 120-137
dashboard/routers/conversations.py            68     25      8      0    57%   84, 103-128, 140-148, 165-187, 216-238
dashboard/routers/coverage.py                 18      8      2      0    50%   20-22, 31-35
dashboard/routers/daemon_control.py           65     11     14      5    75%   51, 66, 94, 97->105, 101->97, 121-128
dashboard/routers/docs.py                    527    438    138      0    13%   29-32, 41-50, 71-79, 98-133, 144-174, 184-231, 247-278, 297-301, 326-379, 384-431, 449-450, 468-483, 504-511, 525-536, 553-605, 623-636, 651-662, 681-684, 698-717, 731-735, 748-756, 773-788, 810-837, 862-896, 922-925, 932, 941-963, 978-996, 1010-1022, 1041-1059, 1074-1080, 1100-1107, 1129-1137, 1158-1165, 1186-1194, 1214-1222, 1242-1254, 1277-1291, 1312-1319
dashboard/routers/docs_global.py              51     38     26      0    17%   27-29, 50-97
dashboard/routers/healthz.py                  13      5      2      0    53%   23-34
dashboard/routers/help.py                     45     21     12      3    47%   17-22, 75-80, 84-87, 97-99, 112-121
dashboard/routers/items.py                   819    596    238      2    23%   243, 261-309, 318-321, 325-333, 338-346, 352-491, 498-520, 529-537, 542-553, 557, 571, 580-599, 608-625, 652-653, 669-679, 684-696, 701-705, 709-719, 723-752, 778-825, 829-891, 896-946, 968-1084, 1105-1135, 1162-1170, 1192-1222, 1246-1282, 1299-1314, 1332-1346, 1364-1382, 1408-1426, 1431-1459, 1464-1498, 1514-1533, 1559-1592, 1602-1650, 1662-1736, 1754-1778, 1788-1793, 1811-1816, 1834-1839, 1857-1862, 1879-1886, 1908-1946, 1958-1972
dashboard/routers/jobs_ui.py                 218    185     56      0    12%   30-33, 47-70, 91-131, 161-201, 226-251, 281-323, 347-425, 444-445, 467-480
dashboard/routers/keep_alive.py               92     58      8      0    34%   47-52, 77-103, 117-125, 130-138, 143-147, 153-154, 160-172, 178-184, 190-203, 214-216
dashboard/routers/oss.py                     253    201     50      0    17%   46, 56-69, 78-184, 209-226, 244-252, 268-294, 307-320, 331-342, 353-376, 390-401, 412-415, 436-443, 458-505, 519-550, 565-582, 591-627, 640-683, 691-694
dashboard/routers/project_dashboard.py        87     46      8      0    43%   82-85, 90-150, 154-162, 175, 190-191, 206-237, 251-259
dashboard/routers/project_pages.py           103     43     26      7    57%   37-40, 63-109, 154->159, 155->154, 160->165, 166-170, 173-177, 186-189, 203-206, 227-242, 268-281
dashboard/routers/projects.py                165     93     34      2    40%   74, 103, 139-140, 151-153, 166-171, 176-193, 199-200, 213-253, 259-267, 279-365
dashboard/routers/quality.py                 114     84     22      0    22%   43-45, 60-79, 97-101, 118-120, 137-160, 185-230, 242-287, 298-308
dashboard/routers/research.py                 88     66     28      0    19%   27-28, 39-42, 53-62, 86-96, 115-154, 168-200
dashboard/routers/running.py                 107     54     18      0    42%   91-129, 134-190, 195-226, 231-232, 245-249, 268-270, 283-289
dashboard/routers/runtime_overrides.py        68     45     16      0    27%   62-81, 93-101, 105-114, 119-131, 136-145, 162-186, 210-236, 260-292
dashboard/routers/search.py                   61     36     14      0    33%   55-109, 127-130, 147-157
dashboard/routers/sse.py                      78     55     16      0    24%   153-167, 182-277, 282-289, 302
dashboard/routers/staleness.py               229    179     58      0    17%   80-83, 91-95, 102-108, 113-119, 124, 138-139, 153-166, 176, 198-209, 229-240, 258-268, 286-296, 314-324, 342-355, 384-411, 429-452, 470-493, 523-604
dashboard/routers/system.py                  200    104     48      2    41%   107, 153-159, 164-194, 198-230, 235-282, 287-294, 299-308, 318-321, 335-338, 352-376, 424->422, 432-435, 447-473
dashboard/routers/tests.py                   163    112     40      0    25%   45-47, 64-66, 91-115, 133-137, 154-156, 172-174, 192-202, 221-244, 269-328, 339-347, 363-382, 404-409, 426-439, 444
dashboard/routers/usage.py                    18      9      4      0    41%   16-20, 25-28
dashboard/routers/worktrees.py               391    303    126      0    17%   58-81, 100-105, 110-131, 136-141, 146-155, 160-165, 170-179, 187-209, 229-273, 278-290, 343-352, 365-382, 391-541, 557-566, 574-576, 589-591, 601-607, 629-727, 733-747, 761-801, 819-851, 865-922
dashboard/services/coverage_service.py        96      5     14      2    94%   61-62, 92-93, 116->119, 126
dashboard/services/oss_accepted.py            58      3     18      3    92%   49, 58->62, 60->59, 87, 92
dashboard/services/oss_check_catalog.py       28      1      4      1    94%   25
dashboard/services/oss_service.py            397    265    144     15    33%   50, 66-102, 106-122, 130-188, 196-228, 238-267, 278-320, 329-387, 392-418, 444, 446, 479, 485->488, 492-495, 498-499, 504-534, 544-550, 552, 563-585, 635, 653, 680-727, 764, 767-768, 771-772, 803, 807-808, 819->823, 827, 836->839, 844-857, 865-877
dashboard/utils/batch_progress.py             15     10      4      0    26%   37-73
dashboard/utils/markdown.py                  253    176    106      4    28%   50-52, 66-67, 69->60, 78-84, 105-142, 170-265, 277-288, 293-336, 345-368, 378-390, 413-419, 433-436, 440-473
dashboard/utils/oss_copy.py                   18      3      0      0    83%   290, 301, 308
dashboard/utils/project_onboarding.py         38      1     14      1    96%   45
dashboard/utils/timing.py                     52      1      6      2    95%   52, 86->92
executor/scope_gate.py                        38     38     16      0     0%   25-80
orch/active_files.py                          16     12      6      0    18%   15-48
orch/agent_runtime/resolver.py                40      3     16      3    89%   58->74, 77->93, 118, 138, 149
orch/archive/archiver.py                      62     12     28      6    76%   50, 54, 77->76, 79->76, 97-100, 104, 138-153
orch/archive/batch_archiver.py               150     33     38      9    76%   75-76, 91, 109, 154, 214, 224-225, 230->233, 264-269, 280-283, 293-300, 309-316, 342-345
orch/archive/extractor.py                     50      2     22      2    94%   88, 91
orch/batch_planner.py                        307     38    118     17    86%   202->200, 214->207, 226, 228, 233->231, 257, 259-261, 263, 349, 355, 360, 369, 374-384, 468->467, 516-519, 534-536, 624, 634->643, 651-669, 678-680
orch/cli/batch_commands.py                   280    212     94      0    23%   106-108, 112-114, 118-120, 136-227, 257-394, 402-464, 472-521, 526-579, 587-610, 618-643
orch/cli/daemon_commands.py                  108     40     22      6    63%   85-97, 115, 118, 140->138, 143, 148, 157-228
orch/cli/db_commands.py                       59     47     12      0    17%   37-54, 63-96
orch/cli/doc_commands.py                     293    105    106     11    58%   142->148, 144, 152-256, 308, 354, 359, 395, 408, 417, 447-448, 451-452, 464-472, 481-498, 501, 573, 593
orch/cli/id_commands.py                       42     28      6      0    29%   40-61, 73-82, 96-118
orch/cli/item_commands.py                    396    287    120      1    24%   226-247, 308-621, 629-686, 694-743, 769-801, 810-939, 967, 996-1011
orch/cli/lock_commands.py                     79     57     18      0    23%   30-73, 81-114, 121-155
orch/cli/main.py                              79      9      6      1    86%   82-101
orch/cli/merge_queue_commands.py             135     68     42      3    44%   87, 93, 103-132, 194-195, 212-332
orch/cli/migrations_commands.py              109     32     30      4    67%   86-87, 113-121, 130->132, 135->exit, 140, 179-225
orch/cli/oss_commands.py                     212    165     68      0    17%   55-91, 100-188, 197-228, 236-249, 260-303, 312-413
orch/cli/project_commands.py                  35     22      8      0    30%   37-83
orch/cli/search_commands.py                   47     33     16      0    22%   40-103
orch/cli/skills_commands.py                  177    153     52      0    10%   19-91, 98-152, 163-245, 263-301
orch/cli/step_commands.py                    393    291    154      0    22%   172-173, 233, 262-298, 317-371, 399-550, 586-696, 710-804, 818-908, 923-981, 996-1079
orch/cli/utils.py                             48      8     14      2    81%   64-71, 107
orch/cli/worktree_commands.py                136    116     58      0    10%   33-61, 66-75, 80-89, 98-125, 145-150, 154-156, 174-320
orch/config.py                                80      1      8      0    99%   117
orch/daemon/__main__.py                       17     17      2      0     0%   3-32
orch/daemon/batch_manager.py                 633    229    188     26    60%   100-109, 118-151, 155-158, 165, 186-277, 344-345, 394, 395->420, 402-418, 428->384, 437, 449, 463-520, 536-554, 654-679, 718-727, 748-749, 762-827, 839-840, 849-863, 905-942, 994, 1030->1187, 1043->1050, 1114-1180, 1200, 1231-1246, 1259, 1261-1280, 1336, 1387->1393, 1390, 1396-1422, 1478->exit, 1594, 1696->1686
orch/daemon/batch_merge_hooks.py              28      3     10      2    87%   48-49, 53
orch/daemon/browser_env.py                   219     32     60      5    82%   139, 173-174, 243->235, 322-328, 480->471, 485, 537-602, 635-637
orch/daemon/chat_summarization_poller.py      73     14     14      5    78%   85-87, 99-100, 104, 121-122, 133->137, 149->151, 153-155, 171-173
orch/daemon/container_info.py                156    110     52      0    22%   37-46, 50-60, 85-87, 91-100, 104, 108, 112, 116-122, 127-200, 210-230, 234-264
orch/daemon/doc_index_poller.py               89     64     20      3    26%   41-42, 49-58, 61-85, 89-147, 155-205, 222-230, 246-249, 252, 255
orch/daemon/doc_job_poller.py                128      9     26      3    92%   85->87, 98-99, 114-115, 185-191, 221-222, 301
orch/daemon/execution_report.py              360     78    134     12    74%   167-169, 273, 325, 344->356, 357->365, 395, 421, 447, 491-497, 534, 550-551, 647, 670-726, 746-759, 775-780
orch/daemon/fix_cycle.py                     636    458    266      4    26%   123-137, 179-197, 208-219, 247-312, 326-356, 365-382, 400-556, 574-587, 601-628, 648-673, 688-705, 710-715, 742-773, 789-925, 941-965, 984-1022, 1042->1045, 1097-1194, 1206-1225, 1230-1242, 1253-1275, 1294-1336, 1349-1356, 1360-1362, 1367-1378, 1383-1412, 1458->1457, 1500-1501, 1544-1589, 1594-1604, 1705-1707, 1910-2016, 2025-2027, 2031-2035, 2051-2073, 2092-2116, 2127-2135, 2147-2155, 2171, 2204-2205
orch/daemon/keep_alive_poller.py              34     23      6      0    28%   46-54, 58-73, 82-91
orch/daemon/main.py                          347    158     86     16    50%   76-91, 138-142, 146-148, 153-174, 210, 245-246, 280-281, 283->293, 286-290, 323-326, 339-355, 369-409, 413-440, 463-466, 473-474, 498-517, 535, 539, 556-557, 561-564, 568-571, 577-578, 589-590, 594-595, 599-604, 613, 619-644, 656-657, 689-690
orch/daemon/merge_queue.py                   160     18     40      7    88%   88-98, 293-294, 313->332, 349->378, 354->378, 359-375, 406, 456-457, 472-481
orch/daemon/migration_pipeline.py            113     28     22      5    71%   107-109, 121-122, 147-198, 247-254, 288->294, 303, 306-309, 336->342, 346->349, 360->exit
orch/daemon/migration_rebase.py              267     31     74     11    88%   80-81, 160-162, 221->220, 227, 235-236, 245, 269, 279, 295-297, 310, 332-334, 398-399, 457->460, 489-490, 530, 562, 576-577, 635-636, 679-681
orch/daemon/project_registry.py              183     43     46      9    76%   162-167, 189-203, 211-216, 224-229, 237-242, 274-285, 322-323, 342-379, 403-404, 411-412, 429-430, 448->443
orch/daemon/qv_baseline.py                   135     32     44      7    72%   95, 107, 117-146, 206->209, 244, 257, 284, 289
orch/daemon/scope_overlap.py                  76      3     46      3    95%   59, 61, 63
orch/daemon/step_monitor.py                  169     16     46      7    87%   196-197, 264->266, 299->302, 343-370, 464->467, 470->472, 507->exit, 509->exit
orch/daemon/worktree_compose.py              329     79     98     17    76%   85-96, 155-159, 196, 269-281, 285, 288, 307, 311-315, 337-344, 348-353, 358-365, 386, 404-408, 431, 432->428, 504-505, 547, 572-584, 606-655, 704-717, 744-781, 795-811
orch/daemon/worktree_reaper.py               210     91     54      6    55%   100-104, 129-133, 137-139, 147-150, 170-187, 197-242, 253-298, 316-368, 408-410, 416, 419-421, 430->428, 436, 456-458, 524-525, 557-559, 566-567
orch/db/alembic_guard.py                      63     13     12      0    80%   65-74, 94-97
orch/db/models.py                            759     13     12      3    97%   222, 609-611, 619, 626-627, 1558, 1731, 2029-2041
orch/db/safe_migrate.py                      327    137     60      7    57%   221-222, 244-246, 253-255, 294-296, 316-317, 320-322, 333-357, 366-378, 388-419, 426-443, 457-509, 542, 543->540, 546, 574-594, 634-637, 646-661, 679-695, 708-724, 770-786
orch/db/session.py                            53     22     12      0    60%   71-80, 85-91, 105-113, 124-132
orch/design_doc_parser.py                    185      8     94      6    94%   76->79, 108-110, 115->117, 179->171, 262->261, 299-303, 363
orch/diagram/install.py                       11      1      4      1    87%   18
orch/diagram/render.py                        82     40     26      7    53%   24, 28-29, 33-34, 45, 49-50, 63-96, 106-129
orch/diff_service.py                         109     25     38      2    75%   176-183, 185-186, 201-212, 214-215, 226-233, 236-237, 271->275, 311
orch/doc_diff.py                              36      1     10      1    96%   77
orch/doc_report.py                            80      9     32      4    88%   48-49, 55-56, 67, 125-126, 199, 204
orch/doc_service.py                          454    135    210     48    66%   47-59, 68, 69->64, 78, 110, 114, 135->147, 171, 173->175, 176, 178, 180, 182, 184, 185->187, 187->189, 190, 192, 196-216, 224-227, 244, 246, 248-251, 263-269, 298, 300, 303-304, 327, 356-357, 414-441, 452-458, 497, 516, 525->528, 529-537, 541->544, 545->548, 551->556, 562, 564, 570->573, 574, 576, 656, 678, 682, 684, 686, 709-710, 726-727, 737-745, 782, 799, 828-863, 920->924, 932-938, 944-956, 960-970
orch/evidences.py                             52     36     12      0    25%   28-31, 38-44, 49-55, 78-128
orch/jobs/aggregator.py                      234     44     86     10    79%   146-153, 176->179, 227, 234-236, 308-327, 370-372, 595-616, 633->635, 636, 640-643, 660, 682, 697-724, 757-763
orch/keep_alive_service.py                    99     45     20      1    55%   58-67, 72-76, 86, 96-100, 105-110, 115-120, 151-153, 171, 193-203, 208, 237-240, 254-255
orch/llm_usage.py                            144     10     40      1    94%   55, 264-266, 270-272, 283-286
orch/oss/config_writer.py                     34      3      8      1    90%   51, 69-70
orch/oss/fix_recipes/__init__.py              15      2      2      1    82%   13, 19
orch/oss/fix_recipes/ci_cd.py                111     24     22      2    79%   14-22, 29-34, 275-307
orch/oss/fix_recipes/community.py            236     32     70      9    85%   15-20, 31-32, 71, 143-144, 217-218, 300, 555-557, 601-602, 610-634, 645-663
orch/oss/fix_recipes/contributor.py           53     16     16      3    67%   61-62, 70-94, 105-123
orch/oss/fix_recipes/governance.py            35      3      6      1    90%   19-20, 58
orch/oss/fix_recipes/hygiene.py              112     21     40      9    75%   35, 39, 41, 43, 86, 108->107, 136-151, 165, 187
orch/oss/fix_recipes/internal_refs.py         21      2      4      2    84%   20, 27
orch/oss/fix_recipes/license_check.py        116     37     34      6    66%   15-20, 31-32, 67-68, 107-108, 116-141, 152-171, 210-211
orch/oss/fix_recipes/release.py               60      8     18      2    82%   83-92, 150-158
orch/oss/fix_recipes/secrets.py               48      3     10      1    93%   19-20, 46
orch/oss/persistence.py                       64     57     24      0     8%   27-102, 106-116, 120-135
orch/oss/scanner.py                           94     78     18      0    14%   37-45, 72-162, 166-181
orch/oss/tool_probe.py                        44      4      8      2    88%   47-48, 56, 59
orch/qv_gate_validator.py                    122     31     52      4    75%   51, 69, 93-94, 109, 127, 274-337
orch/rag/chat_repo.py                        126     75     38      2    38%   38-67, 92-125, 141-165, 181-222, 258-260, 282-284, 302-319, 353, 365, 394-398
orch/rag/classifier.py                        26      0      8      2    94%   74->78, 75->74
orch/rag/condense.py                          32     10      6      1    66%   87-101
orch/rag/config.py                            29      0      2      1    97%   92->94
orch/rag/doc_indexer.py                      190    190     52      0     0%   8-399
orch/rag/doc_job.py                          102    102     24      0     0%   6-212
orch/rag/evidence.py                          41      3     10      2    86%   56-57, 61
orch/rag/git_log_resolver.py                  34      1     12      1    96%   62
orch/rag/index_gen.py                        120      6     46      3    95%   37, 48, 82->81, 204-207
orch/rag/indexer.py                          225    133     76      7    36%   82, 87-94, 96-103, 105-112, 123-133, 144-169, 177-225, 240-291, 301-326, 360-361, 367->373, 391-403, 405->411
orch/rag/job.py                              183    159     44      0    11%   34-43, 47, 50, 53-170, 179-206, 217-233, 236-259, 267-268, 283-336, 346-366, 377-413
orch/rag/mapgen.py                           127     71     30      1    41%   147-273, 277-286, 390
orch/rag/module_gen.py                       182     21     44      8    85%   98-101, 110-117, 124-125, 141, 144->148, 156->161, 157->156, 162->164, 167->169, 239-240, 470-474
orch/rag/module_progress.py                   61     22     10      1    59%   41, 45-46, 76, 83, 87-88, 96-115
orch/rag/parser.py                            84      4     36      2    95%   26-27, 106, 131
orch/rag/qa.py                               344     93    142     14    71%   124-126, 192-200, 218, 227-229, 397, 415-471, 474-514, 517, 564-579, 625-644, 752->751, 768, 769->771, 780->779, 785->784, 808->807, 812->797
orch/rag/symbol_gen.py                        72     56     22      0    17%   50-68, 71-91, 96-104, 107-111, 114-116, 119-120, 133-144
orch/self_assess.py                           98     13     42     13    81%   79, 84, 88, 92, 97, 102, 113, 123, 127, 131, 138, 142, 198
orch/services/__init__.py                     16     12      4      0    20%   27-69
orch/skills/init_project.py                   83      6     14      2    88%   27, 177-181
orch/skills/sync.py                           83      5     30      4    92%   39, 54->58, 56-57, 89, 93
orch/skills/sync_agents.py                    39     11      6      1    64%   38-50
orch/staleness/alembic_check.py               95     14     32      5    85%   98->94, 124, 126, 227-229, 267-278, 287-294, 327->330
orch/staleness/config.py                      85      1     32      1    98%   48
orch/staleness/detection.py                  192     51     64     12    75%   41-45, 50-57, 65-66, 75-83, 106-107, 134, 142, 178-179, 194->198, 214, 236-238, 251, 277->275, 308-313, 319, 328-330, 351, 361-363, 390, 394-396, 402, 427->423, 430-431
orch/staleness/git_lookup.py                  58     15     16      2    77%   78-83, 152-157, 172, 176-177
orch/staleness/service.py                     94     14     24      1    87%   41-43, 140-145, 178-182, 245-247, 259-261
orch/test_runner.py                          360    229     70     10    36%   47-48, 54-60, 78, 87->95, 128-162, 169, 185, 208-222, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 589, 628, 640-641, 657-679, 691-700
orch/utils/log_capture.py                     33      4      8      1    88%   43-46, 58->60
--------------------------------------------------------------------------------------
TOTAL                                      21840   9858   6158    507    52%

28 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 46.0% reached. Total coverage: 51.59%
= 2744 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings in 63.80s (0:01:03) =
```

## Verdict

```
pass
```
