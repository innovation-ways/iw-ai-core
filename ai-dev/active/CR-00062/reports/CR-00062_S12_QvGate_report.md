# CR-00062 S12 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | unit-tests      |
| Command      | `make test-unit` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 79       |

## Output (tail)

```
    async for token in engine.answer_stream(
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_for_architecture_context
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00062/tests/unit/test_qa_engine.py:913: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    async for token in engine.answer_stream(
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_when_module_filter_nonempty
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00062/tests/unit/test_qa_engine.py:827: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    async for token in engine.answer_stream(
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_translates_dotted_module_path_to_filesystem_filter
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00062/tests/unit/test_qa_engine.py:731: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    async for token in engine.answer_stream(
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/unit/test_code_ui_routes.py::TestCodeIndexStream::test_sse_stream_returns_idle_when_no_runner_in_registry
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00062/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.12.3-final-0 ________________

Name                                       Stmts   Miss Branch BrPart  Cover   Missing
--------------------------------------------------------------------------------------
dashboard/app.py                             240     86     46     11    58%   97, 104, 121-142, 149-154, 161-174, 184-187, 189-192, 241-242, 272-273, 275->280, 276, 297, 309-311, 318-322, 325-347, 354, 371, 379-389, 403-424
dashboard/dependencies.py                     27     14      4      0    42%   34-40, 44-56, 65-71
dashboard/middlewares/alembic_guard.py        36      6      8      1    80%   70, 78-83
dashboard/routers/_run_helpers.py             61     24     10      0    52%   24-27, 37-41, 88-112, 117-125, 149-156
dashboard/routers/actions.py                 605    495    184      1    15%   158-167, 172, 181-189, 221->223, 249-260, 288-320, 338-376, 386-399, 413-421, 449-500, 521-570, 591-607, 626-677, 695-719, 730-747, 766-931, 955-984, 1002-1023, 1037-1161, 1185-1246, 1267-1305, 1329-1339, 1357-1366, 1380-1389, 1407-1416, 1438-1535, 1548-1634, 1698-1737, 1768-1778, 1792-1802, 1816-1826, 1842-1862, 1917-1935, 1955-1976
dashboard/routers/auto_merge_ui.py           177    128     56      0    21%   50-55, 59-62, 66, 70, 74-78, 82-83, 90-104, 123-127, 149-159, 181-243, 258-298, 315-416, 426-432
dashboard/routers/batches.py                 293    210     80      0    22%   97-112, 117-124, 166-235, 246-247, 251-254, 258-266, 270-274, 285-410, 421-448, 452-494, 509-513, 535-607, 637-640, 659-672, 690-708, 728-733, 747-752
dashboard/routers/chat.py                    273    210    110      0    16%   106, 114, 119, 124, 131-136, 153-178, 193-200, 209-211, 221-225, 239-248, 273-285, 295-298, 310-313, 334-423, 428-444, 461-474, 485-506, 520-533, 550-566, 575-593, 602-611
dashboard/routers/code.py                    148    115     36      0    18%   41-44, 48, 52-56, 60-63, 72-87, 109-124, 138-222, 245-273, 294-308, 328-361
dashboard/routers/code_qa.py                 236     97     54      6    56%   67-74, 114, 138-141, 181-202, 277-300, 328-399, 405->443, 410-441, 464-507, 537-538
dashboard/routers/code_ui.py                 236    144     60      2    35%   42-47, 83-88, 116-157, 166-228, 249-254, 266-269, 278-323, 336-360, 397-410, 431-464, 503-505, 527, 536-583, 600
dashboard/routers/containers.py               45     29     10      0    29%   36-47, 59-65, 94-98, 120-137
dashboard/routers/conversations.py            68     25      8      0    57%   84, 103-128, 140-148, 165-187, 216-238
dashboard/routers/coverage.py                 18      8      2      0    50%   20-22, 31-35
dashboard/routers/daemon_control.py           65     11     14      5    75%   51, 66, 94, 97->105, 101->97, 121-128
dashboard/routers/docs.py                    570    479    148      0    13%   44-51, 55-58, 67-76, 97-110, 133-185, 196-268, 278-326, 342-373, 392-396, 421-474, 479-526, 544-545, 563-578, 599-606, 620-631, 648-700, 718-731, 746-757, 776-779, 793-812, 826-830, 843-851, 868-883, 905-932, 957-991, 1017-1020, 1027, 1036-1067, 1082-1107, 1121-1133, 1152-1170, 1185-1191, 1211-1218, 1240-1248, 1269-1276, 1297-1305, 1325-1333, 1353-1365, 1388-1402, 1423-1430
dashboard/routers/docs_global.py              51     38     26      0    17%   27-29, 50-97
dashboard/routers/healthz.py                  13      5      2      0    53%   23-34
dashboard/routers/help.py                     45     21     12      3    47%   17-22, 75-80, 84-87, 97-99, 112-121
dashboard/routers/items.py                   864    636    262      2    22%   249, 267-315, 324-327, 331-339, 344-352, 358-519, 526-548, 557-565, 570-579, 584-595, 599, 613, 622-641, 650-667, 694-695, 711-721, 726-738, 743-747, 751-761, 765-794, 820-867, 871-933, 938-988, 1010-1126, 1147-1180, 1210-1219, 1242-1272, 1296-1332, 1352-1393, 1413-1428, 1446-1460, 1478-1496, 1522-1540, 1545-1573, 1578-1612, 1628-1647, 1673-1706, 1716-1764, 1776-1850, 1868-1892, 1902-1907, 1925-1930, 1948-1953, 1971-1976, 1993-2000, 2022-2060, 2072-2086
dashboard/routers/jobs_ui.py                 218    185     56      0    12%   30-33, 47-70, 91-131, 161-201, 226-251, 281-323, 347-425, 444-445, 467-480
dashboard/routers/keep_alive.py               92     58      8      0    34%   47-52, 77-103, 117-125, 130-138, 143-147, 153-154, 160-172, 178-184, 190-203, 214-216
dashboard/routers/oss.py                     253    201     50      0    17%   46, 56-69, 78-184, 209-226, 244-252, 268-294, 307-320, 331-342, 353-376, 390-401, 412-415, 436-443, 458-505, 519-550, 565-582, 591-627, 640-683, 691-694
dashboard/routers/project_dashboard.py        87     46      8      0    43%   82-85, 90-150, 154-162, 175, 190-191, 206-237, 251-259
dashboard/routers/project_pages.py           107     45     26      7    56%   38-41, 65-114, 159->164, 160->159, 165->170, 171-175, 178-182, 191-194, 208-211, 232-247, 273-286
dashboard/routers/projects.py                165     92     34      1    41%   74, 139-140, 151-153, 166-171, 176-193, 199-200, 213-253, 259-267, 279-365
dashboard/routers/quality.py                 114     84     22      0    22%   43-45, 60-79, 97-101, 118-120, 137-160, 185-230, 242-287, 298-308
dashboard/routers/research.py                 88     66     28      0    19%   27-28, 39-42, 53-62, 86-96, 115-154, 168-200
dashboard/routers/running.py                 116     62     24      0    39%   94-132, 137-207, 212-245, 250-251, 264-268, 287-289, 302-308
dashboard/routers/runtime_overrides.py        88     62     16      0    25%   64-83, 95-103, 107-116, 121-133, 138-147, 152-188, 205-229, 254-282, 313-356
dashboard/routers/search.py                   61     36     14      0    33%   55-109, 127-130, 147-157
dashboard/routers/sse.py                      78     55     16      0    24%   153-167, 182-277, 282-289, 302
dashboard/routers/staleness.py               229    179     58      0    17%   80-83, 91-95, 102-108, 113-119, 124, 138-139, 153-166, 176, 198-209, 229-240, 258-268, 286-296, 314-324, 342-355, 384-411, 429-452, 470-493, 523-604
dashboard/routers/system.py                  200    104     48      2    41%   107, 153-159, 164-194, 198-230, 235-282, 287-294, 299-308, 318-321, 335-338, 352-376, 424->422, 432-435, 447-473
dashboard/routers/tests.py                   163    112     40      0    25%   45-47, 64-66, 91-115, 133-137, 154-156, 172-174, 192-202, 221-244, 269-328, 339-347, 363-382, 404-409, 426-439, 444
dashboard/routers/usage.py                    19     10      4      0    39%   16-20, 25-37
dashboard/routers/worktrees.py               391    303    126      0    17%   58-81, 100-105, 110-131, 136-141, 146-155, 160-165, 170-179, 187-209, 229-273, 278-290, 343-352, 365-382, 391-541, 557-566, 574-576, 589-591, 601-607, 629-727, 733-747, 761-801, 819-851, 865-922
dashboard/services/coverage_service.py        96      5     14      2    94%   61-62, 92-93, 116->119, 126
dashboard/services/oss_accepted.py            58      3     18      3    92%   49, 58->62, 60->59, 87, 92
dashboard/services/oss_check_catalog.py       28      1      4      1    94%   25
dashboard/services/oss_service.py            397    265    144     15    33%   50, 66-102, 106-122, 130-188, 196-228, 238-267, 278-320, 329-387, 392-418, 444, 446, 479, 485->488, 492-495, 498-499, 504-534, 544-550, 552, 563-585, 635, 653, 680-727, 764, 767-768, 771-772, 803, 807-808, 819->823, 827, 836->839, 844-857, 865-877
dashboard/utils/batch_progress.py             15     10      4      0    26%   37-73
dashboard/utils/markdown.py                  256    100    106     23    57%   50-52, 66-67, 69->60, 78-84, 105-142, 178->187, 187->199, 193->199, 197, 208-212, 231-234, 238-239, 248->256, 250, 253->248, 256->264, 261-262, 285-288, 321->324, 347-349, 352-353, 356-357, 368-391, 408, 442, 471-499
dashboard/utils/oss_copy.py                   18      3      0      0    83%   290, 301, 308
dashboard/utils/project_onboarding.py         38      1     14      1    96%   45
dashboard/utils/timing.py                     52      1      6      2    95%   52, 86->92
executor/scope_gate.py                        38     38     16      0     0%   25-80
orch/active_files.py                          24     18      8      0    19%   47, 59-134
orch/agent_runtime/resolver.py                40      3     16      3    89%   58->74, 77->93, 118, 138, 149
orch/archive/archiver.py                      62     12     28      6    76%   50, 54, 77->76, 79->76, 97-100, 104, 138-153
orch/archive/batch_archiver.py               150     33     38      9    76%   75-76, 91, 109, 154, 214, 224-225, 230->233, 264-269, 280-283, 293-300, 309-316, 342-345
orch/archive/extractor.py                     50      2     22      2    94%   88, 91
orch/auto_merge_aggregator.py                190      5     44      5    96%   129, 200->207, 228-229, 400, 430
orch/batch_planner.py                        307     38    118     17    86%   202->200, 214->207, 226, 228, 233->231, 257, 259-261, 263, 349, 355, 360, 369, 374-384, 468->467, 516-519, 534-536, 624, 634->643, 651-669, 678-680
orch/cancel.py                               178     17     62      6    88%   219-226, 234-247, 253->293, 268->290, 279->290, 283, 489-490, 503, 543-548
orch/chat/opencode_client.py                  86      5     22      5    91%   42, 73, 101, 109, 125, 227->exit
orch/chat/opencode_runtime.py                184     29     40     14    80%   97->101, 103->109, 117->exit, 124->129, 141-142, 145->exit, 216, 224-225, 229, 235, 242-244, 263, 266-267, 269-271, 280->exit, 283, 286-289, 292, 294-296, 322-326
orch/chat/relay_manager.py                   136     20     38     10    82%   66, 73->77, 129, 152, 165->exit, 169, 173->175, 182-186, 189-219, 249, 255->exit
orch/cli/batch_commands.py                   311    237    104      0    22%   106-108, 112-114, 118-120, 136-227, 257-394, 402-464, 472-521, 526-579, 587-610, 618-643, 672-719
orch/cli/daemon_commands.py                  108     40     22      6    63%   85-97, 115, 118, 140->138, 143, 148, 157-228
orch/cli/db_commands.py                       59     47     12      0    17%   37-54, 63-96
orch/cli/doc_commands.py                     293    105    106     11    58%   142->148, 144, 152-256, 308, 354, 359, 395, 408, 417, 447-448, 451-452, 464-472, 481-498, 501, 573, 593
orch/cli/id_commands.py                       63     21     12      0    61%   126-132, 148-157, 180-204
orch/cli/item_commands.py                    424    309    124      1    24%   226-247, 308-621, 629-686, 694-743, 769-801, 829-869, 878-1007, 1035, 1064-1079
orch/cli/lock_commands.py                     79     57     18      0    23%   30-73, 81-114, 121-155
orch/cli/main.py                              81      9      6      1    86%   84-103
orch/cli/merge_queue_commands.py             135     68     42      3    44%   87, 93, 103-132, 194-195, 212-332
orch/cli/migrations_commands.py              109     32     30      4    67%   86-87, 113-121, 130->132, 135->exit, 140, 179-225
orch/cli/oss_commands.py                     212    165     68      0    17%   55-91, 100-188, 197-228, 236-249, 260-303, 312-413
orch/cli/project_commands.py                  35     22      8      0    30%   37-83
orch/cli/search_commands.py                   47     33     16      0    22%   40-103
orch/cli/skills_commands.py                  178    154     52      0    10%   19-91, 98-155, 166-248, 266-304
orch/cli/step_commands.py                    393    291    154      0    22%   172-173, 233, 262-298, 317-371, 399-550, 586-696, 710-804, 818-908, 923-981, 996-1079
orch/cli/utils.py                             48      8     14      2    81%   64-71, 107
orch/cli/worktree_commands.py                136    116     58      0    10%   33-61, 66-75, 80-89, 98-125, 145-150, 154-156, 174-320
orch/config.py                                82      1      8      0    99%   117
orch/daemon/__main__.py                       17     17      2      0     0%   3-32
orch/daemon/auto_merge.py                    335     73     84      0    77%   247-250, 430-431, 451-452, 552-553, 570-571, 650-664, 855-1024, 1091-1099, 1109-1119, 1129-1139
orch/daemon/batch_manager.py                 713    277    218     30    57%   100-109, 118-151, 155-158, 165, 186-277, 307-314, 402-403, 452, 454->482, 464-480, 495->442, 504, 516, 530-587, 603-621, 728-753, 792-801, 819-835, 849-878, 937-978, 1001-1002, 1015-1080, 1093, 1102-1116, 1158-1195, 1247, 1283->1440, 1296->1303, 1367-1433, 1454, 1481-1496, 1509, 1511-1530, 1569-1572, 1606, 1657->1663, 1660, 1666-1692, 1748->exit, 1864, 1966->1956
orch/daemon/batch_merge_hooks.py              28      3     10      2    87%   48-49, 53
orch/daemon/browser_env.py                   219     32     60      5    82%   139, 173-174, 243->235, 322-328, 480->471, 485, 537-602, 635-637
orch/daemon/chat_summarization_poller.py      73     14     14      5    78%   85-87, 99-100, 104, 121-122, 133->137, 149->151, 153-155, 171-173
orch/daemon/container_info.py                156    110     52      0    22%   37-46, 50-60, 85-87, 91-100, 104, 108, 112, 116-122, 127-200, 210-230, 234-264
orch/daemon/doc_index_poller.py               89     64     20      3    26%   41-42, 49-58, 61-85, 89-147, 155-205, 222-230, 246-249, 252, 255
orch/daemon/doc_job_poller.py                132      8     30      2    94%   85->87, 98-99, 114-115, 185-191, 221-222
orch/daemon/execution_report.py              360     78    134     12    74%   167-169, 273, 325, 344->356, 357->365, 395, 421, 447, 491-497, 534, 550-551, 647, 670-726, 746-759, 775-780
orch/daemon/fix_cycle.py                     738    539    290      4    26%   68-71, 80, 94-108, 121-133, 142-148, 188-189, 215-270, 367-381, 423-441, 452-463, 491-562, 576-606, 615-632, 650-822, 840-853, 868-895, 915-940, 955-972, 977-982, 1009-1040, 1061-1278, 1294-1318, 1337-1375, 1395->1398, 1450-1547, 1559-1578, 1583-1595, 1606-1628, 1647-1689, 1702-1709, 1713-1715, 1720-1731, 1736-1765, 1811->1810, 1853-1854, 1897-1949, 1954-1964, 2068-2070, 2301-2425, 2434-2436, 2440-2444, 2460-2482, 2501-2525, 2536-2544, 2556-2564, 2580, 2613-2614
orch/daemon/keep_alive_poller.py              34     24      6      0    25%   47-56, 60-75, 85-94
orch/daemon/main.py                          356    160     86     16    50%   78-93, 140-144, 148-150, 155-176, 212, 247-248, 282-283, 285->295, 288-292, 325-328, 341-357, 371-411, 415-442, 465-468, 475-476, 500-519, 537, 541, 555-556, 567-568, 572-575, 579-582, 588-589, 600-601, 605-606, 610-615, 624, 630-655, 667-668, 700-701
orch/daemon/merge_queue.py                   190     42     50      9    77%   89-99, 294-295, 314->333, 349->378, 354->378, 359-375, 406, 456-457, 474-477, 484-561, 580-589
orch/daemon/migration_pipeline.py            113     28     22      5    71%   107-109, 121-122, 147-198, 247-254, 288->294, 303, 306-309, 336->342, 346->349, 360->exit
orch/daemon/migration_rebase.py              267     31     74     11    88%   80-81, 160-162, 221->220, 227, 235-236, 245, 269, 279, 295-297, 310, 332-334, 398-399, 457->460, 489-490, 530, 562, 576-577, 635-636, 679-681
orch/daemon/project_registry.py              256     48     88     12    81%   182, 198-203, 225-239, 247-252, 260-265, 273-278, 312-323, 405-408, 433-437, 487-488, 507-544, 568-569, 576-577, 594-595, 613->608
orch/daemon/qv_baseline.py                   135     32     44      7    72%   95, 107, 117-146, 206->209, 244, 257, 284, 289
orch/daemon/scope_amendment.py                90      6     30      5    91%   101, 113->112, 128, 219-220, 224, 231
orch/daemon/scope_overlap.py                 109     12     62      4    91%   95, 97, 99, 122-124, 184->187, 249-253, 269-273
orch/daemon/step_monitor.py                  169     16     46      7    87%   196-197, 264->266, 299->302, 343-370, 464->467, 470->472, 507->exit, 509->exit
orch/daemon/worktree_compose.py              333     82    100     18    75%   85-96, 155-159, 196, 269-281, 285, 288, 307, 311-315, 337-344, 348-353, 358-365, 386, 404-408, 431, 432->428, 504-505, 547, 572-584, 606-655, 703-717, 728-741, 768-805, 819-835
orch/daemon/worktree_reaper.py               210     91     54      6    55%   100-104, 129-133, 137-139, 147-150, 170-187, 197-242, 253-298, 316-368, 408-410, 416, 419-421, 430->428, 436, 456-458, 524-525, 557-559, 566-567
orch/db/alembic_guard.py                      63     13     12      0    80%   65-74, 94-97
orch/db/migrations/env.py                     29      7      6      3    71%   27, 35, 52-61, 107
orch/db/models.py                            786     13     12      3    97%   223, 654-656, 664, 671-672, 1688, 1861, 2159-2171
orch/db/safe_migrate.py                      326    111     58      9    65%   228-229, 251-253, 262, 301-303, 349->352, 355-356, 373-385, 395-426, 433-450, 464-515, 548, 549->546, 552, 580-600, 640-643, 652-667, 685-701, 714-730, 776-792
orch/db/session.py                            53     22     12      0    60%   71-80, 85-91, 105-113, 124-132
orch/design_doc_parser.py                    185      8     94      6    94%   76->79, 108-110, 115->117, 179->171, 262->261, 299-303, 363
orch/diagram/install.py                       11      1      4      1    87%   18
orch/diagram/render.py                        82     19     26      8    73%   22, 31-37, 43, 52-53, 60-61, 96, 103-104, 120-122, 129
orch/diff_service.py                         109     25     38      2    75%   176-183, 185-186, 201-212, 214-215, 226-233, 236-237, 271->275, 311
orch/doc_diff.py                              36      1     10      1    96%   77
orch/doc_report.py                            80      9     32      4    88%   48-49, 55-56, 67, 125-126, 199, 204
orch/doc_service.py                          457    133    212     46    67%   47-59, 68, 69->64, 78, 110, 114, 135->147, 171, 173->175, 176, 178, 180, 182, 184, 185->187, 187->189, 190, 192, 196-216, 224-227, 244, 246, 248-251, 263-269, 298, 300, 303-304, 327, 356-357, 414-441, 452-458, 497, 516, 525->528, 529-537, 541->544, 545->548, 551->556, 562, 564, 570->573, 661, 683, 687, 689, 691, 714-715, 731-732, 742-750, 787, 804, 833-868, 925->929, 937-943, 949-961, 965-975
orch/evidences.py                             52     36     12      0    25%   28-31, 38-44, 49-55, 78-128
orch/jobs/aggregator.py                      234     44     86     10    79%   146-153, 176->179, 227, 234-236, 308-327, 370-372, 595-616, 633->635, 636, 640-643, 660, 682, 697-724, 757-763
orch/keep_alive_service.py                   101     45     20      1    55%   57-66, 71-75, 85, 95-99, 104-109, 114-119, 154-156, 175, 197-207, 212, 241-244, 258-259
orch/llm_usage.py                            197     10     54      1    96%   76, 409-411, 415-417, 434-437
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
orch/skills/sync_agents.py                    43      3      6      1    92%   43, 48-49
orch/staleness/alembic_check.py               95     14     32      5    85%   98->94, 124, 126, 227-229, 267-278, 287-294, 327->330
orch/staleness/config.py                      85      1     32      1    98%   48
orch/staleness/detection.py                  192     51     64     12    75%   41-45, 50-57, 65-66, 75-83, 106-107, 134, 142, 178-179, 194->198, 214, 236-238, 251, 277->275, 308-313, 319, 328-330, 351, 361-363, 390, 394-396, 402, 427->423, 430-431
orch/staleness/git_lookup.py                  58     15     16      2    77%   78-83, 152-157, 172, 176-177
orch/staleness/service.py                     94     14     24      1    87%   41-43, 140-145, 178-182, 245-247, 259-261
orch/test_runner.py                          360    229     70     10    36%   47-48, 54-60, 78, 87->95, 128-162, 169, 185, 208-222, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 589, 628, 640-641, 657-679, 691-700
orch/utils/log_capture.py                     33      4      8      1    88%   43-46, 58->60
--------------------------------------------------------------------------------------
TOTAL                                      24451  10723   6938    591    53%

31 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 50.0% reached. Total coverage: 52.86%
= 3180 passed, 5 skipped, 5 xfailed, 2 xpassed, 46 warnings in 74.73s (0:01:14) =
```

## Verdict

```
pass
```
