# Diagram layout quality

| cloud | fixture | tier | svc | nodeOvl | edge→node | crossings (budget) | labelOvl | orphans | comps | reach | aspect | edgeLen | longest | elk kept/repl | cyc | fanOut | collin | rankSpan | orphan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aws | web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3.32 | 2258 | 779 | 10/1 | 0 | 3 | 0 | 5 | 6 |
| aws | web-ecommerce | Most reliable | 13 | 0 | 0 | 9 (10) | 0 | 0 | 1 | all | 2.86 | 7619 | 1929 | 12/3 | 0 | 4 | 2 | 11 | 6 |
| aws | web-ecommerce | Most optimized | 14 | 0 | 0 | 7 (11) | 0 | 0 | 1 | all | 2.93 | 8907 | 2002 | 16/2 | 1 | 4 | 1 | 12 | 6 |
| aws | web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3.32 | 2258 | 779 | 10/1 | 0 | 3 | 0 | 5 | 5 |
| aws | web-internal-tool | Most reliable | 10 | 0 | 0 | 4 (8) | 0 | 0 | 1 | all | 3.27 | 6049 | 1918 | 11/2 | 0 | 3 | 1 | 11 | 5 |
| aws | web-internal-tool | Most optimized | 14 | 0 | 0 | 7 (11) | 0 | 0 | 1 | all | 2.93 | 8907 | 2002 | 16/2 | 1 | 4 | 1 | 11 | 5 |
| aws | media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 3.47 | 1169 | 474 | 7/0 | 0 | 2 | 0 | 5 | 6 |
| aws | media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 3.06 | 2858 | 1115 | 9/0 | 0 | 2 | 0 | 7 | 6 |
| aws | media-streaming | Most optimized | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3.13 | 3617 | 1188 | 12/0 | 1 | 3 | 0 | 7 | 6 |
| aws | batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.24 | 621 | 231 | 5/0 | 0 | 1 | 0 | 3 | 4 |
| aws | batch-etl | Most reliable | 6 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.26 | 960 | 319 | 6/0 | 0 | 2 | 0 | 3 | 5 |
| aws | batch-etl | Most optimized | 6 | 0 | 0 | 1 (4) | 0 | 0 | 1 | all | 3.32 | 2097 | 778 | 6/1 | 0 | 2 | 0 | 5 | 6 |
| aws | event-iot | Cheapest | 8 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.56 | 3346 | 997 | 11/0 | 0 | 3 | 0 | 3 | 3 |
| aws | event-iot | Most reliable | 10 | 0 | 0 | 2 (6) | 0 | 0 | 1 | missed firehose,streaming | 3.22 | 3792 | 862 | 10/2 | 0 | 2 | 4 | 6 | 4 |
| aws | event-iot | Most optimized | 11 | 0 | 0 | 1 (7) | 0 | 0 | 1 | missed iot | 3.77 | 2792 | 749 | 11/2 | 0 | 3 | 0 | 4 | 5 |
| aws | serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.68 | 2177 | 871 | 11/0 | 0 | 2 | 0 | 4 | 3 |
| aws | serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.83 | 3296 | 1056 | 13/0 | 0 | 3 | 0 | 8 | 3 |
| aws | serverless-api | Most optimized | 11 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.77 | 3567 | 902 | 17/0 | 1 | 3 | 0 | 9 | 3 |
| aws | ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.65 | 2197 | 691 | 12/0 | 0 | 2 | 0 | 6 | 3 |
| aws | ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.84 | 2676 | 752 | 14/0 | 0 | 3 | 0 | 7 | 3 |
| aws | ai-vision | Most optimized | 12 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.79 | 4456 | 912 | 17/1 | 1 | 3 | 0 | 9 | 3 |
| gcp | web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.41 | 2374 | 624 | 11/0 | 0 | 3 | 0 | 5 | 6 |
| gcp | web-ecommerce | Most reliable | 12 | 0 | 0 | 2 (9) | 0 | 0 | 1 | all | 1.07 | 6010 | 1286 | 15/0 | 0 | 4 | 2 | 13 | 6 |
| gcp | web-ecommerce | Most optimized | 13 | 0 | 0 | 2 (11) | 0 | 0 | 1 | all | 1 | 6303 | 1217 | 17/1 | 1 | 4 | 2 | 14 | 6 |
| gcp | web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.41 | 2374 | 624 | 11/0 | 0 | 3 | 0 | 5 | 5 |
| gcp | web-internal-tool | Most reliable | 9 | 0 | 0 | 0 (8) | 0 | 0 | 1 | all | 0.95 | 3701 | 863 | 13/0 | 0 | 3 | 0 | 6 | 5 |
| gcp | web-internal-tool | Most optimized | 13 | 0 | 0 | 2 (11) | 0 | 0 | 1 | all | 1 | 6303 | 1217 | 17/1 | 1 | 4 | 2 | 13 | 5 |
| gcp | media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 2.4 | 917 | 433 | 7/0 | 0 | 2 | 0 | 5 | 6 |
| gcp | media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 2.67 | 1618 | 781 | 9/0 | 0 | 2 | 0 | 7 | 6 |
| gcp | media-streaming | Most optimized | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.76 | 2405 | 997 | 11/1 | 1 | 3 | 0 | 6 | 6 |
| gcp | batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.35 | 556 | 231 | 5/0 | 0 | 1 | 0 | 3 | 4 |
| gcp | batch-etl | Most reliable | 6 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.27 | 895 | 319 | 6/0 | 0 | 2 | 0 | 3 | 5 |
| gcp | batch-etl | Most optimized | 6 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 3.65 | 1331 | 734 | 6/1 | 0 | 2 | 0 | 5 | 6 |
| gcp | event-iot | Cheapest | 8 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.26 | 2804 | 844 | 11/0 | 0 | 3 | 0 | 3 | 3 |
| gcp | event-iot | Most reliable | 10 | 0 | 0 | 2 (6) | 0 | 0 | 1 | missed firehose,streaming | 3.2 | 3438 | 797 | 10/2 | 0 | 2 | 5 | 6 | 4 |
| gcp | event-iot | Most optimized | 11 | 0 | 0 | 3 (7) | 0 | 0 | 1 | missed iot | 0.71 | 4281 | 702 | 9/4 | 0 | 3 | 0 | 8 | 5 |
| gcp | serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.63 | 1970 | 915 | 11/0 | 0 | 2 | 0 | 5 | 3 |
| gcp | serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.82 | 3374 | 1086 | 13/0 | 0 | 3 | 0 | 8 | 3 |
| gcp | serverless-api | Most optimized | 11 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.76 | 3645 | 941 | 17/0 | 1 | 3 | 0 | 7 | 3 |
| gcp | ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.66 | 1990 | 878 | 12/0 | 0 | 2 | 0 | 5 | 3 |
| gcp | ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.83 | 2754 | 791 | 14/0 | 0 | 3 | 0 | 6 | 3 |
| gcp | ai-vision | Most optimized | 12 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.78 | 4534 | 960 | 17/1 | 1 | 3 | 0 | 10 | 3 |
| azure | web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3.24 | 2559 | 833 | 11/0 | 0 | 3 | 0 | 5 | 6 |
| azure | web-ecommerce | Most reliable | 12 | 0 | 0 | 2 (9) | 0 | 0 | 1 | all | 1.02 | 7788 | 1495 | 14/1 | 0 | 4 | 1 | 10 | 6 |
| azure | web-ecommerce | Most optimized | 13 | 0 | 0 | 2 (11) | 0 | 0 | 1 | all | 0.9 | 10047 | 2373 | 17/1 | 1 | 4 | 1 | 14 | 6 |
| azure | web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3.24 | 2559 | 833 | 11/0 | 0 | 3 | 0 | 5 | 5 |
| azure | web-internal-tool | Most reliable | 9 | 0 | 0 | 0 (8) | 0 | 0 | 1 | all | 0.75 | 5477 | 1288 | 12/1 | 0 | 3 | 0 | 8 | 5 |
| azure | web-internal-tool | Most optimized | 13 | 0 | 0 | 2 (11) | 0 | 0 | 1 | all | 0.9 | 10047 | 2373 | 17/1 | 1 | 4 | 1 | 14 | 5 |
| azure | media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 3.3 | 1087 | 433 | 7/0 | 0 | 2 | 0 | 5 | 6 |
| azure | media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 3 | 3420 | 1104 | 9/0 | 0 | 2 | 0 | 8 | 6 |
| azure | media-streaming | Most optimized | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3.11 | 4191 | 1180 | 12/0 | 1 | 3 | 0 | 7 | 6 |
| azure | batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.53 | 579 | 231 | 5/0 | 0 | 1 | 0 | 3 | 4 |
| azure | batch-etl | Most reliable | 6 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.55 | 918 | 319 | 6/0 | 0 | 2 | 0 | 3 | 5 |
| azure | batch-etl | Most optimized | 6 | 0 | 0 | 1 (4) | 0 | 0 | 1 | all | 3.3 | 1962 | 721 | 6/1 | 0 | 2 | 0 | 5 | 6 |
| azure | event-iot | Cheapest | 8 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.49 | 3050 | 937 | 11/0 | 0 | 3 | 0 | 3 | 3 |
| azure | event-iot | Most reliable | 10 | 0 | 0 | 1 (6) | 0 | 0 | 1 | missed firehose,streaming | 0.55 | 2928 | 609 | 10/2 | 0 | 2 | 1 | 7 | 4 |
| azure | event-iot | Most optimized | 11 | 0 | 0 | 1 (7) | 0 | 0 | 1 | missed iot | 4.06 | 2671 | 712 | 11/2 | 0 | 3 | 0 | 4 | 5 |
| azure | serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.68 | 2177 | 871 | 11/0 | 0 | 2 | 0 | 4 | 3 |
| azure | serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.83 | 3296 | 1056 | 13/0 | 0 | 3 | 0 | 8 | 3 |
| azure | serverless-api | Most optimized | 11 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.77 | 3567 | 902 | 17/0 | 1 | 3 | 0 | 9 | 3 |
| azure | ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.65 | 2197 | 691 | 12/0 | 0 | 2 | 0 | 6 | 3 |
| azure | ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.84 | 2676 | 752 | 14/0 | 0 | 3 | 0 | 7 | 3 |
| azure | ai-vision | Most optimized | 12 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.79 | 4456 | 912 | 17/1 | 1 | 3 | 0 | 9 | 3 |
