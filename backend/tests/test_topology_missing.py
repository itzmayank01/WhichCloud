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


def test_every_label_the_estimator_can_emit_maps_to_a_kind():
    """The mapping is checked against its SOURCE, not against a hand-kept list.

    The tests above name six labels. The estimator can emit fifty-one, and
    fourteen of them mapped to nothing -- CDN, the event bus, the search
    cluster, websocket connections -- so those components were priced, found
    to be unpriceable, and then silently dropped before the diagram, which is
    precisely the failure this module's docstring describes. A hand-written
    list could not catch that, because the same person who forgets the mapping
    forgets to add the label to the list.

    So the list is derived: walk estimator.py's AST for every literal appended
    to `result.missing`, and require each one to resolve. Adding a new gap
    without teaching the diagram about it now fails here, without anyone
    remembering to come back.

    Non-literal labels (f-strings carrying a size, e.g. "compute 2vCPU/8GB")
    are deliberately out of scope: their PREFIX is what the matcher keys on,
    and the prefixes are covered by the literal cases above.
    """
    import ast
    import pathlib

    source = pathlib.Path(__file__).resolve().parents[1] / "whichcloud" / "estimator.py"
    tree = ast.parse(source.read_text())

    labels: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "append"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "missing"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            labels.add(node.args[0].value)

    assert len(labels) > 40, (
        f"only found {len(labels)} labels; the AST walk has stopped matching "
        "how the estimator reports gaps, so this test would pass vacuously"
    )

    unmapped = sorted(label for label in labels if _kind_for_missing(label) is None)
    assert not unmapped, (
        "these labels reach the interface but map to no diagram node, so the "
        "component vanishes from the architecture instead of appearing "
        f"unpriced: {unmapped}"
    )
