"""Module: workload archetype. Which shape a description matches, chosen
from a finite set this engine has -- or has not yet -- been taught to
build, and refusing to price when nothing fits confidently.

The coverage map (tests/probes/coverage.md) found six workload shapes
this engine had never been shown, all silently priced as EC2 + RDS
anyway. This module is the fix's first half: classify honestly, and
withhold pricing for any shape nothing has validated. The second half --
teaching the engine web_app's siblings -- happens one archetype at a
time, in the coverage map's severity order, each promoted into
IMPLEMENTED_ARCHETYPES only once its own service graph and fixture
exist.

Two rules make the phrase table below safe to be incomplete, which it
permanently will be:

  1. EVERY archetype must earn its classification from its own positive
     evidence. There is no fallback branch. web_app is not the default
     that wins when nothing else matches -- being the shape the engine
     happens to already build is not evidence about the workload, and
     treating it as such is exactly the silent default the coverage map
     found.
  2. Ambiguity resolves to unknown. No match, or a tie between two
     archetypes, means unknown -- and unknown withholds pricing.

So a missing phrase costs a refusal, never a confident wrong bill. That
is the whole trade, and it is why this table can be added to safely
later (including by replacing it wholesale with an LLM extractor, which
is the recorded follow-up) without any of it being load-bearing for
correctness.
"""

from __future__ import annotations

ARCHETYPES = (
    "web_app", "static_site", "batch_etl", "event_driven",
    "ml_inference", "realtime", "migration",
)
UNKNOWN = "unknown"

#: Archetypes with a real, priced service graph in whichcloud.plan.
#: Grown one at a time -- never edited to include a name whose spec
#: branch does not exist, however confidently classify() names it.
IMPLEMENTED_ARCHETYPES = frozenset({"web_app"})

#: The three states a classification can land in. Both non-priced states
#: withhold pricing, but they are different claims and get different
#: copy: "we know what this is and haven't built it" is a far more
#: useful answer than "we don't know what this is", and collapsing them
#: throws away the more informative half.
PRICED = "priced"
RECOGNISED_UNPRICED = "recognised_unpriced"
STATE_UNKNOWN = "unknown"

#: What each shape's architecture actually needs, in words. Used only for
#: the recognised_unpriced copy: the engine can describe the shape it
#: recognised without pretending to price it, which is the whole point of
#: the state existing separately from unknown.
ARCHETYPE_REQUIREMENTS: dict[str, str] = {
    "static_site": "Object storage holding the files, a CDN in front of it, "
                   "and DNS. No application server, no database, and no VPC "
                   "— so none of the per-hour compute or NAT costs this "
                   "engine currently models apply.",
    "batch_etl": "Object storage for the raw and processed data, a scheduled "
                 "compute runner that exists only while a run is in flight, "
                 "an orchestrator to sequence the steps, and a query layer "
                 "over the results. Billed by run, not by the month.",
    "event_driven": "An ingestion endpoint, a durable queue that holds each "
                    "event until it is confirmed processed, a compute "
                    "consumer that scales with queue depth, and a datastore. "
                    "The queue — not the database — is what stops an event "
                    "being lost.",
    "ml_inference": "A model-serving endpoint on accelerated or "
                    "inference-optimised instances, autoscaled against "
                    "prediction rate, plus storage for the model artefact. "
                    "Sized from predictions/sec and model size, neither of "
                    "which this engine currently measures.",
    "realtime": "A connection-oriented gateway holding persistent sockets, a "
                "low-latency datastore for messages, a search index for "
                "history, and presence/fan-out state. Sized from concurrent "
                "connections, not requests per second.",
    "migration": "One instance per source machine, sized from each one's "
                 "existing vCPU, RAM and disk, with block storage attached "
                 "and the original operating systems preserved. Sized from "
                 "an inventory of what you already run, not from a traffic "
                 "estimate.",
}

#: Human-readable coverage, shown whenever pricing is withheld so the
#: reader can tell whether they described something adjacent.
ARCHETYPE_DESCRIPTIONS: dict[str, str] = {
    "web_app": "A request-serving application with a database behind it — "
               "portals, records systems, marketplaces, internal tools.",
    "static_site": "Files served to visitors, with no application server "
                   "and no database — marketing and brochure sites.",
    "batch_etl": "Scheduled work that processes data on a timetable and is "
                 "idle in between — nightly loads, report generation.",
    "event_driven": "Reacting to external events rather than direct user "
                    "requests — webhooks, queues, uploads.",
    "ml_inference": "Serving predictions from a trained model.",
    "realtime": "Persistent connections rather than discrete requests — "
                "chat, live feeds, presence.",
    "migration": "Moving existing servers or virtual machines to the cloud "
                 "as they are, before redesigning them.",
}

#: Evidence phrases per archetype, deliberately multi-word and specific.
#: A bare "database" or "model" is exactly the false-positive risk
#: earlier sessions kept finding one phrase at a time; this table starts
#: from that lesson rather than relearning it.
_SIGNALS: dict[str, tuple[str, ...]] = {
    "web_app": (
        "web app", "web application", "portal", "internal tool",
        "admin panel", "marketplace", "e-commerce", "ecommerce",
        "checkout", "storefront", "booking system", "appointments",
        "records system", "records online", "records and lab reports",
        "lending platform", "track equipment", "page views",
        "log in", "customer accounts", "saas", "crm",
    ),
    "static_site": (
        "no database", "no login", "marketing site", "brochure site",
        "landing page", "pages and images", "static site", "just pages",
        "portfolio site", "no backend",
    ),
    "batch_etl": (
        "every night", "overnight", "nightly", "batch job",
        "scheduled job", "rerun in the morning", "next-day report",
        "next-day reports", "nobody uses it during the day",
        "runs once a day", "runs once a night",
    ),
    "event_driven": (
        "webhook", "webhooks", "event-driven", "message queue",
        "cannot drop a single", "pub/sub", "events a day",
        "events per day", "in unpredictable bursts",
    ),
    "ml_inference": (
        "trained model", "scores loan applications", "machine learning model",
        "ml model", "inference endpoint", "predictions a second",
        "predictions per second", "scoring model", "model that scores",
    ),
    "realtime": (
        "in-app chat", "real-time", "realtime", "live chat",
        "must arrive instantly", "arrive instantly", "websocket",
        "live feed", "instant messaging", "chat application",
    ),
    "migration": (
        "virtual machines", "server room", "lift and shift", "lift-and-shift",
        "move them to the cloud", "move to the cloud", "on-premises",
        "on-prem", "our own data center", "our own datacenter",
        "before modernising", "before modernizing",
    ),
}

#: What tells these shapes apart, offered whenever pricing is withheld.
#: Generic rather than per-archetype: unknown has by definition not
#: narrowed anything down, so the questions must cover all of them.
CLARIFYING_QUESTIONS = (
    "Does it run continuously and answer live requests, or on a schedule?",
    "Is there a login and a database, or is it files served to visitors?",
    "Are you reacting to external events (webhooks, uploads, messages) "
    "rather than to direct user requests?",
    "Is it serving predictions from a model, rather than storing and "
    "returning records?",
    "Do you have existing servers or virtual machines to move as-is, "
    "rather than something new to build?",
)


def classify(description: str) -> tuple[str, str]:
    """The archetype with the strongest textual evidence, or UNKNOWN.

    Returns (archetype, evidence). Deliberately takes only the raw
    description: classification must not be able to lean on how much
    extraction happened to find, because "extraction found things"
    is evidence about the prompt's specificity, not about its shape.

    No match wins by default and no tie is broken. Both resolve to
    UNKNOWN, and UNKNOWN withholds pricing upstream.
    """
    text = description.lower()
    hits = {
        name: [p for p in phrases if p in text]
        for name, phrases in _SIGNALS.items()
    }
    ranked = sorted(hits.items(), key=lambda kv: len(kv[1]), reverse=True)

    best_name, best_hits = ranked[0]
    if not best_hits:
        return UNKNOWN, "no archetype phrase matched the description"

    runner_up_name, runner_up_hits = ranked[1]
    if len(runner_up_hits) == len(best_hits):
        return UNKNOWN, (
            f"ambiguous: {best_name} and {runner_up_name} matched equally "
            f"({best_hits[0]!r} vs {runner_up_hits[0]!r})"
        )

    return best_name, (
        f"matched {len(best_hits)} phrase(s), first {best_hits[0]!r}"
    )


def is_priceable(archetype: str) -> bool:
    """Whether a real service graph exists for this shape. Separate from
    classification on purpose: knowing what a workload IS and knowing how
    to build it are different claims, and conflating them is how an
    unimplemented shape gets priced as the one shape that is."""
    return archetype in IMPLEMENTED_ARCHETYPES


def state_for(archetype: str) -> str:
    """Which of the three states this classification lands in."""
    if archetype == UNKNOWN:
        return STATE_UNKNOWN
    return PRICED if is_priceable(archetype) else RECOGNISED_UNPRICED


def requirements_for(archetype: str) -> str:
    """What this shape's architecture needs, in words. Empty for shapes
    that are already priced -- there the components speak for themselves."""
    return ARCHETYPE_REQUIREMENTS.get(archetype, "")


def coverage() -> list[dict[str, str]]:
    """Archetypes this engine can price, and those it can only name."""
    return [
        {
            "archetype": name,
            "description": ARCHETYPE_DESCRIPTIONS[name],
            "status": "priced" if is_priceable(name) else "recognised, not yet priced",
        }
        for name in ARCHETYPES
    ]


def coverage_summary() -> dict[str, int]:
    """Two numbers, reported rather than one: how many shapes the engine
    can NAME, and how many it can PRICE. A single "coverage" figure would
    hide which of the two it referred to, and they are very different
    claims about what the product does."""
    return {
        "shapes_recognised": len(ARCHETYPES),
        "shapes_priced": len(IMPLEMENTED_ARCHETYPES),
    }
