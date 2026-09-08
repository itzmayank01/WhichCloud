"""A number the description stated must never vanish on the way in.

The audit's only possible output is a refusal, which is what makes its
unit table safe to be incomplete: a unit it does not know costs an
unnecessary price, never a wrong one. These tests hold that line in both
directions -- it must catch a dropped figure, and it must not cry wolf
over a figure that was read into some other field than the obvious one.
"""

from __future__ import annotations

from whichcloud.constraints import Constraints
from whichcloud.quantity_audit import audit, describe


def test_a_dropped_machine_count_is_caught():
    """The defect verbatim: "40 virtual machines" with nowhere to land."""
    c = Constraints()  # source_vm_count defaults to 0
    found = audit(
        "We run 40 virtual machines in our own server room, a mix of "
        "Windows and Linux.", c,
    )
    families = {u["family"] for u in found}
    assert "machines" in families
    machine = next(u for u in found if u["family"] == "machines")
    assert machine["value"] == 40


def test_a_read_machine_count_is_not_flagged():
    c = Constraints(source_vm_count=40)
    found = audit("We run 40 virtual machines in our own server room.", c)
    assert not [u for u in found if u["family"] == "machines"]


def test_a_dropped_storage_figure_is_caught():
    """"500 GB of sensor readings" left storage_gb at 0.0."""
    c = Constraints()
    found = audit(
        "Every night we pull about 500 GB of sensor readings off our "
        "factory machines.", c,
    )
    assert "storage" in {u["family"] for u in found}


def test_storage_read_into_a_sibling_field_is_accepted():
    """A storage figure may legitimately land in content_storage_gb or a
    migration's source_disk_gb_total. Flagging those would make this
    table second-guess a correct extraction, which is precisely the
    load-bearing role it must not take on."""
    for field_name in ("storage_gb", "content_storage_gb", "user_data_gb",
                       "source_disk_gb_total", "egress_gb"):
        c = Constraints(**{field_name: 500.0})
        found = audit("about 500 GB of readings", c)
        assert not [u for u in found if u["family"] == "storage"], field_name


def test_visitors_a_month_counts_as_a_request_quantity():
    """"30,000 visitors a month" is a stated volume however it is
    phrased. Reading it as nothing is how a live site got sized at the
    zero-traffic floor."""
    c = Constraints()
    found = audit("About 30,000 visitors a month, mostly from India.", c)
    requests = [u for u in found if u["family"] == "requests"]
    assert requests and requests[0]["value"] == 30000


def test_scale_words_are_honoured():
    """A bare "2" for "2 million requests" undercounts by six orders of
    magnitude, which is the error this whole layer exists not to make."""
    c = Constraints()
    found = audit("We serve 2 million requests a day.", c)
    requests = [u for u in found if u["family"] == "requests"]
    assert requests and requests[0]["value"] == 2_000_000


def test_a_number_far_from_its_noun_is_not_claimed():
    """The gap is capped so a figure in one clause and a noun three
    clauses later is not welded together. Over-matching here produces
    refusals nobody can act on."""
    c = Constraints()
    found = audit(
        "We have 3 offices, and after a long discussion about the "
        "roadmap and the budget and the timeline, we agreed on servers.",
        c,
    )
    assert not [u for u in found if u["family"] == "machines"]


def test_a_clean_description_produces_nothing():
    c = Constraints(users=450, requests_per_day=6000, storage_gb=200.0)
    assert audit(
        "450 staff run about 6,000 lookups a day against 200 GB of records.",
        c,
    ) == []


def test_the_message_names_what_was_dropped():
    """A refusal the reader cannot act on is barely better than a guess."""
    c = Constraints()
    found = audit("We run 40 virtual machines.", c)
    message = describe(found)
    assert "40 virtual machines" in message
    assert describe([]) == ""
