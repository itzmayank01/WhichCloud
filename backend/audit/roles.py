"""A canonical role vocabulary, and the map from our node kinds onto it.

Vendor references name SERVICES; we emit node KINDS. Neither can be compared
to the other directly, so both are projected onto one vocabulary of roles --
what a thing is FOR, independent of who sells it. "Application Gateway",
"Cloud Load Balancing" and "ALB" are one role; App Service and EC2 are one
role; DynamoDB and Firestore and Cosmos DB are one role.

Getting this map wrong invents defects, so it is written once, here, rather
than inline in each scorer.
"""

from __future__ import annotations

#: node kind -> canonical role. Kinds absent from this map score as unknown
#: rather than silently as nothing, which is how a new kind would otherwise
#: slip past the audit.
KIND_TO_ROLE: dict[str, str] = {
    "client": "_client",
    "dns": "dns",
    "tls": "tls",
    "edge": "edge-cache",
    "cdn": "edge-cache",
    "waf": "waf",
    "loadbalancer": "ingress-lb",
    # NOT ingress-lb. A load balancer distributes across a fleet of instances
    # you are paying to keep running; an API gateway routes to functions that
    # do not exist between calls. Collapsing them meant a serverless pipeline
    # scored for having "a load balancer" it does not have and could not
    # remove -- the forbidden rule was about a fleet behind a balancer, and
    # this is neither.
    "apigateway": "api-frontdoor",
    "compute": "app-compute",
    "compute_fargate": "container-compute",
    "lambda": "function-compute",
    "database": "relational-db",
    "database_replica": "read-replica",
    "dynamodb": "keyvalue-db",
    "timestream": "timeseries-db",
    "cache": "cache",
    "storage": "object-store",
    "backup": "backup",
    "warehouse": "warehouse",
    "athena": "query-engine",
    "glue": "etl",
    "search": "search",
    "queue": "queue",
    "streaming": "stream",
    "kafka": "stream",
    "firehose": "stream",
    "iot": "device-gateway",
    "email": "email",
    "notification": "notification",
    "nat": "nat-egress",
    "network": "network",
    "auth": "identity",
    "kms": "keys",
    "secrets": "secrets",
    "monitoring": "observability",
    "tracing": "observability",
    "audit": "audit",
    "threat": "security-ops",
    "posture": "security-ops",
    "flowlogs": "security-ops",
    "rekognition": "ai-vision",
    "comprehend": "ai-language",
}

#: Roles that appear on every well-architected design by POLICY, not because
#: the workload asked for them. Scored separately: their presence is never a
#: defect and their absence never a missing role, so leaving them in would
#: flatter every score by the same amount and measure nothing.
BASELINE = frozenset(
    {
        "_client", "dns", "tls", "identity", "keys", "secrets",
        "observability", "audit", "security-ops", "backup", "network",
    }
)


def roles_of(kinds) -> set[str]:
    """Canonical roles for a set of node kinds, baseline excluded."""
    return {KIND_TO_ROLE.get(k, f"?{k}") for k in kinds} - BASELINE


def unknown(kinds) -> set[str]:
    """Kinds with no canonical role. A new kind must be mapped, not ignored."""
    return {k for k in kinds if k not in KIND_TO_ROLE}


#: Roles that FULFIL another role, so its absence is not a gap.
#:
#: A reference architecture names one way of doing something; a different way
#: that serves the same purpose is not a missing role. Amazon's own big-data
#: guidance offers S3 + Glue + Athena and Redshift as alternatives for the
#: same analyst, and BigQuery is not a "query engine INSTEAD of" a warehouse
#: -- it is Google's warehouse, which happens to have no nodes to provision.
#:
#: Kept SMALL and one-directional. Every entry is a place the audit agrees to
#: accept a substitute, so a long list is a scorer that has stopped scoring.
#: A substitution that is merely CHEAPER, not equivalent, does not belong
#: here -- that is the finding, not the exemption.
SATISFIES: dict[str, frozenset[str]] = {
    # Serverless SQL over a lake is how all three clouds sell a warehouse to
    # analysts who do not want a cluster running overnight.
    "warehouse": frozenset({"query-engine"}),
    # A managed key-value store and a relational one are NOT interchangeable,
    # and neither substitutes for the other. Deliberately absent.
}


def satisfied(role: str, present: set[str]) -> bool:
    """Is this role delivered, by itself or by an accepted equivalent?"""
    return role in present or bool(SATISFIES.get(role, frozenset()) & present)
