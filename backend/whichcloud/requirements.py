"""What the user wants, as a structured object.

This is the contract between the front of the system and the engine. Whether it
was filled in by a person, a form, or (later) an LLM reading plain English, the
engine sees only this. That separation is deliberate: it means adding natural
language later is an adapter, not a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

WorkloadType = Literal["web", "api", "batch", "ml", "storage", "mixed"]
TrafficPattern = Literal["steady", "spiky", "unknown"]
Scale = Literal["low", "medium", "high"]
Tolerance = Literal["low", "medium", "high"]
Skill = Literal["beginner", "intermediate", "expert"]

# ── the four derivation axes ──
# Every architecture is derived from the workload by answering these, not
# from a template. Compute and networking FOLLOW from them; they are never
# the starting point. Two workloads answering these differently must produce
# different component sets. Defaults describe a plain request/response web
# app -- the shape an unqualified prompt still lands on.
IngressShape = Literal[
    "requests",     # HTTP/API calls from users
    "events",       # discrete events (webhooks, messages, device signals)
    "files",        # uploaded documents, media, blobs
    "batches",      # scheduled bulk loads
    "connections",  # persistent/long-lived sockets
    "streams",      # continuous high-rate telemetry / clickstream
]
ProcessingMode = Literal[
    "synchronous",     # answered in the request
    "near-real-time",  # processed as it arrives, seconds of latency
    "batch",           # accumulated and processed in runs
    "offline",         # deferred, no latency requirement
]
DataShape = Literal[
    "relational", "time-series", "key-value", "document",
    "object", "search", "warehouse", "mixed",
]
EgressShape = Literal[
    "api",            # JSON/API responses
    "media",          # video/large files served to users
    "notifications",  # push/email/SMS out
    "dashboards",     # reporting / analytics views
    "exports",        # bulk data out
    "none",           # nothing leaves (internal pipeline)
]

VALID_WORKLOADS = ("web", "api", "batch", "ml", "storage", "mixed")
VALID_PATTERNS = ("steady", "spiky", "unknown")
VALID_SCALES = ("low", "medium", "high")


@dataclass(frozen=True, slots=True)
class Requirement:
    """A workload described in provider-neutral terms."""

    goal: str
    workload_type: WorkloadType = "web"
    traffic_pattern: TrafficPattern = "unknown"
    traffic_scale: Scale = "medium"

    region: str = "india"  # our neutral key, see pricing.models.REGIONS
    budget_monthly_usd: float | None = None
    latency_target_ms: int | None = None

    # Data volumes. The user usually knows these roughly; defaults are modest
    # rather than zero so an estimate is never silently missing egress.
    storage_gb: float = 50.0
    egress_gb: float = 100.0

    compliance: tuple[str, ...] = ()
    lock_in_tolerance: Tolerance = "medium"
    team_skill: Skill = "intermediate"
    provider_preference: str | None = None  # None = let us choose

    # Properties that gate specific techniques.
    interruptible: bool = False  # can work be restarted? gates spot
    high_availability: bool = False  # must survive a zone failure?
    arm_compatible: bool = True  # no x86-only dependencies?

    # Functional signals that change which components belong in the
    # architecture, not just how big they are. Each is priced for real when
    # the catalog can (WAF); the rest are surfaced honestly as missing rather
    # than silently dropped or invented — see engine.py and estimator.py.
    needs_waf: bool = False  # named attacks, DDoS, or asked to be protected
    needs_event_streaming: bool = False  # real-time processing of an event stream
    needs_analytics: bool = False  # OLAP / dashboards over the data, not just CRUD
    needs_search: bool = False  # full-text / faceted search over the data
    needs_email: bool = False  # transactional email -- confirmations, receipts, alerts
    needs_queue: bool = False  # background jobs, async work off the request path
    needs_notifications: bool = False  # push/SMS alerts, distinct from email
    #: A genuine serverless fit -- spiky/unpredictable/event-driven, scales to
    #: zero, no need for always-on servers or a relational database. Selects a
    #: different architecture (Lambda + API Gateway + DynamoDB) rather than a
    #: bigger or smaller server one. Deliberately conservative: a steady app
    #: with a real RDBMS is not serverless.
    serverless: bool = False
    #: The app's core value is a managed AI/ML capability. Selects an AI
    #: architecture that calls AWS's managed AI services rather than running
    #: generic servers. The specific capabilities set which services appear.
    ai: bool = False
    ai_vision: bool = False       # image recognition / detection -> Rekognition
    ai_language: bool = False     # sentiment / NLP on text -> Comprehend
    #: A stream processor / event pipeline: continuous ingestion of events or
    #: telemetry, processed as they arrive, rather than a request-serving app.
    #: Selects the event_driven service graph (Kinesis/MSK -> Lambda/Fargate ->
    #: Timestream/DynamoDB -> Athena/OpenSearch) instead of the web shape.
    event_driven: bool = False
    #: Time-series, append-only or sensor telemetry. Routes the PRIMARY store
    #: to a purpose-built time-series store (Timestream), never to RDS.
    telemetry: bool = False

    # ── the four derivation axes ──
    # What enters, what happens to it, where it rests, what leaves. The
    # architecture is derived from these rather than fitted to a template.
    # Defaults are the plain web-app answers, so a prompt that specifies none
    # of them still resolves to the shape it does today.
    ingress_shape: IngressShape = "requests"
    processing_mode: ProcessingMode = "synchronous"
    data_shape: DataShape = "relational"
    egress_shape: EgressShape = "api"

    #: Transactions per day, when the description states one. Drives stream
    #: shard count, which is arithmetic rather than a tier lookup.
    daily_transactions: int | None = None

    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.workload_type not in VALID_WORKLOADS:
            raise ValueError(
                f"workload_type {self.workload_type!r} is not one of {VALID_WORKLOADS}"
            )
        if self.traffic_pattern not in VALID_PATTERNS:
            raise ValueError(
                f"traffic_pattern {self.traffic_pattern!r} is not one of {VALID_PATTERNS}"
            )
        if self.traffic_scale not in VALID_SCALES:
            raise ValueError(
                f"traffic_scale {self.traffic_scale!r} is not one of {VALID_SCALES}"
            )
        if self.budget_monthly_usd is not None and self.budget_monthly_usd <= 0:
            raise ValueError("budget_monthly_usd must be positive when given")
        if self.storage_gb < 0 or self.egress_gb < 0:
            raise ValueError("data volumes cannot be negative")

    @property
    def needs_database(self) -> bool:
        return self.workload_type in ("web", "api", "mixed")

    @property
    def serves_requests(self) -> bool:
        """Does anything outside call this over the network?

        A nightly training job and a bulk store do not. Gating the edge on
        this is what stops a batch pipeline being handed a CDN, a load
        balancer, a web firewall and a public DNS zone -- which is what
        made every architecture look the same whatever was described.
        """
        return self.workload_type in ("web", "api", "mixed")

    @property
    def is_batch(self) -> bool:
        return self.workload_type in ("batch", "ml")

    @classmethod
    def from_dict(cls, data: dict) -> Requirement:
        """Build from a plain dict — the shape an LLM will eventually emit."""
        known = {f for f in cls.__slots__}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown requirement fields: {sorted(unknown)}")

        payload = dict(data)
        for key in ("compliance", "notes"):
            if key in payload and payload[key] is not None:
                payload[key] = tuple(payload[key])
        return cls(**payload)
