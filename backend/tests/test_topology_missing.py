"""Unpriced components must still reach the diagram.

Estimate.missing is prose written for a person to read, so recovering a node
kind from it is a mapping problem, not a substring-of-the-kind-name problem.
When that mapping is wrong nothing raises -- the component just vanishes from
the architecture, which is the failure these tests exist to catch.
"""

import pytest

from whichcloud.topology import _kind_for_missing


@pytest.mark.parametrize(
    "missing,kind",
    [
        # The four that were silently dropped: none of them contain the name
        # of the kind they belong to.
        ("egress", "network"),
        ("load balancer", "loadbalancer"),
        ("cache 2vCPU/2GB", "cache"),
        ("monitoring", "monitoring"),
        # And the two that always worked.
        ("database 2vCPU/8GB", "database"),
        ("object storage", "storage"),
    ],
)
def test_every_gap_maps_to_a_node(missing, kind):
    assert _kind_for_missing(missing) == kind


def test_object_storage_is_not_swallowed_by_the_bare_storage_rule():
    # "object storage" contains "storage"; order in the phrase table decides
    # which wins, and both must land on the same node anyway.
    assert _kind_for_missing("object storage") == "storage"
    assert _kind_for_missing("storage") == "storage"


def test_unknown_phrases_are_refused_rather_than_guessed():
    assert _kind_for_missing("quantum entanglement service") is None
    assert _kind_for_missing("") is None
