# WhichCloud Problem Audit (Phase 1)

Date: 2026-11-16
Status: Phase 1 Complete (Read-Only Audit)

---

## 1. Line Item Sum vs. Tier Total Audit (10 Prompts)

Every prompt was evaluated on both execution paths: the **Recommend Path** (`POST /api/recommend` via `recommend()`) and the **Plan Path** (`POST /api/plan` via `plan.build()`).

### Results Summary
- **Recommend Path:** In all 10 prompts, `abs(option.monthly - sum(item.monthly_usd)) == 0.0000`. There are **no hidden or unlisted charges**; the unrounded total is an exact sum of its line items. However, when individual line items are rounded to 2 decimal places for UI display, floating-point penny discrepancies ($0.01 - $0.02) appear on tiers with many items (e.g., `web_1` Most optimized has rounded total $1,362.63 vs. rounded component sum $1,362.65).
- **Plan Path:** Prompts 1 through 9 have exact mathematical parity (`diff == 0.0000`). Prompt 10 (`ml_2`) was safely withheld by `quantity_audit.py` with `withheld_reason: Your description states a quantity we could not read into the plan ('100,000 customer')` to avoid silently dropping sizing constraints.
- **Topology Graph Parity:** `graph.total_monthly` and `sum(n.monthly_usd for n in graph.nodes if n.priced)` match `tier.estimate.total_monthly` across all evaluated tiers.

### Detailed Breakdown

| Prompt ID | Recommend Path (Cheapest / Reliable / Optimized) | Line Item Parity | Plan Path (Tier 1 / Tier 2 / Tier 3) | Line Item Parity | Notes / Discrepancies |
| :--- | :--- | :---: | :--- | :---: | :--- |
| **web_1** | $199.93 / $437.43 / $1,362.63 | EXACT | $90.95 / $127.97 / $127.97 | EXACT | Plan Tier 2 and Tier 3 have identical totals ($127.97). Recommend has $0.02 penny sum variance in Tier 3. |
| **web_2** | $205.79 / $443.30 / $873.44 | EXACT | $848.81 / $885.83 / $885.83 | EXACT | Plan Tier 2 and Tier 3 have identical totals ($885.83). Recommend has $0.02 penny sum variance in Tier 3. |
| **static_1** | $69.50 / $119.68 / $208.96 | EXACT | $3.90 / $13.09 / $13.75 | EXACT | Recommend path misclassifies static site and prices EC2 VM. Plan path prices serverless CDN/S3 properly ($3.90). |
| **static_2** | $145.51 / $284.86 / $504.87 | EXACT | $3.92 / $16.79 / $17.45 | EXACT | Recommend path forces an RDS relational database. Plan path prices static hosting properly. |
| **batch_1** | $98.23 / $208.21 / $1,866.40 | EXACT | $694.53 / $722.79 / $1,758.08 | EXACT | Exact line sum. |
| **batch_2** | $45.33 / $150.33 / $778.13 | EXACT | $146.74 / $149.17 / $861.67 | EXACT | Exact line sum. |
| **iot_1** | $85.43 / $212.35 / $1,292.06 | EXACT | $285,617.37 / $301,183.53 / $321,399.83 | EXACT | In Plan path, high throughput (10,000 devices / 10s = 86.4M msgs/day) correctly scales streaming shard costs. |
| **iot_2** | $145.51 / $284.86 / $504.87 | EXACT | $39.61 / $43.11 / $71.44 | EXACT | Recommend forces EC2/RDS. Plan path correctly prices SQS queue + worker tasks. |
| **ml_1** | $1,269.74 / $1,357.74 / $1,493.94 | EXACT | $159.51 / $1,147.92 / $1,341.32 | EXACT | Exact line sum. |
| **ml_2** | $518.18 / $605.78 / $726.38 | EXACT | WITHHELD (Safety Guard) | N/A | Plan path refused to price because `'100,000 customer'` quantity was unread by `batch_etl` sizing formula. |

---

## 2. Kafka Line Investigation & Forensic Explanation

### Exact Mechanism & Functions
- **Calling function:** `backend/whichcloud/estimator.py:1784`
- **Underlying function:** `_self_managed_line()` (`backend/whichcloud/estimator.py:751`)
- **Lookup function:** `store.cheapest_compute_like()` (`backend/whichcloud/pricing/store.py:506`)
- **Hourly conversion:** `_hourly_line()` (`backend/whichcloud/estimator.py:736`)

### Inputs & Parameters
- `label`: `"Kafka brokers (self-managed)"`
- `provider`: `"aws"`, `region`: `"ap-south-1"`
- `vcpu`: `spec.kafka_broker_vcpu or 2` (defaults to 2)
- `memory_gb`: `spec.kafka_broker_memory_gb or 0.0` (defaults to 0.0)
- `count`: `spec.kafka_broker_count` (set to `KAFKA_MIN_BROKERS = 3` in `backend/whichcloud/engine.py:203`)

### Price Calculation
1. **With PostgreSQL Live Database:**
   - Query: `SELECT * FROM price_points WHERE provider='aws' AND region='ap-south-1' AND category='compute' AND (vcpu IS NULL OR vcpu >= 2) AND memory_gb >= 0.0 ORDER BY price_usd ASC LIMIT 1`
   - Result: Matches `t4g.nano` (2 vCPU, 0.5 GB RAM) at **$0.0042/hr**.
   - Hours: `3 brokers * 730 hours = 2,190 hours`.
   - Total Monthly: `2,190 * $0.0042 = $9.198` (**$9.20/mo**).
   - Label produced: `"Kafka brokers (self-managed) × 3"`
   - Bug: Running Kafka on `t4g.nano` with 0.5 GB RAM is impossible; memory floor defaulted to `0.0`.
2. **With Offline Fallback Table (`_FALLBACK_POINTS`):**
   - Matches: `t4g.medium` (2 vCPU, 4.0 GB RAM) at **$0.0336/hr** (`backend/whichcloud/pricing/store.py:36`).
   - 1 instance cost: `730 * $0.0336 = $24.528/mo` (**$24.53/mo**).
   - 3 instances cost: `2,190 * $0.0336 = $73.584/mo` (**$73.58/mo**).

### Does any current output still show "Kafka brokers x3" and what does it cost?
- In `recommend()` (legacy engine with heuristic draft for Prompt 7): Most optimized tier currently generates:
  `"Kafka brokers (self-managed) × 3"` with SKU `t4g.nano`, costing **$9.20/mo**.
- In `frontend/lib/fixtureTopologies.json:3593`: Fixture snapshot shows `"label": "Kafka brokers", "monthly_usd": 319.302, "sku": "kafka.m7g.large"`.
- The "$24.53 for 3 brokers" figure in Phase 0 was a transcription bug in the audit report where 1 single instance of `t4g.medium` ($24.53) was reported alongside the "× 3" label instead of multiplying by 3 ($73.58).

---

## 3. Frontend Page-to-API Mapping & Legacy Path Reach

### Page Routing Table

| Frontend Page File | Route | Primary API Endpoint Called | Backend Handler | Workload System | Status |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `frontend/app/page.tsx` | `/` | `POST /compare` (via `/api/landing/*`) | `api.py:1270` | **LEGACY `workload_type`** | Reaches legacy `recommend_across_clouds()` |
| `frontend/app/prices/page.tsx` | `/prices` | `GET /catalog` | `api.py:1150` | N/A (Catalog) | Reads price points directly |
| `frontend/app/estimate/page.tsx` | `/estimate` | `POST /describe` or `POST /recommend` | `api.py:1335`, `925` | **LEGACY `workload_type`** | Reaches legacy `recommend()` |
| `frontend/app/plan/page.tsx` | `/plan` | `POST /plan` | `api.py:1788` | **MODERN `archetype`** | Uses `whichcloud.plan.build()` |
| `frontend/app/terraform/page.tsx` | `/terraform` | `POST /describe`, `/describe/inspect.tf` | `api.py:1335`, `2190` | **LEGACY `workload_type`** | Reaches legacy `recommend()` |
| `frontend/app/environments/page.tsx` | `/environments` | `GET /api/iac/*` | `iac_multi_env.py` | Standalone IaC | Academic multi-env engine |
| `frontend/app/audit/page.tsx` | `/audit` | `POST /audit` | `api.py:1700` | Standalone Audit | Billing export analyzer |
| `frontend/app/finops/page.tsx` | `/finops` | `GET /api/finops/*` | `api.py:3135` | Standalone FinOps | AWS Live Planning / CUR |
| `frontend/app/dashboard/page.tsx` | `/dashboard` | `POST /describe` (via `WorkspaceView`) | `api.py:1335` | **LEGACY `workload_type`** | Reaches legacy `recommend()` |
| `frontend/app/diagram-lab/page.tsx` | `/diagram-lab` | None (reads `fixtureTopologies.json`) | N/A | Static Fixture | Renderer testing tool |
| `frontend/app/connect/*` | `/connect` | `GET/POST /api/connections/*` | `api.py:2700` | Standalone Connect | Credential validators |

### Key Architectural Discovery
**Four major user-facing entry points still reach the legacy `workload_type` path**:
1. `frontend/app/page.tsx` (Landing Page multi-cloud showcase)
2. `frontend/components/estimate/EstimateWorkbench.tsx:140` (`/estimate` interactive workbench)
3. `frontend/app/terraform/page.tsx:371` (`/terraform` IaC Studio editor)
4. `frontend/components/workspace/WorkspaceView.tsx:249` (`/dashboard` authenticated workspace)

Only `frontend/app/plan/page.tsx` connects to the modern `plan.py` (`/plan`) reasoning engine.

---

## 4. Coaching-Platform Fixture Failure Explanation

### Root Cause
- **Failing Tests:**
  - `backend/tests/test_archetype.py:736` (`test_cost_drivers_are_ranked_by_dollar_swing`)
  - `backend/tests/test_archetype.py:748` (`test_the_total_is_reported_as_a_range`)
  - `backend/tests/test_archetype.py:756` (`test_the_dominant_driver_is_surfaced_as_a_question`)
- **The Code:** In `backend/tests/test_archetype.py:731`:
  ```python
  fx = yaml.safe_load(pathlib.Path(f"tests/fixtures/{fid}.yaml").read_text())
  ```
- **Why it failed in Pytest:**
  Pytest is executed from the repository root (`/Users/mayankthakur/Desktop/WhichCloud`). A relative path of `tests/fixtures/coaching-platform.yaml` looks for `<repo_root>/tests/fixtures/...`, which does not exist (`FileNotFoundError`).
- **Why the Regression Harness passed:**
  In `backend/tests/run_harness.py:41`, the harness resolves fixture paths relative to the script's directory:
  ```python
  FIXTURES_DIR = Path(__file__).parent / "fixtures"
  ```
  This resolves to `/Users/mayankthakur/Desktop/WhichCloud/backend/tests/fixtures/coaching-platform.yaml`, which exists and has 164 passing assertions.
- **Verification:** Changing working directory to `backend/` makes `test_archetype.py` pass immediately (1 passed in 0.36s).

---

## 5. Evaluation of the 13 Failing Pytest Tests

| # | Failing Test | Root Cause Classification | Root Cause & File | Proposed Fix | Effort |
| :- | :--- | :---: | :--- | :--- | :-: |
| 1 | `test_archetype.py::test_cost_drivers_are_ranked_by_dollar_swing` | **Env / Test Path Bug** | Hardcoded relative path in `test_archetype.py:731` | Use `Path(__file__).parent / "fixtures" / ...` | **S** |
| 2 | `test_archetype.py::test_the_total_is_reported_as_a_range` | **Env / Test Path Bug** | Hardcoded relative path in `test_archetype.py:731` | Use `Path(__file__).parent / "fixtures" / ...` | **S** |
| 3 | `test_archetype.py::test_the_dominant_driver_is_surfaced_as_a_question` | **Env / Test Path Bug** | Hardcoded relative path in `test_archetype.py:731` | Use `Path(__file__).parent / "fixtures" / ...` | **S** |
| 4 | `test_intake.py::test_refusal_is_surfaced_not_swallowed` | **Real Engine Bug** | Blanket `try...except Exception` in `intake.py:1118` catches and swallows refusals | Propagate `IntakeError` when `client` is injected or failover is exhausted | **S** |
| 5 | `test_intake.py::test_missing_structured_output_is_an_error` | **Real Engine Bug** | Blanket `try...except Exception` in `intake.py:1118` swallows `IntakeError` | Propagate `IntakeError` when output is missing | **S** |
| 6 | `test_intake.py::test_api_failure_becomes_intake_error` | **Real Engine Bug** | Blanket `try...except Exception` in `intake.py:1118` swallows connection errors | Propagate `IntakeError` when `client` fails | **S** |
| 7 | `test_intake.py::test_no_credentials_names_both_options` | **Real Engine Bug** | Blanket fallback in `intake.py:1094-1098` hides missing API keys | Raise `IntakeError` naming missing keys if no provider detected | **S** |
| 8 | `test_intake.py::test_unknown_provider_is_rejected` | **Real Engine Bug** | `intake.py:1097` quietly runs `_fast_heuristic_draft` on unknown providers | Raise `IntakeError("Unknown provider")` | **S** |
| 9 | `test_intake.py::test_gemini_failure_becomes_intake_error` | **Real Engine Bug** | Blanket `try...except Exception` in `intake.py:1118` swallows Gemini errors | Propagate `IntakeError` on Gemini client failure | **S** |
| 10 | `test_intake.py::test_gemini_missing_structured_output_is_an_error` | **Real Engine Bug** | Blanket `try...except Exception` in `intake.py:1118` swallows Gemini structured output errors | Propagate `IntakeError` when structured output is None | **S** |
| 11 | `test_intake_providers.py::test_unknown_reader_is_refused_by_name` | **Real Engine Bug** | `intake.py:1097` quietly runs heuristic on invalid provider name | Raise `IntakeError` naming invalid provider and valid options | **S** |
| 12 | `test_no_hardcoded_rates.py::test_no_decimal_price_literals_in_the_cost_path` | **Policy / Design Bug** | 70+ hardcoded `Decimal` points in `store.py:33-105` violate AST rate rule | Move `_FALLBACK_POINTS` to external JSON seed file or whitelist `store.py` fallback | **S** |
| 13 | `test_price_cache.py::test_an_absent_sku_is_cached_as_absent` | **Real Catalog Bug** | `store.py:166` falls back to random category SKU when requested SKU is absent | Return `None` for specific absent SKUs in `_find_fallback_price` | **S** |

---

## 6. Comprehensive Problem Register (Ranked by Severity & Effort)

### BLOCKER

#### P1-B1: Blanket Exception Swallowing in `parse_description` Suppresses Failures
* **File:** `backend/whichcloud/intake.py:1091-1120`
* **Reason:** A blanket `try...except Exception` catches all API errors, client refusals, missing credentials, and unknown providers, silently returning a heuristic draft. This breaks 8 test cases in `test_intake.py` and `test_intake_providers.py` and prevents errors from being surfaced to callers.
* **Verification Proof:** Command `./backend/.venv/bin/pytest backend/tests/test_intake.py -k "test_refusal_is_surfaced_not_swallowed"` outputs `Failed: DID NOT RAISE IntakeError`.
* **Fix:** When `client` is provided or provider is explicitly requested or when `_detect_provider()` finds no keys, raise `IntakeError`.
* **Effort:** **S**

#### P1-B2: Missing SKU Cache Sentinel Corrupted by Category Fallback
* **File:** `backend/whichcloud/pricing/store.py:166, 396`
* **Reason:** When `get_price()` looks up an absent SKU (e.g., `s3:no-such-class`), `_find_fallback_price()` falls back to `_find_fallback_category()`, returning a real SKU (`s3:ia`). The negative sentinel `_CACHED_ABSENT` is never stored, and nonexistent SKUs are quoted real prices.
* **Verification Proof:** Command `./backend/.venv/bin/pytest backend/tests/test_price_cache.py -k "test_an_absent_sku_is_cached_as_absent"` outputs `AssertionError: assert PricePoint(sku='s3:ia') is None`.
* **Fix:** In `_find_fallback_price()`, return `None` when a specific SKU does not match any fallback item.
* **Effort:** **S**

#### P1-B3: Hardcoded Relative Fixture Path in `test_archetype.py`
* **File:** `backend/tests/test_archetype.py:731`
* **Reason:** `_fixture_plan()` hardcodes `pathlib.Path("tests/fixtures/coaching-platform.yaml")`, which fails with `FileNotFoundError` whenever pytest is executed from the repository root.
* **Verification Proof:** Command `./backend/.venv/bin/pytest backend/tests/test_archetype.py -k "test_cost_drivers_are_ranked_by_dollar_swing"` outputs `FileNotFoundError: [Errno 2] No such file or directory: 'tests/fixtures/coaching-platform.yaml'`.
* **Fix:** Change to `pathlib.Path(__file__).parent / "fixtures" / f"{fid}.yaml"`.
* **Effort:** **S**

#### P1-B4: Hardcoded `Decimal` Price Constants in `store.py` Violate AST Policy
* **File:** `backend/whichcloud/pricing/store.py:33-105`
* **Reason:** `_FALLBACK_POINTS` contains 70+ hardcoded `Decimal` prices in source code, violating the architectural rule that all prices come from catalog data.
* **Verification Proof:** Command `./backend/.venv/bin/pytest backend/tests/test_no_hardcoded_rates.py` outputs `AssertionError: these look like rates written in code rather than read from the price catalog: ['pricing/store.py:33 Decimal(0.0042)', ...]`.
* **Fix:** Relocate `_FALLBACK_POINTS` into an external JSON seed file (`backend/whichcloud/pricing/seed_catalog.json`) loaded dynamically.
* **Effort:** **S**

#### P1-B5: Primary Frontend Surfaces Bypass Modern Archetype Planner
* **File:** `frontend/app/terraform/page.tsx:371`, `frontend/components/estimate/EstimateWorkbench.tsx:140`, `frontend/components/workspace/WorkspaceView.tsx:249`
* **Reason:** `/terraform`, `/estimate`, and `/dashboard` call `/describe` and `/recommend` (the legacy `workload_type` engine) rather than `/plan` (the modern Part 5 archetype engine). Users describing static sites, batch processing, or ML models on these pages receive inaccurate VM-and-RDS architectures.
* **Verification Proof:** Inspected `frontend/app/terraform/page.tsx:371` calling `api.describe()`, which routes to `engine.py:recommend()`.
* **Fix:** Migrate `/terraform` and `WorkspaceView` to consume `/plan` or route `/describe` through `plan.build()`.
* **Effort:** **M**

---

### HIGH

#### P1-H1: Heuristic Intake Parser Misclassifies Web & Static Sites as ML
* **File:** `backend/whichcloud/intake.py:927-940`
* **Reason:** Naive substring matching assigns `workload_type="ml"` to standard e-commerce and portfolio descriptions when terms like "store", "model", or "ml" match substrings without word boundaries.
* **Fix:** Use word-bounded regular expressions `\bml\b` and prioritize web/storefront tokens.
* **Effort:** **S**

#### P1-H2: Kafka Compute Sizing Undercharges on Memory in PostgreSQL Lookup
* **File:** `backend/whichcloud/estimator.py:1788-1790`, `backend/whichcloud/pricing/store.py:530`
* **Reason:** `estimator.py` passes `memory_gb=0.0` when sizing self-managed Kafka. Postgres matches `t4g.nano` (0.5GB RAM) at $0.0042/hr ($9.20/mo total), creating an unrealistic configuration that cannot boot a JVM broker.
* **Fix:** Default minimum broker memory floor to `4.0` or `8.0` GB.
* **Effort:** **S**

#### P1-H3: Windows Server Migration Recommends Incompatible AWS Graviton ARM Compute
* **File:** `backend/whichcloud/engine.py:1000-1050`
* **Reason:** Optimization engine applies `graviton-arm-compute` across all tiers for Windows workloads, even though Windows EC2 cannot run on Graviton processors.
* **Fix:** Add operating system compatibility check (`requirement.os != "windows"`) before applying Graviton optimization.
* **Effort:** **S**

#### P1-H4: Plan Architecture Produces Zero Spread for Web Applications
* **File:** `backend/whichcloud/plan.py`
* **Reason:** Prompts `web_1` and `web_2` output identical pricing for Tier 2 and Tier 3 ($127.97 for `web_1`, $885.83 for `web_2`). The top tier adds no architectural differentiation for modest scale.
* **Fix:** Introduce read replica, distributed cache cluster, or multi-region snapshot storage for Tier 3 web architectures.
* **Effort:** **M**

---

### MEDIUM

#### P1-M1: Audit Page Navigation Absent from Application Layout
* **File:** `frontend/components/Header.tsx`, `frontend/components/Footer.tsx`
* **Reason:** Full billing export audit tool exists at `frontend/app/audit/page.tsx` and passes 31 unit tests in `test_billing_audit.py`, but has zero links in the navigation bar or footer.
* **Fix:** Add "Bill Audit" link to Header and Footer navigation menus.
* **Effort:** **S**

#### P1-M2: Line Item Rounding Causes $0.01 - $0.02 Penny Discrepancy on High-Component Tiers
* **File:** `backend/whichcloud/api.py:1814-1835`
* **Reason:** `monthly_total` is rounded to 2 decimal places independently from individual line items. The sum of displayed rounded component figures diverges from the rounded header total by 1-2 cents.
* **Fix:** Reconcile header total by summing rounded components or applying penny correction to the largest component.
* **Effort:** **S**

#### P1-M3: GitHub App Repository "Analyse" Button Hardcoded Disabled
* **File:** `frontend/app/connect/github-app/page.tsx:96`
* **Reason:** OAuth repo listing works, but the "Analyse" button is disabled with "Repository analysis lands in the next phase".
* **Fix:** Wire button to trigger `/api/github/scan` and load results in IaC viewer.
* **Effort:** **M**

#### P1-M4: Azure High Availability Calculated by Flat 2x Multiplier
* **File:** `backend/whichcloud/pricing/azure.py:294`
* **Reason:** High availability pricing doubles the primary instance cost without checking official Azure Flexible Server HA meters.
* **Fix:** Query official Azure HA rate or document formula as an explicit approximation.
* **Effort:** **M**

---

### LOW

#### P1-L1: AWS Spot Price Catalog Lacks Timestamp Attribute
* **File:** `backend/whichcloud/pricing/aws.py:342`
* **Reason:** Crawled spot rates cover 36 regions but omit crawl timestamps.
* **Fix:** Record ingestion timestamp on price point records.
* **Effort:** **S**

#### P1-L2: GCP Pricing Feed Dormant Without API Key
* **File:** `backend/whichcloud/pricing/gcp.py:8`
* **Reason:** Compute rates load via Vantage, but Cloud SQL and Storage require `GOOGLE_CLOUD_API_KEY`.
* **Fix:** Provide offline seed catalog for core GCP services.
* **Effort:** **M**

