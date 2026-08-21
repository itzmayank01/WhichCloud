# WhichCloud regression harness report

Run at 2026-08-21 18:31:09 UTC

| fixture | passed | failed | status |
|---|---|---|---|
| budget-floor-conflict | 104 | 0 | OK |
| catalog-region-integrity | 5 | 0 | OK |
| ecommerce-scale | 109 | 0 | OK |
| fintech-bengaluru | 113 | 0 | OK |
| hospital-pune-public | 144 | 0 | OK |
| hospital-pune | 137 | 0 | OK |
| internal-low-stakes | 97 | 1 | FAIL |
| probe:batch-etl | 4 | 0 | OK |
| probe:event-webhook | 4 | 0 | OK |
| probe:ml-inference | 4 | 0 | OK |
| probe:realtime-chat | 4 | 0 | OK |
| probe:static-site | 4 | 0 | OK |
| probe:vm-migration | 4 | 0 | OK |

## budget-floor-conflict

Tier totals: tier_1=$307.10, tier_2=$373.83, tier_3=$517.95

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| must_include:multi_az_database:tier_1 | pass | multi_az_database present | present |  |
| must_include:cross_region_backup_copy:tier_1 | pass | cross_region_backup_copy present | present |  |
| budget:tier_1 | pass | False | False | $307.10 vs $80.00 budget |
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
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-8:tier_1 | pass | sum of line items == 307.1 | 307.1 |  |
| INV-8:tier_2 | pass | sum of line items == 373.83 | 373.83 |  |
| INV-8:tier_3 | pass | sum of line items == 517.95 | 517.95 |  |
| INV-9:tier_1:t4g.medium | pass | sku exists in region ap-south-1 | found | Compute × 2 |
| INV-9:tier_1:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_1:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy |
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
| INV-9:tier_2:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_2:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy |
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
| INV-9:tier_3:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy |
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
| INV-9:tier_3:db.t4g.large | pass | sku exists in region ap-south-2 | found | Database (standby — second region) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-2 | found | Audit logging (standby — second region) |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-2 | found | TLS certificate (standby — second region) |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-2 | found | Fargate vCPU × 1 tasks (standby — second region) |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-2 | found | Fargate memory × 1 tasks (standby — second region) |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-2 | found | KMS keys × 1 (standby — second region) |
| INV-10 | pass | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 |  |
| INV-11 | pass | private_standard whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=high, durability=high, isolation_required=True) |  |
| INV-12 | pass | no priced tier when archetype == unknown | archetype=web_app priced=True tiers=3 |  |
| golden_totals:tier_1 | pass | $307.10 | $307.10 |  |
| golden_totals:tier_2 | pass | $373.83 | $373.83 |  |
| golden_totals:tier_3 | pass | $517.95 | $517.95 |  |

## catalog-region-integrity

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| compute-rate-differs-by-region | pass | ap-south-1 rate != us-east-1 rate for t4g.medium | ap-south-1=0.02240000 us-east-1=0.03360000 |  |
| database-rate-differs-by-region | pass | ap-south-1 rate != us-east-1 rate for db.t4g.large | ap-south-1=0.16700000 us-east-1=0.12900000 |  |
| no-catalog-entry-has-a-null-region | pass | 0 rows with a null/empty region | 0 rows |  |
| multi-az-database-costs-more-than-single-az | pass | db.t4g.large:multi-az > db.t4g.large | single=0.16700000 multi=0.33400000 |  |
| guardduty-and-securityhub-scale-with-resource-count | pass | cost(6 instances) > cost(2 instances) > 0 | small=$9.71 large=$24.31 |  |

## ecommerce-scale

Tier totals: tier_1=$1,170.41, tier_2=$1,673.02, tier_3=$3,330.20

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
| budget:tier_1 | pass | True | True | $1,170.41 vs $4,000.00 budget |
| budget:tier_2 | pass | True | True | $1,673.02 vs $4,000.00 budget |
| budget:tier_3 | pass | True | True | $3,330.20 vs $4,000.00 budget |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=True rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_2 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_3 | pass | <= 2 NAT gateways | 2 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=4 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-8:tier_1 | pass | sum of line items == 1170.41 | 1170.41 |  |
| INV-8:tier_2 | pass | sum of line items == 1673.02 | 1673.02 |  |
| INV-8:tier_3 | pass | sum of line items == 3330.2 | 3330.2 |  |
| INV-9:tier_1:c6g.2xlarge | pass | sku exists in region ap-south-1 | found | Compute × 6 |
| INV-9:tier_1:db.t4g.large:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_1:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_1:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_1:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_1:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_1:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_1:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_1:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_1:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_2:db.t4g.large:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_2:db.t4g.large | pass | sku exists in region ap-south-1 | found | Database read replica × 2 |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_2:cache.m8g.large | pass | sku exists in region ap-south-1 | found | Cache |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_2:cloudfront:data-transfer-out | pass | sku exists in region ap-south-1 | found | CDN data transfer |
| INV-9:tier_2:cloudfront:requests-https | pass | sku exists in region ap-south-1 | found | CDN requests |
| INV-9:tier_2:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_2:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_2:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_2:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_2:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_2:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_2:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 6 tasks |
| INV-9:tier_2:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 6 tasks |
| INV-9:tier_2:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_2:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_2:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_2:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_2:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_2:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_2:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_3:db.t4g.large:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_3:db.t4g.large | pass | sku exists in region ap-south-1 | found | Database read replica × 2 |
| INV-9:tier_3:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_3:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_3:cache.m8g.large | pass | sku exists in region ap-south-1 | found | Cache |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_3:cloudfront:data-transfer-out | pass | sku exists in region ap-south-1 | found | CDN data transfer |
| INV-9:tier_3:cloudfront:requests-https | pass | sku exists in region ap-south-1 | found | CDN requests |
| INV-9:tier_3:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_3:waf:webacl | pass | sku exists in region ap-south-1 | found | WAF Web ACL |
| INV-9:tier_3:waf:rule | pass | sku exists in region ap-south-1 | found | WAF rules × 3 |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:nat:gateway-hour | pass | sku exists in region ap-south-1 | found | NAT gateway × 2 |
| INV-9:tier_3:nat:gb-processed | pass | sku exists in region ap-south-1 | found | NAT data processing |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_3:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 18 tasks |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 18 tasks |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_3:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_3:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:vpc:flow-logs | pass | sku exists in region ap-south-1 | found | VPC flow logs |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | (none) | (none) |  |
| INV-11 | pass | private_standard whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=high, durability=normal, isolation_required=False) |  |
| INV-12 | pass | no priced tier when archetype == unknown | archetype=web_app priced=True tiers=3 |  |
| golden_totals:tier_1 | pass | $1170.41 | $1170.41 |  |
| golden_totals:tier_2 | pass | $1673.02 | $1673.02 |  |
| golden_totals:tier_3 | pass | $3330.20 | $3330.20 |  |

## fintech-bengaluru

Tier totals: tier_1=$217.09, tier_2=$254.11, tier_3=$398.23

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
| INV-5:CloudFront (CDN): not added, 0 | pass | non-empty reason string | CloudFront (CDN): not added, 0.00 peak req/sec and staff-only access, no large static assets and no users outside the home country described |  |
| INV-5:AWS WAF: not added, staff-only | pass | non-empty reason string | AWS WAF: not added, staff-only access — reachable only from known networks, so security groups plus an IP allowlist are the control that fits; a firewall in front of an internal system filters traffic that never arrives |  |
| INV-5:ElastiCache: not added, 0.00 p | pass | non-empty reason string | ElastiCache: not added, 0.00 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 0.00  | pass | non-empty reason string | Read replica: not added, 0.00 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=4 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-8:tier_1 | pass | sum of line items == 217.09 | 217.09 |  |
| INV-8:tier_2 | pass | sum of line items == 254.11 | 254.11 |  |
| INV-8:tier_3 | pass | sum of line items == 398.23 | 398.23 |  |
| INV-9:tier_1:t4g.medium | pass | sku exists in region ap-south-1 | found | Compute × 1 |
| INV-9:tier_1:db.t4g.micro | pass | sku exists in region ap-south-1 | found | Database |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy |
| INV-9:tier_1:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_1:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_1:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_1:organizations:scp | pass | sku exists in region ap-south-1 | found | Region-deny guardrail |
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
| INV-9:tier_2:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy |
| INV-9:tier_2:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_2:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_2:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_2:organizations:scp | pass | sku exists in region ap-south-1 | found | Region-deny guardrail |
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
| INV-9:tier_3:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy |
| INV-9:tier_3:s3:glacier-instant | pass | sku exists in region ap-south-1 | found | Archived retention |
| INV-9:tier_3:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_3:s3:object-lock | pass | sku exists in region ap-south-1 | found | Object Lock (WORM retention) |
| INV-9:tier_3:organizations:scp | pass | sku exists in region ap-south-1 | found | Region-deny guardrail |
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
| INV-11 | pass | private_standard whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=low, durability=high, isolation_required=True) |  |
| INV-12 | pass | no priced tier when archetype == unknown | archetype=web_app priced=True tiers=3 |  |
| golden_totals:tier_1 | pass | $217.09 | $217.09 |  |
| golden_totals:tier_2 | pass | $254.11 | $254.11 |  |
| golden_totals:tier_3 | pass | $398.23 | $398.23 |  |

## hospital-pune-public

Tier totals: tier_1=$315.10, tier_2=$381.83, tier_3=$525.95

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
| must_exclude:cdn:tier_1 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.69 peak req/sec and no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_2 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.69 peak req/sec and no large static assets and no users outside the home country described |
| must_exclude:cdn:tier_3 | pass | cdn absent | absent | CloudFront (CDN): not added, 0.69 peak req/sec and no large static assets and no users outside the home country described |
| compliance:Digital Personal Data Protection Act 2023 | pass | cites Digital Personal Data Protection Act 2023 | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| compliance:IT Act s43A | pass | cites IT Act s43A | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| compliance:ABDM | pass | cites ABDM | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| forbidden:HIPAA | pass | never cites HIPAA | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| forbidden:GDPR | pass | never cites GDPR | Digital Personal Data Protection Act 2023; IT Act s43A / SPDI Rules 2011; ABDM Health Data Management Policy; EHR Standards 2016 |  |
| budget:tier_1 | pass | True | True | $315.10 vs $900.00 budget |
| budget:tier_2 | pass | True | True | $381.83 vs $900.00 budget |
| budget:tier_3 | pass | True | True | $525.95 vs $900.00 budget |
| INV-1:tier_1 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_2 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-1:tier_3 | pass | rung-1 satisfied whenever a rung-4 component is present | rung4_present=False rung1_ok=True |  |
| INV-2:tier_1 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_2 | pass | <= 2 NAT gateways | 2 |  |
| INV-2:tier_3 | pass | <= 2 NAT gateways | 2 |  |
| INV-3:tier_1 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_2 | pass | passes constraint_filter.check() | valid |  |
| INV-3:tier_3 | pass | passes constraint_filter.check() | valid |  |
| INV-5:CloudFront (CDN): not added, 0 | pass | non-empty reason string | CloudFront (CDN): not added, 0.69 peak req/sec and no large static assets and no users outside the home country described |  |
| INV-5:ElastiCache: not added, 0.69 p | pass | non-empty reason string | ElastiCache: not added, 0.69 peak req/sec does not repeat reads often enough to pay for itself |  |
| INV-5:Read replica: not added, 0.69  | pass | non-empty reason string | Read replica: not added, 0.69 peak req/sec is served by the primary; a replica adds cost and a second thing to fail over |  |
| INV-5:Message queue: not added, noth | pass | non-empty reason string | Message queue: not added, nothing in the description is asynchronous, batched or long-running |  |
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=5 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-8:tier_1 | pass | sum of line items == 315.1 | 315.1 |  |
| INV-8:tier_2 | pass | sum of line items == 381.83 | 381.83 |  |
| INV-8:tier_3 | pass | sum of line items == 525.95 | 525.95 |  |
| INV-9:tier_1:t4g.medium | pass | sku exists in region ap-south-1 | found | Compute × 2 |
| INV-9:tier_1:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_1:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy |
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
| INV-9:tier_2:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_2:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy |
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
| INV-9:tier_3:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy |
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
| INV-9:tier_3:db.t4g.large | pass | sku exists in region ap-south-2 | found | Database (standby — second region) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-2 | found | Audit logging (standby — second region) |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-2 | found | TLS certificate (standby — second region) |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-2 | found | Fargate vCPU × 1 tasks (standby — second region) |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-2 | found | Fargate memory × 1 tasks (standby — second region) |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-2 | found | KMS keys × 1 (standby — second region) |
| INV-10 | pass | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 |  |
| INV-11 | pass | private_standard whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=high, durability=high, isolation_required=True) |  |
| INV-12 | pass | no priced tier when archetype == unknown | archetype=web_app priced=True tiers=3 |  |
| diff_against:hospital-pune:sizing_unchanged | pass | sizing identical to hospital-pune | identical |  |
| diff_against:hospital-pune:compliance_unchanged | pass | compliance identical to hospital-pune | identical |  |
| golden_totals:tier_1 | pass | $315.10 | $315.10 |  |
| golden_totals:tier_2 | pass | $381.83 | $381.83 |  |
| golden_totals:tier_3 | pass | $525.95 | $525.95 |  |

## hospital-pune

Tier totals: tier_1=$307.10, tier_2=$373.83, tier_3=$517.95

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
| budget:tier_1 | pass | True | True | $307.10 vs $900.00 budget |
| budget:tier_2 | pass | True | True | $373.83 vs $900.00 budget |
| budget:tier_3 | pass | True | True | $517.95 vs $900.00 budget |
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
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=1 no_further=False |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='1-2 min' rpo='~5 min' |  |
| INV-8:tier_1 | pass | sum of line items == 307.1 | 307.1 |  |
| INV-8:tier_2 | pass | sum of line items == 373.83 | 373.83 |  |
| INV-8:tier_3 | pass | sum of line items == 517.95 | 517.95 |  |
| INV-9:tier_1:t4g.medium | pass | sku exists in region ap-south-1 | found | Compute × 2 |
| INV-9:tier_1:db.t4g.micro:multi-az | pass | sku exists in region ap-south-1 | found | Database (Multi-AZ) |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_1:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy |
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
| INV-9:tier_2:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_2:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy |
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
| INV-9:tier_3:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:alb | pass | sku exists in region ap-south-1 | found | Load balancer |
| INV-9:tier_3:backup:cross-region-warm | pass | sku exists in region ap-south-1 | found | Cross-region backup copy |
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
| INV-9:tier_3:db.t4g.large | pass | sku exists in region ap-south-2 | found | Database (standby — second region) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-2 | found | Audit logging (standby — second region) |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-2 | found | TLS certificate (standby — second region) |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-2 | found | Fargate vCPU × 1 tasks (standby — second region) |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-2 | found | Fargate memory × 1 tasks (standby — second region) |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-2 | found | KMS keys × 1 (standby — second region) |
| INV-10 | pass | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 |  |
| INV-11 | pass | private_standard whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=high, durability=high, isolation_required=True) |  |
| INV-12 | pass | no priced tier when archetype == unknown | archetype=web_app priced=True tiers=3 |  |
| golden_totals:tier_1 | pass | $307.10 | $307.10 |  |
| golden_totals:tier_2 | pass | $373.83 | $373.83 |  |
| golden_totals:tier_3 | pass | $517.95 | $517.95 |  |

## internal-low-stakes

Tier totals: tier_1=$65.61, tier_2=$102.63, tier_3=$102.63

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
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
| must_exclude:vpc_flow_logs:tier_1 | pass | vpc_flow_logs absent | absent | public_simple: no stated availability or durability requirement and 0.00 peak req/sec, so private application subnets and their NAT gateway are not bought. |
| must_exclude:vpc_flow_logs:tier_2 | pass | vpc_flow_logs absent | absent | public_simple: no stated availability or durability requirement and 0.00 peak req/sec, so private application subnets and their NAT gateway are not bought. |
| must_exclude:vpc_flow_logs:tier_3 | pass | vpc_flow_logs absent | absent | public_simple: no stated availability or durability requirement and 0.00 peak req/sec, so private application subnets and their NAT gateway are not bought. |
| budget:tier_1 | **FAIL** | True | False | $65.61 vs $60.00 budget |
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
| INV-6:tier_2 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=5 no_further=False |  |
| INV-6:tier_3 | pass | >=1 pattern_diff, or an explicit no-further-improvement note | pattern_diff=0 no_further=True |  |
| INV-7:tier_1 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_2 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-7:tier_3 | pass | non-null rto and rpo | rto='30-120 min' rpo='= backup interval' |  |
| INV-8:tier_1 | pass | sum of line items == 65.61 | 65.61 |  |
| INV-8:tier_2 | pass | sum of line items == 102.63 | 102.63 |  |
| INV-8:tier_3 | pass | sum of line items == 102.63 | 102.63 |  |
| INV-9:tier_1:t4g.medium | pass | sku exists in region ap-south-1 | found | Compute × 1 |
| INV-9:tier_1:db.t4g.micro | pass | sku exists in region ap-south-1 | found | Database |
| INV-9:tier_1:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_1:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_1:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_1:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_1:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_1:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_1:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_1:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-9:tier_2:db.t4g.micro | pass | sku exists in region ap-south-1 | found | Database |
| INV-9:tier_2:s3:general-purpose | pass | sku exists in region ap-south-1 | found | Object storage |
| INV-9:tier_2:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_2:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_2:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_2:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_2:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_2:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_2:cognito:user-pool-mau | pass | sku exists in region ap-south-1 | found | Authentication (MAU) |
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
| INV-9:tier_3:egress:internet | pass | sku exists in region ap-south-1 | found | Egress |
| INV-9:tier_3:cloudwatch:metrics | pass | sku exists in region ap-south-1 | found | Monitoring |
| INV-9:tier_3:vpce:gateway | pass | sku exists in region ap-south-1 | found | Gateway endpoints × 2 (S3 + DynamoDB — no charge, keeps that traffic off NAT) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-1 | found | Audit logging |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-1 | found | TLS certificate |
| INV-9:tier_3:route53:hosted-zone | pass | sku exists in region ap-south-1 | found | DNS hosted zone × 1 |
| INV-9:tier_3:cognito:user-pool-mau | pass | sku exists in region ap-south-1 | found | Authentication (MAU) |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-1 | found | Fargate vCPU × 1 tasks |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-1 | found | Fargate memory × 1 tasks |
| INV-9:tier_3:secretsmanager:secret | pass | sku exists in region ap-south-1 | found | Secrets × 1 |
| INV-9:tier_3:guardduty:fargate-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: Fargate |
| INV-9:tier_3:guardduty:rds-vcpu | pass | sku exists in region ap-south-1 | found | Threat detection: database |
| INV-9:tier_3:xray:traces-recorded | pass | sku exists in region ap-south-1 | found | Distributed tracing |
| INV-9:tier_3:securityhub:compliance-check | pass | sku exists in region ap-south-1 | found | Security posture checks |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-1 | found | KMS keys × 1 |
| INV-10 | pass | (none) | (none) |  |
| INV-11 | pass | private_standard whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=public_simple (availability=low, durability=normal, isolation_required=False) |  |
| INV-12 | pass | no priced tier when archetype == unknown | archetype=web_app priced=True tiers=3 |  |

## probe:batch-etl

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| INV-12 | pass | no priced tier when archetype == unknown | archetype=unknown priced=False tiers=0 | This workload does not match an architecture pattern the engine has been validated on. Pricing is withheld rather than guessed. |
| classified | pass | an archetype name (or 'unknown') | batch_etl | Recognised as 'batch_etl' (matched 4 phrase(s), first 'every night'), which this engine can name but has not yet been taught to build. |
| withholds_pricing | pass | no priced tiers for an unimplemented archetype | 0 tier(s) | This workload does not match an architecture pattern the engine has been validated on. Pricing is withheld rather than guessed. |
| offers_next_steps | pass | clarifying questions and a coverage list | 5 question(s), 7 archetype(s) listed |  |

## probe:event-webhook

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| INV-12 | pass | no priced tier when archetype == unknown | archetype=unknown priced=False tiers=0 | This workload does not match an architecture pattern the engine has been validated on. Pricing is withheld rather than guessed. |
| classified | pass | an archetype name (or 'unknown') | event_driven | Recognised as 'event_driven' (matched 4 phrase(s), first 'webhook'), which this engine can name but has not yet been taught to build. |
| withholds_pricing | pass | no priced tiers for an unimplemented archetype | 0 tier(s) | This workload does not match an architecture pattern the engine has been validated on. Pricing is withheld rather than guessed. |
| offers_next_steps | pass | clarifying questions and a coverage list | 5 question(s), 7 archetype(s) listed |  |

## probe:ml-inference

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| INV-12 | pass | no priced tier when archetype == unknown | archetype=unknown priced=False tiers=0 | This workload does not match an architecture pattern the engine has been validated on. Pricing is withheld rather than guessed. |
| classified | pass | an archetype name (or 'unknown') | ml_inference | Recognised as 'ml_inference' (matched 4 phrase(s), first 'trained model'), which this engine can name but has not yet been taught to build. |
| withholds_pricing | pass | no priced tiers for an unimplemented archetype | 0 tier(s) | This workload does not match an architecture pattern the engine has been validated on. Pricing is withheld rather than guessed. |
| offers_next_steps | pass | clarifying questions and a coverage list | 5 question(s), 7 archetype(s) listed |  |

## probe:realtime-chat

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| INV-12 | pass | no priced tier when archetype == unknown | archetype=unknown priced=False tiers=0 | This workload does not match an architecture pattern the engine has been validated on. Pricing is withheld rather than guessed. |
| classified | pass | an archetype name (or 'unknown') | realtime | Recognised as 'realtime' (matched 3 phrase(s), first 'in-app chat'), which this engine can name but has not yet been taught to build. |
| withholds_pricing | pass | no priced tiers for an unimplemented archetype | 0 tier(s) | This workload does not match an architecture pattern the engine has been validated on. Pricing is withheld rather than guessed. |
| offers_next_steps | pass | clarifying questions and a coverage list | 5 question(s), 7 archetype(s) listed |  |

## probe:static-site

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| INV-12 | pass | no priced tier when archetype == unknown | archetype=unknown priced=False tiers=0 | This workload does not match an architecture pattern the engine has been validated on. Pricing is withheld rather than guessed. |
| classified | pass | an archetype name (or 'unknown') | static_site | Recognised as 'static_site' (matched 5 phrase(s), first 'no database'), which this engine can name but has not yet been taught to build. |
| withholds_pricing | pass | no priced tiers for an unimplemented archetype | 0 tier(s) | This workload does not match an architecture pattern the engine has been validated on. Pricing is withheld rather than guessed. |
| offers_next_steps | pass | clarifying questions and a coverage list | 5 question(s), 7 archetype(s) listed |  |

## probe:vm-migration

| assertion | result | expected | actual | reason |
|---|---|---|---|---|
| INV-12 | pass | no priced tier when archetype == unknown | archetype=unknown priced=False tiers=0 | This workload does not match an architecture pattern the engine has been validated on. Pricing is withheld rather than guessed. |
| classified | pass | an archetype name (or 'unknown') | migration | Recognised as 'migration' (matched 4 phrase(s), first 'virtual machines'), which this engine can name but has not yet been taught to build. |
| withholds_pricing | pass | no priced tiers for an unimplemented archetype | 0 tier(s) | This workload does not match an architecture pattern the engine has been validated on. Pricing is withheld rather than guessed. |
| offers_next_steps | pass | clarifying questions and a coverage list | 5 question(s), 7 archetype(s) listed |  |
