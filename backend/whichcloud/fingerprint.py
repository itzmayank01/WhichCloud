"""Architecture fingerprints — the assertion that makes 'derived, not
templated' testable.

A fingerprint is the sorted set of service identifiers in a tier, with every
size, count and AZ multiplier stripped away. Two architectures with the same
fingerprint are the same architecture however different their bills.

Three properties are checked against it:

  DIVERGENCE  two workloads with a different profile (archetype, data_shape
              or processing_mode) must have different tier-1 fingerprints.
              Identical fingerprints across genuinely different workloads is
              the template bug.
  TIER SPREAD within one workload, consecutive tiers differ by >= 3 services.
  STABILITY   the same requirement produces the same fingerprint every run.

The service identifier is the topology `kind` -- the canonical name a line
item maps to (compute, database, timestream, lambda, ...). It is chosen
because it already ignores size and count: 'Compute x 6' and 'Compute x 1'
are both `compute`, which is exactly what a fingerprint must not distinguish.
"""

from __future__ import annotations

from whichcloud.topology import _kind_for


#: How a standby region's line items are marked when they are merged into
#: a tier's bill (see plan._merge_standby).
_STANDBY_MARKER = "(standby"


def fingerprint(option) -> frozenset[str]:
    """The set of service kinds in one priced option, size/count stripped.

    Unpriced components (an estimate's `missing`) are NOT in the fingerprint:
    a fingerprint describes what the architecture IS, and a component with no
    catalog rate was never selected. `client` is excluded -- the users box is
    on every diagram and distinguishes nothing.

    A standby region's components are counted SEPARATELY, as `kind@standby`.
    Without that, tier 3 fingerprinted identically to tier 2 on every
    fixture that had one -- the standby's compute and database folded onto
    the primary's kinds, so a tier carrying a whole second region in
    another geography looked like the same architecture. A second region
    is not a size and it is not a count; it is the difference between
    surviving a regional outage and not, and the fingerprint has to be
    able to see it.
    """
    kinds = set()
    for item in option.estimate.items:
        kind = _kind_for(item)
        if _STANDBY_MARKER in item.label:
            kind = f"{kind}@standby"
        kinds.add(kind)
    kinds.discard("client")
    return frozenset(kinds)


def profile(requirement) -> tuple:
    """What makes two workloads 'genuinely different' for the divergence
    rule: the archetype-selecting signals plus the derivation axes. Two
    requirements with the same profile may legitimately share a fingerprint;
    two with different profiles may not."""
    ai = getattr(requirement, "ai", False)
    return (
        getattr(requirement, "event_driven", False),
        getattr(requirement, "serverless", False),
        ai and (requirement.ai_vision or requirement.ai_language),
        requirement.workload_type,
        getattr(requirement, "data_shape", "relational"),
        getattr(requirement, "processing_mode", "synchronous"),
        getattr(requirement, "ingress_shape", "requests"),
    )


def tier_spread(options) -> list[int]:
    """Service-count difference between each pair of consecutive tiers."""
    out = []
    for lower, higher in zip(options, options[1:]):
        a, b = fingerprint(lower), fingerprint(higher)
        out.append(len((a - b) | (b - a)))
    return out


#: The minimum a pair of consecutive tiers must differ by, in services.
#: Three, not one, because one service is a size decision wearing a
#: different hat -- adding a second NAT gateway or a replica changes the
#: bill without changing the architecture, and three tiers that differ
#: that way are one design sold three times.
MIN_TIER_SPREAD = 3


# ── the plan path ────────────────────────────────────────────────────
# `fingerprint` above takes an engine Option; a plan Tier exposes the
# same `.estimate.items`, so it works on both unchanged. What differs is
# the PROFILE -- what makes two workloads "genuinely different" -- because
# the two paths carry different information about the workload.


def plan_profile(plan) -> tuple:
    """What makes two PLANS genuinely different.

    The archetype leads, because on this path it is the axis that decides
    the architecture: a static site and a batch job are not two sizes of
    one design. The rest are the shape-selecting signals a Constraints
    object actually carries -- deliberately not a long tuple, since every
    extra element makes divergence easier to satisfy and the check
    weaker.
    """
    c = plan.constraints
    return (
        plan.archetype,
        # Whether work happens off the request path at all.
        bool(getattr(c, "async_processing", False)),
        # Continuous vs duty-cycled: a nightly job and an always-on API
        # are different architectures, not different sizes of one.
        float(getattr(c, "active_hours_per_day", 24.0)) >= 24.0,
        # An estate being moved is sized from an inventory, not traffic.
        bool(getattr(c, "source_vm_count", 0)),
    )


def plan_fingerprints(plan) -> list[frozenset[str]]:
    """One fingerprint per priced tier. Empty when pricing was withheld,
    which is a real answer rather than a missing one -- a withheld plan
    has no architecture to fingerprint, and inventing an empty set for it
    would make two withheld plans look identical to two templated ones."""
    return [fingerprint(tier) for tier in plan.tiers]


def divergence_collisions(plans: dict) -> list[tuple[str, str]]:
    """Fixture pairs with a DIFFERENT profile sharing a tier-1 fingerprint.

    Each one is the template bug: two workloads the engine agrees are
    different, answered with the same architecture.
    """
    entries = []
    for name, plan in plans.items():
        prints = plan_fingerprints(plan)
        if prints:
            entries.append((name, plan_profile(plan), prints[0]))

    collisions = []
    for i, (name_a, profile_a, print_a) in enumerate(entries):
        for name_b, profile_b, print_b in entries[i + 1:]:
            if profile_a != profile_b and print_a == print_b:
                collisions.append((name_a, name_b))
    return collisions


def thin_spreads(plans: dict) -> dict[str, list[int]]:
    """Fixtures whose consecutive tiers differ by fewer than MIN_TIER_SPREAD
    WITHOUT saying so.

    The rule has an escape hatch and it is a real one: three services'
    difference, OR an explicit statement that no further improvement is
    worth buying. A small internal tool whose own description says nobody
    minds an hour of downtime genuinely has nothing worth selling it at
    tier 3, and inventing a difference there would be padding -- the
    failure in the opposite direction. What is forbidden is a thin tier
    that stays SILENT about being thin, because that is the one a reader
    cannot tell from a considered upgrade.
    """
    out = {}
    for name, plan in plans.items():
        if len(plan.tiers) < 2:
            continue
        spreads = tier_spread(plan.tiers)
        offenders = [
            i for i, s in enumerate(spreads)
            if s < MIN_TIER_SPREAD
            and not plan.tiers[i + 1].no_further_improvement
        ]
        if offenders:
            out[name] = spreads
    return out
