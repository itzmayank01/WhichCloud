# Diagram layout quality

| fixture | tier | svc | nodeOvl | edge→node | crossings (budget) | labelOvl | orphans | comps | reach | aspect | edgeLen | longest | elk kept/repl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| web-ecommerce | Cheapest | 6 | 0 | 0 | 3 (6) | 0 | 0 | 1 | all | 2.53 | 3812 | 1449 | 11/1 |
| web-ecommerce | Most reliable | 13 | 0 | 0 | 6 (10) | 0 | 0 | 1 | all | 2.36 | 7207 | 1929 | 14/1 |
| web-ecommerce | Most optimized | 14 | 0 | 1 | 8 (11) | 0 | 0 | 1 | all | 2.4 ⚠️ | 7624 | 1982 | 17/1 |
| web-internal-tool | Cheapest | 6 | 0 | 0 | 3 (6) | 0 | 0 | 1 | all | 2.53 | 3812 | 1449 | 11/1 |
| web-internal-tool | Most reliable | 10 | 0 | 0 | 5 (8) | 0 | 0 | 1 | all | 2.62 | 6032 | 1918 | 12/1 |
| web-internal-tool | Most optimized | 14 | 0 | 1 | 8 (11) | 0 | 0 | 1 | all | 2.4 ⚠️ | 7624 | 1982 | 17/1 |
| media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 2.52 | 2323 | 1074 | 8/0 |
| media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 2.31 | 2858 | 1115 | 9/0 |
| media-streaming | Most optimized | 7 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.36 | 3617 | 1188 | 12/0 |
| batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 2.64 | 1213 | 567 | 6/0 |
| batch-etl | Most reliable | 6 | 0 | 0 | 0 (4) | 1 | 0 | 1 | all | 2.42 ⚠️ | 1552 | 486 | 7/0 |
| batch-etl | Most optimized | 6 | 0 | 0 | 3 (5) | 0 | 0 | 1 | all | 2.98 | 4706 | 1893 | 9/0 |
| event-iot | Cheapest | 8 | 0 | 0 | 2 (6) | 1 | 0 | 1 | all | 2.54 ⚠️ | 3615 | 1007 | 11/0 |
| event-iot | Most reliable | 10 | 0 | 0 | 4 (6) | 0 | 0 | 1 | missed firehose,streaming | 2.76 | 4138 | 862 | 10/2 |
| event-iot | Most optimized | 11 | 0 | 0 | 18 (9) | 1 | 0 | 1 | missed iot | 3.13 ⚠️ | 6877 | 1141 | 13/5 |
| serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.68 | 2177 | 871 | 11/0 |
| serverless-api | Most reliable | 8 | 0 | 0 | 5 (7) | 0 | 0 | 1 | all | 0.82 | 2881 | 671 | 13/1 |
| serverless-api | Most optimized | 11 | 0 | 0 | 2 (9) | 0 | 0 | 1 | all | 0.79 | 3813 | 826 | 17/1 |
| ai-vision | Cheapest | 7 | 0 | 0 | 1 (7) | 0 | 0 | 1 | all | 0.65 | 2422 | 705 | 12/1 |
| ai-vision | Most reliable | 9 | 0 | 0 | 3 (8) | 0 | 0 | 1 | all | 0.83 | 3629 | 777 | 15/1 |
| ai-vision | Most optimized | 12 | 0 | 0 | 8 (10) | 0 | 0 | 1 | all | 0.86 | 5543 | 989 | 19/1 |
