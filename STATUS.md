# WhichCloud System Status (Phase 0 Inventory)

Date: 2026-11-16
Status: Phase 0 Complete & Verified (Read-Only Audit)

---

## 1. Repository Map

- `analytics/`: Telemetry logs, experiment tracking, and visual regression capture data.
- `analytics/data/`: JSONL/CSV outputs from benchmark and latency evaluation runs.
- `analytics/screenshots/`: Automated visual captures of rendered UI panels and diagram components.
- `backend/`: FastAPI application, pricing engine, archetype rules, and data ingest adapters.
- `backend/audit/`: Internal engine evaluation framework and sensitivity triage harnesses.
- `backend/scripts/`: Catalog ingest utilities (Vantage, AWS, GCP, Azure, and Cloudflare pricing).
- `backend/tests/`: Pytest suite (823 test cases) covering routing, topology, pricing, and IaC.
- `backend/whichcloud/`: Core application package containing API routes, engine, and estimator.
- `backend/whichcloud/archetypes/`: Workload classification specs (batch, web, realtime, IoT, ML, migration).
- `backend/whichcloud/architecture/`: Graph generation, layout positioning, and plane separation logic.
- `backend/whichcloud/connections/`: Provider credential verification and read-only GitHub Terraform scanners.
- `backend/whichcloud/pricing/`: In-memory pricing cache, PostgreSQL query store, and provider rate adapters.
- `diagrams/`: Architecture diagrams, sequence flows, and Mermaid documentation source files.
- `docs/`: Academic project reports, API documentation, and verification logs.
- `docs/screenshots/`: Captured proof artifacts for project evaluation and test verification.
- `frontend/`: Next.js 16 App Router interface built with React 19 and Tailwind CSS.
- `frontend/app/`: Page routes (`/`, `/prices`, `/estimate`, `/plan`, `/terraform`, `/environments`, `/audit`, `/finops`, `/connect`).
- `frontend/components/`: Reusable UI components, vector logos, priced diagrams, and inspectors.
- `frontend/harness/`: Visual regression test pages and mock data fixtures.
- `frontend/lib/`: API client bindings, formatting utilities, and client-side fallback recommendations.
- `frontend/public/`: Static assets, vendor SVG cloud icons, and documentation graphics.
- `frontend/scripts/`: Build-time validation tools and pre-rendering test scripts.
- `infra/`: Docker compose manifests and local Postgres initialization SQL files.
- `knowledge-base/`: Cross-cloud mapping definitions and optimization techniques.
- `knowledge-base/service-mappings/`: Equivalence definitions across AWS, GCP, and Azure (`core.yaml`).
- `knowledge-base/techniques/`: 25 YAML optimization definitions (Graviton, spot, burstable, lifecycle).
- `scripts/`: Shell automation scripts for testing, local database setup, and benchmarks.
- `terraform/`: Multi-environment Infrastructure as Code baseline modules and tfvars configurations.
- `terraform/environments/`: Parameterized environment root configurations (`dev`, `staging`, `prod`).
- `terraform/modules/`: Reusable infrastructure modules (`vpc`, `compute`, `database`, `monitoring`, `storage_cache`).

---

## 2. Feature Inventory & Capability Status

### Core Recommendation & Pricing Engine
- **Three-Tier Architecture Output (Cheapest, Most reliable, Most optimized):** PARTIAL
  - *Proof:* Web workloads produce 3 distinct tiers (`web_1` produces distinct prices per tier). However, batch and ML inference prompts return identical figures across all three tiers with zero compute cost.
- **Provider Switching (AWS vs GCP vs Azure):** PARTIAL
  - *Proof:* Sizing logic in `backend/whichcloud/engine.py` builds an identical `ArchitectureSpec` regardless of provider. Only prices change; topology nodes and service mappings default to generic stubs. In `frontend/components/ServiceIcon.tsx`, non-AWS providers only have 7 icon mappings; all others render as neutral squares.
- **Natural Language Workload Intake (LLM):** PARTIAL
  - *Proof:* `backend/tests/probes/classifier_accuracy.md` shows 28 of 50 prompts scored before token quota exhausted. Realtime archetype has 0/4 scored. Adversarial probes remain unscored.
- **Heuristic Workload Intake (Fallback / Fast path):** BROKEN
  - *Proof:* Heuristic classifier (`_fast_heuristic_draft` in `backend/whichcloud/intake.py`) classified an e-commerce storefront with MySQL (`web_2`) and a personal portfolio static site (`static_1`) as `workload_type=ml`.
- **Cross-Cloud Service Equivalence Engine:** WORKING
  - *Proof:* Defined in `knowledge-base/service-mappings/core.yaml`. Loaded in `backend/whichcloud/mappings.py:load()` and invoked in `backend/whichcloud/estimator.py:comparable_lines()` for `POST /api/recommend/compare`. Passes `backend/tests/test_mappings.py`.
- **FinOps Optimization Techniques:** WORKING
  - *Proof:* 25 techniques loaded from `knowledge-base/techniques/*.yaml`. `backend/tests/test_techniques.py` passes.
- **Live Catalog Database (PostgreSQL):** WORKING
  - *Proof:* 36,761 catalog rows in `price_points` and 132 in `constraints_cache`. Container `whichcloud-db` verified running.
- **AWS Spot Price Timestamps:** BROKEN / MISSING
  - *Proof:* Documented in `backend/whichcloud/pricing/aws.py:342`: "covers 36 regions including ap-south-1. It carries no timestamp".
- **Azure HA Sizing:** FAKE
  - *Proof:* Documented in `backend/whichcloud/pricing/azure.py:294`: `"derived": "2x primary; Azure bills the HA standby as a second instance"`. Sized by doubling the primary instance without an official meter.
- **GCP Full-Service Catalog:** PARTIAL
  - *Proof:* Documented in `backend/whichcloud/pricing/gcp.py:8`: Compute is read without credentials via Vantage. Cloud SQL, Storage, and Egress require `GOOGLE_CLOUD_API_KEY` and stay dormant without it.

### User-Facing Pages & Interfaces
- **Landing Page (`/`):** WORKING
  - *Proof:* Verified via visual screenshot `docs/screenshots/landing.png`. Multi-cloud preview and hero showcase functional.
- **Price Index UI (`/prices`):** UNVERIFIED
  - *Proof:* Backend API `GET /api/prices` passes in `test_api.py`. Frontend page `frontend/app/prices/page.tsx` exists, but has no automated test and no screenshot in `docs/screenshots/`.
- **Price Your App UI (`/estimate`):** UNVERIFIED
  - *Proof:* Backend API passes `test_api.py`. Frontend page `frontend/app/estimate/page.tsx` exists, but has no automated test and no screenshot in `docs/screenshots/`.
- **Plan Architecture UI (`/plan`):** UNVERIFIED
  - *Proof:* Backend planner passes in `test_plan.py`. Frontend page `frontend/app/plan/page.tsx` exists, but has no automated test and no screenshot in `docs/screenshots/`.
- **Terraform IaC Studio (`/terraform`):** WORKING
  - *Proof:* Verified via screenshot `docs/screenshots/terraform-iac-studio.png` and user session captures. HCL generation and API validation functional.
- **Multi-Environment IaC Dashboard UI (`/environments`):** UNVERIFIED
  - *Proof:* Backend API passes all 10 unit tests in `backend/tests/test_iac_multi_env.py`. Frontend page `frontend/app/environments/page.tsx` exists, but has no automated UI test and no screenshot in `docs/screenshots/`.
- **Bill Audit Upload (`/audit`):** PARTIAL
  - *Proof:* Backend route `@app.post("/audit")` passes all 31 unit tests in `test_billing_audit.py`. Frontend page exists at `frontend/app/audit/page.tsx`. However, there is zero navigation link to `/audit` anywhere in the app header or footer.
- **Connect Cloud Accounts (`/connect`):** PARTIAL
  - *Proof:* Verified via screenshot `docs/screenshots/connect-accounts.png`. AWS metrics functional; GCP and Azure endpoints return 501.
- **GitHub Connect & Terraform Scan (`/connect/github`):** WORKING
  - *Proof:* Implemented in `backend/whichcloud/connections/github.py` and passes `backend/tests/test_github_app.py`.
- **GitHub App Repo Selector (`/connect/github-app`):** PARTIAL
  - *Proof:* Lists user repositories via Clerk OAuth. However, the "Analyse" button in `frontend/app/connect/github-app/page.tsx:96` is hardcoded as `disabled` with "Repository analysis lands in the next phase".
- **On-Premise Cost Comparison:** MISSING
  - *Proof:* Codebase search for "on-premise" returns zero pricing or hardware calculation logic. Feature does not exist in code.
- **User Authentication (`/sign-in`, `/sign-up`):** UNVERIFIED
  - *Proof:* Clerk code configured in `frontend/app/layout.tsx`. No automated UI test and no screenshot in `docs/screenshots/`.

---

## 3. Test Suite & Regression Harness Results

### Pytest Suite (with Live PostgreSQL Container)
Command: `./backend/.venv/bin/pytest backend/tests/ -q`

- **Total Tests:** 824
- **Passed:** 808
- **Failed:** 13
- **Skipped:** 2 (`test_catalog_completeness.py` needs Google API key, `test_rate_limits.py` marker)
- **Deselected:** 1
- **Warnings:** 1

### Remaining 13 Failing Tests
1. `backend/tests/test_archetype.py::test_cost_drivers_are_ranked_by_dollar_swing` (missing fixture `tests/fixtures/coaching-platform.yaml`)
2. `backend/tests/test_archetype.py::test_the_total_is_reported_as_a_range` (missing fixture `tests/fixtures/coaching-platform.yaml`)
3. `backend/tests/test_archetype.py::test_the_dominant_driver_is_surfaced_as_a_question` (missing fixture `tests/fixtures/coaching-platform.yaml`)
4. `backend/tests/test_intake.py::test_refusal_is_surfaced_not_swallowed` (`intake.py` exception handling mismatch)
5. `backend/tests/test_intake.py::test_missing_structured_output_is_an_error`
6. `backend/tests/test_intake.py::test_api_failure_becomes_intake_error`
7. `backend/tests/test_intake.py::test_no_credentials_names_both_options`
8. `backend/tests/test_intake.py::test_unknown_provider_is_rejected`
9. `backend/tests/test_intake.py::test_gemini_failure_becomes_intake_error`
10. `backend/tests/test_intake.py::test_gemini_missing_structured_output_is_an_error`
11. `backend/tests/test_intake_providers.py::test_unknown_reader_is_refused_by_name`
12. `backend/tests/test_no_hardcoded_rates.py::test_no_decimal_price_literals_in_the_cost_path` (70+ hardcoded `Decimal` price points in `store.py:33-105`)
13. `backend/tests/test_price_cache.py::test_an_absent_sku_is_cached_as_absent` (sentinel cache mismatch)

### Regression Sizing Harness
Command: `./backend/.venv/bin/python backend/tests/run_harness.py`

- **Results:**
  - `all 14 fixtures match their baselines (1814 assertions passed, 0 failed)`
  - `thin tier spreads: 0`
  - `divergence between raw and calibrated totals: 0`

---

## 4. 10 Real Prompts Test Output (LLM Path Verification)

All 10 prompts executed via the LLM path (`parse_description` using `provider=groq`), not the heuristic fallback.

1. **Prompt 1 (Web B2B SaaS):**
   - Path: LLM (`provider=groq`)
   - Classified: `workload_type=web`, `serves_requests=True`
   - Cheapest: $199.93/mo (Compute 1-yr $23.65, DB 1-yr reserved $96.43, Storage $0.37, Monitoring $9.00)
2. **Prompt 2 (Web E-commerce):**
   - Path: LLM (`provider=groq`)
   - Classified: `workload_type=web`, `serves_requests=True`
   - Cheapest: $205.79/mo (Compute 1-yr $23.65, DB 1-yr reserved $96.43, Storage $1.83, Monitoring $9.00)
3. **Prompt 3 (Static Site Portfolio):**
   - Path: LLM (`provider=groq`)
   - Classified: `workload_type=ml`, `serves_requests=False`
   - Cheapest: $69.50/mo (Compute $16.35, Storage $0.91, Monitoring $3.00)
   - Issue: Static site misclassified as ML and given a compute VM.
4. **Prompt 4 (Static Site Docs):**
   - Path: LLM (`provider=groq`)
   - Classified: `workload_type=web`, `serves_requests=True`
   - Cheapest: $145.51/mo (Compute 1-yr $11.83, DB 1-yr reserved $48.18, Storage $0.91, Monitoring $9.00)
   - Issue: Forced into a relational database.
5. **Prompt 5 (Batch ETL Nightly Logs):**
   - Path: LLM (`provider=groq`)
   - Classified: `workload_type=batch`, `serves_requests=False`
   - Cheapest: $62.40/mo (Compute spot $12.26, Storage $9.14, Athena queries $25.00, Monitoring $6.00)
6. **Prompt 6 (Batch ETL Payroll):**
   - Path: LLM (`provider=groq`)
   - Classified: `workload_type=batch`, `serves_requests=False`
   - Cheapest: $45.33/mo (Compute spot $3.42, Storage $0.91, Athena queries $25.00, Monitoring $6.00)
7. **Prompt 7 (Event-Driven Fleet IoT):**
   - Path: LLM (`provider=groq`)
   - Classified: `workload_type=web`, `serves_requests=True`
   - Cheapest: $85.43/mo (Storage $0.91, Monitoring $9.00, Lambda requests $0.60, Lambda duration $3.00)
8. **Prompt 8 (Event-Driven Smart Home):**
   - Path: LLM (`provider=groq`)
   - Classified: `workload_type=web`, `serves_requests=True`
   - Cheapest: $145.51/mo (Compute 1-yr $11.83, DB 1-yr reserved $48.18, Storage $0.91, Monitoring $9.00)
9. **Prompt 9 (ML Real-time Vision):**
   - Path: LLM (`provider=groq`)
   - Classified: `workload_type=api`, `serves_requests=True`
   - Cheapest: $1269.74/mo (Storage $0.91, Monitoring $6.00, Lambda $1.20)
10. **Prompt 10 (ML Batch Summarization):**
    - Path: LLM (`provider=groq`)
    - Classified: `workload_type=batch`, `serves_requests=False`
    - Cheapest: $518.18/mo (Storage $0.91, Monitoring $6.00, Queue $0.40, Lambda $0.20)

---

## 5. Architectural & Implementation Clarifications

### Prompt 7 Kafka Costing Investigation ($24.53 for 3 brokers)
- **Mechanism:** In `backend/whichcloud/estimator.py:1784-1794`, AWS has no managed Kafka in the fallback catalog, so it calls `_self_managed_line("Kafka brokers (self-managed)", provider, region, vcpu=2, memory_gb=0, count=spec.kafka_broker_count)`.
- **Underlying SKU:** Under offline `_FALLBACK_POINTS`, `store.cheapest_compute_like(min_vcpu=2)` matched `t4g.medium` at $0.0336/hr.
- **Mathematical Calculation:**
  - 1 instance: `730 hrs * $0.0336 = $24.528/mo` (rounds to $24.53).
  - 3 instances: `2190 hrs * $0.0336 = $73.584/mo` ($73.58).
- **Why it showed $24.53:** In the Cheapest tier, the calculation evaluated 1 single instance ($24.53) while the label or report summarized `Kafka brokers × 3`, or the line charged for 1 node while labelling it "× 3". The line is **INCORRECT** because 3 brokers at $0.0336/hr cost $73.58/mo, not $24.53/mo.

### Usage of `knowledge-base/service-mappings/core.yaml`
- **Is it used?** YES. It is actively loaded and used in code, not just documentation.
- **Where loaded:** `backend/whichcloud/mappings.py:31, 133-146` (`mappings.load()`) reads and parses `knowledge-base/service-mappings/*.yaml` (containing `core.yaml`).
- **Where invoked:**
  - `backend/whichcloud/mappings.py:149-215` provides `by_category()` and `may_compare()`.
  - `backend/whichcloud/estimator.py:2246-2260` (`comparable_lines()`) calls `mappings.by_category()` and `mappings.may_compare()`.
  - `backend/whichcloud/api.py:1283-1313` (`POST /api/recommend/compare`) calls `comparable_lines()` and `mappings.coverage()`.
- **Scope limitation:** It is used strictly for cross-cloud comparison validation (`/api/recommend/compare`) to avoid apples-to-oranges total comparisons; it is not used during single-provider architecture or Terraform generation.

### Workload Types vs Archetypes: Two Divergent Systems
- **System 1: `workload_type`** (`backend/whichcloud/requirements.py:83`)
  - Types: `web`, `api`, `batch`, `ml`, `storage`, `mixed`.
  - Used by: Legacy engine (`engine.py`, `estimator.py`, `knowledge.py`) and basic recommendation route (`POST /api/recommend`).
  - Funnels all architectures into coarse EC2, RDS, and S3 sizing.
- **System 2: `archetype`** (`backend/whichcloud/archetype.py`, `backend/whichcloud/archetypes/`)
  - Archetypes: `web_app`, `static_site`, `batch_etl`, `event_driven`, `ml_inference`, `realtime`, `migration`.
  - Used by: Modern planner (`plan.py`), regression harness (`run_harness.py`), and topology visualizer (`topology.py`).
  - Defines formal component DAGs (`ArchetypeGraph`) with dedicated components (Glue, Athena, Kafka, Flink).
- **Are they two systems?** YES. They are two generations of workload classification developed in parallel. `api.py` dispatches to different systems depending on whether `/api/recommend` or `/api/plan` is called.

---

## 6. Verification Table of Features

| Feature / Subsystem | Status | Proof / Evidence in Repo |
| :--- | :---: | :--- |
| **Web App Architecture Sizing** | **WORKING** | Verified via `test_10_prompts.py` (`web_1` produced valid 3-tier VM/RDS pricing). |
| **Cross-Cloud Service Equivalence** | **WORKING** | Loaded in `mappings.py:133` from `core.yaml`; tested in `test_mappings.py`. |
| **Optimization Techniques** | **WORKING** | 25 YAML definitions loaded in `knowledge-base/techniques/`; tested in `test_techniques.py`. |
| **Billing Export CSV Audit (Backend)** | **WORKING** | Backend route `@app.post("/audit")` passes all 31 unit tests in `test_billing_audit.py`. |
| **Audit Navigation Link** | **MISSING** | `git grep -i 'href="/audit"' frontend/` returned 0 occurrences. |
| **GitHub Repo Terraform Scan** | **WORKING** | Implemented in `connections/github.py` and tested in `test_github_app.py`. |
| **GitHub App One-Click Analysis** | **PARTIAL** | UI button in `frontend/app/connect/github-app/page.tsx:96` is hardcoded as `disabled`. |
| **Static Site Workloads** | **BROKEN** | Prompts `static_1` and `static_2` forced into EC2 VMs and RDS databases. |
| **Batch ETL Workloads** | **BROKEN** | Legacy estimator outputs flat $12.15/mo; modern planner outputs valid DAG. |
| **ML Inference Workloads** | **BROKEN** | Legacy estimator outputs flat $12.15/mo; modern planner outputs valid DAG. |
| **Windows Migration ARM Sizing** | **BROKEN** | Verified: "10 Windows Server VMs" outputs `applied technique: graviton-arm-compute` on all 3 tiers. |
| **Azure High Availability Costing** | **FAKE** | `backend/whichcloud/pricing/azure.py:294` derives HA cost by flat `2x primary` without a real meter. |
| **AWS Spot Feed Timestamp** | **MISSING** | `backend/whichcloud/pricing/aws.py:342` documents that spot feed carries no timestamp. |
| **Offline Rate Decimals in Code** | **BROKEN** | `backend/tests/test_no_hardcoded_rates.py` fails due to 70+ hardcoded `Decimal` points in `store.py:33-105`. |
| **On-Premise Cost Modeling** | **MISSING** | Zero matching models or pricing logic in `backend/whichcloud/`. |
| **Multi-Env IaC Dashboard (Backend)** | **WORKING** | Passes 10/10 unit tests in `backend/tests/test_iac_multi_env.py`. |
| **Landing Page UI (`/`)** | **WORKING** | Verified via screenshot `docs/screenshots/landing.png`. |
| **Terraform IaC Studio UI (`/terraform`)** | **WORKING** | Verified via screenshot `docs/screenshots/terraform-iac-studio.png`. |
| **Connect Accounts UI (`/connect`)** | **PARTIAL** | Verified via screenshot `docs/screenshots/connect-accounts.png`. |
| **Price Index UI (`/prices`)** | **UNVERIFIED** | API is tested, but UI page has no automated test and no screenshot. |
| **Price Your App UI (`/estimate`)** | **UNVERIFIED** | API is tested, but UI page has no automated test and no screenshot. |
| **Plan Architecture UI (`/plan`)** | **UNVERIFIED** | Planner is tested, but UI page has no automated test and no screenshot. |
| **Multi-Env IaC Dashboard UI (`/environments`)** | **UNVERIFIED** | Backend passes 10/10 tests, but UI page has no automated test and no screenshot. |
| **User Authentication (`/sign-in`, `/sign-up`)** | **UNVERIFIED** | Clerk integrated in code, but has no automated test and no screenshot. |
