# WhichCloud Cost Analytics (Amazon S3 + Athena + QuickSight)

An analytics layer on top of the WhichCloud engine. The engine's real priced
output is exported, queried with SQL in Amazon Athena, and explored in an
interactive Amazon QuickSight dashboard.

![Dashboard overview](screenshots/quicksight-dashboard-overview.png)
![Dashboard detail](screenshots/quicksight-dashboard-details.png)

## Pipeline

1. **Export**: `backend/scripts/export_costs_csv.py` runs all 13 test fixtures
   through the engine (decision mode, no LLM) and writes one row per priced
   line item: 841 rows in `data/whichcloud_costs.csv`.
2. **Store**: CSV uploaded to a private S3 bucket in ap-south-1 (Mumbai).
3. **Query**: Athena external table (OpenCSVSerde) plus a typed view `costs_v`.
   All SQL is in `queries.sql`; `athena_run.sh` runs a query from the CLI.
4. **Visualise**: QuickSight data source, dataset and dashboard are created as
   code by `build_dashboard.py` (analysis/dashboard definitions in JSON).

## Dashboard

- KPIs: total monthly cost, priced line items, free/included line items
- Monthly cost by workload and architecture tier
- Cost of reliability: total by tier
- Top 10 cost drivers by service family
- Workload cost detail table
- Interactive: Workload and Tier filters, click any bar to filter everything

## Findings

- Average monthly cost per workload rises from $546 (Cheapest) to $657
  (Balanced) to $827 (Grow-into): reliability adds about 51% end to end.
- Compute (t3a.large) and backups are the two biggest cost drivers.
- 164 of 841 line items cost $0 (free tier or included in another service).
- The Athena tier totals match the engine's golden regression totals.

## Files

| File | Purpose |
|---|---|
| `queries.sql` | Athena DDL, view and the analysis queries |
| `athena_run.sh` | Run one Athena query from the CLI and print results |
| `build_dashboard.py` | Generates the QuickSight analysis/dashboard definition |
| `dataset.json` | QuickSight dataset definition (Athena direct query) |
| `analysis.json`, `dashboard.json` | Generated definitions |
| `data/whichcloud_costs.csv` | Exported engine output (841 line items) |
