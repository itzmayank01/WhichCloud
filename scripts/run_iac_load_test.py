#!/usr/bin/env python3
"""Automated Load Testing Harness for IaC Multi-Environment Deployment.

Meets Course Project Specification:
- Executes load testing across three distinct workload tiers:
    1. Low Workload:    10 concurrent workers  | 150 requests total
    2. Medium Workload: 50 concurrent workers  | 500 requests total
    3. High Workload:   150 concurrent workers | 1500 requests total
- Measures throughput (RPS), min, p50, p90, p95, p99, max latency, and error rate.
- Saves benchmark data to docs/load_test_results.json for the project report.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from whichcloud.api import app

client = TestClient(app)

ENDPOINTS = [
    ("GET", "/api/iac/environments", None, {"X-API-Key": "whichcloud-iac-viewer-key"}),
    ("GET", "/api/iac/environments/dev", None, {"X-API-Key": "whichcloud-iac-viewer-key"}),
    ("GET", "/api/iac/environments/prod", None, {"X-API-Key": "whichcloud-iac-viewer-key"}),
    ("GET", "/api/iac/metrics", None, {"X-API-Key": "whichcloud-iac-viewer-key"}),
    ("GET", "/api/iac/deployments", None, {"X-API-Key": "whichcloud-iac-devops-key"}),
    ("POST", "/api/iac/drift-detection", {"environment_name": "dev", "auto_remediate": False}, {"X-API-Key": "whichcloud-iac-devops-key"}),
]


def _single_request(client_instance: TestClient, client_id: int) -> Tuple[int, float]:
    method, path, body, base_headers = random.choice(ENDPOINTS)
    headers = dict(base_headers)
    # Simulate distributed client IPs across a CIDR pool
    headers["X-Forwarded-For"] = f"198.51.{client_id % 200}.{(client_id * 7) % 250}"

    start_time = time.perf_counter()
    try:
        if method == "GET":
            res = client_instance.get(path, headers=headers)
        else:
            res = client_instance.post(path, json=body, headers=headers)
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return res.status_code, duration_ms
    except Exception:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return 500, duration_ms


def run_benchmark_tier(concurrency: int, total_requests: int) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"  RUNNING LOAD TIER: Concurrency={concurrency} | Total={total_requests}")
    print(f"=======================================================")

    durations: List[float] = []
    status_codes: Dict[int, int] = {}

    start_wall = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_single_request, client, i) for i in range(total_requests)]
        for f in concurrent.futures.as_completed(futures):
            status, dur = f.result()
            durations.append(dur)
            status_codes[status] = status_codes.get(status, 0) + 1

    total_wall_time = time.perf_counter() - start_wall
    durations.sort()

    p50 = durations[int(len(durations) * 0.50)]
    p90 = durations[int(len(durations) * 0.90)]
    p95 = durations[int(len(durations) * 0.95)]
    p99 = durations[int(len(durations) * 0.99)]
    avg_lat = sum(durations) / len(durations)
    throughput = len(durations) / max(total_wall_time, 0.001)

    successful = status_codes.get(200, 0)
    error_rate = ((len(durations) - successful) / len(durations)) * 100.0

    print(f"Completed {total_requests} requests in {total_wall_time:.2f}s")
    print(f"Throughput:       {throughput:.1f} req/sec")
    print(f"Latency Min:      {durations[0]:.2f} ms")
    print(f"Latency Average:  {avg_lat:.2f} ms")
    print(f"Latency p50:      {p50:.2f} ms")
    print(f"Latency p90:      {p90:.2f} ms")
    print(f"Latency p95:      {p95:.2f} ms")
    print(f"Latency p99:      {p99:.2f} ms")
    print(f"Latency Max:      {durations[-1]:.2f} ms")
    print(f"Error Rate:       {error_rate:.2f}% (Status codes: {status_codes})")

    return {
        "concurrency": concurrency,
        "total_requests": total_requests,
        "elapsed_seconds": round(total_wall_time, 3),
        "throughput_rps": round(throughput, 1),
        "latency_min_ms": round(durations[0], 2),
        "latency_avg_ms": round(avg_lat, 2),
        "latency_p50_ms": round(p50, 2),
        "latency_p90_ms": round(p90, 2),
        "latency_p95_ms": round(p95, 2),
        "latency_p99_ms": round(p99, 2),
        "latency_max_ms": round(durations[-1], 2),
        "error_rate_pct": round(error_rate, 2),
        "status_distribution": status_codes,
    }


def main():
    print("=" * 65)
    print("  WHICHCLOUD - IAC MULTI-ENVIRONMENT LOAD TEST SUITE")
    print("  Student: Mayank Thakur (500123412, Sec B3) | Project ID: P74")
    print("=" * 65)

    results = {
        "metadata": {
            "project_id": "P74",
            "project_title": "Infrastructure-as-Code Multi-Environment Deployment",
            "student_name": "Mayank Thakur",
            "sap_id": "500123412",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "tiers": {},
    }

    # 1. Low Workload
    results["tiers"]["low"] = run_benchmark_tier(concurrency=10, total_requests=150)

    # 2. Medium Workload
    results["tiers"]["medium"] = run_benchmark_tier(concurrency=50, total_requests=500)

    # 3. High Workload
    results["tiers"]["high"] = run_benchmark_tier(concurrency=150, total_requests=1500)

    # Save to docs/load_test_results.json
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "load_test_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[OK] Benchmark results successfully saved to: {out_path}")


if __name__ == "__main__":
    main()
