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
    "waf": "waf",
    "loadbalancer": "ingress-lb",
    "apigateway": "ingress-lb",
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
