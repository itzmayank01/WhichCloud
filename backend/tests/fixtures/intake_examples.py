"""Hand-written descriptions paired with the requirement they should produce.

These serve two purposes at once, which is why they were written before the
adapter was wired to a live model:

  1. Test fixtures — the mapping, validation, and engine paths are exercised
     against them without spending a single API call.
  2. An evaluation set — `scripts/eval_intake.py` feeds each description to
     Claude and scores the extraction field by field.

`expected` lists only the fields the description genuinely determines. A field
left out is one a reasonable reader could not infer, so scoring it would
measure agreement with the author's guess rather than correctness.
"""

from __future__ import annotations

EXAMPLES: list[dict] = [
    {
        "id": "ecommerce-spiky",
        "description": (
            "An e-commerce site for about 50,000 monthly users. Traffic spikes "
            "hard during weekend sales. Budget is around $400/month and the "
            "data has to stay in India."
        ),
        "expected": {
            "workload_type": "web",
            "traffic_pattern": "spiky",
            "traffic_scale": "medium",
            "budget_monthly_usd": 400.0,
            "region": "india",
            "interruptible": False,
        },
    },
    {
        "id": "ml-batch-nightly",
        "description": (
            "A nightly machine learning training pipeline. It processes the "
            "day's data and can be restarted from a checkpoint if it fails. "
            "Nobody is waiting on it in real time."
        ),
        "expected": {
            "workload_type": "ml",
            "interruptible": True,
            "high_availability": False,
        },
    },
    {
        "id": "internal-dashboard",
        "description": (
            "An internal analytics dashboard for our 40-person company. "
            "People check it during business hours. Nothing fancy."
        ),
        "expected": {
            "workload_type": "web",
            "traffic_scale": "low",
            "interruptible": False,
        },
    },
    {
        "id": "video-egress-heavy",
        "description": (
            "A video sharing platform. Users upload clips and we serve about "
            "8 TB of video every month. We store roughly 2 TB of footage."
        ),
        "expected": {
            "workload_type": "web",
            "egress_gb": 8000.0,
            "storage_gb": 2000.0,
        },
    },
    {
        "id": "rest-api-steady",
        "description": (
            "A REST API backing our mobile app. Around 10,000 daily active "
            "users, fairly constant load through the day. We're already on AWS."
        ),
        "expected": {
            "workload_type": "api",
            "traffic_pattern": "steady",
            "provider_preference": "aws",
        },
    },
    {
        "id": "healthcare-ha",
        "description": (
            "A patient records system for a hospital network. It must not go "
            "down — clinicians rely on it during procedures. HIPAA applies."
        ),
        "expected": {
            "workload_type": "web",
            "high_availability": True,
            "interruptible": False,
            "compliance": ["HIPAA"],
        },
    },
    {
        "id": "legacy-x86",
        "description": (
            "A Java application that depends on a vendor library only "
            "available as an x86 binary. Moderate steady traffic, hosted in "
            "Europe."
        ),
        "expected": {
            "arm_compatible": False,
            "traffic_pattern": "steady",
            "region": "eu-west",
        },
    },
    {
        "id": "queue-workers",
        "description": (
            "Background workers that pull jobs off a queue and resize images. "
            "If a worker dies mid-job the job goes back on the queue."
        ),
        "expected": {
            "workload_type": "batch",
            "interruptible": True,
        },
    },
    {
        "id": "flash-sale-launch",
        "description": (
            "A ticketing site. Almost no traffic most of the time, then "
            "200,000 people hit it at once the minute tickets go on sale."
        ),
        "expected": {
            "workload_type": "web",
            "traffic_pattern": "spiky",
            "traffic_scale": "high",
            "high_availability": True,
        },
    },
    {
        "id": "static-storage",
        "description": (
            "A document archive. We keep about 500 GB of PDFs and people "
            "download maybe 50 GB a month. Very little compute needed."
        ),
        "expected": {
            "workload_type": "storage",
            "storage_gb": 500.0,
            "egress_gb": 50.0,
            "traffic_scale": "low",
        },
    },
]


def example(example_id: str) -> dict:
    for item in EXAMPLES:
        if item["id"] == example_id:
            return item
    raise KeyError(f"no intake example named {example_id!r}")
