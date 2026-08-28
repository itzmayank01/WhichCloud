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


def fingerprint(option) -> frozenset[str]:
    """The set of service kinds in one priced option, size/count stripped.

    Unpriced components (an estimate's `missing`) are NOT in the fingerprint:
    a fingerprint describes what the architecture IS, and a component with no
    catalog rate was never selected. `client` is excluded -- the users box is
    on every diagram and distinguishes nothing.
    """
    kinds = {_kind_for(item) for item in option.estimate.items}
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
