# I-00082 S11 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | integration-tests      |
| Command      | `make test-integration` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 645       |

## Output (tail)

```
tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00082/tests/integration/test_doc_indexer.py:345: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names()

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00082/tests/integration/test_doc_indexer.py:364: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names()

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00082/tests/integration/test_oss_migration.py:231: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00082/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x78c710b36780> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x78c65675f1a0>
    db_session.flush()

tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00082/tests/integration/test_project_oss_job_migration.py:244: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_sse_events.py::test_event_generator_surfaces_loop_failures_as_error_frame
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00082/.venv/lib/python3.12/site-packages/coverage/collector.py:260: RuntimeWarning: coroutine 'sleep' was never awaited
    if hasattr(tracer, "concur_id_func"):
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.12.3-final-0 ________________

Name                                       Stmts   Miss Branch BrPart  Cover   Missing
--------------------------------------------------------------------------------------
dashboard/app.py                             202     35     38      8    78%   116-121, 127, 133-141, 158-159, 226, 238-240, 250, 257, 265, 269-276, 308-310, 324-345
dashboard/dependencies.py                     27     11      4      1    55%   36, 44-56, 65-71
dashboard/routers/_run_helpers.py             61     12     10      3    76%   37-41, 91-101, 117-125, 151, 154-155
dashboard/routers/actions.py                 532    140    164     17    70%   161, 183, 298->302, 305->307, 440, 493-517, 568, 584-585, 598, 669-676, 757, 800-821, 835-959, 1001, 1010, 1031-1032, 1155-1164, 1178-1187, 1213-1214, 1280->1282, 1282->1285, 1330->1333, 1346-1432, 1592, 1616, 1715-1733
dashboard/routers/batches.py                 263     36     66      9    83%   94-100, 166, 172, 207-209, 321, 415, 484, 512-520, 526-529, 639, 662-667, 681-686
dashboard/routers/chat.py                    190     16     64      9    89%   128-129, 152, 168-171, 329, 352, 366, 391->387, 407, 411->417, 413->411, 433-437
dashboard/routers/code.py                    148      9     36      6    92%   113-114, 158, 255, 259, 305, 345, 352-353
dashboard/routers/code_qa.py                 236     44     54      7    80%   59-60, 67-74, 122-130, 134, 291-292, 296->298, 308->270, 317-326, 351->270, 356-399, 431, 440->443
dashboard/routers/code_ui.py                 236     63     60     15    70%   43->47, 45->47, 65, 70-74, 84, 125->131, 136, 190->192, 219->221, 249-254, 266-269, 278-323, 343-344, 354->359, 397-410, 445-453, 455-459, 461-462, 480-505, 518, 527, 600, 608-616
dashboard/routers/containers.py               45     29     10      0    29%   36-47, 59-65, 94-98, 120-137
dashboard/routers/daemon_control.py           65     43     14      0    28%   34-36, 51, 57-79, 85-105, 111-141
dashboard/routers/docs.py                    570    122    148     34    75%   48, 137, 139, 143-144, 172-181, 200, 202, 206-207, 261-264, 291-292, 312, 347->352, 348->347, 354->359, 479-526, 544-545, 574, 599-606, 620-631, 746-757, 795->800, 797, 804, 807->809, 877, 979, 1047, 1054-1055, 1082-1107, 1125, 1167, 1189, 1215, 1244, 1273, 1301, 1329, 1357, 1363, 1392, 1427
dashboard/routers/docs_global.py              51      8     26      3    75%   54->59, 61-64, 68-71
dashboard/routers/healthz.py                  13      5      2      0    53%   23-34
dashboard/routers/help.py                     45     10     12      3    74%   17-22, 75-80, 84-87
dashboard/routers/items.py                   826    275    240     26    61%   116-143, 158->160, 162->161, 164, 298, 341-347, 561, 580, 582, 592, 608, 617-634, 678-688, 693-705, 710-714, 718-728, 732-761, 798, 812-833, 916, 929-938, 1000-1005, 1013-1015, 1036-1093, 1259-1295, 1318-1322, 1353-1354, 1432, 1435, 1460-1465, 1486-1501, 1506-1509, 1627-1663, 1684-1696, 1711-1713, 1722-1723, 1736-1737, 1743-1746, 1789-1790, 1921-1959, 1971-1985
dashboard/routers/jobs_ui.py                 218     93     56      9    55%   49, 65-66, 68, 101-107, 111-117, 165, 171-177, 181-187, 242-246, 291-292, 301-302, 316-317, 359-425
dashboard/routers/keep_alive.py               92     10      8      2    88%   153-154, 181-184, 193-203
dashboard/routers/oss.py                     253     36     50     10    82%   60-62, 68, 129, 181-182, 464, 483, 523, 609-627, 648-683, 691-694
dashboard/routers/project_dashboard.py        87      1      8      0    99%   224
dashboard/routers/project_pages.py           103      6     26      2    94%   154->159, 160->165, 169-170, 176-177, 238-239
dashboard/routers/projects.py                165     28     34      5    82%   103, 139-140, 151-153, 166-171, 181, 184-185, 186->179, 190-191, 228-230, 240-241, 245-246, 250, 343-346
dashboard/routers/quality.py                 114     72     22      1    32%   76-77, 97-101, 118-120, 137-160, 185-230, 242-287, 298-308
dashboard/routers/research.py                 88     23     28      4    66%   41, 115-154, 173->178, 180-183, 193
dashboard/routers/running.py                 107     30     18      5    66%   106-111, 146, 152-190, 212, 216, 231-232, 283-289
dashboard/routers/search.py                   61     13     14      1    76%   77-80, 147-157
dashboard/routers/sse.py                      78     31     16      3    53%   153-167, 197->exit, 202-255, 260-261, 266, 282-289, 302
dashboard/routers/staleness.py               229     58     58      5    76%   80-83, 91-95, 115, 260-262, 266, 286-296, 314-324, 342-355, 431-433, 437, 472-474, 478, 525-527, 549-554, 579-581
dashboard/routers/system.py                  200     20     48     10    86%   107, 174-194, 263, 268->270, 292->291, 294, 302-307, 424->422, 435, 461, 465
dashboard/routers/tests.py                   163    100     40      1    32%   64-66, 109-113, 133-137, 154-156, 172-174, 192-202, 221-244, 269-328, 339-347, 363-382, 404-409, 426-439, 444
dashboard/routers/usage.py                    19     10      4      0    39%   16-20, 25-37
dashboard/routers/worktrees.py               391    190    126     19    46%   58-81, 102, 122-131, 138, 154, 162, 179, 195, 201, 205->207, 208-209, 229-273, 278-290, 343-352, 373-381, 399->398, 444->447, 451, 460-464, 497-502, 521, 557-566, 601-607, 629-727, 733-747, 761-801, 821, 826->832, 830, 865-922
dashboard/services/coverage_service.py        96     59     14      0    34%   48-52, 56-67, 74-160
dashboard/services/oss_accepted.py            58     13     18      4    64%   43, 48-50, 57-62, 72, 80-81
dashboard/services/oss_check_catalog.py       28      3      4      2    84%   25, 42, 48
dashboard/services/oss_service.py            397    133    144     31    62%   57, 75, 84-85, 120-122, 139, 156-157, 163-164, 204, 240, 249, 278-320, 341-342, 359-387, 394, 397, 405-418, 446, 479, 492-495, 498-499, 504->507, 582->585, 609, 635, 718-719, 761-781, 786, 792, 800-820, 824-837, 850, 852, 854, 856
dashboard/utils/markdown.py                  256     52    106     22    77%   57->78, 66-67, 140-141, 178->187, 187->199, 193->199, 197, 208-212, 231-234, 238-239, 248->256, 250, 253->248, 256->264, 261-262, 285-288, 321->324, 347-349, 352-353, 356-357, 368-391, 408, 496, 520, 526
dashboard/utils/oss_copy.py                   18      3      0      0    83%   290, 301, 308
dashboard/utils/project_onboarding.py         38     12     14      3    63%   22-30, 45, 63, 66
dashboard/utils/timing.py                     52      1      6      2    95%   52, 86->92
dashboard/utils/ttl_cache.py                  52     16      6      1    67%   38, 47-48, 55-56, 59-71
executor/scope_gate.py                        38     38     16      0     0%   25-80
orch/active_files.py                          24      2      8      2    88%   64, 134
orch/agent_runtime/resolver.py                40      1     16      3    93%   58->74, 77->93, 118
orch/archive/archiver.py                      62      3     28      6    90%   50, 54, 63->66, 79->76, 100, 119->exit
orch/archive/batch_archiver.py               150    131     38      0    10%   53-77, 82-200, 212-233, 249-316, 321-345
orch/archive/extractor.py                     50     40     22      0    14%   38-61, 78-99, 112-131
orch/batch_planner.py                        307     52    118     18    79%   142-144, 180, 201-203, 212-215, 219-234, 257, 259-261, 263, 268->267, 349, 355, 360, 369, 374-384, 468->467, 516-519, 534-536, 624, 634->643, 652, 678-680
orch/cancel.py                               178     47     62      8    74%   280-288, 342-368, 377-391, 485->491, 489-490, 499-505, 509, 514, 517-528, 561->575
orch/chat/filters.py                          22      3      8      4    77%   54, 58-59, 63->71, 65->67, 68->71
orch/chat/opencode_client.py                  76     28     20      7    59%   54, 72, 74, 76, 82, 86-93, 96-99, 102-110, 127, 129, 150-153, 175
orch/chat/opencode_runtime.py                184    147     40      0    17%   63-77, 85, 89, 97-118, 122-130, 136-142, 145-148, 156-179, 187-191, 197-211, 215-229, 233-258, 262-271, 280-326
orch/chat/relay_manager.py                   136     23     38      9    80%   66, 73->77, 87, 129, 165->exit, 169, 173->175, 182-186, 189-219, 225-226, 249, 263
orch/cli/batch_commands.py                   311     72    104     13    75%   87->85, 94-95, 201-205, 268-269, 278, 322-323, 358, 391-392, 409, 448, 464, 516, 521, 526-579, 594, 605, 608, 625, 636, 639, 702-703, 708-719
orch/cli/daemon_commands.py                  108     73     22      1    28%   38, 51-55, 78-120, 127-150, 157-228
orch/cli/db_commands.py                       59     47     12      0    17%   37-54, 63-96
orch/cli/doc_commands.py                     293     69    106     15    74%   139-140, 197, 210->212, 213, 215, 220->224, 256, 291, 308, 353->356, 359, 395, 410-411, 417, 447-448, 451-452, 464-472, 478-479, 494, 501, 519-594
orch/cli/id_commands.py                       63     12     12      0    76%   126-132, 148-157, 189-190
orch/cli/item_commands.py                    424     89    124     20    78%   150, 228-233, 236, 246-247, 323, 326-327, 379-380, 396->398, 407-408, 429-436, 516->503, 527-530, 548-549, 606, 650-651, 674, 686, 707, 738, 741, 770, 772, 781, 784, 788-791, 800-801, 854, 860-861, 866-869, 879, 893, 916->921, 948, 988-989, 994-1007, 1022-1050, 1073-1074
orch/cli/lock_commands.py                     79     10     18      6    84%   42, 58, 61, 93, 109, 112, 131, 141-142, 145
orch/cli/main.py                              81      9      6      1    86%   84-103
orch/cli/merge_queue_commands.py             135     67     42      6    45%   54-135, 154-195, 218-219, 257, 262-273, 280, 299->303, 316, 332
orch/cli/migrations_commands.py              109     76     30      0    24%   60-87, 98-140, 158-225
orch/cli/oss_commands.py                     212     91     68     12    51%   62-91, 108, 119, 124-188, 221-223, 243-244, 260-303, 322, 356, 362->377, 371->377, 374-375, 379-380, 407-409
orch/cli/project_commands.py                  35     11      8      1    63%   68-69, 74-83
orch/cli/search_commands.py                   47      4     16      3    89%   69->72, 85-86, 94-95, 101->103
orch/cli/skills_commands.py                  177    138     52      1    17%   19-91, 98-152, 163-245, 275-276, 279-292
orch/cli/step_commands.py                    393    150    154     22    58%   166, 172-173, 175, 195, 204-209, 217-219, 275-276, 282-298, 349->352, 355, 409, 424, 445, 448, 481, 484->486, 491-497, 516-517, 538, 596, 610-626, 638, 639->641, 677, 683, 718, 726, 749, 784, 788-789, 818-908, 923-981, 996-1079
orch/cli/utils.py                             48     23     14      2    47%   22-36, 64-71, 107
orch/cli/worktree_commands.py                136    116     58      0    10%   33-61, 66-75, 80-89, 98-125, 145-150, 154-156, 174-320
orch/config.py                                82     14      8      2    78%   40, 62-66, 89-97
orch/daemon/__main__.py                       17     17      2      0     0%   3-32
orch/daemon/batch_manager.py                 689    217    206     42    68%   100-109, 123-124, 150-151, 165, 204-277, 394, 421, 428->384, 437, 464, 491-497, 500-501, 514, 570-585, 607-686, 707-716, 725-734, 760->768, 793-794, 803-805, 934-935, 960, 976, 981, 985, 1025->1029, 1041, 1047-1049, 1071-1075, 1113, 1167-1178, 1216->1373, 1230-1233, 1287-1288, 1302-1364, 1374, 1406, 1415, 1425-1432, 1521->1524, 1575->1579, 1585->1610, 1586->1585, 1589-1591, 1592->1608, 1664->exit, 1668-1679, 1716->exit, 1771-1795, 1827-1841, 1882->1872, 1903, 1963-2059
orch/daemon/batch_merge_hooks.py              28      3     10      2    87%   48-49, 53
orch/daemon/browser_env.py                   219    179     60      1    15%   76, 94-95, 110-115, 119, 133-139, 148, 152-160, 164-166, 170-174, 188-259, 279-292, 311-331, 364-367, 378-380, 401-455, 465-486, 537-602, 621-680
orch/daemon/chat_summarization_poller.py      73     15     14      4    78%   85-87, 104, 121-122, 133->137, 139-141, 149->151, 153-155, 171-173
orch/daemon/container_info.py                156    110     52      0    22%   37-46, 50-60, 85-87, 91-100, 104, 108, 112, 116-122, 127-200, 210-230, 234-264
orch/daemon/doc_index_poller.py               89      2     20      2    96%   121-126, 143->exit
orch/daemon/doc_job_poller.py                128     31     26      4    72%   49-55, 82-99, 114-115, 147-155, 185-191, 221-222, 301
orch/daemon/execution_report.py              360     82    134     16    72%   152-156, 165-169, 197, 249, 253, 272-273, 276->280, 344->356, 357->365, 421, 447, 495->497, 550-551, 581, 593, 661->663, 670-726, 746-759, 775-780
orch/daemon/fix_cycle.py                     722    247    284     58    61%   352-357, 472, 479, 549, 553, 560, 569-576, 624-627, 741-743, 863, 948-953, 980-1011, 1034-1040, 1127->1240, 1140, 1151-1178, 1270-1276, 1277->1280, 1309, 1315, 1319-1324, 1328-1330, 1346, 1364->1369, 1367, 1369->1372, 1383->1391, 1393-1405, 1414, 1422, 1426, 1441, 1467, 1491, 1496-1499, 1502-1504, 1547-1549, 1564-1566, 1591-1599, 1643-1647, 1649->1657, 1660, 1675-1680, 1686, 1694-1701, 1710, 1723->1733, 1725->1727, 1728, 1736, 1746-1761, 1780, 1782-1783, 1795-1808, 1822-1841, 1881-1882, 1893, 1925-1935, 1950-1970, 2028, 2040->2072, 2153, 2228-2230, 2247-2353, 2362-2364, 2368-2372, 2392-2410, 2465, 2470, 2501-2531, 2541-2542
orch/daemon/keep_alive_poller.py              34     23      6      0    28%   46-54, 58-73, 82-91
orch/daemon/main.py                          347    279     86      3    16%   76-91, 138-142, 146-148, 151, 159->174, 198-221, 229-250, 266-314, 318-335, 339-355, 369-409, 413-440, 458-474, 485-517, 525-604, 612-644, 652-661, 668-670, 673-675, 678-681, 689-690, 700-706, 717-720
orch/daemon/merge_queue.py                   160     41     40     11    73%   166-170, 184->236, 189-233, 236->265, 239-263, 313->332, 349->378, 359-375, 378->exit, 383-406, 420-440, 452->458, 480-481
orch/daemon/migration_pipeline.py            113     46     22      1    56%   121-122, 193-198, 247-254, 286-312, 332-361
orch/daemon/migration_rebase.py              267    100     74     15    62%   66-70, 74-85, 135, 150-166, 182, 191, 194, 219->224, 226->224, 235-236, 239, 245, 260, 269, 280-300, 311-337, 398-399, 428-462, 507-508, 530, 562, 576-577, 635-636, 667-681
orch/daemon/project_registry.py              183     77     46     10    54%   116-118, 129-130, 133-134, 174-179, 189-203, 211-216, 224-229, 237-242, 278-285, 313-315, 322-323, 325->320, 342-379, 403-404, 409-412, 426-459, 464
orch/daemon/qv_baseline.py                   135     56     44      9    53%   95, 107, 110, 117-146, 176-179, 202, 206->209, 213, 238-259, 284, 289
orch/daemon/review_mapping.py                 32      3     12      2    89%   31-33, 38->35, 59->54
orch/daemon/scope_overlap.py                  76      8     46      5    88%   59, 61, 63, 95, 120-123
orch/daemon/state_machine.py                  41     13      2      1    67%   135, 147-148, 161, 166, 171, 176, 181, 186, 191, 196, 201, 206
orch/daemon/step_monitor.py                  169     43     46     13    71%   86, 91, 97-99, 121-123, 131-133, 187, 196-197, 224->239, 239->exit, 242-243, 245, 264->266, 299->302, 348, 360, 369-370, 427-444, 463-492, 509->exit
orch/daemon/worktree_compose.py              333    163    100     25    47%   85-96, 149, 154-159, 189, 196, 202, 205, 269-281, 285, 288, 302-373, 386, 404-408, 416-423, 431, 432->428, 438-445, 450, 453, 502-526, 540-597, 606-655, 676->680, 679, 681-693, 728-741, 768-805, 819-835, 895, 905-906, 935-936, 979-980
orch/daemon/worktree_reaper.py               210    144     54      4    28%   100-104, 113-158, 170-187, 197-242, 253-298, 312-370, 406-410, 416, 419-421, 430->428, 433-436, 456-458, 471-487, 497-569
orch/db/alembic_guard.py                      63     18     12      4    68%   65-74, 83->86, 92-97, 118, 120, 125
orch/db/identity.py                           52      1     16      1    97%   76
orch/db/live_db_guard.py                      47      5     12      3    86%   90-91, 129, 144, 147
orch/db/migrations/env.py                     29      7      6      3    71%   27, 35, 52-61, 107
orch/db/models.py                            767      4     12      3    99%   222, 654, 1775, 2074
orch/db/safe_migrate.py                      327    115     60     17    63%   79, 81, 97-102, 203-211, 221-222, 255, 272-299, 342->345, 366-378, 388-419, 426-443, 472, 474->477, 506-509, 524, 530, 540->555, 543->540, 546, 572, 632->639, 707-749, 762-811, 821
orch/db/session.py                            53     22     12      0    60%   71-80, 85-91, 105-113, 124-132
orch/design_doc_parser.py                    185     16     94     11    88%   76->79, 90->64, 108-110, 113-116, 124, 127, 203, 226, 262->261, 299-303, 335, 363
orch/diagram/install.py                       11     11      4      0     0%   3-22
orch/diagram/render.py                        82     57     26      5    28%   22, 24, 28-29, 33-34, 42-53, 63-96, 101-129, 134-138
orch/diff_service.py                         109     37     38      5    62%   91-102, 105-116, 122-127, 185-186, 201-212, 214-215, 235-240, 271-275, 283
orch/doc_diff.py                              36      1     10      1    96%   77
orch/doc_report.py                            80      9     32      4    88%   48-49, 55-56, 67, 125-126, 133, 199
orch/doc_sections.py                          17      1      4      1    90%   47
orch/doc_service.py                          454     52    210     34    84%   58, 68, 70-78, 176, 178, 184, 186, 190, 298, 303-304, 327, 341->352, 356-357, 414-441, 469, 497, 499, 516, 525->528, 534, 545->548, 551->556, 571, 575-576, 647, 659, 678, 684, 686, 709-710, 733, 740-745, 798->800, 826, 844, 846, 850-851, 920->924
orch/evidences.py                             52      4     12      0    94%   30-31, 54-55
orch/jobs/aggregator.py                      234     51     86     17    74%   146-153, 196, 230-236, 246, 248, 302, 304, 353, 359, 451, 453, 502, 504, 597, 636, 641->644, 658-661, 674-684, 697-724, 750, 752, 757-763
orch/keep_alive_service.py                    99     20     20      4    78%   45, 151-153, 158, 171, 194, 225-240, 251, 254-255
orch/llm_usage.py                            197    165     54      0    13%   74-77, 97-105, 115-125, 138-149, 160-176, 191-202, 207-213, 218-249, 259-268, 294-306, 311-316, 321-326, 344-361, 381-392, 402-429, 434-437
orch/oss/config_writer.py                     34      3      8      1    90%   51, 69-70
orch/oss/fix_recipes/__init__.py              15      2      2      1    82%   13, 23
orch/oss/fix_recipes/ci_cd.py                111     74     22      0    28%   14-22, 26-34, 42-80, 88-92, 103-143, 151-155, 166-188, 196-200, 211-242, 250-254, 265-307, 315
orch/oss/fix_recipes/community.py            236    157     70      2    26%   15-20, 31-32, 71, 96-102, 113-161, 169-173, 184-242, 250-254, 265-326, 334-338, 349-374, 382-386, 397-432, 440-444, 455-504, 512-516, 527-573, 581-585, 596-634, 642-663
orch/oss/fix_recipes/contributor.py           53     36     16      0    25%   18-33, 41-45, 56-94, 102-123
orch/oss/fix_recipes/governance.py            35     22      6      0    32%   12-20, 28-74, 82-86
orch/oss/fix_recipes/hygiene.py              112     86     40      0    17%   22-26, 30-44, 52-70, 78-92, 103-125, 133-151, 162-177, 185-194
orch/oss/fix_recipes/internal_refs.py         21     10      4      0    44%   17-36, 47, 50-52
orch/oss/fix_recipes/license_check.py        116     89     34      0    18%   12-20, 24-32, 45-79, 87-91, 102-141, 149-171, 182-221, 229-233
orch/oss/fix_recipes/release.py               60     38     18      0    28%   17-48, 56-60, 71-119, 127-131, 142-158, 169
orch/oss/fix_recipes/secrets.py               48     29     10      0    33%   12-20, 28-73, 81-84, 95-118, 126-129
orch/oss/persistence.py                       64     19     24      0    69%   32-33, 38-45, 120-135
orch/oss/scanner.py                           94      9     18      6    87%   39, 43, 110->118, 139-147, 168, 177->181
orch/oss/tool_probe.py                        44      5      8      3    85%   47-48, 56, 59, 96
orch/qv_gate_validator.py                    122     37     52     12    63%   51, 57->80, 65-78, 81, 89, 93-94, 105, 109, 115, 125-142, 202, 212-226, 234, 276-277
orch/rag/chat_repo.py                        126     28     38      8    74%   38->41, 46, 51-57, 61-67, 143->146, 188, 234, 240-247, 258-260, 353, 359, 394-398
orch/rag/citation_allowlist.py                28      1      6      1    94%   55->53, 70
orch/rag/classifier.py                        26      4      8      2    71%   74-76, 101
orch/rag/condense.py                          32      5      6      1    84%   73-74, 86, 100-101
orch/rag/doc_indexer.py                      190     10     52      7    93%   142-143, 173->exit, 269, 320-321, 333, 360, 365->368, 386-395
orch/rag/doc_job.py                          102     16     24      5    83%   49, 80-81, 105-115, 120-121, 146, 154-156, 180, 203
orch/rag/evidence.py                          41     12     10      0    57%   54-64, 69
orch/rag/git_log_resolver.py                  34     26     12      0    17%   45-50, 55-84, 92-95
orch/rag/index_gen.py                        120     29     46      9    73%   30, 37, 43-48, 74->97, 80->86, 87->86, 92, 113-120, 140-148, 204-207
orch/rag/indexer.py                          225    115     76      6    41%   59-63, 75-113, 149-153, 185, 212->218, 216->218, 240-291, 304-307, 320-321, 341-411
orch/rag/job.py                              183     56     44     10    66%   50, 59-80, 92, 105-106, 149-152, 159, 197->exit, 202->204, 223, 236-259, 267-268, 291, 298-300, 346-366, 384-387, 401
orch/rag/mapgen.py                           127     22     30     11    78%   173, 189-191, 198, 214, 226-229, 235-237, 243, 248, 279-285, 342, 384, 390
orch/rag/module_gen.py                       182     27     44     14    79%   98-101, 110-117, 124-125, 141, 144->148, 156->161, 157->156, 162->164, 167->169, 181, 183->188, 187, 206, 316-319, 421, 447, 470-474
orch/rag/module_progress.py                   61      5     10      2    90%   41, 45-46, 99, 110
orch/rag/parser.py                            84     14     36      5    84%   22, 26-27, 48->42, 92-96, 100-104, 130
orch/rag/qa.py                               344    158    142     22    48%   55-60, 167-169, 181-184, 192-200, 218, 242-243, 311-320, 330, 346, 374, 383-391, 394-398, 401-406, 437-441, 469, 474-514, 517, 527, 539, 553-561, 564-579, 617-691, 709, 721, 729, 752->751, 766-773, 780->779, 785->784, 789, 791-793, 803->802, 807-828
orch/rag/summarize.py                         19      3      0      0    84%   74-76
orch/rag/symbol_gen.py                        72     56     22      0    17%   50-68, 71-91, 96-104, 107-111, 114-116, 119-120, 133-144
orch/self_assess.py                           98     20     42     18    71%   71, 79, 84, 88, 92, 97, 102, 107, 113, 117, 123, 127, 131, 138, 142, 172, 194-198, 223
orch/skills/init_project.py                   83     10     14      4    81%   27, 30-31, 107, 166, 177-181
orch/skills/sync.py                           83     48     30      4    35%   29-46, 52-57, 89, 92-141, 151->154
orch/skills/sync_agents.py                    39     11      6      1    64%   38-50
orch/staleness/alembic_check.py               95     71     32      0    19%   94-100, 114-126, 144-153, 179-330
orch/staleness/config.py                      85     21     32     10    65%   48, 51-54, 59, 62-74, 118, 122, 128, 176, 222->226, 227->230
orch/staleness/detection.py                  192    164     64      0    11%   41-45, 50-57, 62-66, 75-83, 101-107, 126-153, 170-187, 193-199, 213-257, 270-279, 301-313, 318-345, 350-380, 389-433
orch/staleness/git_lookup.py                  58     45     16      0    18%   57-95, 121-180
orch/staleness/service.py                     94     63     24      0    26%   41-43, 115-124, 132-212, 240-289
orch/test_runner.py                          360    318     70      2    10%   43-224, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 576-582, 587-594, 608-621, 626-632, 640-641, 657-679, 691-700
orch/utils/log_capture.py                     33     20      8      1    34%   36-62
--------------------------------------------------------------------------------------
TOTAL                                      23117   7946   6510    954    62%

28 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 50.0% reached. Total coverage: 61.70%
==== 2464 passed, 32 skipped, 3 xfailed, 167 warnings in 639.85s (0:10:39) =====
```

## Verdict

```
pass
```
