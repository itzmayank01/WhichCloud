"""Did any number the description STATED fail to reach the Constraints?

The extraction schema is where quantities are meant to be read correctly;
this is the net under it. The two are deliberately different jobs, and
the difference is what makes the table below safe:

    extraction  turns text into values.  A gap there costs a WRONG NUMBER.
    this audit   turns a gap into a refusal. A gap here costs a REFUSAL.

So this table can never invent a constraint, size a plan, or select a
component. Its only possible output is "you stated something and we did
not read it, so we are not going to price this" -- the same trade the
archetype classifier makes, for the same reason. A missing unit here
costs an unnecessary refusal at worst; a missing unit in extraction cost
a 40-machine estate being priced as one small ARM instance.

Why it exists at all. Three figures were being discarded silently:

    "40 virtual machines"          -> nowhere to go, dropped entirely
    "500 GB of sensor readings"    -> storage_gb stayed 0.0
    "30,000 visitors a month"      -> read, but recorded as ASSUMED

The first two produced a plan sized for a workload nobody described. A
zero that should have been forty is not a rounding error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Scale words attached to a figure. Longest first so "million" is not
#: cut short by "m".
_SCALE: tuple[tuple[str, float], ...] = (
    ("billion", 1e9), ("million", 1e6), ("lakh", 1e5), ("crore", 1e7),
    ("thousand", 1e3), ("bn", 1e9), ("mn", 1e6), ("m", 1e6), ("k", 1e3),
)


@dataclass(frozen=True)
class Family:
    """A group of units that all answer the same question.

    `targets` is every Constraints field that could legitimately have
    received the figure -- a storage number may land in `storage_gb`,
    `content_storage_gb` or a migration's `source_disk_gb_total`, and any
    one of them means it was read. Flagging only when ALL of them are
    empty is what keeps this from second-guessing a correct extraction
    that simply chose a different field than we would have.
    """

    name: str
    units: tuple[str, ...]
    targets: tuple[str, ...]
    question: str


#: Deliberately conservative. Every unit here is one that, next to a
#: number, can only be a quantity of the thing it names -- so a false
#: positive needs the extraction to have genuinely missed it.
FAMILIES: tuple[Family, ...] = (
    Family(
        name="machines",
        units=(
            "virtual machine", "virtual machines", "vms", "vm",
            "servers", "server", "machines", "machine",
            "hosts", "host", "physical box", "physical boxes",
            "nodes", "node",
        ),
        targets=("source_vm_count",),
        question="How many machines are you moving?",
    ),
    Family(
        name="requests",
        units=(
            "requests", "request", "lookups", "lookup", "queries", "query",
            "transactions", "transaction", "orders", "order",
            "bookings", "booking", "appointments", "appointment",
            "visitors", "visitor", "visits", "visit",
            "sessions", "session", "pageviews", "pageview", "page views",
            "page view", "hits", "hit", "events", "event",
            "messages", "message", "predictions", "prediction",
            "submissions", "submission", "applications", "application",
            "api calls", "api call", "webhooks", "webhook",
        ),
        targets=("requests_per_day",),
        question="Roughly how many of those happen per day?",
    ),
    Family(
        name="people",
        units=(
            "users", "user", "customers", "customer", "subscribers",
            "subscriber", "members", "member", "staff", "employees",
            "employee", "students", "student", "patients", "patient",
            "people", "doctors", "doctor",
        ),
        targets=("users",),
        question="Roughly how many people use it?",
    ),
    Family(
        name="storage",
        units=("gb", "gigabytes", "tb", "terabytes", "mb", "megabytes",
               "pb", "petabytes"),
        targets=("storage_gb", "content_storage_gb", "user_data_gb",
                 "source_disk_gb_total", "egress_gb"),
        question="How much data is stored, and how much leaves the network?",
    ),
)

#: A figure, an optional scale word, then within a short distance a unit.
#: The gap is capped hard: "40 virtual machines" and "about 30,000
#: visitors a month" both match, while a number in one clause and a noun
#: three clauses later does not.
_GAP = r"[^.\n;]{0,18}?"


def _scale_alternation() -> str:
    return "|".join(re.escape(word) for word, _ in _SCALE)


def _all_units() -> frozenset[str]:
    return frozenset(unit for family in FAMILIES for unit in family.units)


def _matches(text: str, unit: str) -> list[tuple[float, str]]:
    """Every (value, quoted phrase) for this unit in the text.

    A match whose unit is immediately followed by ANOTHER unit word is
    discarded, because in English the first noun is then a modifier
    rather than the thing being counted. "12,000 user sessions" is twelve
    thousand sessions, not twelve thousand users; "40 customer orders" is
    forty orders. Without this the audit flagged a correctly-read session
    count as a dropped user count and refused to price a perfectly
    readable prompt -- a false refusal, which is cheap but not free.
    """
    units = _all_units()
    pattern = (
        rf"(\d[\d,]*(?:\.\d+)?)\s*({_scale_alternation()})?\b{_GAP}"
        rf"\b{re.escape(unit)}\b(\s+[a-z]+)?"
    )
    out = []
    for match in re.finditer(pattern, text):
        raw = match.group(1).replace(",", "")
        if not raw:
            continue
        following = (match.group(3) or "").strip()
        if following in units:
            continue  # modifier, not the head noun
        word = (match.group(2) or "").lower()
        multiplier = next((m for w, m in _SCALE if w == word), 1.0)
        # Trim the lookahead word back off the quoted phrase.
        phrase = match.group(0).strip()
        if following:
            phrase = phrase[: phrase.rfind(following)].strip()
        out.append((float(raw) * multiplier, phrase))
    return out


def audit(description: str, constraints) -> list[dict]:
    """Quantities the text stated that no Constraints field received.

    Returns a list of {family, phrase, value, targets, question}. Empty
    is the normal case and means every figure found a home.
    """
    text = description.lower()
    found: list[dict] = []

    for family in FAMILIES:
        hits: list[tuple[float, str]] = []
        for unit in family.units:
            hits.extend(_matches(text, unit))
        if not hits:
            continue

        # Any target carrying a value means the figure was read. We do
        # not check that it was read CORRECTLY -- that is the extraction
        # eval's job, and guessing here would make this table
        # load-bearing, which is exactly what it must not be.
        if any(float(getattr(constraints, t, 0) or 0) > 0 for t in family.targets):
            continue

        value, phrase = max(hits, key=lambda h: h[0])
        found.append({
            "family": family.name,
            "phrase": phrase,
            "value": value,
            "targets": list(family.targets),
            "question": family.question,
        })

    return found


def describe(unparsed: list[dict]) -> str:
    """One sentence a reader can act on, naming what was dropped."""
    if not unparsed:
        return ""
    quoted = "; ".join(f"{u['phrase']!r}" for u in unparsed)
    return (
        f"Your description states a quantity we could not read into the "
        f"plan ({quoted}). Pricing is withheld rather than computed "
        f"around the gap — a figure that was silently dropped would have "
        f"sized this for a workload you did not describe."
    )
