-- WhichCloud cost analytics on Amazon Athena (ap-south-1)
-- Data: 841 real cost line items exported by backend/scripts/export_costs_csv.py
-- Location: s3://whichcloud-analytics-616551057703/costs/

-- Setup
CREATE DATABASE IF NOT EXISTS whichcloud;

CREATE EXTERNAL TABLE IF NOT EXISTS whichcloud.costs (
  workload string, tier string, provider string, region string,
  service string, sku string, monthly_cost string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar' = ',', 'quoteChar' = '"')
LOCATION 's3://whichcloud-analytics-616551057703/costs/'
TBLPROPERTIES ('skip.header.line.count' = '1');

-- Typed view with short tier names (OpenCSVSerde reads every column as string)
CREATE OR REPLACE VIEW whichcloud.costs_v AS
SELECT workload,
       CASE WHEN tier LIKE 'Cheapest%' THEN '1 Cheapest'
            WHEN tier LIKE 'Balanced%' THEN '2 Balanced'
            ELSE '3 Grow-into' END AS tier,
       provider, region, service, sku,
       CAST(monthly_cost AS double) AS monthly_cost
FROM whichcloud.costs;

-- 1. Total monthly cost by workload and tier
SELECT workload, tier, ROUND(SUM(monthly_cost), 2) AS total
FROM whichcloud.costs_v
GROUP BY workload, tier
ORDER BY workload, total;

-- 2. Top 5 cost drivers
SELECT split_part(sku, ':', 1) AS service_family, ROUND(SUM(monthly_cost), 2) AS total
FROM whichcloud.costs_v
GROUP BY 1 ORDER BY total DESC LIMIT 5;

-- 3. Average cost per tier (how much reliability costs)
SELECT tier, ROUND(AVG(t), 2) AS avg_total
FROM (SELECT workload, tier, SUM(monthly_cost) AS t
      FROM whichcloud.costs_v GROUP BY 1, 2)
GROUP BY tier ORDER BY avg_total;

-- 4. Free-tier / included line items
SELECT COUNT(*) FILTER (WHERE monthly_cost = 0) AS free_items, COUNT(*) AS all_items
FROM whichcloud.costs_v;
