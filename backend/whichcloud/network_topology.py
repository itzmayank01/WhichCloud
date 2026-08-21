"""Whether the workload gets private application subnets, or a public one
with no NAT gateway at all.

Runs after extraction and the load model, before component selection: the
load model has already decided WHAT the workload needs bought; this
decides the network shape everything else gets bought inside of. A
12-person equipment tracker with 200 page views a day and an explicit
"if it's down for an hour nobody minds" has no private compute to route
through a NAT gateway in the first place -- paying ~$41/mo for one is not
a pricing bug to fix line by line, it is the wrong topology.

This is a decision, not a special case: it reads the same extracted
constraints and load every other module reads, and nothing here names a
fixture.
"""

from __future__ import annotations

from dataclasses import dataclass

from whichcloud.constraints import Constraints
from whichcloud.load_model import Load

PUBLIC_SIMPLE = "public_simple"
PRIVATE_STANDARD = "private_standard"

#: Naming any of these is a stated architectural requirement, independent
#: of availability/durability/load -- a workload that asks for network
#: isolation gets it even if nothing else about it looks demanding.
_ISOLATION_HINTS = (
    "network isolation", "private connectivity", "vpn", "site-to-site vpn",
    "direct connect", "pci", "pci dss", "private subnet", "isolated network",
    "no public access", "air-gapped", "airgapped", "private network",
)

#: A stated request for network-traffic audit, independent of full
#: isolation -- checked only inside public_simple, to decide whether flow
#: logs stay off (the topology's default) or are switched back on.
_FLOW_LOG_HINTS = (
    "network audit", "audit network traffic", "traffic log", "flow log",
    "network traffic logging",
)


@dataclass(frozen=True)
class TopologyDecision:
    value: str
    reason: str
    flow_logs_wanted: bool
    #: The regulation name that forced private_standard, when that is why
    #: -- empty otherwise, including when private_standard was chosen for
    #: an ordinary reason (availability/durability/load).
    forced_by_compliance: str = ""


def decide(
    constraints: Constraints, load: Load, description: str,
    compliance: list[dict],
) -> TopologyDecision:
    """public_simple only when every disqualifying signal is absent --
    the compliance override, then availability, durability, load, and any
    stated isolation phrase, checked in that order so the reason string
    names whichever one actually applies."""
    isolation_obligation = next(
        (
            str(c["regulation"]) for c in compliance
            if c.get("requires_network_isolation")
        ),
        "",
    )
    if isolation_obligation:
        return TopologyDecision(
            PRIVATE_STANDARD,
            f"private_standard: {isolation_obligation} requires network "
            "isolation for this sector, regardless of workload size.",
            flow_logs_wanted=True,
            forced_by_compliance=isolation_obligation,
        )

    text = description.lower()
    stated_isolation = any(h in text for h in _ISOLATION_HINTS)

    if (
        constraints.availability == "low"
        and constraints.durability == "normal"
        and load.tier == "trivial"
        and not stated_isolation
    ):
        flow_logs_wanted = any(h in text for h in _FLOW_LOG_HINTS)
        return TopologyDecision(
            PUBLIC_SIMPLE,
            f"public_simple: no stated availability or durability "
            f"requirement and {load.peak_rps:.2f} peak req/sec, so private "
            "application subnets and their NAT gateway are not bought.",
            flow_logs_wanted=flow_logs_wanted,
        )

    return TopologyDecision(
        PRIVATE_STANDARD,
        f"private_standard: {_why_not_simple(constraints, load, stated_isolation)}",
        flow_logs_wanted=True,
    )


def _why_not_simple(constraints: Constraints, load: Load, stated_isolation: bool) -> str:
    reasons = []
    if constraints.availability != "low":
        reasons.append(f"availability={constraints.availability}")
    if constraints.durability != "normal":
        reasons.append(f"durability={constraints.durability}")
    if load.tier != "trivial":
        reasons.append(f"load_tier={load.tier}")
    if stated_isolation:
        reasons.append("a network isolation / VPN / Direct Connect / PCI "
                        "requirement was stated")
    return "; ".join(reasons) or "default"
