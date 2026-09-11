# Diagram layout quality

| cloud | fixture | tier | svc | nodeOvl | edge→node | crossings (budget) | labelOvl | orphans | comps | reach | aspect | edgeLen | longest | elk kept/repl | cyc | fanOut | collin | rankSpan | orphan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aws | web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.56 | 2258 | 779 | 10/1 | 0 | 3 | 0 | 5 | 6 |
| aws | web-ecommerce | Most reliable | 13 | 0 | 0 | 3 (10) | 0 | 0 | 1 | all | 2.36 | 7207 | 1929 | 14/1 | 0 | 4 | 0 | 14 | 6 |
| aws | web-ecommerce | Most optimized | 14 | 0 | 0 | 5 (11) | 0 | 0 | 1 | all | 2.42 | 7952 | 2002 | 17/1 | 1 | 4 | 1 | 14 | 6 |
| aws | web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.56 | 2258 | 779 | 10/1 | 0 | 3 | 0 | 5 | 5 |
| aws | web-internal-tool | Most reliable | 10 | 0 | 0 | 2 (8) | 0 | 0 | 1 | all | 2.62 | 6032 | 1918 | 12/1 | 0 | 3 | 0 | 14 | 5 |
| aws | web-internal-tool | Most optimized | 14 | 0 | 0 | 5 (11) | 0 | 0 | 1 | all | 2.42 | 7952 | 2002 | 17/1 | 1 | 4 | 1 | 13 | 5 |
| aws | media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 2.55 | 1169 | 474 | 7/0 | 0 | 2 | 0 | 5 | 6 |
| aws | media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 2.31 | 2858 | 1115 | 9/0 | 0 | 2 | 0 | 7 | 6 |
| aws | media-streaming | Most optimized | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.36 | 3617 | 1188 | 12/0 | 1 | 3 | 0 | 7 | 6 |
| aws | batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 2.69 | 621 | 231 | 5/0 | 0 | 1 | 0 | 3 | 4 |
| aws | batch-etl | Most reliable | 6 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 2.71 | 960 | 319 | 6/0 | 0 | 2 | 0 | 3 | 5 |
| aws | batch-etl | Most optimized | 6 | 0 | 0 | 1 (4) | 0 | 0 | 1 | all | 2.81 | 2285 | 872 | 6/1 | 0 | 2 | 0 | 5 | 6 |
| aws | event-iot | Cheapest | 8 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.58 | 3675 | 1007 | 11/0 | 0 | 3 | 0 | 3 | 3 |
| aws | event-iot | Most reliable | 10 | 0 | 0 | 2 (6) | 0 | 0 | 1 | missed firehose,streaming | 2.76 | 4138 | 862 | 10/2 | 0 | 2 | 1 | 6 | 4 |
| aws | event-iot | Most optimized | 11 | 0 | 0 | 1 (7) | 0 | 0 | 1 | missed iot | 3.23 | 2792 | 749 | 11/2 | 0 | 3 | 0 | 4 | 5 |
| aws | serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.68 | 2177 | 871 | 11/0 | 0 | 2 | 0 | 4 | 3 |
| aws | serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.83 | 3296 | 1056 | 13/0 | 0 | 3 | 0 | 8 | 3 |
| aws | serverless-api | Most optimized | 11 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.77 | 3567 | 902 | 17/0 | 1 | 3 | 0 | 9 | 3 |
| aws | ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.65 | 2197 | 691 | 12/0 | 0 | 2 | 0 | 6 | 3 |
| aws | ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.84 | 2676 | 752 | 14/0 | 0 | 3 | 0 | 7 | 3 |
| aws | ai-vision | Most optimized | 12 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.79 | 4456 | 912 | 17/1 | 1 | 3 | 0 | 9 | 3 |
| gcp | web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.21 | 2374 | 624 | 11/0 | 0 | 3 | 0 | 5 | 6 |
| gcp | web-ecommerce | Most reliable | 12 | 0 | 0 | 2 (9) | 0 | 0 | 1 | all | 1.3 | 6136 | 1160 | 15/0 | 0 | 4 | 2 | 12 | 6 |
| gcp | web-ecommerce | Most optimized | 13 | 0 | 0 | 2 (11) | 0 | 0 | 1 | all | 1.21 | 6337 | 1183 | 17/1 | 1 | 4 | 2 | 11 | 6 |
| gcp | web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.21 | 2374 | 624 | 11/0 | 0 | 3 | 0 | 5 | 5 |
| gcp | web-internal-tool | Most reliable | 9 | 0 | 0 | 0 (8) | 0 | 0 | 1 | all | 1 | 3718 | 847 | 13/0 | 0 | 3 | 0 | 5 | 5 |
| gcp | web-internal-tool | Most optimized | 13 | 0 | 0 | 2 (11) | 0 | 0 | 1 | all | 1.21 | 6337 | 1183 | 17/1 | 1 | 4 | 2 | 11 | 5 |
| gcp | media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 2.35 | 917 | 433 | 7/0 | 0 | 2 | 0 | 5 | 6 |
| gcp | media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 0.95 | 1939 | 781 | 9/0 | 0 | 2 | 0 | 4 | 6 |
| gcp | media-streaming | Most optimized | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.3 | 2404 | 997 | 11/1 | 1 | 3 | 0 | 6 | 6 |
| gcp | batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 2.79 | 556 | 231 | 5/0 | 0 | 1 | 0 | 3 | 4 |
| gcp | batch-etl | Most reliable | 6 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 2.81 | 895 | 314 | 6/0 | 0 | 2 | 0 | 3 | 5 |
| gcp | batch-etl | Most optimized | 6 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 3.19 | 1331 | 734 | 6/1 | 0 | 2 | 0 | 5 | 6 |
| gcp | event-iot | Cheapest | 8 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.22 | 3249 | 772 | 11/0 | 0 | 3 | 0 | 3 | 3 |
| gcp | event-iot | Most reliable | 10 | 0 | 0 | 1 (6) | 0 | 0 | 1 | missed firehose,streaming | 2.65 | 3685 | 874 | 11/1 | 0 | 2 | 3 | 6 | 4 |
| gcp | event-iot | Most optimized | 11 | 0 | 0 | 3 (7) | 0 | 0 | 1 | missed iot | 0.66 | 3882 | 684 | 10/3 | 0 | 3 | 2 | 7 | 5 |
| gcp | serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.63 | 1970 | 915 | 11/0 | 0 | 2 | 0 | 5 | 3 |
| gcp | serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.82 | 3374 | 1086 | 13/0 | 0 | 3 | 0 | 8 | 3 |
| gcp | serverless-api | Most optimized | 11 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.76 | 3645 | 941 | 17/0 | 1 | 3 | 0 | 7 | 3 |
| gcp | ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.66 | 1990 | 878 | 12/0 | 0 | 2 | 0 | 5 | 3 |
| gcp | ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.83 | 2754 | 791 | 14/0 | 0 | 3 | 0 | 6 | 3 |
| gcp | ai-vision | Most optimized | 12 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.78 | 4534 | 960 | 17/1 | 1 | 3 | 0 | 10 | 3 |
| azure | web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.87 | 2636 | 796 | 11/0 | 0 | 3 | 0 | 5 | 6 |
| azure | web-ecommerce | Most reliable | 12 | 0 | 0 | 2 (9) | 0 | 0 | 1 | all | 1.12 | 8110 | 1766 | 14/1 | 0 | 4 | 1 | 12 | 6 |
| azure | web-ecommerce | Most optimized | 13 | 0 | 0 | 8 (11) | 0 | 0 | 1 | all | 0.93 | 8076 | 1670 | 15/3 | 1 | 4 | 3 | 12 | 6 |
| azure | web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.87 | 2636 | 796 | 11/0 | 0 | 3 | 0 | 5 | 5 |
| azure | web-internal-tool | Most reliable | 9 | 0 | 0 | 0 (8) | 0 | 0 | 1 | all | 0.85 | 5799 | 1559 | 12/1 | 0 | 3 | 0 | 9 | 5 |
| azure | web-internal-tool | Most optimized | 13 | 0 | 0 | 8 (11) | 0 | 0 | 1 | all | 0.93 | 8076 | 1670 | 15/3 | 1 | 4 | 3 | 12 | 5 |
| azure | media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 2.77 | 1087 | 433 | 7/0 | 0 | 2 | 0 | 5 | 6 |
| azure | media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 2.51 | 3420 | 1134 | 9/0 | 0 | 2 | 0 | 8 | 6 |
| azure | media-streaming | Most optimized | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.65 | 4286 | 1299 | 12/0 | 1 | 3 | 0 | 6 | 6 |
| azure | batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 2.87 | 579 | 231 | 5/0 | 0 | 1 | 0 | 3 | 4 |
| azure | batch-etl | Most reliable | 6 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 2.89 | 918 | 319 | 6/0 | 0 | 2 | 0 | 3 | 5 |
| azure | batch-etl | Most optimized | 6 | 0 | 0 | 1 (4) | 0 | 0 | 1 | all | 3.13 | 2020 | 750 | 6/1 | 0 | 2 | 0 | 5 | 6 |
| azure | event-iot | Cheapest | 8 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.51 | 3325 | 944 | 11/0 | 0 | 3 | 0 | 3 | 3 |
| azure | event-iot | Most reliable | 10 | 0 | 0 | 2 (6) | 0 | 0 | 1 | missed firehose,streaming | 2.91 | 3785 | 820 | 10/2 | 0 | 2 | 5 | 6 | 4 |
| azure | event-iot | Most optimized | 11 | 0 | 0 | 1 (7) | 0 | 0 | 1 | missed iot | 3.73 | 2569 | 610 | 11/2 | 0 | 3 | 1 | 4 | 5 |
| azure | serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.68 | 2177 | 871 | 11/0 | 0 | 2 | 0 | 4 | 3 |
| azure | serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.83 | 3296 | 1056 | 13/0 | 0 | 3 | 0 | 8 | 3 |
| azure | serverless-api | Most optimized | 11 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.77 | 3567 | 902 | 17/0 | 1 | 3 | 0 | 9 | 3 |
| azure | ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.65 | 2197 | 691 | 12/0 | 0 | 2 | 0 | 6 | 3 |
| azure | ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.84 | 2676 | 752 | 14/0 | 0 | 3 | 0 | 7 | 3 |
| azure | ai-vision | Most optimized | 12 | 0 | 0 | 0 (9) | 0 | 0 | 1 | all | 0.79 | 4456 | 912 | 17/1 | 1 | 3 | 0 | 9 | 3 |
