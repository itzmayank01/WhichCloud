# WhichCloud Budget-Aware Architecture Ladder (Design Specification)

Date: 2026-11-16
Status: Approved Architecture Specification (Part C)

---

## 1. Principles of the Budget Ladder

1. **Traffic Decides Size**:
   - Transaction volume and peak RPS determine instance sizing (vCPU, RAM, storage, container task size).
   - A 0.28 TPS workload never receives 16 vCPU compute or a 64 GB database.
2. **Requirements and Risk Decide Modules**:
   - Availability class (`business_hours`, `always_on`, `regulated_dr`, `standard`) determines which structural modules are justified.
   - High budget does not invent traffic; high budget unlocks resilience, security, observability, and disaster recovery modules that the brief justifies.
3. **Budget Decides Affordability**:
   - Budget dictates how far up the prioritized ladder of justified modules the architecture can climb.
   - If budget is tight ($500), the engine explicitly identifies which modules were omitted and the risks retained.
   - If budget is abundant ($5,000 or $20,000), the engine stops once all justified modules are satisfied and reports remaining money as **"Budget Left"**, never padding.
4. **Data Residency**:
   - For workloads in India (`ap-south-1` Mumbai), the DR region must stay inside India (`ap-south-2` Hyderabad).

---

## 2. The 6-Step Module Ladder

| Step | Module ID | Module Name | Services / SKUs | Monthly Cost Formula (from Catalog) | Requirement / Risk Addressed | Prereqs | Flag |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **1** | `MOD-AVAIL-BH` | **Business Hours Multi-AZ** | 2-AZ Compute (Fargate / EC2), 2-AZ Load Balancer (ALB), Multi-AZ RDS Postgres | `2 * compute_rate * 730 + alb_rate * 730 + rds_multiaz_rate * 730` | Eliminates single AZ failure during business hours | Base | **Required** for `business_hours`, `always_on`, `regulated_dr` |
| **1** | `MOD-AVAIL-AO` | **Always-On 3-AZ Resiliency** | 3-AZ Compute floor, 3-AZ subnets, Target Group connection draining, health check probe | `3 * compute_rate * 730 + alb_rate * 730 + rds_multiaz_rate * 730` | 24/7 zero-downtime, survives AZ loss without capacity degradation | `MOD-AVAIL-BH` | **Required** for `always_on`, `regulated_dr`; **Optional** for others |
| **2** | `MOD-SEC-BASE` | **Security Baseline** | AWS KMS (`kms:key`), Secrets Manager (`secrets:secret`), AWS WAF v2 (`waf:webacl`, `waf:rule`), GuardDuty (`threat:events`), CloudTrail (`audit:trail`) | `$1.00 (KMS) + $0.40 (Secrets) + $5.00 (WAF ACL) + $3.00 (WAF rules) + $9.71 (GuardDuty) + $0.00 (CloudTrail) = ~$19.11/mo` | Protects customer data, secrets in memory, blocks bot attacks and unauthorized intrusions | Base compute | **Required** for `regulated_dr`; **Recommended** for `business_hours` & `always_on` |
| **3** | `MOD-BCK-REC` | **Backup & Point-in-Time Recovery** | AWS Backup Vault (`backup:vault`), 35-day automated PITR retention, Object Lock (WORM immutability), Cross-Region Backup Copy to Hyderabad (`backup_copy` in `ap-south-2`) | `storage_gb * $0.05 (backup) + storage_gb * $0.02 (PITR) + storage_gb * $0.02 (ap-south-2 copy) = ~$9.00 - $25.00/mo` | Eliminates permanent data loss from database corruption, ransomware, or whole-region storage incidents | `MOD-AVAIL-BH` | **Required** for `regulated_dr`; **Recommended** for `business_hours` & `always_on` |
| **4** | `MOD-OBS-ALERT`| **Comprehensive Observability & Alerting** | CloudWatch 30 Metrics (`monitoring:metric`), CloudWatch Alarm rules, SNS alert topics (`notification:sns`), Log Retention policy | `$9.00 (Metrics) + $1.00 (Alarms) + $0.50 (SNS) = ~$10.50/mo` | Eliminates silent failures; alerts ops when POS API or database latencies spike | Base compute | **Recommended** for Tier 2; **Required** for Tier 3 |
| **5** | `MOD-DR-STANDBY`| **Disaster Recovery Warm Standby (Hyderabad)** | Cross-region Read Replica in `ap-south-2` (`database:replica`), S3 bucket replication in `ap-south-2`, standby Fargate container task in `ap-south-2`, Route 53 DNS failover routing | `rds_single_rate(ap-south-2) + 1 * fargate_rate(ap-south-2) * 730 + r53_health_check = ~$145.00 - $220.00/mo` | Provides estimated RTO < 15 mins and RPO < 1 min if entire AWS Mumbai region experiences complete outage | `MOD-AVAIL-BH`, `MOD-BCK-REC` | **Required** for `regulated_dr`; **Recommended** for Tier 3 when budget >= $1,500; **Optional** for others |
| **6** | `MOD-GROWTH-HEAD`| **Performance & Growth Headroom** | ElastiCache Redis cluster (`cache:node`), In-region Read Replica (`database:replica`), Auto Scaling Max buffer | `cache_rate * 730 + rds_replica_rate * 730 = ~$136.00/mo` | Decouples reporting dashboards from store POS transactions; prevents checkout contention | `MOD-AVAIL-BH` | **Recommended** for Tier 3; **Optional** for Tier 2 |

---

## 3. Tier Assignment Rules

1. **Tier 1 (Cheapest that meets requirements)**:
   - Contains ONLY Required modules for the detected availability class.
   - Sized using the most economical valid SKU that satisfies the floor (e.g. EC2/ASG instead of Fargate if budget is constrained, single-AZ if standard).
   - If budget is below the required modules floor, reports exactly what is missing and flags over-budget.
2. **Tier 2 (Balanced — Production Ready)**:
   - Contains Required + Recommended modules (`MOD-AVAIL-BH` + `MOD-SEC-BASE` + `MOD-BCK-REC` + `MOD-OBS-ALERT`).
   - Sized for measured traffic using managed containers (AWS Fargate) and production Multi-AZ database.
3. **Tier 3 (Most Optimized — Enterprise Resilience)**:
   - Contains Required + Recommended + Justified Optional modules (`MOD-DR-STANDBY` in `ap-south-2` + `MOD-GROWTH-HEAD`).
   - Targets **40% to 70%** of available budget.
   - Stops immediately once all 6 modules are satisfied. Does not inflate task counts or database sizes past what traffic warrants.
   - Every service displays an **"Added because: ..."** tag in the UI.

---

## 4. Retail Store Workload Evaluation ($500 vs. $5,000 vs. $20,000)

**Input Brief**: Retail chain, 40 stores, 300 staff, 8,000 transactions/day, "must not go down during business hours because billing stops", India residency.
- Detected Class: `business_hours`
- Peak Traffic: 0.28 transactions/sec
- Database Working Set: 100 GB storage, 2 vCPU / 8 GB RAM

### Scenario A: Budget = $500/month (Lean Constraint)
- **Tier 1 (Cheapest)**: **$245.28/mo** (49.1% used | $254.72 left)
  - Modules: `MOD-AVAIL-BH` (2-AZ EC2, Multi-AZ RDS Postgres, ALB).
  - Omitted: `MOD-SEC-BASE`, `MOD-DR-STANDBY` (Omitted: "Budget insufficient for secondary region warm standby").
- **Tier 2 (Balanced)**: **$478.16/mo** (95.6% used | $21.84 left)
  - Modules: `MOD-AVAIL-BH` + `MOD-SEC-BASE` + `MOD-OBS-ALERT` (Fargate, Multi-AZ RDS, KMS, WAF, CloudWatch).
  - Omitted: `MOD-DR-STANDBY` (Omitted: "Warm standby region ($185/mo) exceeds remaining $21.84 budget").
- **Tier 3 (Most Optimized)**: **$519.04/mo** (Flagged: Over budget by $19.04, or scaled to $495/mo)
  - Modules: Adds Redis cache for store inventory lookups.

### Scenario B: Budget = $5,000/month (Recommended Operating Target)
- **Tier 1 (Cheapest)**: **$245.28/mo** (4.9% used | $4,754.72 left)
  - Modules: `MOD-AVAIL-BH` (2-AZ EC2 ASG, Multi-AZ RDS, ALB).
  - Why: Satisfies business hours zero-downtime requirement at absolute lowest catalog cost.
- **Tier 2 (Balanced)**: **$478.16/mo** (9.6% used | $4,521.84 left)
  - Modules: `MOD-AVAIL-BH` + `MOD-SEC-BASE` + `MOD-BCK-REC` + `MOD-OBS-ALERT`.
  - Added because: Managed Fargate patching, WAF intrusion prevention, immutable backup vault, and CloudWatch alarms.
- **Tier 3 (Most Optimized / Enterprise Resilience)**: **$865.34/mo** (17.3% used | **$4,134.66 left**)
  - Modules Included:
    - `MOD-AVAIL-BH`: 2-AZ Fargate compute + 2-AZ ALB + Multi-AZ RDS ($285.40/mo)
    - `MOD-SEC-BASE`: WAF v2 + KMS + Secrets Manager + GuardDuty ($19.11/mo)
    - `MOD-BCK-REC`: Immutable Object Lock + Cross-Region Backup Copy to Hyderabad ($22.40/mo)
    - `MOD-OBS-ALERT`: CloudWatch 30 metrics + Alarms + SNS alerting ($10.50/mo)
    - `MOD-DR-STANDBY`: **Warm Standby in Hyderabad (`ap-south-2`)** with RDS cross-region replica, S3 replication, standby container, and Route 53 health check failover ($218.43/mo)
    - `MOD-GROWTH-HEAD`: Redis ElastiCache cluster for POS inventory catalog queries + read replica for head office live numbers ($309.50/mo)
  - **Budget Used**: $865.34 / $5,000 (17.3%).
  - **Budget Left**: **$4,134.66** unspent. UI states: *"All 6 availability, security, disaster recovery, and caching modules satisfied. Additional spend would buy excess capacity this workload cannot consume."*

### Scenario C: Budget = $20,000/month (Abundant Enterprise Budget)
- **Tier 1**: **$245.28/mo** (1.2% used | $19,754.72 left)
- **Tier 2**: **$478.16/mo** (2.4% used | $19,521.84 left)
- **Tier 3**: **$865.34/mo** (4.3% used | **$19,134.66 left**)
  - Does NOT balloon to $15,000 or buy unneeded 64-core instances.
  - Sizing remains pinned to 0.28 TPS.
  - UI reports: *"Budget used: 4.3%. Budget left: $19,134.66/mo. Enterprise resilience and cross-region disaster recovery fully provisioned."*

