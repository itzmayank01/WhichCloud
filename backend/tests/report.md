# WhichCloud regression harness report

Run at 2026-09-08 16:53:03 UTC

| fixture | passed | failed | status |
|---|---|---|---|
| hospital-pune | 140 | 3 | FAIL |

## hospital-pune

Tier totals: tier_1=$281.01, tier_2=$347.74, tier_3=$491.86

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
| budget:tier_3 | pass | True | True | $491.86 vs $900.00 budget |
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
| INV-8:tier_1 | pass | sum of line items == 281.01 | 281.01 |  |
| INV-8:tier_2 | pass | sum of line items == 347.74 | 347.74 |  |
| INV-8:tier_3 | pass | sum of line items == 491.86 | 491.86 |  |
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
| INV-9:tier_3:db.t4g.large | pass | sku exists in region ap-south-2 | found | Database (standby — second region) |
| INV-9:tier_3:cloudtrail:management-events | pass | sku exists in region ap-south-2 | found | Audit logging (standby — second region) |
| INV-9:tier_3:acm:public-certificate | pass | sku exists in region ap-south-2 | found | TLS certificate (standby — second region) |
| INV-9:tier_3:fargate:arm-vcpu-hour | pass | sku exists in region ap-south-2 | found | Fargate vCPU × 1 tasks (standby — second region) |
| INV-9:tier_3:fargate:arm-gb-hour | pass | sku exists in region ap-south-2 | found | Fargate memory × 1 tasks (standby — second region) |
| INV-9:tier_3:kms:key | pass | sku exists in region ap-south-2 | found | KMS keys × 1 (standby — second region) |
| INV-10 | pass | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 | ABDM Health Data Management Policy; Digital Personal Data Protection Act 2023; EHR Standards 2016; IT Act s43A / SPDI Rules 2011 |  |
| INV-11 | pass | private_standard whenever availability=high, durability=high, or a compliance obligation requires network isolation | topology=private_standard (availability=high, durability=high, isolation_required=True) |  |
| INV-12 | pass | no priced output when the archetype is not priceable | state=priced (priceable, not withheld) |  |
| INV-13:tier_1 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=510.986 durability=high (stated) |  |
| INV-13:tier_2 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=510.986 durability=high (stated) |  |
| INV-13:tier_3 | pass | a backup component, unless durability == ephemeral from stated text | backup_gb=510.986 durability=high (stated) |  |
| INV-14 | pass | no priced tier when the prompt describes two workloads | state=priced tiers=3 composite_of=[] |  |
| INV-15 | pass | no ARM instance family when x86 is required | cpu_architecture=unknown (not x86_required) |  |
| INV-16 | pass | a stated quantity that was not read withholds pricing | every stated quantity was read |  |
| golden_totals:tier_1 | **FAIL** | $287.02 | $281.01 |  |
| golden_totals:tier_2 | **FAIL** | $353.75 | $347.74 |  |
| golden_totals:tier_3 | **FAIL** | $497.87 | $491.86 |  |
