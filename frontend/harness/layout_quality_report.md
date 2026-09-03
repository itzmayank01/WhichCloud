# Diagram layout quality

| fixture | tier | services | node ovl | edge→node | crossings (budget) | label ovl | orphans | components | reach(users) | aspect |
|---|---|---|---|---|---|---|---|---|---|---|
| web-ecommerce | Cheapest | 6 | 0 | 0 | 2 (6) | 0 | 0 | 1 | all | 0.91 |
| web-ecommerce | Most reliable | 13 | 0 | 0 | 6 (10) | 0 | 0 | 1 | all | 0.87 |
| web-ecommerce | Most optimized | 14 | 0 | 0 | 11 (11) | 0 | 0 | 1 | all | 0.81 |
| web-internal-tool | Cheapest | 6 | 0 | 0 | 2 (6) | 0 | 0 | 1 | all | 0.81 |
| web-internal-tool | Most reliable | 10 | 0 | 0 | 8 (8) | 0 | 0 | 1 | all | 0.76 |
| web-internal-tool | Most optimized | 14 | 0 | 0 | 11 (11) | 0 | 0 | 1 | all | 0.81 |
| media-streaming | Cheapest | 5 | 0 | 0 | 4 (4) | 0 | 0 | 1 | all | 0.9 |
| media-streaming | Most reliable | 6 | 0 | 0 | 2 (5) | 0 | 0 | 1 | all | 1.03 |
| media-streaming | Most optimized | 7 | 0 | 0 | 5 (6) | 0 | 0 | 1 | all | 0.93 |
| batch-etl | Cheapest | 5 | 0 | 0 | 4 (3) | 0 | 0 | 1 | all | 0.83 ⚠️ |
| batch-etl | Most reliable | 6 | 0 | 0 | 3 (4) | 0 | 0 | 1 | all | 0.94 |
| batch-etl | Most optimized | 6 | 0 | 0 | 6 (5) | 0 | 0 | 1 | all | 1.18 ⚠️ |
| event-iot | Cheapest | 8 | 0 | 0 | 13 (6) | 0 | 0 | 1 | all | 0.79 ⚠️ |
| event-iot | Most reliable | 10 | 0 | 0 | 27 (6) | 0 | 0 | 1 | missed firehose,streaming | 0.8 ⚠️ |
| event-iot | Most optimized | 11 | 0 | 0 | 42 (9) | 0 | 0 | 1 | missed iot | 0.97 ⚠️ |
| serverless-api | Cheapest | 6 | 0 | 0 | 11 (6) | 0 | 0 | 1 | all | 1.09 ⚠️ |
| serverless-api | Most reliable | 8 | 0 | 0 | 17 (7) | 0 | 0 | 1 | all | 1.03 ⚠️ |
| serverless-api | Most optimized | 11 | 0 | 0 | 22 (9) | 0 | 0 | 1 | all | 0.85 ⚠️ |
| ai-vision | Cheapest | 7 | 0 | 0 | 15 (7) | 0 | 0 | 1 | all | 1.12 ⚠️ |
| ai-vision | Most reliable | 9 | 0 | 0 | 32 (8) | 0 | 0 | 1 | all | 1.03 ⚠️ |
| ai-vision | Most optimized | 12 | 0 | 0 | 57 (10) | 0 | 0 | 1 | all | 0.85 ⚠️ |
