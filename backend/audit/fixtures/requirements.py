"""The six fixtures the audit runs against.

Chosen to be DELIBERATELY DIFFERENT in shape, not in size. If the resolver
derives an architecture from what was described, these six produce six
different role sets. If it emits a template with the sizes adjusted, they
collapse -- and that collapse is the thing Phase 0 exists to detect.

Each carries what it must NOT have, because an architecture audit that only
checks for presence cannot catch a default leaking in. F2 has no user-facing
component at all: an edge cache or a load balancer there is not a debatable
design choice, it is a role nobody asked for.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Fixture:
    id: str
    name: str
    description: str
    #: Roles whose presence would prove a default leaked in, with the reason.
    #: Not a wish list -- each is something the description rules out.
    forbidden: dict[str, str] = field(default_factory=dict)
    #: Roles the workload cannot be built without. Absence is a missing role.
    required: dict[str, str] = field(default_factory=dict)


FIXTURES: tuple[Fixture, ...] = (
    Fixture(
        id="F1",
        name="retail-billing",
        description=(
            "Online stock and billing for a retail chain in India, 40 stores, "
            "300 internal staff, 8,000 transactions/day, must not go down in "
            "business hours."
        ),
        required={
            "compute": "staff use it interactively, so something serves requests",
            "database": "stock and billing records are relational and transactional",
        },
    ),
    Fixture(
        id="F2",
        name="batch-etl",
        description=(
            "Nightly ETL over 2 TB of sales data. No user-facing component. "
            "Results land in a warehouse for analysts."
        ),
        forbidden={
            "edge": "no user-facing component -- there is nothing to cache at an edge",
            "loadbalancer": "nothing serves requests, so there is nothing to balance",
            "waf": "no public surface to protect",
        },
        required={
            "warehouse": "the description names a warehouse as the destination",
            "storage": "2 TB of sales data lands somewhere before it is transformed",
        },
    ),
    Fixture(
        id="F3",
        name="content-site",
        description=(
            "Product catalogue site, 5M page views a month, almost no writes, "
            "visitors across India."
        ),
        required={
            "edge": "5M public page views of near-static content is the CDN case",
        },
    ),
    Fixture(
        id="F4",
        name="event-driven",
        description=(
            "Process uploaded documents: extract text, classify, notify the "
            "uploader. Bursty, up to 2,000 documents an hour."
        ),
        required={
            "storage": "uploaded documents have to land somewhere",
        },
        forbidden={
            "loadbalancer": "bursty document processing is queue-driven, not "
            "a request-serving fleet behind a balancer",
        },
    ),
    Fixture(
        id="F5",
        name="internal-crud",
        description=(
            "Internal HR tool for 80 employees. Leave requests and payroll "
            "records. Office hours only."
        ),
        forbidden={
            "edge": "80 internal employees is not a CDN workload",
            "waf": "an internal tool behind the corporate boundary",
        },
        required={
            "database": "leave requests and payroll records are relational",
        },
    ),
    Fixture(
        id="F6",
        name="realtime-api",
        description=(
            "Public API serving 3,000 requests/second, p99 under 100ms, "
            "read-heavy with a small key-value store."
        ),
        required={
            "loadbalancer": "3,000 rps across a fleet has to be distributed",
        },
        forbidden={
            "database": "the description says key-value, not relational",
        },
    ),
)
