# CR-00061 S10 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | diff-coverage      |
| Command      | `make diff-coverage` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 410       |

## Output (tail)

```
tests/integration/test_doc_indexer.py::TestDocIndexerReindex::test_watermark_none_indexes_all
tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00061/orch/rag/doc_indexer.py:349: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in lancedb_uri.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_skip_null_functional_doc_content
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00061/tests/integration/test_doc_indexer.py:283: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00061/orch/rag/doc_indexer.py:365: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in ldb_uri.table_names():

tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_lock_timeout_failure_under_short_timeout
tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock
tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_self_blocker_failure_when_caller_holds_share_lock
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00061/orch/db/safe_migrate.py:626: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context(live_db_url)

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00061/tests/integration/test_oss_migration.py:231: SAWarning: transaction already deassociated from connection
    transaction.rollback()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.12.3-final-0 ________________

Name                                       Stmts   Miss Branch BrPart  Cover   Missing
--------------------------------------------------------------------------------------
dashboard/app.py                             235     34     46      7    82%   149-154, 166-174, 191-192, 297, 309-311, 321, 328, 336, 340-347, 379-381, 395-416
dashboard/dependencies.py                     27     11      4      1    55%   36, 44-56, 65-71
dashboard/routers/_run_helpers.py             61     12     10      3    76%   37-41, 91-101, 117-125, 151, 154-155
dashboard/routers/actions.py                 532    140    164     17    70%   161, 183, 298->302, 305->307, 440, 493-517, 568, 584-585, 598, 669-676, 757, 800-821, 835-959, 1001, 1010, 1031-1032, 1155-1164, 1178-1187, 1213-1214, 1280->1282, 1282->1285, 1330->1333, 1346-1432, 1592, 1616, 1715-1733
dashboard/routers/auto_merge_ui.py           169     19     54     14    85%   50->55, 54, 61, 77-78, 175, 178->235, 182, 185, 190->207, 203-205, 210, 223, 232-233, 259, 289-290, 330->350, 377-378
dashboard/routers/batches.py                 263     36     66      9    83%   94-100, 166, 172, 207-209, 321, 415, 484, 512-520, 526-529, 639, 662-667, 681-686
dashboard/routers/chat.py                    273     24    110     19    88%   135-136, 159, 175-178, 347, 371, 420, 431, 434, 438, 440, 442->441, 466->474, 469, 471->467, 486, 500, 561, 578->584, 580->578, 593, 607-611
dashboard/routers/code.py                    148      9     36      6    92%   113-114, 158, 255, 259, 305, 345, 352-353
dashboard/routers/code_qa.py                 236     29     54      5    87%   67-74, 291-292, 296->298, 351->270, 356-399, 431, 440->443
dashboard/routers/code_ui.py                 236     40     60     13    79%   43->47, 45->47, 84, 125->131, 136, 190->192, 219->221, 249-254, 266-269, 278-323, 343-344, 354->359, 397-410, 445-453, 455-459, 461-462, 503-505, 527, 600
dashboard/routers/containers.py               45     29     10      0    29%   36-47, 59-65, 94-98, 120-137
dashboard/routers/daemon_control.py           65     11     14      5    75%   51, 66, 94, 97->105, 101->97, 121-128
dashboard/routers/docs.py                    570    122    148     34    75%   48, 137, 139, 143-144, 172-181, 200, 202, 206-207, 261-264, 291-292, 312, 347->352, 348->347, 354->359, 479-526, 544-545, 574, 599-606, 620-631, 746-757, 795->800, 797, 804, 807->809, 877, 979, 1047, 1054-1055, 1082-1107, 1125, 1167, 1189, 1215, 1244, 1273, 1301, 1329, 1357, 1363, 1392, 1427
dashboard/routers/docs_global.py              51      8     26      4    74%   54->59, 61-64, 68-71, 86->88
dashboard/routers/healthz.py                  13      0      2      1    93%   32->34
dashboard/routers/help.py                     45     10     12      3    74%   17-22, 75-80, 84-87
dashboard/routers/items.py                   855    264    256     23    64%   300, 343-349, 558, 578, 597, 609, 625, 634-651, 695-705, 710-722, 727-731, 735-745, 749-778, 815, 829-850, 933, 946-955, 1017-1022, 1030-1032, 1053-1110, 1280-1316, 1403-1407, 1438-1439, 1517, 1520, 1545-1550, 1571-1586, 1591-1594, 1712-1748, 1769-1781, 1796-1798, 1807-1808, 1821-1822, 1828-1831, 1874-1875, 2006-2044, 2056-2070
dashboard/routers/jobs_ui.py                 218     93     56      9    55%   49, 65-66, 68, 101-107, 111-117, 165, 171-177, 181-187, 242-246, 291-292, 301-302, 316-317, 359-425
dashboard/routers/keep_alive.py               92     10      8      2    88%   153-154, 181-184, 193-203
dashboard/routers/oss.py                     253     36     50     10    82%   60-62, 68, 129, 181-182, 464, 483, 523, 609-627, 648-683, 691-694
dashboard/routers/project_dashboard.py        87      1      8      0    99%   224
dashboard/routers/project_pages.py           103      6     26      2    94%   154->159, 160->165, 169-170, 176-177, 238-239
dashboard/routers/projects.py                165     28     34      5    82%   103, 139-140, 151-153, 166-171, 181, 184-185, 186->179, 190-191, 228-230, 240-241, 245-246, 250, 343-346
dashboard/routers/quality.py                 114     72     22      1    32%   76-77, 97-101, 118-120, 137-160, 185-230, 242-287, 298-308
dashboard/routers/research.py                 88     23     28      4    66%   41, 115-154, 173->178, 180-183, 193
dashboard/routers/running.py                 107      9     18      3    89%   107-112, 158->180, 178, 236-237
dashboard/routers/search.py                   61     13     14      1    76%   77-80, 147-157
dashboard/routers/sse.py                      78     31     16      3    53%   153-167, 197->exit, 202-255, 260-261, 266, 282-289, 302
dashboard/routers/staleness.py               229     58     58      5    76%   80-83, 91-95, 115, 260-262, 266, 286-296, 314-324, 342-355, 431-433, 437, 472-474, 478, 525-527, 549-554, 579-581
dashboard/routers/system.py                  200     20     48     10    86%   107, 174-194, 263, 268->270, 292->291, 294, 302-307, 424->422, 435, 461, 465
dashboard/routers/tests.py                   163    100     40      1    32%   64-66, 109-113, 133-137, 154-156, 172-174, 192-202, 221-244, 269-328, 339-347, 363-382, 404-409, 426-439, 444
dashboard/routers/usage.py                    19     10      4      0    39%   16-20, 25-37
dashboard/routers/worktrees.py               391    190    126     19    46%   58-81, 102, 122-131, 138, 154, 162, 179, 195, 201, 205->207, 208-209, 229-273, 278-290, 343-352, 373-381, 399->398, 444->447, 451, 460-464, 497-502, 521, 557-566, 601-607, 629-727, 733-747, 761-801, 821, 826->832, 830, 865-922
dashboard/services/coverage_service.py        96      5     14      2    94%   61-62, 92-93, 116->119, 126
dashboard/services/oss_accepted.py            58      1     18      3    95%   49, 58->62, 60->59
dashboard/services/oss_check_catalog.py       28      1      4      1    94%   25
dashboard/services/oss_service.py            397    107    144     32    70%   75, 84-85, 120-122, 139, 156-157, 163-164, 204, 240, 249, 278-320, 336-337, 341-342, 359-387, 394, 397, 405-418, 446, 479, 492-495, 498-499, 504->507, 582->585, 635, 718-719, 764, 767-768, 771-772, 803, 807-808, 819->823, 827, 836->839, 850, 852, 854, 856
dashboard/utils/markdown.py                  256     50    106     20    78%   57->78, 66-67, 140-141, 178->187, 187->199, 193->199, 197, 208-212, 231-234, 238-239, 248->256, 250, 253->248, 256->264, 261-262, 285-288, 321->324, 347-349, 352-353, 356-357, 368-391, 408, 496
dashboard/utils/oss_copy.py                   18      3      0      0    83%   290, 301, 308
dashboard/utils/project_onboarding.py         38      1     14      1    96%   45
dashboard/utils/timing.py                     52      1      6      2    95%   52, 86->92
executor/scope_gate.py                        38     38     16      0     0%   25-80
orch/active_files.py                          24      2      8      2    88%   64, 134
orch/agent_runtime/resolver.py                40      1     16      3    93%   58->74, 77->93, 118
orch/archive/archiver.py                      62      3     28      4    92%   50, 54, 79->76, 100
orch/archive/batch_archiver.py               150     33     38      9    76%   75-76, 91, 109, 154, 214, 224-225, 230->233, 264-269, 280-283, 293-300, 309-316, 342-345
orch/archive/extractor.py                     50      2     22      2    94%   88, 91
orch/auto_merge_aggregator.py                178      4     38      3    97%   113, 201-202, 397
orch/batch_planner.py                        307     30    118     17    88%   202->200, 214->207, 226, 228, 233->231, 257, 259-261, 263, 349, 355, 360, 369, 374-384, 468->467, 516-519, 534-536, 624, 634->643, 652, 678-680
orch/cancel.py                               178      4     62      0    98%   283, 489-490, 503
orch/chat/opencode_client.py                  86      5     22      4    92%   42, 73, 101, 109, 125
orch/chat/opencode_runtime.py                184     29     40     14    80%   97->101, 103->109, 117->exit, 124->129, 141-142, 145->exit, 216, 224-225, 229, 235, 242-244, 263, 266-267, 269-271, 280->exit, 283, 286-289, 292, 294-296, 322-326
orch/chat/relay_manager.py                   136     19     38      8    83%   66, 73->77, 129, 165->exit, 169, 173->175, 182-186, 189-219, 249
orch/cli/batch_commands.py                   311     70    104     11    76%   201-205, 268-269, 278, 322-323, 358, 391-392, 409, 448, 464, 516, 521, 526-579, 594, 605, 608, 625, 636, 639, 702-703, 708-719
orch/cli/daemon_commands.py                  108     40     22      6    63%   85-97, 115, 118, 140->138, 143, 148, 157-228
orch/cli/db_commands.py                       59     47     12      0    17%   37-54, 63-96
orch/cli/doc_commands.py                     293     23    106     11    90%   197, 210->212, 213, 215, 220->224, 256, 308, 359, 395, 417, 447-448, 451-452, 464-472, 494, 501, 573, 593
orch/cli/id_commands.py                       63     12     12      0    76%   126-132, 148-157, 189-190
orch/cli/item_commands.py                    424     70    124     20    82%   228-233, 236, 246-247, 323, 326-327, 379-380, 396->398, 407-408, 429-436, 516->503, 527-530, 548-549, 606, 650-651, 674, 686, 707, 738, 741, 770, 772, 781, 784, 788-791, 800-801, 854, 860-861, 866-869, 879, 893, 916->921, 948, 988-989, 994-1007, 1035, 1073-1074
orch/cli/lock_commands.py                     79     10     18      6    84%   42, 58, 61, 93, 109, 112, 131, 141-142, 145
orch/cli/main.py                              81      9      6      1    86%   84-103
orch/cli/merge_queue_commands.py             135     35     42      9    69%   87, 93, 103-132, 194-195, 218-219, 257, 262-273, 280, 299->303, 316, 332
orch/cli/migrations_commands.py              109     32     30      4    67%   86-87, 113-121, 130->132, 135->exit, 140, 179-225
orch/cli/oss_commands.py                     212     91     68     12    51%   62-91, 108, 119, 124-188, 221-223, 243-244, 260-303, 322, 356, 362->377, 371->377, 374-375, 379-380, 407-409
orch/cli/project_commands.py                  35     11      8      1    63%   68-69, 74-83
orch/cli/search_commands.py                   47      4     16      3    89%   69->72, 85-86, 94-95, 101->103
orch/cli/skills_commands.py                  177    138     52      1    17%   19-91, 98-152, 163-245, 275-276, 279-292
orch/cli/step_commands.py                    393    141    154     19    61%   172-173, 275-276, 282-298, 349->352, 355, 409, 424, 445, 448, 481, 484->486, 491-497, 516-517, 538, 596, 610-626, 638, 639->641, 677, 683, 718, 726, 749, 784, 788-789, 818-908, 923-981, 996-1079
orch/cli/utils.py                             48      8     14      2    81%   64-71, 107
orch/cli/worktree_commands.py                136    116     58      0    10%   33-61, 66-75, 80-89, 98-125, 145-150, 154-156, 174-320
orch/daemon/__main__.py                       17     17      2      0     0%   3-32
orch/daemon/auto_merge.py                    335     15     84      2    95%   247-250, 430-431, 451-452, 552-553, 570-571, 660->664, 1007-1009
orch/daemon/batch_manager.py                 698    108    210     31    83%   100-109, 123-124, 150-151, 165, 204-277, 394, 428->384, 437, 464, 491-497, 500-501, 514, 661-686, 725-734, 760->768, 793-794, 803-805, 934-935, 960, 976, 981, 985, 1041, 1047-1049, 1113, 1216->1373, 1302-1364, 1429->1435, 1430->1429, 1432, 1506-1509, 1606->1631, 1607->1606, 1610-1612, 1613->1629, 1685->exit, 1801, 1903->1893
orch/daemon/batch_merge_hooks.py              28      3     10      2    87%   48-49, 53
orch/daemon/browser_env.py                   219     32     60      5    82%   139, 173-174, 243->235, 322-328, 480->471, 485, 537-602, 635-637
orch/daemon/chat_summarization_poller.py      73     12     14      4    82%   85-87, 104, 121-122, 133->137, 149->151, 153-155, 171-173
orch/daemon/container_info.py                156    110     52      0    22%   37-46, 50-60, 85-87, 91-100, 104, 108, 112, 116-122, 127-200, 210-230, 234-264
orch/daemon/doc_index_poller.py               89      7     20      2    92%   121-126, 143->exit, 146-147, 183-189
orch/daemon/doc_job_poller.py                128      9     26      3    92%   85->87, 98-99, 114-115, 185-191, 221-222, 301
orch/daemon/execution_report.py              360     69    134      8    78%   167-169, 273, 344->356, 357->365, 421, 447, 495->497, 550-551, 670-726, 746-759, 775-780
orch/daemon/fix_cycle.py                     730    137    286     52    77%   352-357, 472, 479, 549, 553, 560, 569-576, 624-627, 741-743, 863, 948-953, 980-1011, 1034-1040, 1127->1240, 1140, 1151-1178, 1270-1276, 1277->1280, 1309, 1315, 1319-1324, 1328-1330, 1346, 1422, 1426, 1441, 1467, 1491, 1496-1499, 1502-1504, 1547-1549, 1564-1566, 1591-1599, 1643-1647, 1649->1657, 1660, 1675-1680, 1686, 1694-1701, 1710, 1723->1733, 1725->1727, 1728, 1736, 1782->1781, 1824-1825, 1881-1882, 1893, 1925-1935, 2040->2072, 2280, 2292, 2343->2356, 2385-2387, 2391-2395, 2415-2433, 2488, 2493, 2531
orch/daemon/keep_alive_poller.py              34      2      6      0    95%   55-56
orch/daemon/main.py                          356    151     86     16    53%   78-93, 140-144, 148-150, 161->176, 212, 247-248, 282-283, 285->295, 288-292, 325-328, 341-357, 371-411, 415-442, 465-468, 475-476, 500-519, 537, 541, 555-556, 567-568, 572-575, 579-582, 588-589, 600-601, 605-606, 610-615, 624, 630-655, 667-668, 700-701
orch/daemon/merge_queue.py                   190      7     50      3    96%   314->333, 349->378, 359-375, 406, 588-589
orch/daemon/migration_pipeline.py            113     14     22      5    84%   121-122, 193-198, 247-254, 288->294, 303, 306-309, 336->342, 346->349, 360->exit
orch/daemon/migration_rebase.py              267     26     74      6    91%   80-81, 160-162, 235-236, 245, 269, 295-297, 332-334, 398-399, 457->460, 530, 562, 576-577, 635-636, 679-681
orch/daemon/project_registry.py              219     27     66      9    87%   198-212, 220-225, 233-238, 246-251, 287-294, 307-310, 335-339, 389-390, 470-471, 478-479, 496-497, 515->510
orch/daemon/qv_baseline.py                   135     32     44      7    72%   95, 107, 117-146, 206->209, 244, 257, 284, 289
orch/daemon/scope_overlap.py                  70      3     40      3    95%   77, 79, 81
orch/daemon/step_monitor.py                  169      6     46      7    94%   196-197, 264->266, 299->302, 348, 360, 369-370, 464->467, 470->472, 509->exit
orch/daemon/worktree_compose.py              333     79    100     17    76%   85-96, 155-159, 196, 269-281, 285, 288, 307, 311-315, 337-344, 348-353, 358-365, 386, 404-408, 431, 432->428, 504-505, 547, 572-584, 606-655, 728-741, 768-805, 819-835
orch/daemon/worktree_reaper.py               210     91     54      6    55%   100-104, 129-133, 137-139, 147-150, 170-187, 197-242, 253-298, 316-368, 408-410, 416, 419-421, 430->428, 436, 456-458, 524-525, 557-559, 566-567
orch/db/alembic_guard.py                      63      5     12      1    92%   73, 94-97
orch/db/migrations/env.py                     29      7      6      3    71%   27, 35, 52-61, 107
orch/db/models.py                            786      4     12      3    99%   223, 655, 1856, 2155
orch/db/safe_migrate.py                      326     59     58      6    82%   228-229, 262, 301-303, 349->352, 373-385, 395-426, 433-450, 512-515, 549->546, 552, 714-730, 776-792
orch/db/session.py                            53     22     12      0    60%   71-80, 85-91, 105-113, 124-132
orch/design_doc_parser.py                    185      8     94      5    94%   76->79, 108-110, 115->117, 262->261, 299-303, 363
orch/diagram/install.py                       11      1      4      1    87%   18
orch/diagram/render.py                        82     13     26      7    81%   22, 33-34, 43, 52-53, 96, 103-104, 120-122, 129
orch/diff_service.py                         109     18     38      1    82%   185-186, 201-212, 214-215, 236-237, 271->275
orch/doc_diff.py                              36      1     10      1    96%   77
orch/doc_report.py                            80      8     32      3    90%   48-49, 55-56, 67, 125-126, 199
orch/doc_service.py                          454     40    210     24    88%   58, 68, 78, 176, 178, 184, 190, 298, 303-304, 327, 356-357, 414-441, 497, 516, 525->528, 534, 545->548, 551->556, 576, 678, 684, 686, 709-710, 740-745, 844, 846, 850-851, 920->924
orch/evidences.py                             52      4     12      0    94%   30-31, 54-55
orch/jobs/aggregator.py                      234     27     86      6    87%   146-153, 234-236, 597, 636, 641->644, 660, 682, 697-724, 757-763
orch/keep_alive_service.py                   101      9     20      1    92%   154-156, 198, 241-244, 258-259
orch/llm_usage.py                            197     10     54      1    96%   76, 409-411, 415-417, 434-437
orch/oss/config_writer.py                     34      3      8      1    90%   51, 69-70
orch/oss/fix_recipes/__init__.py              15      1      2      1    88%   13
orch/oss/fix_recipes/ci_cd.py                111     24     22      2    79%   14-22, 29-34, 275-307
orch/oss/fix_recipes/community.py            236     32     70      9    85%   15-20, 31-32, 71, 143-144, 217-218, 300, 555-557, 601-602, 610-634, 645-663
orch/oss/fix_recipes/contributor.py           53     16     16      3    67%   61-62, 70-94, 105-123
orch/oss/fix_recipes/governance.py            35      3      6      1    90%   19-20, 58
orch/oss/fix_recipes/hygiene.py              112     21     40      9    75%   35, 39, 41, 43, 86, 108->107, 136-151, 165, 187
orch/oss/fix_recipes/internal_refs.py         21      2      4      2    84%   20, 27
orch/oss/fix_recipes/license_check.py        116     37     34      6    66%   15-20, 31-32, 67-68, 107-108, 116-141, 152-171, 210-211
orch/oss/fix_recipes/release.py               60      8     18      2    82%   83-92, 150-158
orch/oss/fix_recipes/secrets.py               48      3     10      1    93%   19-20, 46
orch/oss/persistence.py                       64     19     24      0    69%   32-33, 38-45, 120-135
orch/oss/scanner.py                           94      9     18      6    87%   39, 43, 110->118, 139-147, 168, 177->181
orch/oss/tool_probe.py                        44      4      8      2    88%   47-48, 56, 59
orch/qv_gate_validator.py                    122      8     52      5    93%   51, 69, 93-94, 109, 127, 276-277
orch/rag/chat_repo.py                        126     18     38      5    84%   38->41, 46, 51-57, 61-67, 143->146, 188, 258-260, 353, 394-398
orch/rag/classifier.py                        26      0      8      2    94%   74->78, 75->74
orch/rag/condense.py                          32      2      6      0    95%   100-101
orch/rag/doc_indexer.py                      190     10     52      7    93%   142-143, 173->exit, 269, 320-321, 333, 360, 365->368, 386-395
orch/rag/doc_job.py                          102     16     24      5    83%   49, 80-81, 105-115, 120-121, 146, 154-156, 180, 203
orch/rag/evidence.py                          41      3     10      2    86%   56-57, 61
orch/rag/git_log_resolver.py                  34      1     12      1    96%   62
orch/rag/index_gen.py                        120      6     46      2    95%   37, 48, 204-207
orch/rag/indexer.py                          225     72     76     13    61%   82, 87-94, 96-103, 105-112, 149-153, 185, 212->218, 216->218, 240-291, 304-307, 320-321, 360-361, 367->373, 391-403, 405->411
orch/rag/job.py                              183     56     44     10    66%   50, 59-80, 92, 105-106, 149-152, 159, 197->exit, 202->204, 223, 236-259, 267-268, 291, 298-300, 346-366, 384-387, 401
orch/rag/mapgen.py                           127     20     30      9    80%   173, 189-191, 198, 214, 226-229, 235-237, 243, 248, 279-285, 390
orch/rag/module_gen.py                       182     19     44      8    85%   98-101, 110-117, 124-125, 141, 144->148, 156->161, 157->156, 162->164, 167->169, 470-474
orch/rag/module_progress.py                   61      5     10      2    90%   41, 45-46, 99, 110
orch/rag/parser.py                            84      2     36      0    98%   26-27
orch/rag/qa.py                               344     66    142     14    77%   192-200, 218, 397, 437-441, 469, 474-514, 517, 564-579, 625-644, 752->751, 768, 769->771, 780->779, 785->784, 808->807, 812->797
orch/rag/symbol_gen.py                        72     56     22      0    17%   50-68, 71-91, 96-104, 107-111, 114-116, 119-120, 133-144
orch/self_assess.py                           98     13     42     13    81%   79, 84, 88, 92, 97, 102, 113, 123, 127, 131, 138, 142, 198
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
TOTAL                                      24100   4792   6792    905    77%

39 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
2662 passed, 34 skipped, 4 xfailed, 2 xpassed, 186 warnings in 330.95s (0:05:30)
uv run coverage xml -o tests/output/coverage/coverage-combined.xml
Wrote XML report to tests/output/coverage/coverage-combined.xml
uv run diff-cover tests/output/coverage/coverage-combined.xml --compare-branch=origin/main --fail-under=90
-------------
Diff Coverage
Diff: origin/main...HEAD, staged and unstaged changes
-------------
No lines with coverage information in this diff.
-------------
```

## Verdict

```
pass
```
