"""Phase 1 regression tests: stale-result prevention and cache-key isolation.

Verifies that submitting two different workloads (or different provider /
environment / tier combinations) always produces distinct cache keys, distinct
architectures, distinct monthly totals, distinct Terraform output, and
`Cache-Control: no-store` response headers.
"""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from whichcloud.api import app, build_workload_cache_key


WORKLOAD_A = (
    "I manage IT for a 3-hospital group in Pune. We want to move patient "
    "appointments, records and lab reports online so doctors and front desk "
    "can access them from all three sites. About 450 staff use it, roughly "
    "6,000 record lookups a day, with peaks in the morning. Patient data must "
    "stay inside India and cannot be lost. Downtime during OPD hours is "
    "unacceptable. Budget is about $900 a month."
)

WORKLOAD_B = (
    "Marketing site for our design studio. About 30,000 visitors a month, "
    "mostly from India. It's just pages and images, no login, no database. "
    "We want it cheap."
)


def test_workload_cache_key_includes_all_dimensions():
    k_base = build_workload_cache_key(WORKLOAD_A, provider="aws", environment="dev", option="Most optimized")
    k_ws = build_workload_cache_key(f"  {WORKLOAD_A}   ", provider="aws", environment="dev", option="Most optimized")
    assert k_base == k_ws, "whitespace normalization should preserve cache hit"

    assert k_base != build_workload_cache_key(WORKLOAD_B, provider="aws", environment="dev", option="Most optimized")
    assert k_base != build_workload_cache_key(WORKLOAD_A, provider="gcp", environment="dev", option="Most optimized")
    assert k_base != build_workload_cache_key(WORKLOAD_A, provider="aws", environment="prod", option="Most optimized")
    assert k_base != build_workload_cache_key(WORKLOAD_A, provider="aws", environment="dev", option="Cheapest")
    assert k_base != build_workload_cache_key(
        WORKLOAD_A, provider="aws", environment="dev", option="Most optimized", schema_version="v99"
    )


def test_two_different_workloads_produce_different_describe_and_terraform():
    client = TestClient(app)

    r_desc_a = client.post("/describe", json={"description": WORKLOAD_A, "provider": "aws"})
    r_desc_b = client.post("/describe", json={"description": WORKLOAD_B, "provider": "aws"})
    assert r_desc_a.status_code == 200, r_desc_a.text
    assert r_desc_b.status_code == 200, r_desc_b.text
    assert r_desc_a.headers.get("cache-control") == "no-store"
    assert r_desc_b.headers.get("cache-control") == "no-store"

    desc_a = r_desc_a.json()
    desc_b = r_desc_b.json()
    assert desc_a["options"][-1]["monthly_usd"] != desc_b["options"][-1]["monthly_usd"]

    r_tf_a = client.post(
        "/describe/terraform/inspect",
        json={"description": WORKLOAD_A, "option": "Most optimized", "provider": "aws", "environment": "dev"},
    )
    r_tf_b = client.post(
        "/describe/terraform/inspect",
        json={"description": WORKLOAD_B, "option": "Most optimized", "provider": "aws", "environment": "dev"},
    )
    assert r_tf_a.status_code == 200, r_tf_a.text
    assert r_tf_b.status_code == 200, r_tf_b.text
    assert r_tf_a.headers.get("cache-control") == "no-store"
    assert r_tf_b.headers.get("cache-control") == "no-store"

    tf_a = r_tf_a.json()
    tf_b = r_tf_b.json()
    assert tf_a["cache_key"] != tf_b["cache_key"]
    assert tf_a["monthly_cost"] != tf_b["monthly_cost"]
    assert tf_a["files"]["main.tf"] != tf_b["files"]["main.tf"]


def test_export_zip_differs_between_workloads():
    client = TestClient(app)

    z_a = client.post(
        "/describe/export.tf",
        json={"description": WORKLOAD_A, "option": "Most optimized", "provider": "aws", "environment": "dev"},
    )
    z_b = client.post(
        "/describe/export.tf",
        json={"description": WORKLOAD_B, "option": "Most optimized", "provider": "aws", "environment": "dev"},
    )
    assert z_a.status_code == 200
    assert z_b.status_code == 200
    assert z_a.headers.get("cache-control") == "no-store"

    with zipfile.ZipFile(io.BytesIO(z_a.content)) as za, zipfile.ZipFile(io.BytesIO(z_b.content)) as zb:
        assert za.read("main.tf") != zb.read("main.tf")
