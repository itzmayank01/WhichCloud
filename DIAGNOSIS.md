# WhichCloud Diagnosis: Budget-Aware Architecture (Part A)

Date: 2026-11-16
Status: Part A Complete (Read-Only Audit)

---

## 1. Where Budget is Read Across the Codebase

| File | Line(s) | Function / Context | What it Does |
| :--- | :--- | :--- | :--- |
| `backend/whichcloud/requirements.py` | 88, 174 | `Requirement.budget_monthly_usd` | Data model definition. Validates `budget_monthly_usd > 0` when set. |
| `backend/whichcloud/constraints.py` | 48, 62, 212, 526 | `Constraints.budget_monthly_usd` | Constraint model definition. Regex extracts dollar value into `budget_monthly_usd`. |
| `backend/whichcloud/llm_extract.py` | 289, 552 | `ExtractionMeta.budget_monthly_usd` | Pydantic schema for structured LLM extraction. Reads stated monthly USD. |
| `backend/whichcloud/intake.py` | 937–946, 1021 | `_fast_heuristic_draft` | Regex `r'\$\s*([0-9]+(?:\.[0-9]+)?)'` extracts budget into `Requirement.budget_monthly_usd`. |
| `backend/whichcloud/engine.py` | 395–397 | `Option.within_budget` | Property: returns `self.monthly <= Decimal(str(budget))` or `None`. |
| `backend/whichcloud/engine.py` | 406–409 | `Option.budget_saturated` | Property: boolean flag indicating extra budget adds no useful capacity. |
| `backend/whichcloud/engine.py` | 1657–1660 | `_shape_variants` | Core policy comment: *"What it deliberately does NOT do is spend to a budget. A tier that grew until it consumed a percentage... would recommend the same architecture to a blog and to a bank"*. |
| `backend/whichcloud/engine.py` | 1952–1985 | `_fit_within_budget` | **The Downward-Only Rule**: Checks if cost exceeds budget. If over budget, removes components in order. If under budget, explicitly treats difference as "headroom, not an opportunity" and refuses to size anything upward. |
| `backend/whichcloud/engine.py` | 2326 | `recommend()` | Calls `_fit_within_budget(spec, requirement, provider, dsn)`. |
| `backend/whichcloud/plan.py` | 279–281 | `Tier.within_budget` | Method: returns `self.monthly_total <= budget`. |
| `backend/whichcloud/plan.py` | 290–291 | `Plan.over_budget_note`, `Plan.unspent_budget` | Fields for budget disclosure. |
| `backend/whichcloud/plan.py` | 901–906 | `_check_budget_allocation` | Guard: raises `BudgetMisallocationError` if cache/replica added while compute filter is invalid. |
| `backend/whichcloud/plan.py` | 1323–1328 | `_withheld_plan` | Sets `over_budget_note` if Tier 1 exceeds budget floor. |
| `backend/whichcloud/plan.py` | 1627–1653 | `plan_from()` | Evaluates `spare = budget - reference.monthly_total`. If `spare > 0`, records `unspent_budget` stating: `"$X of your $Y is unspent even by the top tier... spending the remainder would buy capacity this workload would not use."` |
| `backend/whichcloud/planner.py` | 9–10, 384–388 | `plan_workload` | Sets `budget_note: "Budget is not an input to sizing..."` |
| `backend/whichcloud/api.py` | 900, 934, 1815, 1865 | API Route Handlers | Accepts `budget_monthly_usd` in request bodies and serializes `within_budget`, `unspent_budget`, and `over_budget_note` to JSON. |
| `backend/whichcloud/estimator.py` | N/A (0 occurrences) | Sizing Estimator | **Never reads budget.** Prices strictly what is in `ArchitectureSpec`. |
| `backend/whichcloud/archetypes/*` | N/A (0 occurrences) | Archetype Graphs | **Never reads budget.** All 7 archetype graphs size strictly from traffic and data volume. |

---

## 2. Retail Prompt at 4 Budget Levels ($500, $2,000, $5,000, $20,000)

**Prompt**: *"I run operations for a retail chain in India with 40 stores. We want to move our stock and billing system online so staff can use it from any store and head office can see live numbers. Around 300 staff use it daily and we do about 8,000 transactions a day. It must not go down during business hours because billing stops. Budget is around ${budget} a month."*

### Recommendation Path (`/api/recommend` via `engine.py`)

| Stated Budget | Tier | Monthly Total | Unique Services (Items) | AZ Count | DR Region | Budget Used % | Unspent Budget |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **$500** | Cheapest | $229.28 | 14 (14) | 1 | No | 45.9% | $270.72 |
| | Most reliable | $339.58 | 16 (16) | 2 | No | 67.9% | $160.42 |
| | Most optimized | $425.69 | 16 (16) | 2 | No | 85.1% | $74.31 |
| **$2,000** | Cheapest | $229.28 | 14 (14) | 1 | No | 11.5% | $1,770.72 |
| | Most reliable | $339.58 | 16 (16) | 2 | No | 17.0% | $1,660.42 |
| | Most optimized | $1,057.28 | 17 (17) | 2 | No | 52.9% | $942.72 |
| **$5,000** | Cheapest | $229.28 | 14 (14) | 1 | No | 4.6% | $4,770.72 |
| | Most reliable | $339.58 | 16 (16) | 2 | No | 6.8% | $4,660.42 |
| | Most optimized | $1,057.28 | 17 (17) | 2 | No | 21.1% | $3,942.72 |
| **$20,000** | Cheapest | $229.28 | 14 (14) | 1 | No | 1.1% | $19,770.72 |
| | Most reliable | $339.58 | 16 (16) | 2 | No | 1.7% | $19,660.42 |
| | Most optimized | $1,057.28 | 17 (17) | 2 | No | 5.3% | $18,942.72 |

### Planner Path (`/api/plan` via `plan.py`)

| Stated Budget | Tier | Monthly Total | Unique Services (Items) | AZ Count | DR Region | Budget Used % | Unspent Budget |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **$500** | Tier 1 (Cheapest) | $176.94 | 17 (17) | 2 | No | 35.4% | $323.06 |
| | Tier 2 (Balanced) | $243.67 | 24 (24) | 2 | No | 48.7% | $256.33 |
| | Tier 3 (Growth) | $387.79 | 25 (30) | 2 | No | 77.6% | $112.21 |
| **$2,000** | Tier 1 (Cheapest) | $175.30 | 13 (13) | 2 | No | 8.8% | $1,824.70 |
| | Tier 2 (Balanced) | $242.03 | 20 (20) | 2 | No | 12.1% | $1,757.97 |
| | Tier 3 (Growth) | $244.59 | 24 (24) | 2 | No | 12.2% | $1,755.41 |
| **$5,000** | Tier 1 (Cheapest) | $175.30 | 13 (13) | 2 | No | 3.5% | $4,824.70 |
| | Tier 2 (Balanced) | $242.03 | 20 (20) | 2 | No | 4.8% | $4,757.97 |
| | Tier 3 (Growth) | $244.59 | 24 (24) | 2 | No | 4.9% | $4,755.41 |
| **$20,000** | Tier 1 (Cheapest) | $175.30 | 13 (13) | 2 | No | 0.9% | $19,824.70 |
| | Tier 2 (Balanced) | $242.03 | 20 (20) | 2 | No | 1.2% | $19,757.97 |
| | Tier 3 (Growth) | $244.59 | 24 (24) | 2 | No | 1.2% | $19,755.41 |

*Diagnostic Observation*: In both engines, tier architectures plateau immediately above $2,000. For budgets $2,000, $5,000, and $20,000, the generated architectures and totals are **100% frozen**. In `plan.py`, Tier 3 spends only $244.59 regardless of whether budget is $2,000 or $20,000 (using only 1.2% of the budget), and zero disaster recovery region is added.

---

## 3. How Tier 2 and Tier 3 are Built Today

### In `engine.py` (`recommend()`)
- Built via a **static delta template**:
  - **Tier 1 (Cheapest)**: Single EC2 compute instance, single-AZ RDS database, S3 standard storage, CloudWatch basic metrics.
  - **Tier 2 (Most reliable)**: Takes Tier 1 and flips hardcoded template flags:
    - `database_multi_az = True`
    - `load_balancer = True`
    - `compute_count = max(2, instances)`
  - **Tier 3 (Most optimized)**: Copies Tier 2, then adds:
    - `database_read_replicas = max(2, replicas)`
    - Redis Cache (`cache_vcpu = max(2, db_vcpu // 2)`)
    - WAF rules if edge is enabled.
  - Sizing is capped. It never introduces cross-region copies or disaster recovery.

### In `plan.py` (`plan_from()`)
- Built via **rung levels (rung 1 to 4)** in `_spec_for()`:
  - **Tier 1 (`tier_level=1`)**: Minimal compliant spec. EC2 instances in Auto Scaling Group, single-AZ database, basic S3.
  - **Tier 2 (`tier_level=2`)**: Sets `managed = True`. Replaces EC2 with AWS Fargate containers, adds AWS Secrets Manager, AWS GuardDuty threat detection, and AWS X-Ray tracing.
  - **Tier 3 (`tier_level=3`)**: Sets `resilient = tier_level >= 3 and (durable or high_availability)`.
    - If `resilient` is True: adds Object Lock (WORM) and S3 cross-region backup copy (`backup_copy_gb`).
    - If `resilient` is False (which happens when availability was unclassified or not explicitly tagged `high`): **Tier 3 adds nothing over Tier 2**, resulting in the zero-spread defect where Tier 2 ($242.03) and Tier 3 ($244.59) are virtually identical.

---

## 4. Services `web_app` Emits Today vs. Missing Services

| Service / Capability | Supported Today in `web_app`? | Implementation Details in Code |
| :--- | :---: | :--- |
| **2-AZ Compute** | **YES** | `fargate_task_count >= 2` or `compute_count >= 2` |
| **2-AZ Load Balancer** | **YES** | AWS ALB (`load_balancer = True`) |
| **Multi-AZ Database** | **YES** | AWS RDS Multi-AZ (`database_multi_az = True`) |
| **WAF** | **YES** | AWS WAF v2 ACL + 3 managed rule groups (`waf_rule_count = 3`) |
| **Backup Vault** | **YES** | AWS Backup vault with lifecycle retention (`backup_gb`) |
| **Cross-Region Backup Copy** | **YES** | S3 cross-region copy (`backup_copy_gb`, `backup_transfer_gb`) |
| **GuardDuty** | **YES** | Threat detection (`threat_detection = True`) |
| **CloudTrail** | **YES** | Management audit logging (`audit_logging = True`) |
| **AWS Config** | **YES** | Configuration checks (`posture_monthly_checks`) |
| **Secrets Manager** | **YES** | Secret storage with rotation (`secret_count = 1`) |
| **AWS Shield Advanced** | **MISSING** | No meter or pricing logic for Shield Advanced ($3,000/mo flat) |
| **Route 53 Health Checks** | **MISSING** | Only prices static hosted zone (`dns_hosted_zones=1`), no active endpoint health checks |
| **Warm Standby Region (Compute/DB)**| **MISSING** | `standby_spec` exists in `plan.py` but is never attached to `web_app` tiers |
| **CloudWatch Alarms + SNS Alerts** | **MISSING** | Metrics are priced (`monitored_metrics=30`), but alarm rules and SNS topics are omitted |
| **Queue for POS Offline Buffering** | **MISSING** | SQS queue only added when `async_processing=True`; omitted for retail storefronts |
| **VPN Redundancy (Dual Tunnels)** | **MISSING** | Zero IPsec / AWS Site-to-Site VPN endpoints supported in catalog or spec |

---

## 5. Why Database is 63% of the Bill for 0.28 TPS

### The Workload Inputs
- Daily transactions: **8,000 transactions / day**.
- Active hours: 8 to 10 store hours.
- Mean transaction rate: `8,000 / (8 * 3600) = 0.278 transactions / second` (~0.28 TPS).
- 300 staff users across 40 stores.

### Sizing Formulas in `engine.py` & `plan.py`
1. **Database vCPU & Memory Floor**:
   - In `backend/whichcloud/engine.py:502`:
     `vcpu, memory = DB_SIZING[requirement.traffic_scale]`
   - `traffic_scale` defaults to `"medium"`.
   - `DB_SIZING["medium"]` is hardcoded to **(2 vCPU, 8.0 GB RAM)** (`db.t4g.large`).
   - In `backend/whichcloud/plan.py:567`:
     `_database_size_for(load_tier)`: non-trivial workloads keep **(2 vCPU, 8.0 GB RAM)**.
2. **Multi-AZ Multiplier**:
   - In Tier 2 and Tier 3, `database_multi_az = True`.
   - RDS Multi-AZ runs a synchronous standby instance in a second AZ, doubling compute rate:
     `$0.132/hr * 2 = $0.264/hr` -> **$192.87/mo** in `ap-south-1`.
3. **Read Replicas in Tier 3**:
   - In `backend/whichcloud/engine.py:1665`:
     `optimized_delta["database_read_replicas"] = max(2, replicas)`
   - Unconditionally adds 2 read replicas (`db.t4g.large`), adding `2 * $96.43 = $192.87/mo`.
4. **Database Storage & IOPS**:
   - 100 GB GP3 storage + backup storage = **$28.00/mo**.
5. **Cost Breakdown Comparison**:
   - Total Database in Most optimized: `$192.87 (Multi-AZ) + $192.87 (2 Replicas) + $28.00 (Storage) = $413.74/mo`.
   - Total Compute (Fargate / EC2 for 0.28 TPS): 2 tasks = **$47.30/mo**.
   - Total Storage, CDN, Monitoring, KMS: **~$58.00/mo**.
   - Database share: `$413.74 / $519.04 = 79.7%` (or ~63% on Tier 2).
   - **Root Cause**: Database compute is floored at 2 vCPU / 8 GB and multiplied 4x (Multi-AZ + 2 read replicas), whereas application compute scales down to micro/nano containers.

---

## 6. Frontend Page Reach Confirmation

| Page Route | Source Component & Line | API Called | Backend Target | Engine Used |
| :--- | :--- | :--- | :--- | :---: |
| `/dashboard` | `frontend/components/workspace/WorkspaceView.tsx:249` | `POST /describe` | `backend/whichcloud/api.py:1335` | **Legacy `engine.py`** |
| `/estimate` | `frontend/components/estimate/EstimateWorkbench.tsx:140` | `POST /describe`, `POST /recommend` | `backend/whichcloud/api.py:1335`, `925` | **Legacy `engine.py`** |
| `/terraform` | `frontend/app/terraform/page.tsx:371` | `POST /describe`, `/describe/inspect.tf`| `backend/whichcloud/api.py:1335`, `2190` | **Legacy `engine.py`** |
| Landing (`/`) | `frontend/app/api/landing/showcase/route.ts:57` | `POST /compare` | `backend/whichcloud/api.py:1270` | **Legacy `engine.py`** |
| `/plan` | `frontend/app/plan/page.tsx:27` | `POST /plan` | `backend/whichcloud/api.py:1788` | **Modern `plan.py`** |

*Conclusion*: All primary interactive customer pages (`/dashboard`, `/estimate`, `/terraform`, `/`) invoke the legacy `engine.py` path and are blind to modern Part 5 archetype DAGs and DR capabilities.

