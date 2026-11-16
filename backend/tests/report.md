# WhichCloud regression harness report

Run at 2026-11-16 17:21:02 UTC

## Architecture fingerprint matrix

| fixture | archetype | tier-1 services | tier spread |
|---|---|---|---|
| batch-etl | batch_etl | 7 | [6, 6] |
| budget-floor-conflict | web_app | 16 | [6, 0] _(declared: no further improvement)_ |
| coaching-platform | web_app | 21 | [7, 0] _(declared: no further improvement)_ |
| ecommerce-scale | web_app | 17 | [8, 0] _(declared: no further improvement)_ |
| event-webhook | event_driven | 10 | [5, 6] |
| fintech-bengaluru | web_app | 17 | [6, 5] |
| hospital-pune | web_app | 17 | [7, 0] _(declared: no further improvement)_ |
| hospital-pune-public | web_app | 18 | [8, 0] _(declared: no further improvement)_ |
| internal-low-stakes | web_app | 10 | [7, 0] _(declared: no further improvement)_ |
| ml-inference | ml_inference | 8 | [8, 5] |
| realtime-chat | realtime | 8 | [5, 6] |
| static-site | static_site | 6 | [3, 4] |
| vm-migration | migration | 10 | [4, 4] |

**Divergence** (different profile, same tier-1 fingerprint — each one is the template bug): none

**Tier spread** (consecutive tiers must differ by >= 3 services, or say no further improvement is worth buying): none thin

Coverage: **13** fixture(s) priced, **0** withheld.

| fixture | passed | failed | status |
|---|---|---|---|
| batch-etl | 130 | 0 | OK |
| budget-floor-conflict | 115 | 0 | OK |
| catalog-region-integrity | 5 | 0 | OK |
| coaching-platform | 158 | 0 | OK |
| ecommerce-scale | 139 | 0 | OK |
| event-webhook | 144 | 0 | OK |
| fintech-bengaluru | 136 | 0 | OK |
| hospital-pune-public | 155 | 0 | OK |
| hospital-pune | 148 | 0 | OK |
| internal-low-stakes | 122 | 0 | OK |
| ml-inference | 133 | 0 | OK |
| realtime-chat | 142 | 0 | OK |
| static-site | 126 | 0 | OK |
| vm-migration | 137 | 0 | OK |

## batch-etl

Tier totals: tier_1=$693.33, tier_2=$722.79, tier_3=$1,758.08

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:object_storage:tier_1 | pass | object_storage present | present |  |
| must_include:object_storage:tier_2 | pass | object_storage present | present |  |
| must_include:object_storage:tier_3 | pass | object_storage present | present |  |
| must_include:backup:tier_1 | pass | backup present | present |  |
| must_include:backup:tier_2 | pass | backup present | present |  |
| must_include:backup:tier_3 | pass | backup present | present |  |
| must_include:event_bus:tier_1 | pass | event_bus present | present |  |
| must_include:event_bus:tier_2 | pass | event_bus present | present |  |
| must_include:event_bus:tier_3 | pass | event_bus present | present |  |
| must_include:glue_etl:tier_2 | pass | glue_etl present | present |  |
| must_include:glue_etl:tier_3 | pass | glue_etl present | present |  |
| must_include:athena:tier_2 | pass | athena present | present |  |
| must_include:athena:tier_3 | pass | athena present | present |  |
| must_include:warehouse:tier_3 | pass | warehouse present | present |  |
| must_include:archive_tier:tier_3 | pass | archive_tier present | present |  |
| must_include:object_lock:tier_3 | pass | object_lock present | present |  |
| must_exclude:relational_database:tier_1 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:relational_database:tier_2 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:relational_database:tier_3 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_1 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_2 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_3 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:cdn:tier_1 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_2 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_3 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:nat_gateway:tier_1 | pass | nat_gateway absent | absent | instances run in a public subnet; nothing about this workload requires network isolation |
| must_exclude:nat_gateway:tier_2 | pass | nat_gateway absent | absent | instances run in a public subnet; nothing about this workload requires network isolation |
| must_exclude:nat_gateway:tier_3 | pass | nat_gateway absent | absent | instances run in a public subnet; nothing about this workload requires network isolation |
| must_exclude:cache:tier_1 | pass | cache absent | absent | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cache:tier_2 | pass | cache absent | absent | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cache:tier_3 | pass | cache absent | absent | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:read_replica:tier_1 | pass | read_replica absent | absent | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:read_replica:tier_2 | pass | read_replica absent | absent | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:read_replica:tier_3 | pass | read_replica absent | absent | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:waf:tier_1 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| must_exclude:waf:tier_2 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| must_exclude:waf:tier_3 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| complete:tier_1 | pass | every selected component has a catalog rate | complete |  |
| complete:tier_2 | pass | every selected component has a catalog rate | complete |  |
| complete:tier_3 | pass | every selected component has a catalog rate | complete |  |
| forbidden:tier_1 | pass | no component forbidden by batch_etl | none of 3 forbidden components |  |
| forbidden:tier_2 | pass | no component forbidden by batch_etl | none of 3 forbidden components |  |
| forbidden:tier_3 | pass | no component forbidden by batch_etl | none of 3 forbidden components |  |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 1 NAT gateways | 0 |  |
| INV-2:tier_2 | pass | <= 1 NAT gateways | 0 |  |
| INV-2:tier_3 | pass | <= 1 NAT gateways | 0 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:CloudFront (CDN): not added, 0 | pass | non-empty reason string | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |  |
| INV-5:AWS WAF: not added, staff-only | pass | non-empty reason string | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |  |
| INV-5:ElastiCache: not added, 0.00 p | pass | non-empty reason string | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 0.00  | pass | non-empty reason string | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-8:tier_1 | pass | sum of line items == 693.33 | 693.33 |  |
| INV-8:tier_2 | pass | sum of line items == 722.79 | 722.79 |  |
| INV-8:tier_3 | pass | sum of line items == 1758.08 | 1758.08 |  |
| INV-9:tier_1:t4g.xlarge:spot | pass | sku exists in region ap-south-1 | found | Compute × 1 (spot) |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:eventbridge:events | pass | sku exists in region ap-south-1 | found | Event bus |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_1:s3:put-requests | pass | sku exists in region ap-south-1 | found | Object storage write requests |
| INV-9:tier_1:s3:get-requests | pass | sku exists in region ap-south-1 | found | Object storage read requests |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:sns:requests | pass | sku exists in region ap-south-1 | found | Notifications |
| INV-9:tier_2:eventbridge:events | pass | sku exists in region ap-south-1 | found | Event bus |
| INV-9:tier_2:athena:scanned | pass | sku exists in region ap-south-1 | found | Athena data scanned |
| INV-9:tier_2:glue:etl-dpu-hour | pass | sku exists in region ap-south-1 | found | Glue ETL |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:s3:put-requests | pass | sku exists in region ap-south-1 | found | Object storage write requests |
| INV-9:tier_2:s3:get-requests | pass | sku exists in region ap-south-1 | found | Object storage read requests |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 2 |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:sns:requests | pass | sku exists in region ap-south-1 | found | Notifications |
| INV-9:tier_3:eventbridge:events | pass | sku exists in region ap-south-1 | found | Event bus |
| INV-9:tier_3:athena:scanned | pass | sku exists in region ap-south-1 | found | Athena data scanned |
| INV-9:tier_3:glue:etl-dpu-hour | pass | sku exists in region ap-south-1 | found | Glue ETL |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_3:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:rg.large | pass | sku exists in region ap-south-1 | found | Warehouse nodes × 2 |
| INV-9:tier_3:s3:put-requests | pass | sku exists in region ap-south-1 | found | Object storage write requests |
| INV-9:tier_3:s3:get-requests | pass | sku exists in region ap-south-1 | found | Object storage read requests |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 2 |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | (none) | (none) |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=public_simple (availability=low, durability=normal, isolation_required=False) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=3750 durability=normal (assumed) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=3750 durability=normal (assumed) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=3750 durability=normal (assumed) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=6 added=['athena', 'glue', 'kms', 'notification', 'secrets'] dropped=['compute'] | Execution: a self-managed runner you keep alive → AWS Glue billed per DPU-hour, with Athena querying the curated zone in place — removes host patching, schedule |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=6 added=['archive', 'backup_dr', 'object_lock', 'posture', 'tracing', 'warehouse'] dropped=[] | Results: re-scanning Parquet on every query → a columnar warehouse, plus Object Lock and a second-region copy — removes repeat scan cost, and removes losing rea |
| INV-18:tier_1 | pass | compute billed at 8% of 730 hours | duty 8% applied |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 7 nodes, 5 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 11 nodes, 8 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 17 nodes, 12 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 7 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 11 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 17 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 6 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | 6 node(s) differ |  |
| golden_totals:tier_1 | pass | $693.33 | $693.33 |  |
| golden_totals:tier_2 | pass | $722.79 | $722.79 |  |
| golden_totals:tier_3 | pass | $1758.08 | $1758.08 |  |

## budget-floor-conflict

Tier totals: tier_1=$263.89, tier_2=$330.62, tier_3=$330.62

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:multi_az_database:tier_1 | pass | multi_az_database present | present |  |
| must_include:cross_region_backup_copy:tier_1 | pass | cross_region_backup_copy present | present |  |
| budget:tier_1 | pass | False | False | $263.89 vs $80.00 budget |
| over_budget_note | pass | contains 'Your requirements set a floor above your budget.' | Your requirements set a floor above your budget. Cheapest compliant design shown. |  |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_2 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_3 | pass | <= 2 NAT gateways | 2 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:CloudFront (CDN): not added, 0 | pass | non-empty reason string | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |  |
| INV-5:AWS WAF: not added, staff-only | pass | non-empty reason string | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |  |
| INV-5:ElastiCache: not added, 0.00 p | pass | non-empty reason string | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 0.00  | pass | non-empty reason string | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=4 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=0 no_further=True |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-8:tier_1 | pass | sum of line items == 263.89 | 263.89 |  |
| INV-8:tier_2 | pass | sum of line items == 330.62 | 330.62 |  |
| INV-8:tier_3 | pass | sum of line items == 330.62 | 330.62 |  |
| INV-9:tier_1:t4g.medium | pass | sku exists in region ap-south-1 | found | Compute × 2 |
| INV-9:tier_1:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_1:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_1:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_1:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_1:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_1:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_1:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_1:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_1:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_1:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_1:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_2:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_2:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_2:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_2:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_2:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_2:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_2:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_2:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_2:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 2 tasks |
| INV-9:tier_2:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 2 tasks |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_2:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_2:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_2:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_2:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_2:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_3:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_3:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_3:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 2 tasks |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 2 tasks |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_3:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_3:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=high, durability=high, isolation_required=True) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=500 durability=high (stated) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=500 durability=high (stated) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=500 durability=high (stated) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=6 added=['compute_fargate', 'posture', 'secrets', 'threat', 'tracing'] dropped=['compute'] | Compute: self-managed EC2 + Auto Scaling → ECS on Fargate — removes unpatched-host compromise and manual patch-window downtime as risks.; Secrets: environment v |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=0 added=[] dropped=[] (declared no further improvement) |  |
| INV-18 | pass | duty cycle applied wherever it is below 1.0 | no tier has a duty cycle below 1.0 (always-on workload) |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 17 nodes, 15 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 21 nodes, 14 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 21 nodes, 14 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 16 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 20 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 20 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 6 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | identical graph (declared) |  |
| golden_totals:tier_1 | pass | $263.89 | $263.89 |  |
| golden_totals:tier_2 | pass | $330.62 | $330.62 |  |
| golden_totals:tier_3 | pass | $330.62 | $330.62 |  |

## catalog-region-integrity

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| compute-rate-differs-by-region | pass | ap-south-1 rate != us-east-1 rate for t4g.medium | ap-south-1=0.02240000 us-east-1=0.03360000 |  |
| database-rate-differs-by-region | pass | ap-south-1 rate != us-east-1 rate for db.t4g.large | ap-south-1=0.16700000 us-east-1=0.12900000 |  |
| no-catalog-entry-has-a-null-region | pass | 0 rows with a null/empty region | 0 rows |  |
| multi-az-database-costs-more-than-single-az | pass | db.t4g.large:multi-az > db.t4g.large | single=0.16700000 multi=0.33400000 |  |
| guardduty-and-securityhub-scale-with-resource-count | pass | cost(6 instances) > cost(2 instances) > 0 | small=$9.71 large=$24.31 |  |

## coaching-platform

Tier totals: tier_1=$1,202.31, tier_2=$1,269.04, tier_3=$1,269.04

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:cdn:tier_1 | pass | cdn present | present |  |
| must_include:cdn:tier_2 | pass | cdn present | present |  |
| must_include:cdn:tier_3 | pass | cdn present | present |  |
| must_include:email:tier_1 | pass | email present | present |  |
| must_include:email:tier_2 | pass | email present | present |  |
| must_include:email:tier_3 | pass | email present | present |  |
| must_include:queue:tier_1 | pass | queue present | present |  |
| must_include:queue:tier_2 | pass | queue present | present |  |
| must_include:queue:tier_3 | pass | queue present | present |  |
| must_include:load_balancer:tier_1 | pass | load_balancer present | present |  |
| must_include:load_balancer:tier_2 | pass | load_balancer present | present |  |
| must_include:load_balancer:tier_3 | pass | load_balancer present | present |  |
| must_include:multi_az_database:tier_1 | pass | multi_az_database present | present |  |
| must_include:multi_az_database:tier_2 | pass | multi_az_database present | present |  |
| must_include:multi_az_database:tier_3 | pass | multi_az_database present | present |  |
| must_include:backup:tier_1 | pass | backup present | present |  |
| must_include:backup:tier_2 | pass | backup present | present |  |
| must_include:backup:tier_3 | pass | backup present | present |  |
| must_exclude:vpc_flow_logs:tier_1 | pass | vpc_flow_logs absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:vpc_flow_logs:tier_2 | pass | vpc_flow_logs absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:vpc_flow_logs:tier_3 | pass | vpc_flow_logs absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| forbidden:HIPAA | pass | never cites HIPAA | (none) |  |
| forbidden:GDPR | pass | never cites GDPR | (none) |  |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_2 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_3 | pass | <= 2 NAT gateways | 2 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:ElastiCache: not added, 0.00 p | pass | non-empty reason string | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 0.00  | pass | non-empty reason string | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:VPC flow logs: not added, no c | pass | non-empty reason string | VPC flow logs: not added, no compliance obligation requires network audit — they are an audit control billed per GB of traffic, not baseline infrastructure |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=5 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=0 no_further=True |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-8:tier_1 | pass | sum of line items == 1202.31 | 1202.31 |  |
| INV-8:tier_2 | pass | sum of line items == 1269.04 | 1269.04 |  |
| INV-8:tier_3 | pass | sum of line items == 1269.04 | 1269.04 |  |
| INV-9:tier_1:t4g.medium | pass | sku exists in region ap-south-1 | found | Compute × 2 |
| INV-9:tier_1:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_1:cloudfront:data-transfer-out | pass | sku exists in region ap-south-1 | found | CDN data transfer |
| INV-9:tier_1:ses:outbound-email | pass | sku exists in region ap-south-1 | found | Transactional email |
| INV-9:tier_1:sqs:requests | pass | sku exists in region ap-south-1 | found | Queue requests |
| INV-9:tier_1:sns:requests | pass | sku exists in region ap-south-1 | found | Notifications |
| INV-9:tier_1:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_1:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_1:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_1:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_1:vpce:interface-hour | pass | sku exists in region ap-south-1 | found | Interface endpoints × 10 (ECR, SSM, Secrets Manager, CloudWatch Logs, KMS — cheaper than the NAT data they divert) |
| INV-9:tier_1:vpce:gb-processed | pass | sku exists in region ap-south-1 | found | Interface endpoint data processing |
| INV-9:tier_1:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_1:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_1:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_1:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_1:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_1:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_1:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_2:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_2:cloudfront:data-transfer-out | pass | sku exists in region ap-south-1 | found | CDN data transfer |
| INV-9:tier_2:ses:outbound-email | pass | sku exists in region ap-south-1 | found | Transactional email |
| INV-9:tier_2:sqs:requests | pass | sku exists in region ap-south-1 | found | Queue requests |
| INV-9:tier_2:sns:requests | pass | sku exists in region ap-south-1 | found | Notifications |
| INV-9:tier_2:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_2:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_2:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_2:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_2:vpce:interface-hour | pass | sku exists in region ap-south-1 | found | Interface endpoints × 10 (ECR, SSM, Secrets Manager, CloudWatch Logs, KMS — cheaper than the NAT data they divert) |
| INV-9:tier_2:vpce:gb-processed | pass | sku exists in region ap-south-1 | found | Interface endpoint data processing |
| INV-9:tier_2:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_2:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_2:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_2:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_2:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_2:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_2:cognito:user-pool-mau | pass | sku exists in region ap-south-1 | found | Authentication (MAU) |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 2 tasks |
| INV-9:tier_2:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 2 tasks |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_2:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_2:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_2:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_2:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_3:cloudfront:data-transfer-out | pass | sku exists in region ap-south-1 | found | CDN data transfer |
| INV-9:tier_3:ses:outbound-email | pass | sku exists in region ap-south-1 | found | Transactional email |
| INV-9:tier_3:sqs:requests | pass | sku exists in region ap-south-1 | found | Queue requests |
| INV-9:tier_3:sns:requests | pass | sku exists in region ap-south-1 | found | Notifications |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_3:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_3:vpce:interface-hour | pass | sku exists in region ap-south-1 | found | Interface endpoints × 10 (ECR, SSM, Secrets Manager, CloudWatch Logs, KMS — cheaper than the NAT data they divert) |
| INV-9:tier_3:vpce:gb-processed | pass | sku exists in region ap-south-1 | found | Interface endpoint data processing |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_3:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_3:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_3:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_3:cognito:user-pool-mau | pass | sku exists in region ap-south-1 | found | Authentication (MAU) |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 2 tasks |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 2 tasks |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_3:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_3:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | (none) | (none) |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=high, durability=high, isolation_required=False) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=2390.62 durability=high (stated) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=2390.62 durability=high (stated) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=2390.62 durability=high (stated) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=7 added=['auth', 'compute_fargate', 'posture', 'secrets', 'threat', 'tracing'] dropped=['compute'] | Compute: self-managed EC2 + Auto Scaling → ECS on Fargate — removes unpatched-host compromise and manual patch-window downtime as risks.; Identity: static IAM u |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=0 added=[] dropped=[] (declared no further improvement) |  |
| INV-18 | pass | duty cycle applied wherever it is below 1.0 | no tier has a duty cycle below 1.0 (always-on workload) |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 22 nodes, 21 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 27 nodes, 22 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 27 nodes, 22 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 21 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 26 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 26 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 7 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | identical graph (declared) |  |
| golden_totals:tier_1 | pass | $1202.31 | $1202.31 |  |
| golden_totals:tier_2 | pass | $1269.04 | $1269.04 |  |
| golden_totals:tier_3 | pass | $1269.04 | $1269.04 |  |

## ecommerce-scale

Tier totals: tier_1=$1,547.27, tier_2=$1,966.98, tier_3=$1,966.98

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:cdn:tier_2 | pass | cdn present | present |  |
| must_include:cdn:tier_3 | pass | cdn present | present |  |
| must_include:waf:tier_1 | pass | waf present | present |  |
| must_include:waf:tier_2 | pass | waf present | present |  |
| must_include:waf:tier_3 | pass | waf present | present |  |
| must_include:cache:tier_2 | pass | cache present | present |  |
| must_include:cache:tier_3 | pass | cache present | present |  |
| must_include:read_replica:tier_2 | pass | read_replica present | present |  |
| must_include:read_replica:tier_3 | pass | read_replica present | present |  |
| must_include:autoscaling_compute:tier_2 | pass | autoscaling_compute present | present |  |
| must_include:autoscaling_compute:tier_3 | pass | autoscaling_compute present | present |  |
| must_include:multi_az_database:tier_1 | pass | multi_az_database present | present |  |
| must_include:multi_az_database:tier_2 | pass | multi_az_database present | present |  |
| must_include:multi_az_database:tier_3 | pass | multi_az_database present | present |  |
| budget:tier_1 | pass | True | True | $1,547.27 vs $4,000.00 budget |
| budget:tier_2 | pass | True | True | $1,966.98 vs $4,000.00 budget |
| budget:tier_3 | pass | True | True | $1,966.98 vs $4,000.00 budget |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_2 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_3 | pass | <= 2 NAT gateways | 2 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-5:VPC flow logs: not added, no c | pass | non-empty reason string | VPC flow logs: not added, no compliance obligation requires network audit — they are an audit control billed per GB of traffic, not baseline infrastructure |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=4 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=0 no_further=True |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-8:tier_1 | pass | sum of line items == 1547.27 | 1547.27 |  |
| INV-8:tier_2 | pass | sum of line items == 1966.98 | 1966.98 |  |
| INV-8:tier_3 | pass | sum of line items == 1966.98 | 1966.98 |  |
| INV-9:tier_1:c6g.2xlarge | pass | sku exists in region ap-south-1 | found | Compute × 6 |
| INV-9:tier_1:db.t4g.large:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_1:cloudfront:data-transfer-out | pass | sku exists in region ap-south-1 | found | CDN data transfer |
| INV-9:tier_1:cloudfront:requests-https | pass | sku exists in region ap-south-1 | found | CDN requests |
| INV-9:tier_1:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_1:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_1:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_1:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_1:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_1:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_1:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_1:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_1:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_1:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_1:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_2:db.t4g.large:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_2:db.t4g.large | pass | sku exists in region ap-south-1 | found | Database read replica × 2 |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:cache.m8g.large | pass | sku exists in region ap-south-1 | found | Cache |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_2:cloudfront:data-transfer-out | pass | sku exists in region ap-south-1 | found | CDN data transfer |
| INV-9:tier_2:cloudfront:requests-https | pass | sku exists in region ap-south-1 | found | CDN requests |
| INV-9:tier_2:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_2:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_2:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_2:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_2:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_2:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_2:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_2:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_2:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_2:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 6 tasks |
| INV-9:tier_2:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 6 tasks |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_2:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_2:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_2:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_2:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:db.t4g.large:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_3:db.t4g.large | pass | sku exists in region ap-south-1 | found | Database read replica × 2 |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:cache.m8g.large | pass | sku exists in region ap-south-1 | found | Cache |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_3:cloudfront:data-transfer-out | pass | sku exists in region ap-south-1 | found | CDN data transfer |
| INV-9:tier_3:cloudfront:requests-https | pass | sku exists in region ap-south-1 | found | CDN requests |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_3:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_3:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_3:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_3:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 6 tasks |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 6 tasks |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_3:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_3:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | (none) | (none) |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=high, durability=high, isolation_required=False) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=2000 durability=high (assumed) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=2000 durability=high (assumed) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=2000 durability=high (assumed) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=8 added=['cache', 'compute_fargate', 'database_replica', 'posture', 'secrets', 'threat', 'tracing'] dropped=['compute'] | Compute: self-managed EC2 + Auto Scaling → ECS on Fargate — removes unpatched-host compromise and manual patch-window downtime as risks.; Secrets: environment v |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=0 added=[] dropped=[] (declared no further improvement) |  |
| INV-18 | pass | duty cycle applied wherever it is below 1.0 | no tier has a duty cycle below 1.0 (always-on workload) |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 18 nodes, 17 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 24 nodes, 19 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 24 nodes, 19 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 17 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 23 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 23 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 8 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | identical graph (declared) |  |
| INV-4:public_facing | pass | True not written in the prompt | not in prompt text |  |
| golden_totals:tier_1 | pass | $1547.27 | $1547.27 |  |
| golden_totals:tier_2 | pass | $1966.98 | $1966.98 |  |
| golden_totals:tier_3 | pass | $1966.98 | $1966.98 |  |

## event-webhook

Tier totals: tier_1=$137.50, tier_2=$146.40, tier_3=$180.17

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:queue:tier_1 | pass | queue present | present |  |
| must_include:queue:tier_2 | pass | queue present | present |  |
| must_include:queue:tier_3 | pass | queue present | present |  |
| must_include:serverless_compute:tier_1 | pass | serverless_compute present | present |  |
| must_include:serverless_compute:tier_2 | pass | serverless_compute present | present |  |
| must_include:serverless_compute:tier_3 | pass | serverless_compute present | present |  |
| must_include:email:tier_1 | pass | email present | present |  |
| must_include:email:tier_2 | pass | email present | present |  |
| must_include:email:tier_3 | pass | email present | present |  |
| must_include:backup:tier_1 | pass | backup present | present |  |
| must_include:backup:tier_2 | pass | backup present | present |  |
| must_include:backup:tier_3 | pass | backup present | present |  |
| must_include:event_bus:tier_2 | pass | event_bus present | present |  |
| must_include:event_bus:tier_3 | pass | event_bus present | present |  |
| must_include:notifications:tier_2 | pass | notifications present | present |  |
| must_include:notifications:tier_3 | pass | notifications present | present |  |
| must_include:object_lock:tier_3 | pass | object_lock present | present |  |
| must_include:athena:tier_3 | pass | athena present | present |  |
| must_include:archive_tier:tier_3 | pass | archive_tier present | present |  |
| must_exclude:load_balancer:tier_1 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_2 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_3 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:cdn:tier_1 | pass | cdn absent | absent | CloudFront (CDN): not added, 11.57 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_2 | pass | cdn absent | absent | CloudFront (CDN): not added, 11.57 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_3 | pass | cdn absent | absent | CloudFront (CDN): not added, 11.57 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:autoscaling_compute:tier_1 | pass | autoscaling_compute absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:autoscaling_compute:tier_2 | pass | autoscaling_compute absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:autoscaling_compute:tier_3 | pass | autoscaling_compute absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:nat_gateway:tier_1 | pass | nat_gateway absent | absent | nothing runs in a network you own — this design is regional managed services throughout, so isolation is IAM and resource policy rather than subnets, and there is no NAT gateway to buy |
| must_exclude:nat_gateway:tier_2 | pass | nat_gateway absent | absent | nothing runs in a network you own — this design is regional managed services throughout, so isolation is IAM and resource policy rather than subnets, and there is no NAT gateway to buy |
| must_exclude:nat_gateway:tier_3 | pass | nat_gateway absent | absent | nothing runs in a network you own — this design is regional managed services throughout, so isolation is IAM and resource policy rather than subnets, and there is no NAT gateway to buy |
| must_exclude:read_replica:tier_1 | pass | read_replica absent | absent | Read replica: not added, 11.57 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:read_replica:tier_2 | pass | read_replica absent | absent | Read replica: not added, 11.57 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:read_replica:tier_3 | pass | read_replica absent | absent | Read replica: not added, 11.57 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| complete:tier_1 | pass | every selected component has a catalog rate | complete |  |
| complete:tier_2 | pass | every selected component has a catalog rate | complete |  |
| complete:tier_3 | pass | every selected component has a catalog rate | complete |  |
| forbidden:tier_1 | pass | no component forbidden by event_driven | none of 3 forbidden components |  |
| forbidden:tier_2 | pass | no component forbidden by event_driven | none of 3 forbidden components |  |
| forbidden:tier_3 | pass | no component forbidden by event_driven | none of 3 forbidden components |  |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=False |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=False |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=False |  |
| INV-2:tier_1 | pass | <= 2 NAT gateways | 0 |  |
| INV-2:tier_2 | pass | <= 2 NAT gateways | 0 |  |
| INV-2:tier_3 | pass | <= 2 NAT gateways | 0 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:CloudFront (CDN): not added, 1 | pass | non-empty reason string | CloudFront (CDN): not added, 11.57 peak req/sec and staff-only access, no large static assets and no users outside the home country described |  |
| INV-5:AWS WAF: not added, staff-only | pass | non-empty reason string | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |  |
| INV-5:ElastiCache: not added, 11.57  | pass | non-empty reason string | ElastiCache: not added, 11.57 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 11.57 | pass | non-empty reason string | Read replica: not added, 11.57 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-8:tier_1 | pass | sum of line items == 137.5 | 137.5 |  |
| INV-8:tier_2 | pass | sum of line items == 146.4 | 146.4 |  |
| INV-8:tier_3 | pass | sum of line items == 180.17 | 180.17 |  |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:ses:outbound-email | pass | sku exists in region ap-south-1 | found | Transactional email |
| INV-9:tier_1:sqs:requests | pass | sku exists in region ap-south-1 | found | Queue requests |
| INV-9:tier_1:lambda:requests | pass | sku exists in region ap-south-1 | found | Lambda requests |
| INV-9:tier_1:lambda:duration | pass | sku exists in region ap-south-1 | found | Lambda duration |
| INV-9:tier_1:apigateway:http-requests | pass | sku exists in region ap-south-1 | found | API Gateway requests |
| INV-9:tier_1:dynamodb:read-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB reads |
| INV-9:tier_1:dynamodb:write-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB writes |
| INV-9:tier_1:dynamodb:storage | pass | sku exists in region ap-south-1 | found | DynamoDB storage |
| INV-9:tier_1:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_1:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_1:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:ses:outbound-email | pass | sku exists in region ap-south-1 | found | Transactional email |
| INV-9:tier_2:sqs:requests | pass | sku exists in region ap-south-1 | found | Queue requests |
| INV-9:tier_2:sns:requests | pass | sku exists in region ap-south-1 | found | Notifications |
| INV-9:tier_2:lambda:requests | pass | sku exists in region ap-south-1 | found | Lambda requests |
| INV-9:tier_2:lambda:duration | pass | sku exists in region ap-south-1 | found | Lambda duration |
| INV-9:tier_2:apigateway:http-requests | pass | sku exists in region ap-south-1 | found | API Gateway requests |
| INV-9:tier_2:dynamodb:read-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB reads |
| INV-9:tier_2:dynamodb:write-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB writes |
| INV-9:tier_2:dynamodb:storage | pass | sku exists in region ap-south-1 | found | DynamoDB storage |
| INV-9:tier_2:eventbridge:events | pass | sku exists in region ap-south-1 | found | Event bus |
| INV-9:tier_2:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_2:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_2:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 3 |
| INV-9:tier_2:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:ses:outbound-email | pass | sku exists in region ap-south-1 | found | Transactional email |
| INV-9:tier_3:sqs:requests | pass | sku exists in region ap-south-1 | found | Queue requests |
| INV-9:tier_3:sns:requests | pass | sku exists in region ap-south-1 | found | Notifications |
| INV-9:tier_3:lambda:requests | pass | sku exists in region ap-south-1 | found | Lambda requests |
| INV-9:tier_3:lambda:duration | pass | sku exists in region ap-south-1 | found | Lambda duration |
| INV-9:tier_3:apigateway:http-requests | pass | sku exists in region ap-south-1 | found | API Gateway requests |
| INV-9:tier_3:dynamodb:read-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB reads |
| INV-9:tier_3:dynamodb:write-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB writes |
| INV-9:tier_3:dynamodb:storage | pass | sku exists in region ap-south-1 | found | DynamoDB storage |
| INV-9:tier_3:eventbridge:events | pass | sku exists in region ap-south-1 | found | Event bus |
| INV-9:tier_3:firehose:ingest | pass | sku exists in region ap-south-1 | found | Firehose delivery |
| INV-9:tier_3:athena:scanned | pass | sku exists in region ap-south-1 | found | Athena data scanned |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_3:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:kinesis:shard-hour | pass | sku exists in region ap-south-1 | found | Event stream shards × 2 |
| INV-9:tier_3:kinesis:put-payload-units | pass | sku exists in region ap-south-1 | found | Event stream PUT units |
| INV-9:tier_3:s3:put-requests | pass | sku exists in region ap-south-1 | found | Object storage write requests |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 3 |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | (none) | (none) |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=no_vpc (availability=high, durability=high, isolation_required=False) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=13.7329 durability=high (stated) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=13.7329 durability=high (stated) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=13.7329 durability=high (stated) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=5 added=['eventbus', 'kms', 'notification', 'secrets', 'tracing'] dropped=[] | Routing: consumers wired directly to the queue → EventBridge routing by provider and event type, with signing secrets and tracing — removes a fourth provider ne |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=6 added=['archive', 'athena', 'firehose', 'posture', 'storage', 'streaming'] dropped=[] | Replay: a queue that forgets once acknowledged → an ordered Kinesis log plus every raw event archived and queryable — removes 'we processed it wrong and cannot  |
| INV-18 | pass | duty cycle applied wherever it is below 1.0 | no tier has a duty cycle below 1.0 (always-on workload) |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 11 nodes, 8 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 16 nodes, 13 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 22 nodes, 18 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 10 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 15 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 21 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 5 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | 6 node(s) differ |  |
| golden_totals:tier_1 | pass | $137.50 | $137.50 |  |
| golden_totals:tier_2 | pass | $146.40 | $146.40 |  |
| golden_totals:tier_3 | pass | $180.17 | $180.17 |  |

## fintech-bengaluru

Tier totals: tier_1=$139.66, tier_2=$176.69, tier_3=$320.80

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:cross_region_backup_copy:tier_1 | pass | cross_region_backup_copy present | present |  |
| must_include:cross_region_backup_copy:tier_2 | pass | cross_region_backup_copy present | present |  |
| must_include:cross_region_backup_copy:tier_3 | pass | cross_region_backup_copy present | present |  |
| must_include:object_lock:tier_1 | pass | object_lock present | present |  |
| must_include:object_lock:tier_2 | pass | object_lock present | present |  |
| must_include:object_lock:tier_3 | pass | object_lock present | present |  |
| must_include:extended_retention_audit:tier_1 | pass | extended_retention_audit present | present |  |
| must_include:extended_retention_audit:tier_2 | pass | extended_retention_audit present | present |  |
| must_include:extended_retention_audit:tier_3 | pass | extended_retention_audit present | present |  |
| compliance:RBI Storage of Payment System Data directive | pass | cites RBI Storage of Payment System Data directive | RBI Storage of Payment System Data directive; Digital Personal Data Protection Act 2023 |  |
| compliance:Digital Personal Data Protection Act 2023 | pass | cites Digital Personal Data Protection Act 2023 | RBI Storage of Payment System Data directive; Digital Personal Data Protection Act 2023 |  |
| forbidden:HIPAA | pass | never cites HIPAA | RBI Storage of Payment System Data directive; Digital Personal Data Protection Act 2023 |  |
| forbidden:ABDM | pass | never cites ABDM | RBI Storage of Payment System Data directive; Digital Personal Data Protection Act 2023 |  |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 1 NAT gateways | 1 |  |
| INV-2:tier_2 | pass | <= 1 NAT gateways | 1 |  |
| INV-2:tier_3 | pass | <= 1 NAT gateways | 1 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:CloudFront (CDN): not added, 0 | pass | non-empty reason string | CloudFront (CDN): not added, 0.06 peak req/sec and no large static assets and no users outside the home country described |  |
| INV-5:ElastiCache: not added, 0.06 p | pass | non-empty reason string | ElastiCache: not added, 0.06 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 0.06  | pass | non-empty reason string | Read replica: not added, 0.06 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=4 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-8:tier_1 | pass | sum of line items == 139.66 | 139.66 |  |
| INV-8:tier_2 | pass | sum of line items == 176.69 | 176.69 |  |
| INV-8:tier_3 | pass | sum of line items == 320.8 | 320.8 |  |
| INV-9:tier_1:t4g.medium | pass | sku exists in region ap-south-1 | found | Compute × 1 |
| INV-9:tier_1:db.t4g.micro | pass | sku exists in region ap-south-1 | found | Database |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_1:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_1:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_1:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_1:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_1:organizations:scp | pass | sku exists in region ap-south-1 | found | Region-deny guardrail |
| INV-9:tier_1:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_1:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 1 |
| INV-9:tier_1:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_1:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_1:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_1:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_1:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_2:db.t4g.micro | pass | sku exists in region ap-south-1 | found | Database |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_2:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_2:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_2:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_2:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_2:organizations:scp | pass | sku exists in region ap-south-1 | found | Region-deny guardrail |
| INV-9:tier_2:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_2:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 1 |
| INV-9:tier_2:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_2:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_2:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 1 tasks |
| INV-9:tier_2:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 1 tasks |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_2:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_2:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_2:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_2:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_2:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:db.t4g.micro | pass | sku exists in region ap-south-1 | found | Database |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_3:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:organizations:scp | pass | sku exists in region ap-south-1 | found | Region-deny guardrail |
| INV-9:tier_3:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_3:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 1 |
| INV-9:tier_3:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_3:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 1 tasks |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 1 tasks |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_3:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_3:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:db.t4g.large | pass | sku exists in region ap-south-2 | found | Database (standby — second region) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-2 | found | Audit logging (standby — second region) |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-2 | found | TLS certificate (standby — second region) |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-2 | found | Fargate vCPU × 1 tasks (standby — second region) |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-2 | found | Fargate memory × 1 tasks (standby — second region) |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-2 | found | KMS keys × 1 (standby — second region) |
| INV-10 | pass | Digital Personal Data Protection Act 2023; RBI Storage of Payment System Data directive | Digital Personal Data Protection Act 2023; RBI Storage of Payment System Data directive |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=low, durability=high, isolation_required=True) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=250 durability=high (stated) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=250 durability=high (stated) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=250 durability=high (stated) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=6 added=['compute_fargate', 'posture', 'secrets', 'threat', 'tracing'] dropped=['compute'] | Compute: self-managed EC2 + Auto Scaling → ECS on Fargate — removes unpatched-host compromise and manual patch-window downtime as risks.; Secrets: environment v |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=5 added=['audit@standby', 'compute_fargate@standby', 'database@standby', 'kms@standby', 'tls@standby'] dropped=[] | Topology: single-region Multi-AZ → warm standby in a second in-country region — removes a whole-region outage as a risk. |
| INV-18 | pass | duty cycle applied wherever it is below 1.0 | no tier has a duty cycle below 1.0 (always-on workload) |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 18 nodes, 15 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 22 nodes, 14 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 26 nodes, 18 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 17 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 21 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 21 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 6 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | 4 node(s) differ |  |
| INV-4:public_facing | pass | True not written in the prompt | not in prompt text |  |
| golden_totals:tier_1 | pass | $139.66 | $139.66 |  |
| golden_totals:tier_2 | pass | $176.69 | $176.69 |  |
| golden_totals:tier_3 | pass | $320.80 | $320.80 |  |

## hospital-pune-public

Tier totals: tier_1=$289.01, tier_2=$346.29, tier_3=$346.29

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:waf:tier_1 | pass | waf present | present |  |
| must_include:waf:tier_2 | pass | waf present | present |  |
| must_include:waf:tier_3 | pass | waf present | present |  |
| must_include:cross_region_backup_copy:tier_1 | pass | cross_region_backup_copy present | present |  |
| must_include:cross_region_backup_copy:tier_2 | pass | cross_region_backup_copy present | present |  |
| must_include:cross_region_backup_copy:tier_3 | pass | cross_region_backup_copy present | present |  |
| must_include:object_lock:tier_1 | pass | object_lock present | present |  |
| must_include:object_lock:tier_2 | pass | object_lock present | present |  |
| must_include:object_lock:tier_3 | pass | object_lock present | present |  |
| must_include:multi_az_database:tier_1 | pass | multi_az_database present | present |  |
| must_include:multi_az_database:tier_2 | pass | multi_az_database present | present |  |
| must_include:multi_az_database:tier_3 | pass | multi_az_database present | present |  |
| must_include:load_balancer:tier_1 | pass | load_balancer present | present |  |
| must_include:load_balancer:tier_2 | pass | load_balancer present | present |  |
| must_include:load_balancer:tier_3 | pass | load_balancer present | present |  |
| must_exclude:read_replica:tier_1 | pass | read_replica absent | absent | Read replica: not added, 0.69 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:read_replica:tier_2 | pass | read_replica absent | absent | Read replica: not added, 0.69 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:read_replica:tier_3 | pass | read_replica absent | absent | Read replica: not added, 0.69 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:cache:tier_1 | pass | cache absent | absent | ElastiCache: not added, 0.69 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cache:tier_2 | pass | cache absent | absent | ElastiCache: not added, 0.69 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cache:tier_3 | pass | cache absent | absent | ElastiCache: not added, 0.69 peak req/sec does not repeat reads often enough to pay for itself |
| compliance:Digital Personal Data Protection Act 2023 | pass | cites Digital Personal Data Protection Act 2023 | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| compliance:IT Act s43A | pass | cites IT Act s43A | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| compliance:ABDM | pass | cites ABDM | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| forbidden:HIPAA | pass | never cites HIPAA | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| forbidden:GDPR | pass | never cites GDPR | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| budget:tier_1 | pass | True | True | $289.01 vs $900.00 budget |
| budget:tier_2 | pass | True | True | $346.29 vs $900.00 budget |
| budget:tier_3 | pass | True | True | $346.29 vs $900.00 budget |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_2 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_3 | pass | <= 2 NAT gateways | 2 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:ElastiCache: not added, 0.69 p | pass | non-empty reason string | ElastiCache: not added, 0.69 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 0.69  | pass | non-empty reason string | Read replica: not added, 0.69 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=5 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=0 no_further=True |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-8:tier_1 | pass | sum of line items == 289.01 | 289.01 |  |
| INV-8:tier_2 | pass | sum of line items == 346.29 | 346.29 |  |
| INV-8:tier_3 | pass | sum of line items == 346.29 | 346.29 |  |
| INV-9:tier_1:t4g.medium | pass | sku exists in region ap-south-1 | found | Compute × 2 |
| INV-9:tier_1:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_1:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_1:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_1:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_1:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_1:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_1:organizations:scp | pass | sku exists in region ap-south-1 | found | Region-deny guardrail |
| INV-9:tier_1:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_1:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_1:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_1:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_1:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_1:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_1:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_2:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_2:cloudfront:data-transfer-out | pass | sku exists in region ap-south-1 | found | CDN data transfer |
| INV-9:tier_2:cloudfront:requests-https | pass | sku exists in region ap-south-1 | found | CDN requests |
| INV-9:tier_2:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_2:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_2:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_2:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_2:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_2:organizations:scp | pass | sku exists in region ap-south-1 | found | Region-deny guardrail |
| INV-9:tier_2:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_2:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_2:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_2:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_2:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_2:cognito:user-pool-mau | pass | sku exists in region ap-south-1 | found | Authentication (MAU) |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 2 tasks |
| INV-9:tier_2:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 2 tasks |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_2:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_2:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_2:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_2:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_2:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_3:cloudfront:data-transfer-out | pass | sku exists in region ap-south-1 | found | CDN data transfer |
| INV-9:tier_3:cloudfront:requests-https | pass | sku exists in region ap-south-1 | found | CDN requests |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_3:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:organizations:scp | pass | sku exists in region ap-south-1 | found | Region-deny guardrail |
| INV-9:tier_3:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_3:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_3:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_3:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_3:cognito:user-pool-mau | pass | sku exists in region ap-south-1 | found | Authentication (MAU) |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 2 tasks |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 2 tasks |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_3:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_3:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=high, durability=high, isolation_required=True) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=510.986 durability=high (stated) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=510.986 durability=high (stated) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=510.986 durability=high (stated) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=8 added=['auth', 'cdn', 'compute_fargate', 'posture', 'secrets', 'threat', 'tracing'] dropped=['compute'] | Compute: self-managed EC2 + Auto Scaling → ECS on Fargate — removes unpatched-host compromise and manual patch-window downtime as risks.; Identity: static IAM u |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=0 added=[] dropped=[] (declared no further improvement) |  |
| INV-18 | pass | duty cycle applied wherever it is below 1.0 | no tier has a duty cycle below 1.0 (always-on workload) |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 19 nodes, 16 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 25 nodes, 18 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 25 nodes, 18 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 18 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 24 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 24 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 8 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | identical graph (declared) |  |
| diff_against:hospital-pune:sizing_unchanged | pass | sizing identical to hospital-pune | identical |  |
| diff_against:hospital-pune:compliance_unchanged | pass | compliance identical to hospital-pune | identical |  |
| golden_totals:tier_1 | pass | $289.01 | $289.01 |  |
| golden_totals:tier_2 | pass | $346.29 | $346.29 |  |
| golden_totals:tier_3 | pass | $346.29 | $346.29 |  |

## hospital-pune

Tier totals: tier_1=$281.01, tier_2=$347.74, tier_3=$347.74

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:cross_region_backup_copy:tier_1 | pass | cross_region_backup_copy present | present |  |
| must_include:cross_region_backup_copy:tier_2 | pass | cross_region_backup_copy present | present |  |
| must_include:cross_region_backup_copy:tier_3 | pass | cross_region_backup_copy present | present |  |
| must_include:object_lock:tier_1 | pass | object_lock present | present |  |
| must_include:object_lock:tier_2 | pass | object_lock present | present |  |
| must_include:object_lock:tier_3 | pass | object_lock present | present |  |
| must_include:multi_az_database:tier_1 | pass | multi_az_database present | present |  |
| must_include:multi_az_database:tier_2 | pass | multi_az_database present | present |  |
| must_include:multi_az_database:tier_3 | pass | multi_az_database present | present |  |
| must_include:load_balancer:tier_1 | pass | load_balancer present | present |  |
| must_include:load_balancer:tier_2 | pass | load_balancer present | present |  |
| must_include:load_balancer:tier_3 | pass | load_balancer present | present |  |
| must_exclude:read_replica:tier_1 | pass | read_replica absent | absent | Read replica: not added, 0.69 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:read_replica:tier_2 | pass | read_replica absent | absent | Read replica: not added, 0.69 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:read_replica:tier_3 | pass | read_replica absent | absent | Read replica: not added, 0.69 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:cache:tier_1 | pass | cache absent | absent | ElastiCache: not added, 0.69 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cache:tier_2 | pass | cache absent | absent | ElastiCache: not added, 0.69 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cache:tier_3 | pass | cache absent | absent | ElastiCache: not added, 0.69 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cdn:tier_1 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.69 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_2 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.69 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_3 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.69 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:waf:tier_1 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| must_exclude:waf:tier_2 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| must_exclude:waf:tier_3 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| compliance:Digital Personal Data Protection Act 2023 | pass | cites Digital Personal Data Protection Act 2023 | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| compliance:IT Act s43A | pass | cites IT Act s43A | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| compliance:ABDM | pass | cites ABDM | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| forbidden:HIPAA | pass | never cites HIPAA | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| forbidden:GDPR | pass | never cites GDPR | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| budget:tier_1 | pass | True | True | $281.01 vs $900.00 budget |
| budget:tier_2 | pass | True | True | $347.74 vs $900.00 budget |
| budget:tier_3 | pass | True | True | $347.74 vs $900.00 budget |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_2 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_3 | pass | <= 2 NAT gateways | 2 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:CloudFront (CDN): not added, 0 | pass | non-empty reason string | CloudFront (CDN): not added, 0.69 peak req/sec and staff-only access, no large static assets and no users outside the home country described |  |
| INV-5:AWS WAF: not added, staff-only | pass | non-empty reason string | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |  |
| INV-5:ElastiCache: not added, 0.69 p | pass | non-empty reason string | ElastiCache: not added, 0.69 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 0.69  | pass | non-empty reason string | Read replica: not added, 0.69 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=5 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=0 no_further=True |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-8:tier_1 | pass | sum of line items == 281.01 | 281.01 |  |
| INV-8:tier_2 | pass | sum of line items == 347.74 | 347.74 |  |
| INV-8:tier_3 | pass | sum of line items == 347.74 | 347.74 |  |
| INV-9:tier_1:t4g.medium | pass | sku exists in region ap-south-1 | found | Compute × 2 |
| INV-9:tier_1:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_1:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_1:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_1:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_1:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_1:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_1:organizations:scp | pass | sku exists in region ap-south-1 | found | Region-deny guardrail |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_1:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_1:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_1:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_1:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_1:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_2:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_2:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_2:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_2:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_2:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_2:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_2:organizations:scp | pass | sku exists in region ap-south-1 | found | Region-deny guardrail |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_2:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_2:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_2:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_2:cognito:user-pool-mau | pass | sku exists in region ap-south-1 | found | Authentication (MAU) |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 2 tasks |
| INV-9:tier_2:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 2 tasks |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_2:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_2:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_2:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_2:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_2:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_3:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:organizations:scp | pass | sku exists in region ap-south-1 | found | Region-deny guardrail |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_3:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_3:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_3:cognito:user-pool-mau | pass | sku exists in region ap-south-1 | found | Authentication (MAU) |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 2 tasks |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 2 tasks |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_3:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_3:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=high, durability=high, isolation_required=True) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=510.986 durability=high (stated) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=510.986 durability=high (stated) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=510.986 durability=high (stated) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=7 added=['auth', 'compute_fargate', 'posture', 'secrets', 'threat', 'tracing'] dropped=['compute'] | Compute: self-managed EC2 + Auto Scaling → ECS on Fargate — removes unpatched-host compromise and manual patch-window downtime as risks.; Identity: static IAM u |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=0 added=[] dropped=[] (declared no further improvement) |  |
| INV-18 | pass | duty cycle applied wherever it is below 1.0 | no tier has a duty cycle below 1.0 (always-on workload) |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 18 nodes, 15 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 23 nodes, 15 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 23 nodes, 15 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 17 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 22 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 22 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 7 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | identical graph (declared) |  |
| golden_totals:tier_1 | pass | $281.01 | $281.01 |  |
| golden_totals:tier_2 | pass | $347.74 | $347.74 |  |
| golden_totals:tier_3 | pass | $347.74 | $347.74 |  |

## internal-low-stakes

Tier totals: tier_1=$43.79, tier_2=$80.81, tier_3=$80.81

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:backup:tier_1 | pass | backup present | present |  |
| must_include:backup:tier_2 | pass | backup present | present |  |
| must_include:backup:tier_3 | pass | backup present | present |  |
| must_exclude:multi_az_database:tier_1 | pass | multi_az_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:multi_az_database:tier_2 | pass | multi_az_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:multi_az_database:tier_3 | pass | multi_az_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:cross_region_backup_copy:tier_1 | pass | cross_region_backup_copy absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:cross_region_backup_copy:tier_2 | pass | cross_region_backup_copy absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:cross_region_backup_copy:tier_3 | pass | cross_region_backup_copy absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_1 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_2 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_3 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:waf:tier_1 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| must_exclude:waf:tier_2 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| must_exclude:waf:tier_3 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| must_exclude:cdn:tier_1 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_2 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_3 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cache:tier_1 | pass | cache absent | absent | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cache:tier_2 | pass | cache absent | absent | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cache:tier_3 | pass | cache absent | absent | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:read_replica:tier_1 | pass | read_replica absent | absent | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:read_replica:tier_2 | pass | read_replica absent | absent | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:read_replica:tier_3 | pass | read_replica absent | absent | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:nat_gateway:tier_1 | pass | nat_gateway absent | absent | public_simple: no stated availability or durability requirement and 0.00 peak req/sec, so private application subnets and their NAT gateway are not bought. |
| must_exclude:nat_gateway:tier_2 | pass | nat_gateway absent | absent | public_simple: no stated availability or durability requirement and 0.00 peak req/sec, so private application subnets and their NAT gateway are not bought. |
| must_exclude:nat_gateway:tier_3 | pass | nat_gateway absent | absent | public_simple: no stated availability or durability requirement and 0.00 peak req/sec, so private application subnets and their NAT gateway are not bought. |
| must_exclude:vpc_flow_logs:tier_1 | pass | vpc_flow_logs absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:vpc_flow_logs:tier_2 | pass | vpc_flow_logs absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:vpc_flow_logs:tier_3 | pass | vpc_flow_logs absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| budget:tier_1 | pass | True | True | $43.79 vs $60.00 budget |
| network_topology | pass | public_simple | public_simple | public_simple: no stated availability or durability requirement and 0.00 peak req/sec, so private application subnets and their NAT gateway are not bought. |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 1 NAT gateways | 0 |  |
| INV-2:tier_2 | pass | <= 1 NAT gateways | 0 |  |
| INV-2:tier_3 | pass | <= 1 NAT gateways | 0 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:CloudFront (CDN): not added, 0 | pass | non-empty reason string | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |  |
| INV-5:AWS WAF: not added, staff-only | pass | non-empty reason string | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |  |
| INV-5:ElastiCache: not added, 0.00 p | pass | non-empty reason string | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 0.00  | pass | non-empty reason string | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-5:VPC flow logs: not added, no c | pass | non-empty reason string | VPC flow logs: not added, no compliance obligation requires network audit — they are an audit control billed per GB of traffic, not baseline infrastructure |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=5 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=0 no_further=True |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-8:tier_1 | pass | sum of line items == 43.79 | 43.79 |  |
| INV-8:tier_2 | pass | sum of line items == 80.81 | 80.81 |  |
| INV-8:tier_3 | pass | sum of line items == 80.81 | 80.81 |  |
| INV-9:tier_1:t4g.medium | pass | sku exists in region ap-south-1 | found | Compute × 1 |
| INV-9:tier_1:db.t4g.micro | pass | sku exists in region ap-south-1 | found | Database |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_1:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_1:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_2:db.t4g.micro | pass | sku exists in region ap-south-1 | found | Database |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_2:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_2:cognito:user-pool-mau | pass | sku exists in region ap-south-1 | found | Authentication (MAU) |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 1 tasks |
| INV-9:tier_2:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 1 tasks |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_2:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_2:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_2:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_2:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:db.t4g.micro | pass | sku exists in region ap-south-1 | found | Database |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_3:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_3:cognito:user-pool-mau | pass | sku exists in region ap-south-1 | found | Authentication (MAU) |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 1 tasks |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 1 tasks |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_3:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_3:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | (none) | (none) |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=public_simple (availability=low, durability=normal, isolation_required=False) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=20.0586 durability=normal (assumed) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=20.0586 durability=normal (assumed) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=20.0586 durability=normal (assumed) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=7 added=['auth', 'compute_fargate', 'posture', 'secrets', 'threat', 'tracing'] dropped=['compute'] | Compute: self-managed EC2 + Auto Scaling → ECS on Fargate — removes unpatched-host compromise and manual patch-window downtime as risks.; Identity: static IAM u |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=0 added=[] dropped=[] (declared no further improvement) |  |
| INV-18 | pass | duty cycle applied wherever it is below 1.0 | no tier has a duty cycle below 1.0 (always-on workload) |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 11 nodes, 9 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 16 nodes, 9 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 16 nodes, 9 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 10 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 15 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 15 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 7 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | identical graph (declared) |  |
| golden_totals:tier_1 | pass | $43.79 | $43.79 |  |
| golden_totals:tier_2 | pass | $80.81 | $80.81 |  |
| golden_totals:tier_3 | pass | $80.81 | $80.81 |  |

## ml-inference

Tier totals: tier_1=$83.86, tier_2=$437.50, tier_3=$560.82

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:object_storage:tier_1 | pass | object_storage present | present |  |
| must_include:object_storage:tier_2 | pass | object_storage present | present |  |
| must_include:object_storage:tier_3 | pass | object_storage present | present |  |
| must_include:backup:tier_1 | pass | backup present | present |  |
| must_include:backup:tier_2 | pass | backup present | present |  |
| must_include:backup:tier_3 | pass | backup present | present |  |
| must_include:object_lock:tier_1 | pass | object_lock present | present |  |
| must_include:object_lock:tier_2 | pass | object_lock present | present |  |
| must_include:object_lock:tier_3 | pass | object_lock present | present |  |
| must_include:cross_region_backup_copy:tier_1 | pass | cross_region_backup_copy present | present |  |
| must_include:cross_region_backup_copy:tier_2 | pass | cross_region_backup_copy present | present |  |
| must_include:cross_region_backup_copy:tier_3 | pass | cross_region_backup_copy present | present |  |
| must_include:model_endpoint:tier_2 | pass | model_endpoint present | present |  |
| must_include:model_endpoint:tier_3 | pass | model_endpoint present | present |  |
| must_include:cache:tier_3 | pass | cache present | present |  |
| must_include:athena:tier_3 | pass | athena present | present |  |
| must_exclude:relational_database:tier_1 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:relational_database:tier_2 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:relational_database:tier_3 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_1 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_2 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_3 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:cdn:tier_1 | pass | cdn absent | absent | CloudFront (CDN): not added, 37.50 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_2 | pass | cdn absent | absent | CloudFront (CDN): not added, 37.50 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_3 | pass | cdn absent | absent | CloudFront (CDN): not added, 37.50 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:nat_gateway:tier_1 | pass | nat_gateway absent | absent | instances run in private subnets, reaching AWS services through VPC endpoints — no NAT gateway, because nothing here needs general internet egress |
| must_exclude:nat_gateway:tier_2 | pass | nat_gateway absent | absent | instances run in private subnets, reaching AWS services through VPC endpoints — no NAT gateway, because nothing here needs general internet egress |
| must_exclude:nat_gateway:tier_3 | pass | nat_gateway absent | absent | instances run in private subnets, reaching AWS services through VPC endpoints — no NAT gateway, because nothing here needs general internet egress |
| must_exclude:waf:tier_1 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| must_exclude:waf:tier_2 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| must_exclude:waf:tier_3 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| complete:tier_1 | pass | every selected component has a catalog rate | complete |  |
| complete:tier_2 | pass | every selected component has a catalog rate | complete |  |
| complete:tier_3 | pass | every selected component has a catalog rate | complete |  |
| forbidden:tier_1 | pass | no component forbidden by ml_inference | none of 3 forbidden components |  |
| forbidden:tier_2 | pass | no component forbidden by ml_inference | none of 3 forbidden components |  |
| forbidden:tier_3 | pass | no component forbidden by ml_inference | none of 3 forbidden components |  |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 1 NAT gateways | 0 |  |
| INV-2:tier_2 | pass | <= 1 NAT gateways | 0 |  |
| INV-2:tier_3 | pass | <= 1 NAT gateways | 0 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:CloudFront (CDN): not added, 3 | pass | non-empty reason string | CloudFront (CDN): not added, 37.50 peak req/sec and staff-only access, no large static assets and no users outside the home country described |  |
| INV-5:AWS WAF: not added, staff-only | pass | non-empty reason string | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |  |
| INV-5:ElastiCache: not added, 37.50  | pass | non-empty reason string | ElastiCache: not added, 37.50 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 37.50 | pass | non-empty reason string | Read replica: not added, 37.50 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-8:tier_1 | pass | sum of line items == 83.86 | 83.86 |  |
| INV-8:tier_2 | pass | sum of line items == 437.5 | 437.5 |  |
| INV-8:tier_3 | pass | sum of line items == 560.82 | 560.82 |  |
| INV-9:tier_1:c6g.xlarge | pass | sku exists in region ap-south-1 | found | Compute × 2 |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_1:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_1:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_1:vpce:interface-hour | pass | sku exists in region ap-south-1 | found | Interface endpoints × 3 (ECR, SSM, Secrets Manager, CloudWatch Logs, KMS — cheaper than the NAT data they divert) |
| INV-9:tier_1:vpce:gb-processed | pass | sku exists in region ap-south-1 | found | Interface endpoint data processing |
| INV-9:tier_1:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_1:s3:get-requests | pass | sku exists in region ap-south-1 | found | Object storage read requests |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:lambda:requests | pass | sku exists in region ap-south-1 | found | Lambda requests |
| INV-9:tier_2:lambda:duration | pass | sku exists in region ap-south-1 | found | Lambda duration |
| INV-9:tier_2:apigateway:http-requests | pass | sku exists in region ap-south-1 | found | API Gateway requests |
| INV-9:tier_2:sagemaker:ml.c6i.xlarge | pass | sku exists in region ap-south-1 | found | Model endpoint × 2 |
| INV-9:tier_2:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_2:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_2:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:s3:get-requests | pass | sku exists in region ap-south-1 | found | Object storage read requests |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 2 |
| INV-9:tier_2:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:cache.m8g.large | pass | sku exists in region ap-south-1 | found | Cache |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:lambda:requests | pass | sku exists in region ap-south-1 | found | Lambda requests |
| INV-9:tier_3:lambda:duration | pass | sku exists in region ap-south-1 | found | Lambda duration |
| INV-9:tier_3:apigateway:http-requests | pass | sku exists in region ap-south-1 | found | API Gateway requests |
| INV-9:tier_3:dynamodb:read-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB reads |
| INV-9:tier_3:dynamodb:write-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB writes |
| INV-9:tier_3:dynamodb:storage | pass | sku exists in region ap-south-1 | found | DynamoDB storage |
| INV-9:tier_3:sagemaker:ml.c6i.xlarge | pass | sku exists in region ap-south-1 | found | Model endpoint × 2 |
| INV-9:tier_3:athena:scanned | pass | sku exists in region ap-south-1 | found | Athena data scanned |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_3:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:s3:get-requests | pass | sku exists in region ap-south-1 | found | Object storage read requests |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 2 |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | (none) | (none) |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=low, durability=high, isolation_required=False) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=10 durability=high (stated) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=10 durability=high (stated) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=10 durability=high (stated) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=8 added=['apigateway', 'inference', 'kms', 'lambda', 'secrets', 'tracing'] dropped=['compute', 'vpc_endpoints'] | Serving: a host you patch and restart → a managed real-time endpoint behind API Gateway, with tracing — removes the serving host as something to operate, and re |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=5 added=['archive', 'athena', 'cache', 'dynamodb', 'posture'] dropped=[] | Features: a lookup on the critical path of every prediction → a hot feature cache with the prediction log queryable for drift — removes per-call latency you can |
| INV-18:tier_1 | pass | compute billed at 37% of 1460 hours | duty 37% applied |  |
| INV-18:tier_2 | pass | compute billed at 37% of 730 hours | duty 37% applied |  |
| INV-18:tier_3 | pass | compute billed at 37% of 730 hours | duty 37% applied |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 9 nodes, 6 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 13 nodes, 10 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 18 nodes, 15 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 8 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 12 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 17 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 8 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | 5 node(s) differ |  |
| golden_totals:tier_1 | pass | $83.86 | $83.86 |  |
| golden_totals:tier_2 | pass | $437.50 | $437.50 |  |
| golden_totals:tier_3 | pass | $560.82 | $560.82 |  |

## realtime-chat

Tier totals: tier_1=$386.78, tier_2=$485.18, tier_3=$546.60

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:search:tier_1 | pass | search present | present |  |
| must_include:search:tier_2 | pass | search present | present |  |
| must_include:search:tier_3 | pass | search present | present |  |
| must_include:connections:tier_1 | pass | connections present | present |  |
| must_include:connections:tier_2 | pass | connections present | present |  |
| must_include:connections:tier_3 | pass | connections present | present |  |
| must_include:serverless_compute:tier_1 | pass | serverless_compute present | present |  |
| must_include:serverless_compute:tier_2 | pass | serverless_compute present | present |  |
| must_include:serverless_compute:tier_3 | pass | serverless_compute present | present |  |
| must_include:backup:tier_1 | pass | backup present | present |  |
| must_include:backup:tier_2 | pass | backup present | present |  |
| must_include:backup:tier_3 | pass | backup present | present |  |
| must_include:cache:tier_2 | pass | cache present | present |  |
| must_include:cache:tier_3 | pass | cache present | present |  |
| must_include:notifications:tier_2 | pass | notifications present | present |  |
| must_include:notifications:tier_3 | pass | notifications present | present |  |
| must_include:archive_tier:tier_3 | pass | archive_tier present | present |  |
| must_include:object_lock:tier_3 | pass | object_lock present | present |  |
| must_exclude:relational_database:tier_1 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:relational_database:tier_2 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:relational_database:tier_3 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_1 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_2 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_3 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:cdn:tier_1 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_2 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_3 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:nat_gateway:tier_1 | pass | nat_gateway absent | absent | nothing runs in a network you own — this design is regional managed services throughout, so isolation is IAM and resource policy rather than subnets, and there is no NAT gateway to buy |
| must_exclude:nat_gateway:tier_2 | pass | nat_gateway absent | absent | nothing runs in a network you own — this design is regional managed services throughout, so isolation is IAM and resource policy rather than subnets, and there is no NAT gateway to buy |
| must_exclude:nat_gateway:tier_3 | pass | nat_gateway absent | absent | nothing runs in a network you own — this design is regional managed services throughout, so isolation is IAM and resource policy rather than subnets, and there is no NAT gateway to buy |
| must_exclude:waf:tier_1 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| must_exclude:waf:tier_2 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| must_exclude:waf:tier_3 | pass | waf absent | absent | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |
| complete:tier_1 | pass | every selected component has a catalog rate | complete |  |
| complete:tier_2 | pass | every selected component has a catalog rate | complete |  |
| complete:tier_3 | pass | every selected component has a catalog rate | complete |  |
| forbidden:tier_1 | pass | no component forbidden by realtime | none of 3 forbidden components |  |
| forbidden:tier_2 | pass | no component forbidden by realtime | none of 3 forbidden components |  |
| forbidden:tier_3 | pass | no component forbidden by realtime | none of 3 forbidden components |  |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 1 NAT gateways | 0 |  |
| INV-2:tier_2 | pass | <= 1 NAT gateways | 0 |  |
| INV-2:tier_3 | pass | <= 1 NAT gateways | 0 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:CloudFront (CDN): not added, 0 | pass | non-empty reason string | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |  |
| INV-5:AWS WAF: not added, staff-only | pass | non-empty reason string | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |  |
| INV-5:ElastiCache: not added, 0.00 p | pass | non-empty reason string | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 0.00  | pass | non-empty reason string | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-8:tier_1 | pass | sum of line items == 386.78 | 386.78 |  |
| INV-8:tier_2 | pass | sum of line items == 485.18 | 485.18 |  |
| INV-8:tier_3 | pass | sum of line items == 546.6 | 546.6 |  |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:lambda:requests | pass | sku exists in region ap-south-1 | found | Lambda requests |
| INV-9:tier_1:lambda:duration | pass | sku exists in region ap-south-1 | found | Lambda duration |
| INV-9:tier_1:apigateway:http-requests | pass | sku exists in region ap-south-1 | found | API Gateway requests |
| INV-9:tier_1:dynamodb:read-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB reads |
| INV-9:tier_1:dynamodb:write-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB writes |
| INV-9:tier_1:dynamodb:storage | pass | sku exists in region ap-south-1 | found | DynamoDB storage |
| INV-9:tier_1:apigateway:ws-connection | pass | sku exists in region ap-south-1 | found | Connection minutes |
| INV-9:tier_1:apigateway:ws-messages | pass | sku exists in region ap-south-1 | found | Connection messages |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_1:m6g.large.search | pass | sku exists in region ap-south-1 | found | Search nodes × 3 |
| INV-9:tier_1:opensearch:gp3-storage | pass | sku exists in region ap-south-1 | found | Search storage |
| INV-9:tier_2:cache.m8g.large | pass | sku exists in region ap-south-1 | found | Cache |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:sns:requests | pass | sku exists in region ap-south-1 | found | Notifications |
| INV-9:tier_2:lambda:requests | pass | sku exists in region ap-south-1 | found | Lambda requests |
| INV-9:tier_2:lambda:duration | pass | sku exists in region ap-south-1 | found | Lambda duration |
| INV-9:tier_2:apigateway:http-requests | pass | sku exists in region ap-south-1 | found | API Gateway requests |
| INV-9:tier_2:dynamodb:read-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB reads |
| INV-9:tier_2:dynamodb:write-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB writes |
| INV-9:tier_2:dynamodb:storage | pass | sku exists in region ap-south-1 | found | DynamoDB storage |
| INV-9:tier_2:apigateway:ws-connection | pass | sku exists in region ap-south-1 | found | Connection minutes |
| INV-9:tier_2:apigateway:ws-messages | pass | sku exists in region ap-south-1 | found | Connection messages |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:m6g.large.search | pass | sku exists in region ap-south-1 | found | Search nodes × 3 |
| INV-9:tier_2:opensearch:gp3-storage | pass | sku exists in region ap-south-1 | found | Search storage |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 2 |
| INV-9:tier_2:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:cache.m8g.large | pass | sku exists in region ap-south-1 | found | Cache |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:sns:requests | pass | sku exists in region ap-south-1 | found | Notifications |
| INV-9:tier_3:lambda:requests | pass | sku exists in region ap-south-1 | found | Lambda requests |
| INV-9:tier_3:lambda:duration | pass | sku exists in region ap-south-1 | found | Lambda duration |
| INV-9:tier_3:apigateway:http-requests | pass | sku exists in region ap-south-1 | found | API Gateway requests |
| INV-9:tier_3:dynamodb:read-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB reads |
| INV-9:tier_3:dynamodb:write-request-units | pass | sku exists in region ap-south-1 | found | DynamoDB writes |
| INV-9:tier_3:dynamodb:storage | pass | sku exists in region ap-south-1 | found | DynamoDB storage |
| INV-9:tier_3:apigateway:ws-connection | pass | sku exists in region ap-south-1 | found | Connection minutes |
| INV-9:tier_3:apigateway:ws-messages | pass | sku exists in region ap-south-1 | found | Connection messages |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_3:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:kinesis:shard-hour | pass | sku exists in region ap-south-1 | found | Event stream shards × 1 |
| INV-9:tier_3:kinesis:put-payload-units | pass | sku exists in region ap-south-1 | found | Event stream PUT units |
| INV-9:tier_3:m6g.large.search | pass | sku exists in region ap-south-1 | found | Search nodes × 3 |
| INV-9:tier_3:opensearch:gp3-storage | pass | sku exists in region ap-south-1 | found | Search storage |
| INV-9:tier_3:s3:put-requests | pass | sku exists in region ap-south-1 | found | Object storage write requests |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 2 |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | (none) | (none) |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=no_vpc (availability=low, durability=normal, isolation_required=False) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=308.99 durability=normal (assumed) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=308.99 durability=normal (assumed) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=308.99 durability=normal (assumed) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=5 added=['cache', 'kms', 'notification', 'secrets', 'tracing'] dropped=[] | State: a table lookup per recipient per message → presence and fan-out in a cache, with push for recipients who are not connected — removes per-message latency  |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=6 added=['archive', 'backup_dr', 'object_lock', 'posture', 'storage', 'streaming'] dropped=[] | History: writing the index synchronously → an ordered Kinesis log feeding the index and a cold archive — removes delivery waiting on the index, and removes old  |
| INV-18 | pass | duty cycle applied wherever it is below 1.0 | no tier has a duty cycle below 1.0 (always-on workload) |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 9 nodes, 7 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 14 nodes, 11 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 20 nodes, 17 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 8 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 13 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 19 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 5 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | 6 node(s) differ |  |
| golden_totals:tier_1 | pass | $386.78 | $386.78 |  |
| golden_totals:tier_2 | pass | $485.18 | $485.18 |  |
| golden_totals:tier_3 | pass | $546.60 | $546.60 |  |

## static-site

Tier totals: tier_1=$3.92, tier_2=$18.73, tier_3=$19.39

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:object_storage:tier_1 | pass | object_storage present | present |  |
| must_include:object_storage:tier_2 | pass | object_storage present | present |  |
| must_include:object_storage:tier_3 | pass | object_storage present | present |  |
| must_include:backup:tier_1 | pass | backup present | present |  |
| must_include:backup:tier_2 | pass | backup present | present |  |
| must_include:backup:tier_3 | pass | backup present | present |  |
| must_include:dns:tier_1 | pass | dns present | present |  |
| must_include:dns:tier_2 | pass | dns present | present |  |
| must_include:dns:tier_3 | pass | dns present | present |  |
| must_include:tls:tier_1 | pass | tls present | present |  |
| must_include:tls:tier_2 | pass | tls present | present |  |
| must_include:tls:tier_3 | pass | tls present | present |  |
| must_include:cdn:tier_2 | pass | cdn present | present |  |
| must_include:cdn:tier_3 | pass | cdn present | present |  |
| must_include:object_lock:tier_3 | pass | object_lock present | present |  |
| must_include:cross_region_backup_copy:tier_3 | pass | cross_region_backup_copy present | present |  |
| must_exclude:relational_database:tier_1 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:relational_database:tier_2 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:relational_database:tier_3 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_1 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_2 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_3 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:nat_gateway:tier_1 | pass | nat_gateway absent | absent | nothing runs in a network you own — this design is regional managed services throughout, so isolation is IAM and resource policy rather than subnets, and there is no NAT gateway to buy |
| must_exclude:nat_gateway:tier_2 | pass | nat_gateway absent | absent | nothing runs in a network you own — this design is regional managed services throughout, so isolation is IAM and resource policy rather than subnets, and there is no NAT gateway to buy |
| must_exclude:nat_gateway:tier_3 | pass | nat_gateway absent | absent | nothing runs in a network you own — this design is regional managed services throughout, so isolation is IAM and resource policy rather than subnets, and there is no NAT gateway to buy |
| must_exclude:vpc_flow_logs:tier_1 | pass | vpc_flow_logs absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:vpc_flow_logs:tier_2 | pass | vpc_flow_logs absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:vpc_flow_logs:tier_3 | pass | vpc_flow_logs absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:cache:tier_1 | pass | cache absent | absent | ElastiCache: not added, 0.02 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cache:tier_2 | pass | cache absent | absent | ElastiCache: not added, 0.02 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cache:tier_3 | pass | cache absent | absent | ElastiCache: not added, 0.02 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:read_replica:tier_1 | pass | read_replica absent | absent | Read replica: not added, 0.02 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:read_replica:tier_2 | pass | read_replica absent | absent | Read replica: not added, 0.02 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| must_exclude:read_replica:tier_3 | pass | read_replica absent | absent | Read replica: not added, 0.02 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |
| complete:tier_1 | pass | every selected component has a catalog rate | complete |  |
| complete:tier_2 | pass | every selected component has a catalog rate | complete |  |
| complete:tier_3 | pass | every selected component has a catalog rate | complete |  |
| forbidden:tier_1 | pass | no component forbidden by static_site | none of 4 forbidden components |  |
| forbidden:tier_2 | pass | no component forbidden by static_site | none of 4 forbidden components |  |
| forbidden:tier_3 | pass | no component forbidden by static_site | none of 4 forbidden components |  |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 1 NAT gateways | 0 |  |
| INV-2:tier_2 | pass | <= 1 NAT gateways | 0 |  |
| INV-2:tier_3 | pass | <= 1 NAT gateways | 0 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:ElastiCache: not added, 0.02 p | pass | non-empty reason string | ElastiCache: not added, 0.02 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 0.02  | pass | non-empty reason string | Read replica: not added, 0.02 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-8:tier_1 | pass | sum of line items == 3.92 | 3.92 |  |
| INV-8:tier_2 | pass | sum of line items == 18.73 | 18.73 |  |
| INV-8:tier_3 | pass | sum of line items == 19.39 | 19.39 |  |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_1:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_1:route53:dns-queries | pass | sku exists in region ap-south-1 | found | DNS queries |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_1:s3:get-requests | pass | sku exists in region ap-south-1 | found | Object storage read requests |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:cloudfront:data-transfer-out | pass | sku exists in region ap-south-1 | found | CDN data transfer |
| INV-9:tier_2:cloudfront:requests-https | pass | sku exists in region ap-south-1 | found | CDN requests |
| INV-9:tier_2:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_2:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_2:waf:request | pass | sku exists in region ap-south-1 | found | WAF request inspection |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_2:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_2:route53:dns-queries | pass | sku exists in region ap-south-1 | found | DNS queries |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:s3:get-requests | pass | sku exists in region ap-south-1 | found | Object storage read requests |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:cloudfront:data-transfer-out | pass | sku exists in region ap-south-1 | found | CDN data transfer |
| INV-9:tier_3:cloudfront:requests-https | pass | sku exists in region ap-south-1 | found | CDN requests |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_3:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_3:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_3:waf:request | pass | sku exists in region ap-south-1 | found | WAF request inspection |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_3:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_3:route53:dns-queries | pass | sku exists in region ap-south-1 | found | DNS queries |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:s3:get-requests | pass | sku exists in region ap-south-1 | found | Object storage read requests |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | (none) | (none) |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=no_vpc (availability=low, durability=normal, isolation_required=False) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=5 durability=normal (assumed) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=5 durability=normal (assumed) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=5 durability=normal (assumed) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=3 added=['cdn', 'kms', 'waf'] dropped=[] | Delivery: origin serves every byte → CloudFront caches at the edge — removes the origin paying per-GB for every viewer, and the latency of a single-region origi |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=4 added=['archive', 'backup_dr', 'object_lock', 'posture'] dropped=[] | Durability: a mutable bucket → Object Lock, a second-region copy and an archive tier — removes a compromised credential erasing the site, and stops hot-class ra |
| INV-18 | pass | duty cycle applied wherever it is below 1.0 | no tier has a duty cycle below 1.0 (always-on workload) |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 7 nodes, 4 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 10 nodes, 9 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 14 nodes, 12 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 6 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 9 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 13 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 3 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | 4 node(s) differ |  |
| INV-4:requests_per_day | pass | 1000 not written in the prompt | not in prompt text |  |
| INV-4:public_facing | pass | True not written in the prompt | not in prompt text |  |
| golden_totals:tier_1 | pass | $3.92 | $3.92 |  |
| golden_totals:tier_2 | pass | $18.73 | $18.73 |  |
| golden_totals:tier_3 | pass | $19.39 | $19.39 |  |

## vm-migration

Tier totals: tier_1=$2,028.32, tier_2=$2,217.99, tier_3=$2,443.79

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:block_storage:tier_1 | pass | block_storage present | present |  |
| must_include:block_storage:tier_2 | pass | block_storage present | present |  |
| must_include:block_storage:tier_3 | pass | block_storage present | present |  |
| must_include:backup:tier_1 | pass | backup present | present |  |
| must_include:backup:tier_2 | pass | backup present | present |  |
| must_include:backup:tier_3 | pass | backup present | present |  |
| must_include:nat_gateway:tier_1 | pass | nat_gateway present | present |  |
| must_include:nat_gateway:tier_2 | pass | nat_gateway present | present |  |
| must_include:nat_gateway:tier_3 | pass | nat_gateway present | present |  |
| must_include:vpc_flow_logs:tier_2 | pass | vpc_flow_logs present | present |  |
| must_include:vpc_flow_logs:tier_3 | pass | vpc_flow_logs present | present |  |
| must_include:archive_tier:tier_3 | pass | archive_tier present | present |  |
| must_include:object_lock:tier_3 | pass | object_lock present | present |  |
| must_exclude:serverless_compute:tier_1 | pass | serverless_compute absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:serverless_compute:tier_2 | pass | serverless_compute absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:serverless_compute:tier_3 | pass | serverless_compute absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:relational_database:tier_1 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:relational_database:tier_2 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:relational_database:tier_3 | pass | relational_database absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_1 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_2 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:load_balancer:tier_3 | pass | load_balancer absent | absent | (no exclusion reason recorded -- rung-1/2 items are gated by extraction, not by the load model's excluded_with_reason list) |
| must_exclude:cdn:tier_1 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_2 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_3 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |
| must_exclude:cache:tier_1 | pass | cache absent | absent | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cache:tier_2 | pass | cache absent | absent | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |
| must_exclude:cache:tier_3 | pass | cache absent | absent | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |
| complete:tier_1 | pass | every selected component has a catalog rate | complete |  |
| complete:tier_2 | pass | every selected component has a catalog rate | complete |  |
| complete:tier_3 | pass | every selected component has a catalog rate | complete |  |
| forbidden:tier_1 | pass | no component forbidden by migration | none of 3 forbidden components |  |
| forbidden:tier_2 | pass | no component forbidden by migration | none of 3 forbidden components |  |
| forbidden:tier_3 | pass | no component forbidden by migration | none of 3 forbidden components |  |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 1 NAT gateways | 1 |  |
| INV-2:tier_2 | pass | <= 1 NAT gateways | 1 |  |
| INV-2:tier_3 | pass | <= 1 NAT gateways | 1 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:CloudFront (CDN): not added, 0 | pass | non-empty reason string | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |  |
| INV-5:AWS WAF: not added, staff-only | pass | non-empty reason string | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |  |
| INV-5:ElastiCache: not added, 0.00 p | pass | non-empty reason string | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 0.00  | pass | non-empty reason string | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-8:tier_1 | pass | sum of line items == 2028.32 | 2028.32 |  |
| INV-8:tier_2 | pass | sum of line items == 2217.99 | 2217.99 |  |
| INV-8:tier_3 | pass | sum of line items == 2443.79 | 2443.79 |  |
| INV-9:tier_1:t3a.large | pass | sku exists in region ap-south-1 | found | Compute × 40 |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 1 |
| INV-9:tier_1:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_1:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_1:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_1:route53:dns-queries | pass | sku exists in region ap-south-1 | found | DNS queries |
| INV-9:tier_1:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_1:ebs:gp3 | pass | sku exists in region ap-south-1 | found | Block storage |
| INV-9:tier_1:s3:put-requests | pass | sku exists in region ap-south-1 | found | Object storage write requests |
| INV-9:tier_2:t3a.large | pass | sku exists in region ap-south-1 | found | Compute × 40 |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_2:vpce:interface-hour | pass | sku exists in region ap-south-1 | found | Interface endpoints × 3 (ECR, SSM, Secrets Manager, CloudWatch Logs, KMS — cheaper than the NAT data they divert) |
| INV-9:tier_2:vpce:gb-processed | pass | sku exists in region ap-south-1 | found | Interface endpoint data processing |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 1 |
| INV-9:tier_2:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_2:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_2:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_2:route53:dns-queries | pass | sku exists in region ap-south-1 | found | DNS queries |
| INV-9:tier_2:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_2:ebs:gp3 | pass | sku exists in region ap-south-1 | found | Block storage |
| INV-9:tier_2:s3:put-requests | pass | sku exists in region ap-south-1 | found | Object storage write requests |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 4 |
| INV-9:tier_2:guardduty:ec2-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: compute |
| INV-9:tier_2:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:t3a.large | pass | sku exists in region ap-south-1 | found | Compute × 40 |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy (storage at destination) |
| INV-9:tier_3:transfer:inter-region | pass | sku exists in region ap-south-1 | found | Cross-region backup transfer (changed data) |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_3:vpce:interface-hour | pass | sku exists in region ap-south-1 | found | Interface endpoints × 3 (ECR, SSM, Secrets Manager, CloudWatch Logs, KMS — cheaper than the NAT data they divert) |
| INV-9:tier_3:vpce:gb-processed | pass | sku exists in region ap-south-1 | found | Interface endpoint data processing |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 1 |
| INV-9:tier_3:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_3:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_3:route53:dns-queries | pass | sku exists in region ap-south-1 | found | DNS queries |
| INV-9:tier_3:backup:warm-storage | pass | sku exists in region ap-south-1 | found | Backup storage |
| INV-9:tier_3:ebs:gp3 | pass | sku exists in region ap-south-1 | found | Block storage |
| INV-9:tier_3:s3:put-requests | pass | sku exists in region ap-south-1 | found | Object storage write requests |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 4 |
| INV-9:tier_3:guardduty:ec2-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: compute |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | (none) | (none) |  |
| INV-11 | pass | private_standard (or no_vpc, for a design with no network of your own) whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=low, durability=normal, isolation_required=False) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=2400 durability=normal (assumed) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=2400 durability=normal (assumed) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=2400 durability=normal (assumed) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15:tier_1 | pass | no ARM/Graviton instance family, because the workload is x86-only | no ARM families selected |  |
| INV-15:tier_2 | pass | no ARM/Graviton instance family, because the workload is x86-only | no ARM families selected |  |
| INV-15:tier_3 | pass | no ARM/Graviton instance family, because the workload is x86-only | no ARM families selected |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| INV-17:tier_1->tier_2 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=4 added=['flowlogs', 'kms', 'secrets', 'threat'] dropped=[] | Operability: machines moved and left alone → volume encryption, credentials out of config files, flow logs recording what the estate actually talks to, and thre |
| INV-17:tier_2->tier_3 | pass | >= 3 services different, or an explicit 'no further improvement' statement | spread=4 added=['archive', 'backup_dr', 'object_lock', 'posture'] dropped=[] | Recovery and posture: snapshots in one region → immutable snapshots copied elsewhere, with configuration drift watched across every machine — removes ransomware |
| INV-18 | pass | duty cycle applied wherever it is below 1.0 | no tier has a duty cycle below 1.0 (always-on workload) |  |
| INV-19:tier_1 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 11 nodes, 8 edges, clean |  |
| INV-19:tier_2 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 15 nodes, 10 edges, clean |  |
| INV-19:tier_3 | pass | every data-plane node reachable, every edge endpoint real, no edges on account-plane nodes | 19 nodes, 13 edges, clean |  |
| INV-20:tier_1 | pass | every priced service kind has a node | all 10 priced kinds drawn |  |
| INV-20:tier_2 | pass | every priced service kind has a node | all 14 priced kinds drawn |  |
| INV-20:tier_3 | pass | every priced service kind has a node | all 18 priced kinds drawn |  |
| INV-21:tier_1->tier_2 | pass | a different graph, or an explicit 'no further improvement' statement | 4 node(s) differ |  |
| INV-21:tier_2->tier_3 | pass | a different graph, or an explicit 'no further improvement' statement | 4 node(s) differ |  |
| golden_totals:tier_1 | pass | $2028.32 | $2028.32 |  |
| golden_totals:tier_2 | pass | $2217.99 | $2217.99 |  |
| golden_totals:tier_3 | pass | $2443.79 | $2443.79 |  |
