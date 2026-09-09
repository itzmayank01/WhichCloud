"""Persistent connections rather than discrete requests.

PROBE-5, verbatim:

    "In-app chat for our 100,000 users. Messages must arrive instantly
     and history must be searchable."

Severity CRITICAL, and the coverage map was precise about why: the search
index this workload EXPLICITLY ASKS FOR had a working, tested pricing
path -- 213 OpenSearch rows in the catalog, `search_node_count` on the
spec, an estimator branch for it -- that the decision layer simply never
reached. Meanwhile no WebSocket or connection-billing concept existed
anywhere, so the one figure that describes a chat backend had nowhere to
go. And a Cognito line priced off the stated user count made the wrong
bill look tailored to this specific workload, which is exactly the
condition under which a generic "review before use" note is least likely
to be heeded.

TWO THINGS THIS SHAPE GETS RIGHT THAT THE OLD ENGINE COULD NOT.

CONNECTIONS, NOT REQUESTS. A chat backend is billed on how many sockets
are open and for how long. 100,000 registered users is not 100,000
sockets, and requests-per-day cannot express either figure. The sizing
driver is peak concurrent connections; connection-minutes follow from it.

SEARCH IS RUNG ONE. "history must be searchable" is a stated hard
requirement, so an index is present on the CHEAPEST tier. Selling it at
tier 3 would mean offering a tier-1 design that fails the brief and
letting it be picked on price -- and buying a performance component while
a stated requirement goes unmet is the specific failure this engine is
built to refuse.

CANDIDATE SET
From the AWS Architecture Center's serverless real-time chat reference
(API Gateway WebSocket -> Lambda -> DynamoDB, with a connection table
keyed by connection id) and the Well-Architected reliability pillar on
fan-out and presence state.
"""

from __future__ import annotations

import math

from whichcloud.archetypes.base import (
    ArchetypeGraph, Candidate, Forbidden, SizingDriver,
    has_cdn, has_load_balancer, has_relational_database, resilience_wanted,
)
from whichcloud.estimator import ArchitectureSpec

#: Share of registered users connected AT ONCE at peak, when the text
#: gives a user count but no concurrency figure.
#:
#: This is the single most load-bearing assumption in the shape --
#: connection-minutes are linear in it -- so it is deliberately at the
#: low end of what published chat-platform figures suggest, and it is
#: surfaced through the sizing driver rather than buried. Reading
#: "100,000 users" as 100,000 simultaneous sockets would overstate the
#: connection bill by more than an order of magnitude.
CONCURRENCY_SHARE = 0.08

#: Minutes a connected session lasts, and messages sent per session
#: minute. Both drive meters that bill per million, so the bill is
#: insensitive to modest error here -- unlike the concurrency share.
SESSION_MINUTES = 25.0
MESSAGES_PER_SESSION_MINUTE = 1.5

#: Sessions per connected user per day.
SESSIONS_PER_USER_PER_DAY = 3.0

#: KB per message, for the history index and the archive.
MESSAGE_KB = 1.0

#: OpenSearch sizing. A search domain has a floor: two nodes, because one
#: node is not a domain you can lose a node from.
SEARCH_NODE_FLOOR = 2
MESSAGES_PER_SEARCH_NODE = 40_000_000.0

#: MONTHS OF HISTORY HELD IN THE SEARCH INDEX.
#:
#: This was 12, and it was the single worst assumption in the file. The
#: prompt says "history must be searchable" and says nothing about how
#: far back -- so a year of full-text-indexed chat was invented, and it
#: sized the domain at NINE nodes, $551.88, seventy percent of the whole
#: bill, on a figure nobody supplied.
#:
#: Three months is the defensible default: it is the window people
#: actually search in a chat product, and it is what makes tier 3's cold
#: archive mean something -- older conversations go there, retrievable,
#: rather than being held in a search index at index prices forever.
#:
#: Surfaced through the sizing driver, so the reader can see the figure
#: their bill turns on rather than discovering it.
SEARCHABLE_MONTHS = 3


def _peak_connections(constraints) -> int:
    """Sockets open at the same time at peak.

    A stated figure wins outright. Otherwise derived from the user count,
    which is what people actually write.
    """
    stated = int(getattr(constraints, "peak_concurrent_connections", 0) or 0)
    if stated:
        return stated
    users = int(constraints.users or 0)
    if users:
        return max(1, int(users * CONCURRENCY_SHARE))
    return 500


def _connection_minutes(constraints) -> float:
    """Connection-minutes a month -- the meter this shape bills on."""
    return (
        _peak_connections(constraints)
        * SESSIONS_PER_USER_PER_DAY
        * SESSION_MINUTES
        * 30.0
    )


def _messages_per_month(constraints) -> float:
    return _connection_minutes(constraints) * MESSAGES_PER_SESSION_MINUTE


def _history_gb(constraints) -> float:
    return _messages_per_month(constraints) * MESSAGE_KB / 1_048_576.0


def _search_nodes(constraints) -> int:
    needed = math.ceil(
        _messages_per_month(constraints)
        * SEARCHABLE_MONTHS
        / MESSAGES_PER_SEARCH_NODE
    )
    return max(SEARCH_NODE_FLOOR, needed)


def _describe(constraints, load) -> str:
    stated = bool(getattr(constraints, "peak_concurrent_connections", 0))
    basis = "stated" if stated else (
        f"derived at {CONCURRENCY_SHARE:.0%} of {constraints.users:,} users"
    )
    return (
        f"{_peak_connections(constraints):,} peak concurrent connections "
        f"({basis}), {_connection_minutes(constraints):,.0f} "
        f"connection-minutes/month, {_messages_per_month(constraints):,.0f} "
        f"messages/month, {SEARCHABLE_MONTHS} months held searchable "
        f"(assumed — the text does not say how far back)"
    )


SIZING = SizingDriver(
    name="peak concurrent connections",
    fields=("peak_concurrent_connections", "users", "searchable_history"),
    describe=_describe,
)


CANDIDATES = (
    # ── ingest: the socket layer ──
    Candidate("API Gateway WebSocket", "ingest", "connection",
              "Holds the sockets and bills per connection-minute.",
              instead_of="a load-balanced fleet holding connections on "
                         "instances you provision for the peak"),
    Candidate("WebSocket messages", "ingest", "connection",
              "Per-message charge over an open socket."),
    Candidate("Amazon API Gateway (HTTP)", "ingest", "apigateway",
              "History and search queries, which are ordinary requests."),
    # ── compute ──
    Candidate("AWS Lambda", "compute", "lambda-requests",
              "Connect, disconnect and message handlers.",
              instead_of="a fleet sized for peak concurrency all month"),
    Candidate("Lambda duration", "compute", "lambda-duration",
              "Per-GB-second for handler execution."),
    # ── store ──
    Candidate("Amazon DynamoDB", "store", "dynamodb-writes",
              "Messages and the connection table, written per event.",
              instead_of="a relational store taking a write per message "
                         "at chat write rates"),
    Candidate("DynamoDB reads", "store", "dynamodb-reads",
              "Recent history and connection lookups on fan-out."),
    Candidate("DynamoDB storage", "store", "dynamodb-storage",
              "The message table."),
    Candidate("Amazon OpenSearch", "analytics", "search",
              "The searchable history the prompt asks for, by name.",
              instead_of="scanning a message table that was never built "
                         "for text search"),
    Candidate("OpenSearch storage", "analytics", "search_storage",
              "Indexed message history."),
    Candidate("Amazon ElastiCache", "store", "cache",
              "Presence and fan-out state, read on every message.",
              instead_of="a table lookup per recipient per message"),
    Candidate("Amazon S3", "store", "storage",
              "Cold message archive beyond the searchable window."),
    Candidate("S3 requests", "store", "s3_requests", "Archive writes."),
    Candidate("S3 lifecycle tiering", "store", "storage_lifecycle",
              "Old conversations, kept but not at hot rates."),
    # ── async ──
    Candidate("Amazon Kinesis Data Streams", "async", "streaming",
              "Ordered message log feeding the index and the archive.",
              instead_of="writing to the index synchronously and making "
                         "delivery wait for it"),
    Candidate("Amazon SNS", "async", "notification",
              "Push notifications for recipients who are not connected."),
    # ── ops ──
    Candidate("Amazon CloudWatch", "ops", "monitoring",
              "Connection count, message latency, handler errors."),
    Candidate("AWS CloudTrail", "ops", "audit", "Configuration changes."),
    Candidate("AWS X-Ray", "ops", "tracing",
              "Where a message spent its time between send and delivery."),
    # ── security ──
    Candidate("AWS KMS", "security", "kms", "Encryption for messages at rest."),
    Candidate("AWS Secrets Manager", "security", "secrets", "Push credentials."),
    Candidate("Amazon GuardDuty", "security", "threat", "Account detection."),
    Candidate("AWS Security Hub", "security", "posture", "Configuration drift."),
    # ── resilience ──
    Candidate("AWS Backup", "resilience", "backup", "The message table."),
    Candidate("Cross-region backup copy", "resilience", "backup_copy",
              "A copy elsewhere of conversations that cannot be recreated."),
)


FORBIDDEN = (
    Forbidden(
        "relational database",
        "Chat is append-heavy and read by recency, and its history needs "
        "text search. A relational primary is the wrong engine on both "
        "counts — it takes a write per message at chat rates and cannot "
        "answer the search the prompt asks for without a second system "
        "anyway.",
        has_relational_database,
    ),
    Forbidden(
        "load balancer",
        "The WebSocket API holds the sockets and is the endpoint. A "
        "balancer in front of it balances across nothing, and a fleet "
        "behind it would be provisioned for peak concurrency all month.",
        has_load_balancer,
    ),
    Forbidden(
        "CDN",
        "Messages are per-recipient and arrive over an open socket. There "
        "is nothing an edge cache can serve twice.",
        has_cdn,
    ),
)


def build(*, tier_level, constraints, load, region, **_) -> ArchitectureSpec:
    """One tier of a connection-oriented service."""
    minutes = _connection_minutes(constraints)
    messages = _messages_per_month(constraints)
    history_gb = _history_gb(constraints)

    presence = tier_level >= 2    # state off the critical path
    streamed = tier_level >= 3    # an ordered log and a cold archive
    resilient = resilience_wanted(constraints, tier_level)

    # SEARCH IS RUNG ONE WHEN IT WAS ASKED FOR. Selling it at tier 3
    # would offer a tier-1 design that fails the stated brief and let it
    # be picked on price. When nothing asked for it, tier 3 still buys
    # it -- an index is what a chat backend grows into.
    search_wanted = bool(constraints.searchable_history) or streamed
    nodes = _search_nodes(constraints) if search_wanted else 0

    return ArchitectureSpec(
        name=f"tier_{tier_level}",
        region=region,
        # Nothing is provisioned by the hour to hold a socket.
        compute_count=0,
        fargate_task_count=0,
        database_vcpu=None,
        database_memory_gb=None,
        load_balancer=False,
        cdn_gb=0.0,
        nat_gateway_count=0,
        serves_requests=True,
        # ── the meter this shape actually bills on ──
        ws_connection_minutes_per_month=minutes,
        ws_messages_per_month=messages,
        apigateway_requests_per_month=messages * 0.1,
        # ── handlers ──
        lambda_invocations_per_month=messages * 2,
        lambda_avg_ms=60.0,
        lambda_memory_mb=256.0,
        # ── messages ──
        dynamodb_write_units_per_month=messages,
        dynamodb_read_units_per_month=messages * 3,
        dynamodb_storage_gb=max(1.0, history_gb * 12),
        # ── the searchable history the prompt names ──
        search_node_count=nodes,
        search_node_vcpu=2 if nodes else None,
        search_node_memory_gb=8.0 if nodes else None,
        search_storage_gb=(
            max(10.0, history_gb * SEARCHABLE_MONTHS) if nodes else 0.0
        ),
        # ── ops and resilience on every tier ──
        monitored_metrics=25,
        audit_logging=True,
        backup_gb=(
            0.0 if constraints.durability == "ephemeral"
            else max(1.0, history_gb * 12)
        ),
        backup_retention_days=(
            0 if constraints.durability == "ephemeral" else 35
        ),
        # ── tier 2: presence off the critical path, push, keys, tracing ──
        cache_vcpu=2 if presence else None,
        cache_memory_gb=4.0 if presence else None,
        notifications_per_month=messages * 0.2 if presence else 0.0,
        kms_key_count=1 if presence else None,
        secret_count=2 if presence else 0,
        tracing_monthly_traces=messages * 0.1 if presence else 0.0,
        # ── tier 3: an ordered log, a cold archive, detection ──
        stream_shards=max(1, int(messages / 20_000_000)) if streamed else 0,
        stream_put_units=messages if streamed else 0.0,
        storage_gb=history_gb * 24 if streamed else 0.0,
        s3_put_requests=messages * 0.01 if streamed else 0.0,
        lifecycle_gb=history_gb * 18 if streamed else 0.0,
        threat_detection=streamed,
        posture_monthly_checks=200.0 if streamed else 0.0,
        # ── a stated durability requirement applies on every tier ──
        object_lock=resilient,
        backup_copy_gb=max(1.0, history_gb * 12) if resilient else 0.0,
        backup_seed_gb=max(1.0, history_gb * 12) if resilient else 0.0,
        backup_transfer_gb=history_gb if resilient else 0.0,
    )


GRAPH = ArchetypeGraph(
    name="realtime",
    summary="Persistent connections rather than discrete requests — chat, "
            "live feeds, presence.",
    sources=(
        "AWS Architecture Center: serverless real-time chat (API Gateway "
        "WebSocket -> Lambda -> DynamoDB with a connection table keyed by "
        "connection id)",
        "Amazon OpenSearch sizing guidance: a domain floor of two nodes, "
        "because one node is not a domain you can lose a node from",
        "Well-Architected reliability pillar: keep presence and fan-out "
        "state off the message critical path",
    ),
    sizing=SIZING,
    candidates=CANDIDATES,
    forbidden=FORBIDDEN,
    build=build,
    # Sized and drawn by CONNECTIONS. The socket layer is the entry
    # point, not a load balancer.
    flow=(
        ("users", "connections", "opens socket"),
        ("connections", "lambda", "connect/message"),
        ("lambda", "dynamodb", "stores message"),
        ("lambda", "cache", "presence"),
        ("lambda", "notification", "push when offline"),
        ("lambda", "streaming", "ordered log"),
        ("streaming", "search", "indexes history"),
        ("dynamodb", "search", "indexes history"),
        ("users", "apigateway", "history + search"),
        ("apigateway", "search", "queries"),
        ("streaming", "storage", "cold archive"),
    ),
    tier_notes={
        2: "State: a table lookup per recipient per message → presence and "
           "fan-out in a cache, with push for recipients who are not "
           "connected — removes per-message latency you cannot explain, "
           "and removes messages silently going nowhere when the "
           "recipient is offline.",
        3: "History: writing the index synchronously → an ordered Kinesis "
           "log feeding the index and a cold archive — removes delivery "
           "waiting on the index, and removes old conversations being "
           "held at hot rates forever.",
    },
)
