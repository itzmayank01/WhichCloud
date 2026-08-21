"""Module 1. Read a description into constraints, and be honest about which.

The rule that shapes this file: a field may be marked "assumed" only if
nothing in the text supports it, and that set is computed AFTER extraction
by subtracting what was found from what was required. Deciding in advance
which fields are usually missing is how "must stay inside India" ends up
filed under assumptions -- the fact was in the text, and the reader simply
did not look for it.

Phrase matching runs first and an LLM only fills what is left. That order
matters: a regex that finds "cannot be lost" cannot later be talked out of
it, whereas a model asked to fill a whole struct will occasionally return
its own defaults for fields the text answered plainly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Source = Literal["stated", "assumed"]
Sector = Literal[
    "healthcare", "fintech", "ecommerce", "education",
    "internal_tools", "public_web", "other",
]
PeakShape = Literal["flat", "morning", "evening", "spiky"]

#: Fields the planner cannot run without. `assumed` is this set minus
#: whatever extraction actually found -- never a hand-maintained list.
REQUIRED = (
    "country", "sector", "availability", "durability", "users",
    "requests_per_day", "peak_shape", "budget_monthly_usd",
    "storage_gb", "egress_gb", "public_facing",
)

#: What to ask when a field had to be assumed. The question is part of the
#: contract: an assumption the reader cannot challenge is just a guess.
QUESTIONS: dict[str, str] = {
    "country": "Which country must the data stay in?",
    "sector": "What kind of organisation is this for?",
    "availability": "What happens to the business if this is down for an hour?",
    "durability": "If you lost yesterday's data, could it be recreated?",
    "users": "Roughly how many people use it?",
    "requests_per_day": "Roughly how many actions or lookups per day?",
    "peak_shape": "When during the day is it busiest?",
    "budget_monthly_usd": "What is the monthly budget?",
    "storage_gb": "How much data is stored today, and how fast does it grow?",
    "egress_gb": "Roughly how much data leaves the network each month?",
    "public_facing": "Do members of the public use this directly, or only staff?",
}

# ── phrase tables ────────────────────────────────────────────────────
# Deliberately literal. Each entry is a phrase a person actually writes,
# not a stemmed token, because the cost of a false positive here is a
# constraint invented from nothing.

_AVAILABILITY_HIGH = (
    "downtime is unacceptable", "downtime during", "cannot go down",
    "can't go down", "must not go down", "no downtime", "24x7", "24/7",
    "always available", "critical", "business hours", "opd hours",
    "working hours", "trading hours", "must stay up", "high availability",
    "cannot have downtime", "can't have downtime", "must not have downtime",
)

#: An explicit LOW-availability statement is just as much "stated" as a
#: high one -- "if it's down for an hour nobody minds" answers the same
#: question business hours does, and defaulting it to "assumed" would
#: claim the text never addressed availability when it plainly did.
_AVAILABILITY_LOW = (
    "nobody minds", "no one minds", "if it is down", "if it goes down",
    "downtime is fine", "downtime is acceptable", "not critical",
    "can be down", "best effort", "not mission critical", "low priority",
)

_DURABILITY_HIGH = (
    "cannot be lost", "can't be lost", "must not lose", "must not be lost",
    "irreplaceable", "regulated", "patient record", "patient data",
    "medical record", "health record", "financial record", "lab report",
    "audit trail", "cannot lose", "no data loss",
    # Fintech record-keeping: KYC and repayment history are retained under
    # regulatory mandate whether or not the prompt uses the word
    # "regulated" -- "kyc" alone is specific enough to carry no false-
    # positive risk, unlike a bare word such as "records".
    "kyc", "repayment record", "loan record", "regulatory audit",
    "audited by", "audits us",
)

_RESIDENCY = ("must stay inside", "must stay in", "must remain in",
              "data residency", "stay within", "not leave")

#: Naming one of these alongside a country is itself a residency signal --
#: "regulated by RBI" implies India-only storage even when nobody writes
#: the word "residency". Kept separate from _RESIDENCY so the evidence
#: string can say which kind of phrase triggered the lock.
_REGULATORS = ("rbi", "sebi", "irdai", "dpdp", "hipaa", "gdpr", "abdm",
               "pci dss", "sox", "ferpa", "ccpa", "reserve bank")

_SECTORS: tuple[tuple[Sector, tuple[str, ...]], ...] = (
    ("healthcare", ("hospital", "patient", "clinic", "doctor", "medical",
                    "lab report", "health record", "opd", "diagnostic")),
    ("fintech", ("bank", "payment", "lending", "loan", "kyc", "trading",
                 "financial record", "wallet", "upi", "insurance")),
    ("ecommerce", ("store", "shop", "retail", "checkout", "cart", "order",
                   "inventory", "catalogue", "catalog")),
    ("education", ("school", "college", "university", "student", "course",
                   "campus", "exam")),
    ("internal_tools", ("internal", "staff only", "back office", "back-office",
                        "employee", "admin panel", "intranet")),
)

#: City and region names to countries. Only places specific enough to be
#: unambiguous -- a bare "Springfield" names no country.
_PLACES: dict[str, str] = {
    "pune": "IN", "mumbai": "IN", "bengaluru": "IN", "bangalore": "IN",
    "delhi": "IN", "hyderabad": "IN", "chennai": "IN", "kolkata": "IN",
    "gurgaon": "IN", "noida": "IN", "ahmedabad": "IN", "india": "IN",
    "jaipur": "IN", "lucknow": "IN", "surat": "IN", "kochi": "IN",
    "cochin": "IN", "chandigarh": "IN", "indore": "IN", "nagpur": "IN",
    "bhopal": "IN", "coimbatore": "IN", "visakhapatnam": "IN",
    "patna": "IN", "vadodara": "IN", "thiruvananthapuram": "IN",
    "mysuru": "IN", "mysore": "IN", "amritsar": "IN", "guwahati": "IN",
    "bhubaneswar": "IN", "varanasi": "IN",
    "london": "GB", "manchester": "GB", "united kingdom": "GB", "uk": "GB",
    "dublin": "IE", "ireland": "IE",
    "singapore": "SG",
    "new york": "US", "san francisco": "US", "austin": "US", "seattle": "US",
    "united states": "US", "usa": "US", "u.s.": "US",
    "berlin": "DE", "frankfurt": "DE", "germany": "DE",
    "paris": "FR", "france": "FR",
    "sydney": "AU", "melbourne": "AU", "australia": "AU",
}

_PEAK_SHAPES: tuple[tuple[PeakShape, tuple[str, ...]], ...] = (
    ("morning", ("morning", "start of the day", "opd hours", "am rush",
                 "first thing")),
    ("evening", ("evening", "night", "after work", "end of day", "pm rush")),
    ("spiky", ("spike", "spiky", "burst", "sale", "campaign", "flash",
               "unpredictable", "sudden")),
    ("flat", ("steady", "flat", "constant", "even throughout", "all day")),
)

_PUBLIC = ("customer", "public", "consumer", "shopper", "visitor", "patient portal",
           "members of the public", "anyone can", "sign up online",
           "book their own", "book online", "book appointments online",
           "access their own", "manage their own", "log in themselves",
           "create an account", "register online", "self-service")
_STAFF_ONLY = ("staff", "employee", "internal", "front desk", "back office",
               "our team", "doctors and", "only staff")


@dataclass
class Constraints:
    """Extracted constraints, each carrying where it came from."""

    country: str = ""
    sector: Sector = "other"
    availability: str = "low"
    durability: str = "normal"
    users: int = 0
    requests_per_day: int = 0
    peak_shape: PeakShape = "flat"
    budget_monthly_usd: float = 0.0
    storage_gb: float = 0.0
    egress_gb: float = 0.0
    public_facing: bool = False

    #: Distinct from merely naming a country. Naming Pune infers where the
    #: business is; it does not by itself demand a region-deny guardrail.
    #: Only a residency phrase, or a country plus its regulator, does that
    #: -- otherwise every prompt that names a city ends up hard-locked to
    #: it, including ones that never asked for that.
    country_lock: bool = False

    #: Which fields the TEXT supported. Everything in REQUIRED and not in
    #: here is assumed, computed after the fact rather than declared.
    stated: set[str] = field(default_factory=set)
    evidence: dict[str, str] = field(default_factory=dict)

    def source(self, name: str) -> Source:
        return "stated" if name in self.stated else "assumed"

    def confidence(self, name: str) -> str:
        """"high" when matched from explicit text, "low" when it fell
        through to a default. The same distinction as source(), named for
        what a reader of the output actually wants to know: not where the
        value came from, but how much to trust it."""
        return "high" if name in self.stated else "low"

    def confidence_map(self) -> dict[str, str]:
        """Every required field's confidence, not just the low ones --
        so "what did extraction trust" is answerable without inferring it
        from what assumed_fields() left out."""
        return {name: self.confidence(name) for name in REQUIRED}

    @property
    def assumed(self) -> list[str]:
        """REQUIRED minus stated. Computed here, never maintained by hand."""
        return [f for f in REQUIRED if f not in self.stated]

    def assumed_fields(self) -> list[dict]:
        """Step 7's contract: field, what was assumed, what to ask -- every
        entry here is, by construction, confidence "low"."""
        return [
            {
                "field": name,
                "assumption": getattr(self, name),
                "question": QUESTIONS.get(name, f"What is {name}?"),
                "confidence": "low",
            }
            for name in self.assumed
        ]


def _find(text: str, phrases: tuple[str, ...]) -> str:
    """The first phrase present, or "" -- returned so it can be quoted."""
    for phrase in phrases:
        if phrase in text:
            return phrase
    return ""


#: Scale words, longest/most-specific first so "million" is not cut short
#: by "m" matching first in the alternation.
_SCALE: tuple[tuple[str, int], ...] = (
    ("million", 1_000_000), ("m", 1_000_000), ("k", 1_000),
)


def _number_near(text: str, units: tuple[str, ...]) -> tuple[int | None, str]:
    """A figure written next to one of these units, with what matched.

    Handles "about 450 staff", "roughly 6,000 record lookups a day",
    "6k lookups" and "2 million requests a day" -- the forms people
    actually write. A bare "2" for "2 million requests" undercounts a
    marketplace's real traffic by six orders of magnitude, which is
    exactly the kind of error this exists to not make.
    """
    scale_group = "|".join(re.escape(word) + r"\b" for word, _ in _SCALE)
    for unit in units:
        # A leading DIGIT is required. "[\d,]+" alone matches a bare comma,
        # which survives the comma-stripping below as an empty string and
        # takes float() down with it.
        pattern = (
            rf"(\d[\d,]*(?:\.\d+)?)\s*({scale_group})?"
            rf"[^.\n]{{0,24}}?{re.escape(unit)}"
        )
        match = re.search(pattern, text)
        if match:
            raw = match.group(1).replace(",", "")
            if not raw:
                continue
            scale_word = (match.group(2) or "").lower()
            multiplier = next((m for w, m in _SCALE if w == scale_word), 1)
            value = float(raw) * multiplier
            return int(value), match.group(0).strip()
    return None, ""


def extract(description: str) -> Constraints:
    """Phrase matching first; whatever it cannot answer is left assumed."""
    text = description.lower()
    c = Constraints()

    # ── country ──
    for place, code in _PLACES.items():
        if re.search(rf"\b{re.escape(place)}\b", text):
            c.country = code
            c.stated.add("country")
            residency = _find(text, _RESIDENCY)
            regulator = _find(text, _REGULATORS)
            # The lock is the residency phrase or the regulator, not the
            # place name itself -- naming Pune says where the business is,
            # not that data may never leave India.
            c.country_lock = bool(residency or regulator)
            trigger = residency or (f"regulator {regulator!r}" if regulator else "")
            c.evidence["country"] = (
                f"named {place!r}" + (f"; {trigger}" if trigger else "")
            )
            break

    # ── sector ──
    for sector, phrases in _SECTORS:
        hit = _find(text, phrases)
        if hit:
            c.sector = sector
            c.stated.add("sector")
            c.evidence["sector"] = f"{hit!r}"
            break

    # ── availability ──
    hit = _find(text, _AVAILABILITY_HIGH)
    if hit:
        c.availability = "high"
        c.stated.add("availability")
        c.evidence["availability"] = f"{hit!r}"
    else:
        low_hit = _find(text, _AVAILABILITY_LOW)
        if low_hit:
            # Value stays "low" (the default) -- only its source changes,
            # from unaddressed to explicitly answered.
            c.stated.add("availability")
            c.evidence["availability"] = f"{low_hit!r}"

    # ── durability ──
    hit = _find(text, _DURABILITY_HIGH)
    if hit:
        c.durability = "high"
        c.stated.add("durability")
        c.evidence["durability"] = f"{hit!r}"

    # ── volumes ──
    users, ev = _number_near(
        text, ("staff", "users", "people", "employees", "doctors", "person")
    )
    if users:
        c.users = users
        c.stated.add("users")
        c.evidence["users"] = ev

    reqs, ev = _number_near(
        text, ("lookups", "requests", "transactions", "orders", "appointments",
               "records a day", "queries", "visits", "hits", "bookings",
               "page views", "views a day")
    )
    if reqs:
        c.requests_per_day = reqs
        c.stated.add("requests_per_day")
        c.evidence["requests_per_day"] = ev

    # ── peak shape ──
    for shape, phrases in _PEAK_SHAPES:
        hit = _find(text, phrases)
        if hit:
            c.peak_shape = shape
            c.stated.add("peak_shape")
            c.evidence["peak_shape"] = f"{hit!r}"
            break

    # ── budget ──
    money = re.search(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(k\b)?", text)
    if money:
        value = float(money.group(1).replace(",", "")) * (1000 if money.group(2) else 1)
        c.budget_monthly_usd = value
        c.stated.add("budget_monthly_usd")
        c.evidence["budget_monthly_usd"] = money.group(0).strip()

    # ── storage / egress ──
    storage, ev = _number_near(text, ("gb of", "gb ", "terabytes", "tb "))
    if storage:
        c.storage_gb = float(storage)
        c.stated.add("storage_gb")
        c.evidence["storage_gb"] = ev

    # ── public facing ──
    public_hit = _find(text, _PUBLIC)
    staff_hit = _find(text, _STAFF_ONLY)
    if public_hit or staff_hit:
        # A concrete public-action phrase wins over a staff mention, not
        # the reverse: "doctors and front desk... patients also book their
        # own appointments online" describes a system BOTH groups use, and
        # the public half is what makes it public-facing. Staff-only is
        # only the answer when nothing describes the public doing
        # anything themselves -- "patient records" alone names whose data
        # it holds, not who is issuing the request, which is why bare
        # "patient" was deliberately left out of _PUBLIC.
        c.public_facing = bool(public_hit)
        c.stated.add("public_facing")
        c.evidence["public_facing"] = f"{public_hit or staff_hit!r}"

    return c
