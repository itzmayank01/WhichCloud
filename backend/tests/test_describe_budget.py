"""/describe must report affordability, not silently drop the budget.

A workload stating "Budget is around $600 a month" was shown a $5,331/mo
architecture as the recommended PICK on /terraform. Two defects stacked up:

  * describe_route built every Option without `spec_budget`, so
    Option.within_budget -- which is derived from it -- returned None for
    every option the route produced, whatever the user had asked for. The
    budget was extracted by the planner and then dropped.

  * The interface treated that None as "affordable" and picked the dearest
    option, so an unknown budget actively upsold the most expensive design.

These cover the backend half: the budget reaches the response, and
affordability is answered as a real boolean rather than None.

A note for anyone reading the commit that introduced this file: it claims
the production LLM extractor returned "no budget" for text that plainly
states one. That is wrong, and it is wrong because of a mistake in the
probe used to investigate, which read budget_monthly_usd from a nested
"requirement" object that the response does not have, and so saw None for
a field that was present all along. Re-checked against production: the
extractor reads 600.0 from this description correctly, via groq. There is
no extraction bug to chase. The only backend defect was the dropped
spec_budget tested below.

The over-budget case uses an absurdly small budget on purpose. Asserting
"$600 does not buy this" would depend on the size of the ingested catalog
and would pass or fail by accident on a developer machine with only the
115-point fallback table; nothing priceable fits in $1, on any catalog.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from whichcloud.api import app
from whichcloud.pricing.store import stats

pytestmark = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)

client = TestClient(app)

REPORTING = (
    "Our sales data is loaded overnight from the till systems into a "
    "reporting database, and the finance team reads next-day reports each "
    "morning. Nobody uses it during the day. We keep about 2 TB of history. "
)


def _describe(description: str, provider: str = "azure") -> dict:
    res = client.post("/describe", json={"description": description, "provider": provider})
    assert res.status_code == 200, res.text
    return res.json()


def test_stated_budget_reaches_the_response():
    body = _describe(REPORTING + "Budget is around $600 a month.")
    assert body["budget_monthly_usd"] == pytest.approx(600.0)


def test_every_option_answers_affordability_when_a_budget_is_given():
    """None means "no budget given". With one given, it is a real answer."""
    body = _describe(REPORTING + "Budget is around $600 a month.")
    assert body["options"], "expected priced options"
    for opt in body["options"]:
        assert opt["within_budget"] is not None, (
            f"{opt['label']} reports within_budget=None though a budget was "
            "stated -- spec_budget was not passed to the Option"
        )
        assert isinstance(opt["within_budget"], bool)


def test_an_unaffordable_budget_is_reported_as_over():
    """Nothing priceable fits in $1, so every option must say so."""
    body = _describe(REPORTING + "Budget is around $1 a month.")
    assert body["budget_monthly_usd"] == pytest.approx(1.0)
    assert body["options"], "expected priced options"
    for opt in body["options"]:
        assert opt["within_budget"] is False, (
            f"{opt['label']} at {opt['monthly_usd']}/mo claims to fit a $1 budget"
        )


def test_no_stated_budget_still_leaves_affordability_unknown():
    """The tri-state matters: without a budget there is nothing to answer."""
    body = _describe(REPORTING + "We have not set a budget yet.")
    for opt in body["options"]:
        assert opt["within_budget"] is None
