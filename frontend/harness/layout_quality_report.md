# Diagram layout quality

| fixture | tier | svc | nodeOvl | edge→node | crossings (budget) | labelOvl | orphans | comps | reach | aspect | edgeLen | longest | elk kept/repl | cyc | fanOut | collin | rankSpan | orphan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| web-ecommerce | Cheapest | 6 | 0 | 0 | 3 (6) | 0 | 0 | 1 | all | 2.56 | 2258 | 779 | 10/1 | 0 | 3 | 0 | 5 | 6 |
| web-ecommerce | Most reliable | 13 | 0 | 0 | 6 (10) | 0 | 0 | 1 | all | 2.36 | 7207 | 1929 | 14/1 | 0 | 4 | 0 | 14 | 6 |
| web-ecommerce | Most optimized | 14 | 0 | 0 | 8 (11) | 0 | 0 | 1 | all | 2.42 | 7952 | 2002 | 17/1 | 1 | 4 | 1 | 14 | 6 |
| web-internal-tool | Cheapest | 6 | 0 | 0 | 3 (6) | 0 | 0 | 1 | all | 2.56 | 2258 | 779 | 10/1 | 0 | 3 | 0 | 5 | 5 |
| web-internal-tool | Most reliable | 10 | 0 | 0 | 5 (8) | 0 | 0 | 1 | all | 2.62 | 6032 | 1918 | 12/1 | 0 | 3 | 0 | 14 | 5 |
| web-internal-tool | Most optimized | 14 | 0 | 0 | 8 (11) | 0 | 0 | 1 | all | 2.42 | 7952 | 2002 | 17/1 | 1 | 4 | 1 | 13 | 5 |
| media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 2.55 | 1169 | 474 | 7/0 | 0 | 2 | 0 | 5 | 6 |
| media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 2.31 | 2858 | 1115 | 9/0 | 0 | 2 | 0 | 7 | 6 |
| media-streaming | Most optimized | 7 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.36 | 3617 | 1188 | 12/0 | 1 | 3 | 0 | 7 | 6 |
| batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 2.69 | 621 | 231 | 5/0 | 0 | 1 | 0 | 3 | 4 |
| batch-etl | Most reliable | 6 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 2.71 | 960 | 319 | 6/0 | 0 | 2 | 0 | 3 | 5 |
| batch-etl | Most optimized | 6 | 0 | 0 | 3 (4) | 0 | 0 | 1 | all | 2.81 | 2285 | 872 | 6/1 | 0 | 2 | 0 | 5 | 6 |
| event-iot | Cheapest | 8 | 0 | 0 | 2 (6) | 0 | 0 | 1 | all | 2.58 | 3675 | 1007 | 11/0 | 0 | 3 | 0 | 3 | 3 |
| event-iot | Most reliable | 10 | 0 | 0 | 4 (6) | 0 | 0 | 1 | missed firehose,streaming | 2.76 | 4138 | 862 | 10/2 | 0 | 2 | 1 | 6 | 4 |
| event-iot | Most optimized | 11 | 0 | 0 | 2 (7) | 0 | 0 | 1 | missed iot | 3.23 | 2792 | 749 | 11/2 | 0 | 3 | 0 | 4 | 5 |
| serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.68 | 2177 | 871 | 11/0 | 0 | 2 | 0 | 4 | 3 |
| serverless-api | Most reliable | 8 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.83 | 3296 | 1056 | 13/0 | 0 | 3 | 0 | 8 | 3 |
| serverless-api | Most optimized | 11 | 0 | 0 | 1 (9) | 0 | 0 | 1 | all | 0.77 | 3567 | 902 | 17/0 | 1 | 3 | 0 | 9 | 3 |
| ai-vision | Cheapest | 7 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.65 | 2197 | 691 | 12/0 | 0 | 2 | 0 | 6 | 3 |
| ai-vision | Most reliable | 9 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.84 | 2676 | 752 | 14/0 | 0 | 3 | 0 | 7 | 3 |
| ai-vision | Most optimized | 12 | 0 | 0 | 2 (9) | 0 | 0 | 1 | all | 0.79 | 4456 | 912 | 17/1 | 1 | 3 | 0 | 9 | 3 |
