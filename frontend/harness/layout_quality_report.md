# Diagram layout quality

| fixture | tier | services | node ovl | edge→node | crossings (budget) | label ovl | orphans | components | reach(users) | aspect |
|---|---|---|---|---|---|---|---|---|---|---|
| web-ecommerce | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3.28 |
| web-ecommerce | Most reliable | 13 | 0 | 0 | 5 (10) | 0 | 0 | 1 | all | 2.86 |
| web-ecommerce | Most optimized | 14 | 0 | 0 | 7 (11) | 0 | 0 | 1 | all | 2.91 |
| web-internal-tool | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 3.28 |
| web-internal-tool | Most reliable | 10 | 0 | 0 | 5 (8) | 0 | 0 | 1 | all | 3.27 |
| web-internal-tool | Most optimized | 14 | 0 | 0 | 7 (11) | 0 | 0 | 1 | all | 2.91 |
| media-streaming | Cheapest | 5 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 3.45 |
| media-streaming | Most reliable | 6 | 0 | 0 | 0 (5) | 0 | 0 | 1 | all | 3.06 |
| media-streaming | Most optimized | 7 | 0 | 0 | 1 (6) | 0 | 0 | 1 | all | 3.13 |
| batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 3.16 |
| batch-etl | Most reliable | 6 | 0 | 0 | 0 (4) | 1 | 0 | 1 | all | 2.85 ⚠️ |
| batch-etl | Most optimized | 6 | 0 | 0 | 3 (5) | 1 | 0 | 1 | all | 3.35 ⚠️ |
| event-iot | Cheapest | 8 | 0 | 0 | 2 (6) | 1 | 0 | 1 | all | 2.53 ⚠️ |
| event-iot | Most reliable | 10 | 0 | 0 | 2 (6) | 0 | 0 | 1 | missed firehose,streaming | 3.22 |
| event-iot | Most optimized | 11 | 0 | 2 | 6 (9) | 0 | 0 | 1 | missed iot | 3.58 ⚠️ |
| serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.68 |
| serverless-api | Most reliable | 8 | 0 | 0 | 1 (7) | 0 | 0 | 1 | all | 0.82 |
| serverless-api | Most optimized | 11 | 0 | 1 | 3 (9) | 1 | 0 | 1 | all | 0.79 ⚠️ |
| ai-vision | Cheapest | 7 | 0 | 0 | 0 (7) | 0 | 0 | 1 | all | 0.65 |
| ai-vision | Most reliable | 9 | 0 | 1 | 3 (8) | 1 | 0 | 1 | all | 0.83 ⚠️ |
| ai-vision | Most optimized | 12 | 0 | 1 | 4 (10) | 0 | 0 | 1 | all | 0.86 ⚠️ |
