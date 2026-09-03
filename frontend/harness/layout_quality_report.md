# Diagram layout quality

| fixture | tier | services | node ovl | edge→node | crossings (budget) | label ovl | orphans | components | reach(users) | aspect |
|---|---|---|---|---|---|---|---|---|---|---|
| web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.36 |
| web-ecommerce | Most reliable | 13 | 0 | 0 | 6 (10) | 0 | 0 | 1 | all | 2.23 |
| web-ecommerce | Most optimized | 14 | 0 | 0 | 8 (11) | 0 | 0 | 1 | all | 2.27 |
| web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 2.36 |
| web-internal-tool | Most reliable | 10 | 0 | 0 | 5 (8) | 0 | 0 | 1 | all | 2.47 |
| web-internal-tool | Most optimized | 14 | 0 | 0 | 8 (11) | 0 | 0 | 1 | all | 2.27 |
| media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 2.31 |
| media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 2.12 |
| media-streaming | Most optimized | 7 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 2.17 |
| batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 2.05 |
| batch-etl | Most reliable | 6 | 0 | 0 | 0 (4) | 1 | 0 | 1 | all | 1.91 ⚠️ |
| batch-etl | Most optimized | 6 | 0 | 0 | 3 (5) | 1 | 0 | 1 | all | 2.27 ⚠️ |
| event-iot | Cheapest | 8 | 0 | 0 | 2 (6) | 1 | 0 | 1 | all | 1.75 ⚠️ |
| event-iot | Most reliable | 10 | 0 | 0 | 4 (6) | 0 | 0 | 1 | missed firehose,streaming | 2.26 |
| event-iot | Most optimized | 11 | 0 | 2 | 9 (9) | 1 | 0 | 1 | missed iot | 2.63 ⚠️ |
| serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 1.91 |
| serverless-api | Most reliable | 8 | 0 | 0 | 1 (7) | 0 | 0 | 1 | all | 1.75 |
| serverless-api | Most optimized | 11 | 0 | 1 | 3 (9) | 1 | 0 | 1 | all | 1.95 ⚠️ |
| ai-vision | Cheapest | 7 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 1.93 |
| ai-vision | Most reliable | 9 | 0 | 1 | 3 (8) | 0 | 0 | 1 | all | 1.75 ⚠️ |
| ai-vision | Most optimized | 12 | 0 | 0 | 3 (10) | 1 | 0 | 1 | all | 1.88 ⚠️ |
