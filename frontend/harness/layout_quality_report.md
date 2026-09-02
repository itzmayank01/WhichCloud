# Diagram layout quality

| fixture | tier | services | node ovl | edge→node | crossings (budget) | label ovl | orphans | components | reach(users) | aspect |
|---|---|---|---|---|---|---|---|---|---|---|
| web-ecommerce | Cheapest | 6 | 0 | 5 | 2 (6) | 0 | 0 | 1 | all | 0.76 ⚠️ |
| web-ecommerce | Most reliable | 9 | 0 | 7 | 8 (8) | 0 | 0 | 1 | all | 0.9 ⚠️ |
| web-ecommerce | Most optimized | 10 | 0 | 2 | 7 (9) | 0 | 0 | 1 | all | 0.85 ⚠️ |
| web-internal-tool | Cheapest | 6 | 0 | 5 | 2 (6) | 0 | 0 | 1 | all | 0.76 ⚠️ |
| web-internal-tool | Most reliable | 7 | 0 | 5 | 5 (7) | 0 | 0 | 1 | all | 0.69 ⚠️ |
| web-internal-tool | Most optimized | 10 | 0 | 2 | 7 (9) | 0 | 0 | 1 | all | 0.85 ⚠️ |
| media-streaming | Cheapest | 5 | 0 | 1 | 0 (4) | 0 | 0 | 1 | all | 0.85 ⚠️ |
| media-streaming | Most reliable | 6 | 0 | 0 | 5 (5) | 0 | 0 | 1 | all | 0.84 |
| media-streaming | Most optimized | 7 | 0 | 1 | 2 (6) | 0 | 0 | 1 | all | 0.77 ⚠️ |
| batch-etl | Cheapest | 5 | 0 | 0 | 0 (3) | 0 | 0 | 1 | all | 0.67 |
| batch-etl | Most reliable | 6 | 0 | 0 | 0 (4) | 0 | 0 | 1 | all | 0.83 |
| batch-etl | Most optimized | 6 | 0 | 3 | 1 (5) | 0 | 0 | 1 | all | 0.88 ⚠️ |
| event-iot | Cheapest | 8 | 0 | 2 | 0 (6) | 0 | 0 | 1 | all | 0.46 ⚠️ |
| event-iot | Most reliable | 10 | 0 | 0 | 1 (6) | 0 | 0 | 1 | missed firehose,streaming | 0.65 |
| event-iot | Most optimized | 11 | 0 | 5 | 13 (9) | 0 | 0 | 1 | missed iot | 0.56 ⚠️ |
| serverless-api | Cheapest | 6 | 0 | 0 | 0 (6) | 0 | 0 | 1 | all | 0.83 |
| serverless-api | Most reliable | 8 | 0 | 3 | 0 (7) | 0 | 0 | 1 | all | 1.01 ⚠️ |
| serverless-api | Most optimized | 11 | 0 | 2 | 0 (9) | 0 | 0 | 1 | all | 1.08 ⚠️ |
| ai-vision | Cheapest | 7 | 0 | 2 | 0 (7) | 0 | 0 | 1 | all | 0.79 ⚠️ |
| ai-vision | Most reliable | 9 | 0 | 3 | 0 (8) | 0 | 0 | 1 | all | 1.01 ⚠️ |
| ai-vision | Most optimized | 12 | 0 | 1 | 0 (10) | 1 | 0 | 1 | all | 1.1 ⚠️ |
