"""The registry of shapes this engine can actually build.

An archetype appears here only once it has a candidate set, a sizing
driver appropriate to its shape, a forbidden list and three tiers that
differ by service. Until then `whichcloud.archetype.classify` can still
NAME it -- and the engine will say so, and say what it would need -- but
`plan` refuses to price it.

That separation is the whole design. Knowing what a workload IS and
knowing how to build it are different claims, and the coverage map found
six shapes where conflating them produced a confident bill for the wrong
architecture.
"""

from __future__ import annotations

from whichcloud.archetypes.base import ArchetypeGraph

#: name -> graph. `whichcloud.archetype.IMPLEMENTED_ARCHETYPES` is derived
#: from this, so a shape cannot be marked priceable without a graph
#: existing -- the two can never drift.
GRAPHS: dict[str, ArchetypeGraph] = {}


def _register(module) -> None:
    graph = module.GRAPH
    GRAPHS[graph.name] = graph


def _load() -> None:
    from whichcloud.archetypes import (
        batch_etl, event_driven, ml_inference, static_site,
    )

    for module in (static_site, batch_etl, event_driven, ml_inference):
        _register(module)


_load()


def graph_for(name: str) -> ArchetypeGraph | None:
    return GRAPHS.get(name)


def implemented() -> frozenset[str]:
    """Shapes with a real, priced service graph."""
    return frozenset(GRAPHS)
