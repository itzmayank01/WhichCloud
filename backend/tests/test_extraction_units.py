"""Stated volumes must survive the trip into Constraints, however phrased.

These are deterministic tests of the RULES around extraction -- the
provenance correction, the duty-cycle field and the audit's compound-noun
guard. The model's own accuracy across phrasings is measured separately
(scripts/eval_intake.py); mixing a live call in here would make the suite
measure the provider instead of the code, and fail for reasons nobody
changed.

What was measured before this work, on live reads:

    "600 lookups a minute"                  -> 288,000 (wrong basis)
    "20 predictions a second in business
     hours"                                 -> 0       (silent zero)
    "12 clinics, 150 appointments each"     -> 0       (no multiplier)
    "2,000 transactions an hour"            -> right number, ASSUMED
    "30,000 visitors a month"               -> right number, ASSUMED
    "3.65 million submissions a year"       -> right number, ASSUMED

The zeroes were the dangerous ones: a workload sized at the zero-traffic
floor looks like a cheap answer rather than a missing one.
"""

from __future__ import annotations

from whichcloud.constraints import Constraints
from whichcloud.llm_extract import _correct_requests_provenance
from whichcloud.quantity_audit import audit


# ── provenance ───────────────────────────────────────────────────────


def test_a_quoted_basis_makes_the_figure_stated():
    """A number the model normalised from a phrase it can quote came from
    the TEXT. Filing it as `assumed` drives assumed_fields(), the
    confidence map and the "what did we guess" panel -- so the interface
    asked the user to confirm a figure they had just supplied, and
    presented their own number back to them as the engine's guess."""
    c = Constraints(requests_per_day=1000, requests_basis="30,000 visitors a month")
    assert c.source("requests_per_day") == "assumed"
    _correct_requests_provenance(c)
    assert c.source("requests_per_day") == "stated"
    assert c.evidence["requests_per_day"] == "30,000 visitors a month"


def test_no_basis_means_no_promotion():
    """The correction may only ever promote assumed -> stated on
    evidence. With nothing quoted there is no evidence, and inventing a
    provenance claim is the exact failure it exists to fix, inverted."""
    c = Constraints(requests_per_day=5000, requests_basis="")
    _correct_requests_provenance(c)
    assert c.source("requests_per_day") == "assumed"


def test_a_basis_without_a_figure_promotes_nothing():
    c = Constraints(requests_per_day=0, requests_basis="some traffic")
    _correct_requests_provenance(c)
    assert c.source("requests_per_day") == "assumed"


def test_an_existing_evidence_string_is_not_overwritten():
    """The span the model gave is the better quote when it gave one."""
    c = Constraints(requests_per_day=1000, requests_basis="30,000 visitors a month")
    c.stated.add("requests_per_day")
    c.evidence["requests_per_day"] = "about 30,000 visitors a month, mostly India"
    _correct_requests_provenance(c)
    assert c.evidence["requests_per_day"].startswith("about 30,000")


# ── duty cycle ───────────────────────────────────────────────────────


def test_active_hours_defaults_to_a_full_day():
    """24 is the honest default: a workload nobody said anything about
    runs all the time, and assuming otherwise would quietly divide every
    compute bill by three."""
    assert Constraints().active_hours_per_day == 24.0


# ── the audit's compound-noun guard ──────────────────────────────────


def test_a_modifier_noun_is_not_counted_as_the_thing_counted():
    """"12,000 user sessions" is twelve thousand SESSIONS. Reading it as
    a user count made the audit refuse a prompt it had read correctly --
    a false refusal, which is cheap but not free."""
    c = Constraints(requests_per_day=12000)   # sessions landed correctly
    found = audit("Around 12,000 user sessions a day on the portal.", c)
    assert not [u for u in found if u["family"] == "people"]


def test_the_head_noun_is_still_caught_when_it_was_dropped():
    """The guard must not blind the audit: with the session count NOT
    read, the requests family still fires."""
    c = Constraints()
    found = audit("Around 12,000 user sessions a day on the portal.", c)
    assert "requests" in {u["family"] for u in found}


def test_customer_orders_counts_orders_not_customers():
    c = Constraints(requests_per_day=400)
    found = audit("We take about 400 customer orders a day.", c)
    assert not [u for u in found if u["family"] == "people"]
