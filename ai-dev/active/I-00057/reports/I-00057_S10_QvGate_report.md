# I-00057 S10 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | integration-tests      |
| Command      | `make test-integration` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 322       |

## Output (tail)

```
    assert table_name in db.table_names(), f"Expected table {table_name} in {db.table_names()}"

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
tests/integration/test_doc_indexer.py::TestDocIndexerReindex::test_watermark_none_indexes_all
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/orch/rag/doc_indexer.py:349: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in lancedb_uri.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/orch/rag/doc_indexer.py:365: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in ldb_uri.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_skip_null_functional_doc_content
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/integration/test_doc_indexer.py:283: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/integration/test_doc_indexer.py:345: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names()

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/integration/test_doc_indexer.py:364: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names()

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/integration/test_oss_migration.py:231: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x72f7ff35fcb0> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x72f769d1c470>
    db_session.flush()

tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00057/tests/integration/test_project_oss_job_migration.py:244: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_step_monitor_lifecycle.py::test_full_lifecycle_emits_single_warn_then_idempotent
  /usr/lib/python3.12/json/encoder.py:249: RuntimeWarning: coroutine 'sleep' was never awaited
    _iterencode = c_make_encoder(
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.12.3-final-0 ________________

Name                                      Stmts   Miss Branch BrPart  Cover   Missing
-------------------------------------------------------------------------------------
dashboard/app.py                            119     20     20      8    77%   68, 74, 75->84, 80-82, 127-129, 139, 146, 151, 154, 158-165, 181
dashboard/dependencies.py                    21     14      2      0    30%   18-22, 26-38, 47-53
dashboard/middlewares/alembic_guard.py       36      5      8      2    84%   70, 79-83
dashboard/routers/_run_helpers.py            61     12     10      3    76%   37-41, 91-101, 117-125, 151, 154-155
dashboard/routers/actions.py                397    195    108      7    47%   136, 158, 273->277, 280->282, 415, 468-492, 501-512, 531-678, 702-712, 736-757, 771-895, 913-962, 980-989, 1003-1012, 1030-1039, 1048-1134, 1280, 1304
dashboard/routers/batches.py                181     29     40      8    80%   110-112, 178, 224, 283, 288-290, 307-315, 321-324, 416, 439-444, 458-463
dashboard/routers/code.py                   138     19     34      5    84%   43, 125, 222, 226, 261-275, 312, 319-320
dashboard/routers/code_qa.py                179     61     40      5    63%   50-54, 56-57, 64-71, 107-112, 116-124, 128, 172-193, 265->249, 270-284, 288->249, 301-322, 389-390
dashboard/routers/code_ui.py                211    109     54      5    43%   41-46, 57-59, 63-73, 77-78, 82-85, 117-120, 145-153, 176-181, 193-196, 205-250, 263-287, 323-336, 371-379, 381-385, 387-388, 406-431, 444, 453, 526, 534-542
dashboard/routers/containers.py              45     29     10      0    29%   36-47, 59-65, 94-98, 120-137
dashboard/routers/coverage.py                18      8      2      0    50%   20-22, 31-35
dashboard/routers/daemon_control.py          65     43     14      0    28%   34-36, 51, 57-79, 85-105, 111-141
dashboard/routers/docs.py                   528    140    132     24    70%   99-134, 145-175, 198-199, 219-227, 240-246, 267->272, 268->267, 274->279, 384-431, 449-450, 479, 504-511, 525-536, 578-589, 627->632, 629, 636, 639->641, 709, 811, 863, 887, 913-931, 949, 991, 1013, 1039, 1068, 1097, 1125, 1153, 1181, 1187, 1216, 1251
dashboard/routers/docs_global.py             51      8     26      3    75%   54->59, 61-64, 68-71
dashboard/routers/healthz.py                 13      5      2      0    53%   23-34
dashboard/routers/items.py                  556    175    142     17    62%   116-143, 158->160, 162->161, 164, 173-206, 216, 311, 354-360, 523, 542, 544, 546, 553-559, 566-583, 616-626, 631-643, 648-652, 656-666, 670-684, 721, 735-756, 839, 852-861, 985-989, 1020-1021, 1131-1132, 1263-1301, 1313-1327
dashboard/routers/jobs_ui.py                 81     25     16      5    69%   53-59, 63-69, 117, 123-129, 133-139
dashboard/routers/keep_alive.py              92     58      8      0    34%   47-52, 77-103, 117-125, 130-138, 143-147, 153-154, 160-172, 178-184, 190-203, 214-216
dashboard/routers/oss.py                    253     36     50     10    82%   60-62, 68, 129, 181-182, 464, 483, 523, 609-627, 648-683, 691-694
dashboard/routers/project_dashboard.py       87      1      8      0    99%   224
dashboard/routers/project_pages.py           95      4     26      2    95%   154->159, 160->165, 169-170, 176-177
dashboard/routers/projects.py               165     30     34      7    80%   91, 103, 115, 139-140, 151-153, 166-171, 181, 184-185, 186->179, 190-191, 228-230, 240-241, 245-246, 250, 343-346
dashboard/routers/quality.py                114     72     22      1    32%   76-77, 97-101, 118-120, 137-160, 185-230, 242-287, 298-308
dashboard/routers/research.py                88     23     28      4    66%   41, 115-154, 173->178, 180-183, 193
dashboard/routers/running.py                107     30     18      5    66%   106-111, 146, 152-190, 212, 216, 231-232, 283-289
dashboard/routers/search.py                  61     13     14      1    76%   77-80, 147-157
dashboard/routers/sse.py                     78     31     16      3    53%   151-165, 195->exit, 200-253, 258-259, 264, 280-287, 300
dashboard/routers/staleness.py              229    179     58      0    17%   80-83, 91-95, 102-108, 113-119, 124, 138-139, 153-166, 176, 198-209, 229-240, 258-268, 286-296, 314-324, 342-355, 384-411, 429-452, 470-493, 523-604
dashboard/routers/system.py                 156     17     30      6    85%   103, 170-190, 259, 264->266, 288->287, 290, 298-303
dashboard/routers/tests.py                  163    100     40      1    32%   64-66, 109-113, 133-137, 154-156, 172-174, 192-202, 221-244, 269-328, 339-347, 363-382, 404-409, 426-439, 444
dashboard/routers/usage.py                   18      9      4      0    41%   16-20, 25-28
dashboard/routers/worktrees.py              388    301    126      0    17%   57-80, 99-104, 109-130, 135-140, 145-154, 159-164, 169-178, 186-208, 228-272, 277-289, 340-349, 362-379, 388-525, 541-550, 558-560, 573-575, 585-591, 613-711, 717-731, 745-785, 803-835, 849-906
dashboard/services/coverage_service.py       96     59     14      0    34%   48-52, 56-67, 74-160
dashboard/services/oss_accepted.py           58     13     18      4    64%   43, 48-50, 57-62, 72, 80-81
dashboard/services/oss_check_catalog.py      28      3      4      2    84%   25, 42, 48
dashboard/services/oss_service.py           343     94    110     25    69%   56, 74, 83-84, 119-121, 138, 155-156, 203, 239, 248, 277-319, 340-341, 358-386, 393, 396, 404-417, 445, 478, 491-494, 497-498, 503->506, 581->584, 608, 634, 731, 733, 735, 737
dashboard/utils/batch_progress.py            15      4      4      1    74%   68-71
dashboard/utils/markdown.py                  44     25     14      1    38%   58-86
dashboard/utils/oss_copy.py                  18      3      0      0    83%   290, 301, 308
dashboard/utils/project_onboarding.py        38     12     14      3    63%   22-30, 45, 63, 66
dashboard/utils/timing.py                    52      4      6      2    90%   52, 72-74, 86->92
dashboard/utils/ttl_cache.py                 52     16      6      1    67%   38, 47-48, 55-56, 59-71
executor/scope_gate.py                       38     38     16      0     0%   25-80
orch/active_files.py                         16      6      6      2    55%   19, 34-48
orch/archive/archiver.py                     62      3     28      6    90%   50, 54, 63->66, 79->76, 100, 119->exit
orch/archive/batch_archiver.py              122    106     26      0    11%   52-71, 76-181, 188-236, 241-265, 277-284
orch/archive/extractor.py                    50     40     22      0    14%   38-61, 78-99, 112-131
orch/batch_planner.py                       299     58    112     18    76%   113, 126-132, 138-142, 190-192, 201-204, 208-217, 240, 242-244, 246, 251->250, 332, 338, 343, 352, 357-367, 451->450, 499-502, 517-519, 607, 617->626, 635, 661-663
orch/cli/batch_commands.py                  257     58     86     11    76%   84->82, 91-92, 197-201, 252, 296-297, 331, 359-360, 377, 400, 459, 464, 469-522, 537, 548, 551, 568, 579, 582
orch/cli/daemon_commands.py                 108     73     22      1    28%   38, 51-55, 78-120, 127-150, 157-228
orch/cli/db_commands.py                      59     47     12      0    17%   37-54, 63-96
orch/cli/doc_commands.py                    246     28     92     15    86%   136-137, 194, 207->209, 210, 212, 217->221, 253, 288, 305, 350->353, 356, 392, 407-408, 414, 444-445, 448-449, 461-469, 475-476, 491, 498
orch/cli/id_commands.py                      42      9      6      0    73%   73-82, 103-104
orch/cli/item_commands.py                   352     79    110     18    77%   65, 142-147, 150, 160-161, 237, 240-241, 289-290, 306->308, 317-318, 339-346, 388->379, 399-402, 420-421, 478, 518-519, 540, 562, 592, 595, 624, 626, 635, 638, 642-645, 654-655, 665, 675, 697->702, 728, 768-769, 774-787, 802-826
orch/cli/lock_commands.py                    79     10     18      6    84%   42, 58, 61, 93, 109, 112, 131, 141-142, 145
orch/cli/main.py                             77      9      6      1    86%   68-87
orch/cli/merge_queue_commands.py            124     90     36      0    21%   53-134, 153-194, 211-299
orch/cli/migrations_commands.py             109     76     30      0    24%   60-87, 98-140, 158-225
orch/cli/oss_commands.py                    212     91     68     12    51%   62-91, 108, 119, 124-188, 221-223, 243-244, 260-303, 322, 356, 362->377, 371->377, 374-375, 379-380, 407-409
orch/cli/project_commands.py                 35     11      8      1    63%   68-69, 74-83
orch/cli/search_commands.py                  47      4     16      3    89%   69->72, 85-86, 94-95, 101->103
orch/cli/skills_commands.py                 177    138     52      1    17%   19-91, 98-152, 163-245, 275-276, 279-292
orch/cli/step_commands.py                   346    135    124     19    57%   73, 79-80, 82, 102, 111-113, 121-123, 177-178, 184-200, 249->252, 255, 291, 306, 314->316, 317, 330-337, 350-351, 366, 372, 419, 436, 437->439, 474, 480, 515, 523, 545, 578, 582-583, 612-699, 714-767, 782-855
orch/cli/utils.py                            48     23     14      2    47%   22-36, 64-71, 107
orch/cli/worktree_commands.py               136    116     58      0    10%   33-61, 66-75, 80-89, 98-125, 145-150, 154-156, 174-320
orch/config.py                               67      9      2      1    86%   40, 66-74
orch/daemon/__main__.py                      17     17      2      0     0%   3-32
orch/daemon/batch_manager.py                518    184    158     32    62%   91-100, 114-115, 141-142, 156, 195-268, 318-341, 350, 380-407, 457-472, 482-545, 566-570, 579-588, 609-610, 635, 651, 656, 660, 700->704, 716, 722-724, 746-750, 788, 842-853, 877->962, 891-894, 948-949, 963, 991, 997, 1007-1014, 1029, 1071->1074, 1125->1129, 1135->1160, 1136->1135, 1139-1141, 1142->1158, 1214->1217, 1247-1264, 1302-1326, 1354, 1408-1503
orch/daemon/batch_merge_hooks.py             28      3     10      2    87%   48-49, 53
orch/daemon/browser_env.py                  192    155     46      1    16%   76, 94-95, 110-115, 119, 133-139, 148, 152-160, 164-166, 170-174, 188-259, 279-292, 311-331, 364-367, 378-380, 401-455, 465-486, 505-564
orch/daemon/container_info.py               156    110     52      0    22%   37-46, 50-60, 85-87, 91-100, 104, 108, 112, 116-122, 127-200, 210-230, 234-264
orch/daemon/doc_index_poller.py              89      2     20      2    96%   121-126, 143->exit
orch/daemon/doc_job_poller.py                92      7     14      2    92%   66-67, 103-109, 139-140, 229
orch/daemon/execution_report.py             265     34     88     13    83%   138-142, 151-155, 183, 214->226, 227->235, 242, 291, 302, 317, 365->367, 441, 453, 521->523, 546-559, 575-580
orch/daemon/fix_cycle.py                    465    195    192     46    52%   125, 176-206, 215-232, 252-255, 450, 468-474, 475->480, 510-516, 517->520, 549, 555, 559-564, 568-570, 586, 604->609, 607, 609->612, 623->631, 633-645, 654, 662, 666, 677, 681, 707, 731, 736-739, 742-744, 787-789, 804-806, 831-839, 857, 860-865, 867->870, 873, 881, 889, 891->901, 893->895, 896, 904, 914-929, 948, 950-951, 963-976, 990-1009, 1045-1046, 1056, 1086-1096, 1110-1130, 1186, 1198->1230, 1309, 1370-1432, 1441-1443, 1447-1451, 1480-1510
orch/daemon/keep_alive_poller.py             34     23      6      0    28%   46-54, 58-73, 82-91
orch/daemon/main.py                         335    270     86      3    16%   74-89, 136-140, 144-146, 149, 157->172, 196-217, 225-246, 262-310, 314-331, 335-351, 365-405, 409-436, 454-470, 481-513, 521-593, 601-633, 641-650, 657-659, 662-664, 667-670, 678-679, 689-695
orch/daemon/merge_queue.py                  114     47     28     10    57%   100, 116-119, 136-140, 154->193, 159-190, 193->222, 196-220, 231, 254->258, 258->exit, 261-299, 304-313
orch/daemon/migration_pipeline.py           109     46     20      1    54%   112-113, 154-156, 204-211, 243-269, 289-318
orch/daemon/migration_rebase.py             215     57     58     15    74%   101, 116, 123, 126, 151->156, 158->156, 167-168, 171, 177, 192, 201, 212-232, 243-269, 316-321, 366-367, 389, 421, 435-436, 494-495, 526-540
orch/daemon/project_registry.py             139     70     30      5    46%   77-78, 81-83, 94-95, 98-99, 141-148, 176-178, 185-186, 188->183, 205-242, 263-268, 272-275, 289-322, 327
orch/daemon/qv_baseline.py                  124     52     42      8    52%   95, 107, 110, 117-146, 169, 173->167, 177, 200-221, 246, 251
orch/daemon/state_machine.py                 41     13      2      1    67%   135, 147-148, 161, 166, 171, 176, 181, 186, 191, 196, 201, 206
orch/daemon/step_monitor.py                 169     43     46     13    71%   86, 91, 97-99, 121-123, 131-133, 187, 196-197, 224->239, 239->exit, 242-243, 245, 264->266, 299->302, 348, 360, 369-370, 427-444, 463-492, 509->exit
orch/daemon/worktree_compose.py             312    151     92     24    48%   121, 126-131, 161, 168, 174, 177, 240-252, 256, 259, 273-344, 357, 375-379, 387-394, 402, 403->399, 409-416, 421, 424, 465-489, 503-560, 569-618, 639->643, 642, 644-656, 666-679, 705-741, 754-770, 828, 838-839, 868-869, 912-913
orch/daemon/worktree_reaper.py               97     28     26      7    67%   74-78, 84, 87-89, 98->96, 101-104, 124-126, 140, 144-145, 152-155, 175-180, 192-193, 225-227
orch/db/alembic_guard.py                     63     18     12      4    68%   65-74, 83->86, 92-97, 118, 120, 125
orch/db/identity.py                          52      1     16      1    97%   76
orch/db/live_db_guard.py                     47      5     12      3    86%   90-91, 129, 144, 147
orch/db/migrations/env.py                    29      7      6      3    71%   27, 35, 52-61, 107
orch/db/models.py                           682      4     10      3    99%   174, 523, 1542, 1841
orch/db/safe_migrate.py                     264    140     42      6    43%   73, 75, 91-96, 179-196, 206-207, 227-233, 240, 257-284, 327->330, 351-363, 371-404, 409-428, 442-474, 491, 531-582, 593-642, 652
orch/db/session.py                           53     22     12      0    60%   71-80, 85-91, 105-113, 124-132
orch/design_doc_parser.py                   120     51     60      3    53%   44-69, 81-110, 115-116, 141->140, 178-182, 214, 242
orch/diagram/install.py                      11     11      4      0     0%   3-22
orch/diagram/render.py                       82     69     26      0    12%   21-37, 42-53, 58-96, 101-129, 134-138
orch/doc_diff.py                             36      1     10      1    96%   77
orch/doc_sections.py                         17      1      4      1    90%   47
orch/doc_service.py                         414     52    184     32    83%   54, 64, 66-74, 171, 177, 179, 183, 185, 187->208, 291, 296-297, 320, 334->345, 349-350, 407-434, 462, 490, 492, 507, 509, 516->519, 525, 586, 598, 617, 623, 625, 648-649, 672, 679-684, 721, 738, 765, 783, 785, 789-790
orch/evidences.py                            52      4     12      0    94%   30-31, 54-55
orch/jobs/aggregator.py                     226     62     84     16    67%   146-153, 196, 228-236, 246, 248, 298, 300, 349, 355, 364->368, 423, 425, 474, 476, 565, 597-606, 619-622, 635-645, 658-685, 711, 713, 718-724
orch/keep_alive_service.py                   99     24     20      7    72%   45, 86, 107, 117, 151-153, 158, 171, 194, 225-240, 251, 254-255, 257
orch/llm_usage.py                           139    113     28      0    16%   55-62, 71-75, 84-95, 105-138, 152-163, 168-174, 179-210, 220-229, 239-260, 265-268
orch/oss/config_writer.py                    34      3      8      1    90%   51, 69-70
orch/oss/fix_recipes/__init__.py             15      2      2      1    82%   13, 23
orch/oss/fix_recipes/ci_cd.py               111     74     22      0    28%   14-22, 26-34, 42-80, 88-92, 103-143, 151-155, 166-188, 196-200, 211-242, 250-254, 265-307, 315
orch/oss/fix_recipes/community.py           236    157     70      2    26%   15-20, 31-32, 71, 96-102, 113-161, 169-173, 184-242, 250-254, 265-326, 334-338, 349-374, 382-386, 397-432, 440-444, 455-504, 512-516, 527-573, 581-585, 596-634, 642-663
orch/oss/fix_recipes/contributor.py          53     36     16      0    25%   18-33, 41-45, 56-94, 102-123
orch/oss/fix_recipes/governance.py           35     22      6      0    32%   12-20, 28-74, 82-86
orch/oss/fix_recipes/hygiene.py             112     86     40      0    17%   22-26, 30-44, 52-70, 78-92, 103-125, 133-151, 162-177, 185-194
orch/oss/fix_recipes/internal_refs.py        21     10      4      0    44%   17-36, 47, 50-52
orch/oss/fix_recipes/license_check.py       116     89     34      0    18%   12-20, 24-32, 45-79, 87-91, 102-141, 149-171, 182-221, 229-233
orch/oss/fix_recipes/release.py              60     38     18      0    28%   17-48, 56-60, 71-119, 127-131, 142-158, 169
orch/oss/fix_recipes/secrets.py              48     29     10      0    33%   12-20, 28-73, 81-84, 95-118, 126-129
orch/oss/persistence.py                      64     19     24      0    69%   32-33, 38-45, 120-135
orch/oss/scanner.py                          94      9     18      6    87%   39, 43, 110->118, 139-147, 168, 177->181
orch/oss/tool_probe.py                       44      5      8      3    85%   47-48, 56, 59, 96
orch/rag/citation_allowlist.py               28      1      6      1    94%   55->53, 70
orch/rag/classifier.py                       26      4      8      2    71%   74-76, 101
orch/rag/doc_indexer.py                     190     10     52      7    93%   142-143, 173->exit, 269, 320-321, 333, 360, 365->368, 386-395
orch/rag/doc_job.py                         102     16     24      5    83%   49, 80-81, 105-115, 120-121, 146, 154-156, 180, 203
orch/rag/evidence.py                         41     12     10      0    57%   54-64, 69
orch/rag/git_log_resolver.py                 34     26     12      0    17%   45-50, 55-84, 92-95
orch/rag/index_gen.py                       120     29     46      9    73%   30, 37, 43-48, 74->97, 80->86, 87->86, 92, 113-120, 140-148, 204-207
orch/rag/indexer.py                         225    115     76      6    41%   59-63, 75-113, 149-153, 185, 212->218, 216->218, 240-291, 304-307, 320-321, 341-411
orch/rag/job.py                             183     56     44     10    66%   50, 59-80, 92, 105-106, 149-152, 159, 197->exit, 202->204, 223, 236-259, 267-268, 291, 298-300, 346-366, 384-387, 401
orch/rag/mapgen.py                          117     16     20      7    82%   173, 194, 210, 222-225, 235, 240, 271-277, 334
orch/rag/module_gen.py                      182     27     44     14    79%   98-101, 110-117, 124-125, 141, 144->148, 156->161, 157->156, 162->164, 167->169, 181, 183->188, 187, 206, 316-319, 421, 447, 470-474
orch/rag/module_progress.py                  61      5     10      2    90%   41, 45-46, 99, 110
orch/rag/parser.py                           84     22     36      8    73%   22, 26-27, 48-50, 51->42, 54->57, 76-80, 92-96, 100-104, 130
orch/rag/qa.py                              334    167    140     22    44%   43-48, 120-139, 147-155, 171-173, 185-186, 254-263, 273, 285, 289, 318, 321-329, 332-336, 339-344, 375-379, 407, 412-452, 455, 465, 477, 491-499, 502-517, 553-626, 644, 656, 664, 687->686, 701-708, 715->714, 720->719, 724, 726-728, 738->737, 742-763
orch/rag/symbol_gen.py                       72     56     22      0    17%   50-68, 71-91, 96-104, 107-111, 114-116, 119-120, 133-144
orch/skills/init_project.py                  83     10     14      4    81%   27, 30-31, 107, 166, 177-181
orch/skills/sync.py                          83     48     30      4    35%   29-46, 52-57, 89, 92-141, 151->154
orch/skills/sync_agents.py                   39     11      6      1    64%   38-50
orch/staleness/alembic_check.py              95     71     32      0    19%   94-100, 114-126, 144-153, 179-330
orch/staleness/config.py                     85     21     32     10    65%   48, 51-54, 59, 62-74, 118, 122, 128, 176, 222->226, 227->230
orch/staleness/detection.py                 192    164     64      0    11%   41-45, 50-57, 62-66, 75-83, 101-107, 126-153, 170-187, 193-199, 213-257, 270-279, 301-313, 318-345, 350-380, 389-433
orch/staleness/git_lookup.py                 58     45     16      0    18%   57-95, 121-180
orch/staleness/service.py                    94     63     24      0    26%   41-43, 115-124, 132-212, 240-289
orch/test_runner.py                         360    318     70      2    10%   43-224, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 576-582, 587-594, 608-621, 626-632, 640-641, 657-679, 691-700
orch/utils/log_capture.py                    33     21      8      1    32%   22, 36-62
-------------------------------------------------------------------------------------
TOTAL                                     18578   7296   4990    681    56%

19 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 46.0% reached. Total coverage: 56.30%
========== 1177 passed, 11 skipped, 150 warnings in 317.56s (0:05:17) ==========
```

## Verdict

```
pass
```
