"""No price or rate may be written in the cost path.

Every figure on a bill is supposed to come from the catalog, which is the
whole argument for this tool over a language model guessing. A rate written
in code looks identical to one that was ingested, reads as authoritative, and
goes stale silently the day the provider changes it -- there is no ingest to
notice, and no `fetched_at` to show.

This guards the class rather than the instances: it reads the source, so a
rate added tomorrow fails here without anyone remembering to check.

It deliberately does NOT object to sizing heuristics. RPS_PER_VCPU and
LAMBDA_AVG_MS are statements about a workload, not about a price list -- no
cloud publishes how many requests a vCPU serves, so those cannot come from a
catalog and are labelled as heuristic elsewhere. The line this draws is
between what a PROVIDER charges and what this engine assumes.
"""

import ast
import pathlib
import re

COST_PATH = ("estimator.py", "engine.py", "pricing/store.py")

#: Values that are arithmetic, not prices: identities, an epsilon used for
#: quantisation, and the mean days in a month.
ALLOWED = {"0", "1", "0.00000001", "30.4"}


def _sources():
    root = pathlib.Path(__file__).resolve().parents[1] / "whichcloud"
    for name in COST_PATH:
        yield name, (root / name).read_text()


def test_no_decimal_price_literals_in_the_cost_path():
    """Decimal("0.0446") in code is a rate the catalog should have supplied."""
    offenders = []
    for name, src in _sources():
        for node in ast.walk(ast.parse(src)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Decimal"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                raw = str(node.args[0].value)
                if raw not in ALLOWED:
                    offenders.append(f"{name}:{node.lineno} Decimal({raw!r})")
    assert not offenders, (
        "these look like rates written in code rather than read from the "
        f"price catalog: {offenders}"
    )


def test_no_variable_named_like_a_price_is_assigned_a_literal():
    """`unit_price = 0.045` is the same bug with a different shape."""
    pattern = re.compile(
        r"^\s*\w*(price|rate|usd|cost)\w*\s*=\s*[\d.]+\s*(#.*)?$", re.I
    )
    offenders = [
        f"{name}:{i} {line.strip()}"
        for name, src in _sources()
        for i, line in enumerate(src.splitlines(), 1)
        if pattern.match(line)
    ]
    assert not offenders, (
        f"prices must come from the catalog, not from source: {offenders}"
    )
