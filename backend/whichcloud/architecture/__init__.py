"""Reading an architecture out of a description, and drawing it.

Distinct from `intake`, which reads the same text for a different purpose:
intake produces what the pricer needs and discards the rest, this keeps
everything the description named so there is something to draw.
"""

from whichcloud.architecture.schema import (
    Architecture,
    Boundary,
    Flow,
    Service,
    Tier,
    normalize_edges,
)

__all__ = ["Architecture", "Boundary", "Flow", "Service", "Tier", "normalize_edges"]
