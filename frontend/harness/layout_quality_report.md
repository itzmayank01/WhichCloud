# Diagram layout quality

| cloud | fixture | tier | svc | nodeOvl | edge→node | crossings (budget) | labelOvl | orphans | comps | reach | aspect | edgeLen | longest | elk kept/repl | cyc | fanOut | collin | rankSpan | orphan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aws | web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 2.46 | 2606 | 789 | 10/3 | 0 | 3 | 0 | 5 | 5 |
| aws | web-ecommerce | Most reliable | 13 | 0 | 0 | 9 (11) | 0 | 0 | 1 | all | 2.34 | 8213 | 1943 | 15/3 | 0 | 4 | 2 | 14 | 5 |
| aws | web-ecommerce | Most optimized | 14 | 0 | 0 | 5 (13) | 0 | 0 | 1 | all | 2.37 | 9654 | 2061 | 17/4 | 1 | 4 | 0 | 13 | 5 |
| aws | web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 2.46 | 2606 | 789 | 10/3 | 0 | 3 | 0 | 4 | 4 |
| aws | web-internal-tool | Most reliable | 10 | 0 | 0 | 6 (10) | 0 | 0 | 1 | all | 2.61 | 6857 | 1916 | 13/3 | 0 | 3 | 2 | 13 | 4 |
| aws | web-internal-tool | Most optimized | 14 | 0 | 0 | 5 (13) | 0 | 0 | 1 | all | 2.37 | 9654 | 2061 | 17/4 | 1 | 4 | 0 | 12 | 4 |
| aws | media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 2.8 | 1610 | 551 | 8/0 | 0 | 2 | 0 | 5 | 5 |
| aws | media-streaming | Most reliable | 6 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.51 | 2976 | 1295 | 9/2 | 0 | 2 | 0 | 8 | 5 |
| aws | media-streaming | Most optimized | 7 | 0 | 0 | 1 (7) | 0 | 0 | 1 | all | 2.59 | 3807 | 1390 | 12/2 | 1 | 3 | 0 | 7 | 5 |
| aws | batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 2.92 | 828 | 296 | 6/0 | 0 | 1 | 0 | 2 | 3 |
| aws | batch-etl | Most reliable | 6 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 2.91 | 1168 | 319 | 7/0 | 0 | 2 | 0 | 3 | 4 |
| aws | batch-etl | Most optimized | 6 | 0 | 0 | 1 (4) | 0 | 0 | 1 | all | 2.94 | 3065 | 1074 | 6/2 | 0 | 2 | 0 | 5 | 5 |
| aws | event-iot | Cheapest | 8 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.73 | 5098 | 1237 | 12/0 | 0 | 3 | 2 | 3 | 2 |
| aws | event-iot | Most reliable | 10 | 0 | 0 | 1 (7) | 0 | 0 | 1 | missed firehose,streaming | 2.95 | 5091 | 1042 | 12/1 | 0 | 2 | 1 | 6 | 3 |
| aws | event-iot | Most optimized | 11 | 0 | 0 | 1 (7) | 0 | 0 | 1 | missed iot | 3.51 | 3722 | 859 | 11/3 | 0 | 3 | 1 | 4 | 4 |
| aws | serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.68 | 2177 | 871 | 11/0 | 0 | 2 | 0 | 4 | 2 |
| aws | serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.83 | 3296 | 1056 | 13/0 | 0 | 3 | 0 | 8 | 2 |
| aws | serverless-api | Most optimized | 11 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.77 | 3567 | 902 | 17/0 | 1 | 3 | 0 | 8 | 2 |
| aws | ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.65 | 2197 | 691 | 12/0 | 0 | 2 | 0 | 5 | 2 |
| aws | ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.84 | 2676 | 752 | 14/0 | 0 | 3 | 0 | 6 | 2 |
| aws | ai-vision | Most optimized | 12 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.79 | 4456 | 912 | 17/1 | 1 | 3 | 0 | 8 | 2 |
| gcp | web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.73 | 4221 | 1191 | 12/1 | 0 | 3 | 2 | 8 | 5 |
| gcp | web-ecommerce | Most reliable | 12 | 0 | 0 | 3 (11) | 0 | 0 | 1 | all | 1.13 | 6962 | 1213 | 16/2 | 0 | 4 | 3 | 8 | 5 |
| gcp | web-ecommerce | Most optimized | 13 | 0 | 0 | 3 (12) | 0 | 0 | 1 | all | 1.05 | 7701 | 1343 | 18/3 | 1 | 4 | 3 | 8 | 5 |
| gcp | web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.73 | 4221 | 1191 | 12/1 | 0 | 3 | 2 | 7 | 4 |
| gcp | web-internal-tool | Most reliable | 9 | 0 | 0 | 2 (9) | 0 | 0 | 1 | all | 0.74 | 6534 | 1294 | 15/1 | 0 | 3 | 1 | 5 | 4 |
| gcp | web-internal-tool | Most optimized | 13 | 0 | 0 | 3 (12) | 0 | 0 | 1 | all | 1.05 | 7701 | 1343 | 18/3 | 1 | 4 | 3 | 8 | 4 |
| gcp | media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 2.49 | 1358 | 433 | 8/0 | 0 | 2 | 0 | 5 | 5 |
| gcp | media-streaming | Most reliable | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.27 | 2361 | 798 | 11/0 | 0 | 2 | 0 | 7 | 5 |
| gcp | media-streaming | Most optimized | 7 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 2.56 | 3345 | 1175 | 13/1 | 1 | 3 | 0 | 6 | 5 |
| gcp | batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 2.92 | 763 | 252 | 6/0 | 0 | 1 | 0 | 2 | 3 |
| gcp | batch-etl | Most reliable | 6 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 3.17 | 1103 | 319 | 7/0 | 0 | 2 | 0 | 3 | 4 |
| gcp | batch-etl | Most optimized | 6 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 3.55 | 1784 | 954 | 7/1 | 0 | 2 | 0 | 6 | 5 |
| gcp | event-iot | Cheapest | 8 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.39 | 4582 | 988 | 12/0 | 0 | 3 | 1 | 3 | 2 |
| gcp | event-iot | Most reliable | 10 | 0 | 0 | 1 (7) | 0 | 0 | 1 | missed firehose,streaming | 2.84 | 4752 | 1054 | 12/1 | 0 | 2 | 1 | 6 | 3 |
| gcp | event-iot | Most optimized | 11 | 0 | 0 | 3 (7) | 0 | 0 | 1 | missed iot | 0.62 | 4376 | 717 | 10/4 | 0 | 3 | 1 | 7 | 4 |
| gcp | serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.63 | 1970 | 915 | 11/0 | 0 | 2 | 0 | 4 | 2 |
| gcp | serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.82 | 3374 | 1086 | 13/0 | 0 | 3 | 0 | 8 | 2 |
| gcp | serverless-api | Most optimized | 11 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.76 | 3645 | 941 | 17/0 | 1 | 3 | 0 | 6 | 2 |
| gcp | ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.66 | 1990 | 878 | 12/0 | 0 | 2 | 0 | 4 | 2 |
| gcp | ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.83 | 2754 | 791 | 14/0 | 0 | 3 | 0 | 5 | 2 |
| gcp | ai-vision | Most optimized | 12 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.78 | 4534 | 960 | 17/1 | 1 | 3 | 0 | 9 | 2 |
| azure | web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.65 | 3877 | 1173 | 11/2 | 0 | 3 | 2 | 6 | 5 |
| azure | web-ecommerce | Most reliable | 12 | 0 | 0 | 1 (11) | 0 | 0 | 1 | all | 0.66 | 6261 | 1449 | 15/3 | 0 | 4 | 4 | 9 | 5 |
| azure | web-ecommerce | Most optimized | 13 | 0 | 0 | 5 (12) | 0 | 0 | 1 | all | 3.34 | 7880 | 2110 | 18/3 | 1 | 4 | 3 | 10 | 5 |
| azure | web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.65 | 3877 | 1173 | 11/2 | 0 | 3 | 2 | 6 | 4 |
| azure | web-internal-tool | Most reliable | 9 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.57 | 5024 | 1506 | 13/3 | 0 | 3 | 3 | 5 | 4 |
| azure | web-internal-tool | Most optimized | 13 | 0 | 0 | 5 (12) | 0 | 0 | 1 | all | 3.34 | 7880 | 2110 | 18/3 | 1 | 4 | 3 | 9 | 4 |
| azure | media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 2.92 | 1528 | 510 | 8/0 | 0 | 2 | 0 | 5 | 5 |
| azure | media-streaming | Most reliable | 6 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.65 | 2994 | 1317 | 9/2 | 0 | 2 | 1 | 8 | 5 |
| azure | media-streaming | Most optimized | 7 | 0 | 0 | 1 (7) | 0 | 0 | 1 | all | 0.72 | 3806 | 1128 | 12/2 | 1 | 3 | 0 | 8 | 5 |
| azure | batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.02 | 786 | 275 | 6/0 | 0 | 1 | 0 | 2 | 3 |
| azure | batch-etl | Most reliable | 6 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 3.01 | 1126 | 319 | 7/0 | 0 | 2 | 0 | 3 | 4 |
| azure | batch-etl | Most optimized | 6 | 0 | 0 | 1 (4) | 0 | 0 | 1 | all | 3.27 | 2894 | 966 | 7/1 | 0 | 2 | 0 | 5 | 5 |
| azure | event-iot | Cheapest | 8 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.82 | 4680 | 1106 | 12/0 | 0 | 3 | 2 | 3 | 2 |
| azure | event-iot | Most reliable | 10 | 0 | 0 | 1 (7) | 0 | 0 | 1 | missed firehose,streaming | 3.12 | 4842 | 1000 | 12/1 | 0 | 2 | 1 | 6 | 3 |
| azure | event-iot | Most optimized | 11 | 0 | 0 | 1 (7) | 0 | 0 | 1 | missed iot | 3.94 | 3584 | 798 | 11/3 | 0 | 3 | 1 | 4 | 4 |
| azure | serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.68 | 2177 | 871 | 11/0 | 0 | 2 | 0 | 4 | 2 |
| azure | serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.83 | 3296 | 1056 | 13/0 | 0 | 3 | 0 | 8 | 2 |
| azure | serverless-api | Most optimized | 11 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.77 | 3567 | 902 | 17/0 | 1 | 3 | 0 | 8 | 2 |
| azure | ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.65 | 2197 | 691 | 12/0 | 0 | 2 | 0 | 5 | 2 |
| azure | ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.84 | 2676 | 752 | 14/0 | 0 | 3 | 0 | 6 | 2 |
| azure | ai-vision | Most optimized | 12 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.79 | 4456 | 912 | 17/1 | 1 | 3 | 0 | 8 | 2 |
