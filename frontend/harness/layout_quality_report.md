# Diagram layout quality

| cloud | fixture | tier | svc | nodeOvl | edge→node | crossings (budget) | labelOvl | orphans | comps | reach | aspect | edgeLen | longest | elk kept/repl | cyc | fanOut | collin | rankSpan | orphan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aws | web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3.19 | 2258 | 779 | 10/1 | 0 | 3 | 0 | 5 | 0 |
| aws | web-ecommerce | Most reliable | 13 | 0 | 0 | 9 (10) | 0 | 0 | 1 | all | 2.78 | 7619 | 1929 | 12/3 | 0 | 4 | 2 | 12 | 0 |
| aws | web-ecommerce | Most optimized | 14 | 0 | 0 | 7 (11) | 0 | 0 | 1 | all | 2.85 | 8907 | 2002 | 16/2 | 1 | 4 | 1 | 11 | 0 |
| aws | web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3.19 | 2258 | 779 | 10/1 | 0 | 3 | 0 | 5 | 0 |
| aws | web-internal-tool | Most reliable | 10 | 0 | 0 | 4 (8) | 0 | 0 | 1 | all | 3.16 | 6049 | 1918 | 11/2 | 0 | 3 | 1 | 11 | 0 |
| aws | web-internal-tool | Most optimized | 14 | 0 | 0 | 7 (11) | 0 | 0 | 1 | all | 2.85 | 8907 | 2002 | 16/2 | 1 | 4 | 1 | 11 | 0 |
| aws | media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 3.3 | 1169 | 474 | 7/0 | 0 | 2 | 0 | 5 | 0 |
| aws | media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 2.93 | 2858 | 1115 | 9/0 | 0 | 2 | 0 | 8 | 0 |
| aws | media-streaming | Most optimized | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3 | 3617 | 1188 | 12/0 | 1 | 3 | 0 | 6 | 0 |
| aws | batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.07 | 621 | 231 | 5/0 | 0 | 1 | 0 | 3 | 0 |
| aws | batch-etl | Most reliable | 6 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.09 | 960 | 319 | 6/0 | 0 | 2 | 0 | 3 | 0 |
| aws | batch-etl | Most optimized | 6 | 0 | 0 | 1 (4) | 0 | 0 | 1 | all | 3.17 | 2097 | 778 | 6/1 | 0 | 2 | 0 | 5 | 0 |
| aws | event-iot | Cheapest | 8 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.46 | 3346 | 997 | 11/0 | 0 | 3 | 0 | 3 | 0 |
| aws | event-iot | Most reliable | 10 | 0 | 0 | 2 (6) | 0 | 0 | 1 | missed firehose,streaming | 3.08 | 3792 | 862 | 10/2 | 0 | 2 | 4 | 6 | 0 |
| aws | event-iot | Most optimized | 11 | 0 | 0 | 1 (7) | 0 | 0 | 1 | missed iot | 3.61 | 2792 | 749 | 11/2 | 0 | 3 | 0 | 4 | 0 |
| aws | serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.67 | 2177 | 871 | 11/0 | 0 | 2 | 0 | 4 | 0 |
| aws | serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.81 | 3296 | 1056 | 13/0 | 0 | 3 | 0 | 8 | 0 |
| aws | serverless-api | Most optimized | 11 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.75 | 3567 | 902 | 17/0 | 1 | 3 | 0 | 9 | 0 |
| aws | ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.64 | 2197 | 691 | 12/0 | 0 | 2 | 0 | 6 | 0 |
| aws | ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.82 | 2676 | 752 | 14/0 | 0 | 3 | 0 | 7 | 0 |
| aws | ai-vision | Most optimized | 12 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.77 | 4456 | 912 | 17/1 | 1 | 3 | 0 | 9 | 0 |
| gcp | web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.32 | 2374 | 624 | 11/0 | 0 | 3 | 0 | 5 | 0 |
| gcp | web-ecommerce | Most reliable | 12 | 0 | 0 | 2 (9) | 0 | 0 | 1 | all | 1.05 | 6010 | 1286 | 15/0 | 0 | 4 | 2 | 12 | 0 |
| gcp | web-ecommerce | Most optimized | 13 | 0 | 0 | 2 (11) | 0 | 0 | 1 | all | 0.98 | 6303 | 1217 | 17/1 | 1 | 4 | 2 | 13 | 0 |
| gcp | web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.32 | 2374 | 624 | 11/0 | 0 | 3 | 0 | 5 | 0 |
| gcp | web-internal-tool | Most reliable | 9 | 0 | 0 | 0 (8) | 0 | 0 | 1 | all | 0.93 | 3701 | 863 | 13/0 | 0 | 3 | 0 | 6 | 0 |
| gcp | web-internal-tool | Most optimized | 13 | 0 | 0 | 2 (11) | 0 | 0 | 1 | all | 0.98 | 6303 | 1217 | 17/1 | 1 | 4 | 2 | 13 | 0 |
| gcp | media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 2.3 | 917 | 433 | 7/0 | 0 | 2 | 0 | 5 | 0 |
| gcp | media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 2.55 | 1618 | 781 | 9/0 | 0 | 2 | 0 | 7 | 0 |
| gcp | media-streaming | Most optimized | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.65 | 2405 | 997 | 11/1 | 1 | 3 | 0 | 6 | 0 |
| gcp | batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.17 | 556 | 231 | 5/0 | 0 | 1 | 0 | 3 | 0 |
| gcp | batch-etl | Most reliable | 6 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.09 | 895 | 319 | 6/0 | 0 | 2 | 0 | 3 | 0 |
| gcp | batch-etl | Most optimized | 6 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 3.46 | 1331 | 734 | 6/1 | 0 | 2 | 0 | 6 | 0 |
| gcp | event-iot | Cheapest | 8 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.18 | 2804 | 844 | 11/0 | 0 | 3 | 0 | 3 | 0 |
| gcp | event-iot | Most reliable | 10 | 0 | 0 | 2 (6) | 0 | 0 | 1 | missed firehose,streaming | 3.07 | 3438 | 797 | 10/2 | 0 | 2 | 5 | 6 | 0 |
| gcp | event-iot | Most optimized | 11 | 0 | 0 | 3 (7) | 0 | 0 | 1 | missed iot | 0.7 | 4281 | 702 | 9/4 | 0 | 3 | 0 | 8 | 0 |
| gcp | serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.53 | 1970 | 915 | 11/0 | 0 | 2 | 0 | 5 | 0 |
| gcp | serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.8 | 3374 | 1086 | 13/0 | 0 | 3 | 0 | 8 | 0 |
| gcp | serverless-api | Most optimized | 11 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.75 | 3645 | 941 | 17/0 | 1 | 3 | 0 | 7 | 0 |
| gcp | ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.56 | 1990 | 878 | 12/0 | 0 | 2 | 0 | 5 | 0 |
| gcp | ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.81 | 2754 | 791 | 14/0 | 0 | 3 | 0 | 6 | 0 |
| gcp | ai-vision | Most optimized | 12 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.76 | 4534 | 960 | 17/1 | 1 | 3 | 0 | 10 | 0 |
| azure | web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3.11 | 2559 | 833 | 11/0 | 0 | 3 | 0 | 5 | 0 |
| azure | web-ecommerce | Most reliable | 12 | 0 | 0 | 2 (9) | 0 | 0 | 1 | all | 1 | 7788 | 1495 | 14/1 | 0 | 4 | 1 | 9 | 0 |
| azure | web-ecommerce | Most optimized | 13 | 0 | 0 | 2 (11) | 0 | 0 | 1 | all | 0.89 | 10047 | 2373 | 17/1 | 1 | 4 | 1 | 14 | 0 |
| azure | web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3.11 | 2559 | 833 | 11/0 | 0 | 3 | 0 | 5 | 0 |
| azure | web-internal-tool | Most reliable | 9 | 0 | 0 | 0 (8) | 0 | 0 | 1 | all | 0.74 | 5477 | 1288 | 12/1 | 0 | 3 | 0 | 8 | 0 |
| azure | web-internal-tool | Most optimized | 13 | 0 | 0 | 2 (11) | 0 | 0 | 1 | all | 0.89 | 10047 | 2373 | 17/1 | 1 | 4 | 1 | 14 | 0 |
| azure | media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 3.15 | 1087 | 433 | 7/0 | 0 | 2 | 0 | 5 | 0 |
| azure | media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 2.87 | 3420 | 1104 | 9/0 | 0 | 2 | 0 | 8 | 0 |
| azure | media-streaming | Most optimized | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.97 | 4191 | 1180 | 12/0 | 1 | 3 | 0 | 6 | 0 |
| azure | batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.32 | 579 | 231 | 5/0 | 0 | 1 | 0 | 3 | 0 |
| azure | batch-etl | Most reliable | 6 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.35 | 918 | 319 | 6/0 | 0 | 2 | 0 | 3 | 0 |
| azure | batch-etl | Most optimized | 6 | 0 | 0 | 1 (4) | 0 | 0 | 1 | all | 3.15 | 1962 | 721 | 6/1 | 0 | 2 | 0 | 5 | 0 |
| azure | event-iot | Cheapest | 8 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.39 | 3050 | 937 | 11/0 | 0 | 3 | 0 | 3 | 0 |
| azure | event-iot | Most reliable | 10 | 0 | 0 | 1 (6) | 0 | 0 | 1 | missed firehose,streaming | 0.56 | 2928 | 609 | 10/2 | 0 | 2 | 1 | 7 | 0 |
| azure | event-iot | Most optimized | 11 | 0 | 0 | 1 (7) | 0 | 0 | 1 | missed iot | 3.87 | 2671 | 712 | 11/2 | 0 | 3 | 0 | 4 | 0 |
| azure | serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.67 | 2177 | 871 | 11/0 | 0 | 2 | 0 | 4 | 0 |
| azure | serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.81 | 3296 | 1056 | 13/0 | 0 | 3 | 0 | 8 | 0 |
| azure | serverless-api | Most optimized | 11 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.75 | 3567 | 902 | 17/0 | 1 | 3 | 0 | 9 | 0 |
| azure | ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.64 | 2197 | 691 | 12/0 | 0 | 2 | 0 | 6 | 0 |
| azure | ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.82 | 2676 | 752 | 14/0 | 0 | 3 | 0 | 7 | 0 |
| azure | ai-vision | Most optimized | 12 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.77 | 4456 | 912 | 17/1 | 1 | 3 | 0 | 9 | 0 |
