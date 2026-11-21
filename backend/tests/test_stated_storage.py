"""A size the description states outright is not the model's to invent.

groq read "We keep about 2 TB of history" as 75,000 GB. Object storage came
out at 75,000 GB / $1,875, backup tracked it at 15,000 GB / $825, and the two
made 97% of a $2,783 estimate against a stated $600 budget -- for a workload
whose own description gives the figure in plain words.

The draft was cached, so the wrong answer was durable: every later visit with
that description got the same 75,000 back without a model being asked.

These tests pin the deterministic reader that now overrides the model, and
in particular the readings that must NOT happen: "16 GB" next to vCPU is
memory, and "500 GB egress" is traffic. Reading either as disk would be the
same class of error in the opposite direction.
"""

from __future__ import annotations

import pytest

from whichcloud.intake import stated_storage_gb


@pytest.mark.parametrize(
    "text,expected",
    [
        # The case that started it.
        ("We keep about 2 TB of history.", 2048.0),
        # Units, decimals, thousands separators.
        ("We store 500 GB of documents", 500.0),
        ("1.5 TB of archived records", 1536.0),
        ("We keep 2,048 GB of data", 2048.0),
        ("retention of 10 TB", 10240.0),
        ("a 1 PB data lake", 1048576.0),
        # TB is the whole point: the heuristic fallback's regex matched `gb`
        # only, so every description stating TB took a 50 GB default.
        ("roughly 4 TB of stored images", 4096.0),
    ],
)
def test_reads_a_stated_size(text: str, expected: float) -> None:
    got = stated_storage_gb(text)
    assert got is not None
    assert got == pytest.approx(expected, rel=0.01)


@pytest.mark.parametrize(
    "text",
    [
        # Memory, not disk. The dangerous one -- this phrasing appears in the
        # app's own compute summary ("1 × 4 vCPU / 16 GB arm64").
        "1 x 4 vCPU / 16 GB arm64",
        "servers with 32 GB RAM",
        "each node has 64 GB memory",
        # Traffic, not storage.
        "about 500 GB egress per month",
        "5 TB of data transfer out",
        "2 TB of bandwidth per month",
        # Nothing stated.
        "a reporting system for the finance team",
        "",
    ],
)
def test_does_not_invent_a_size(text: str) -> None:
    assert stated_storage_gb(text) is None


def test_takes_the_largest_stated_store() -> None:
    """Two stated stores means the estate is at least the larger of them;
    taking the first mention would under-size on a description that works up
    to its real figure."""
    assert stated_storage_gb(
        "We keep 200 GB of documents and about 3 TB of historical records"
    ) == pytest.approx(3072.0)


def test_ignores_memory_while_reading_a_real_store() -> None:
    assert stated_storage_gb(
        "Servers are 4 vCPU / 16 GB RAM, and we keep about 2 TB of history."
    ) == pytest.approx(2048.0)


# ── the wiring, not just the reader ──────────────────────────────────────
#
# The reader being right is half of it; the other half is that
# parse_description actually prefers it over the model, and that it does
# NOT start overriding descriptions that state nothing.


def _stub(storage_gb: float):
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from test_intake import FakeGeminiClient, FakeGeminiResponse, draft

    d = draft(assumed=["storage_gb"])
    d.storage_gb = storage_gb
    return FakeGeminiClient(FakeGeminiResponse(d))


BATCH_DESCRIPTION = (
    "Our sales data is loaded overnight from the till systems into a reporting "
    "database, and the finance team reads next-day reports each morning. Nobody "
    "uses it during the day. We keep about 2 TB of history. Budget is around "
    "$600 a month."
)


def test_a_stated_size_overrides_the_model() -> None:
    """The production failure, reproduced: groq returned 75,000 GB for a
    description whose own sentence says 2 TB."""
    from whichcloud.intake import parse_description

    intake = parse_description(BATCH_DESCRIPTION, provider="gemini", client=_stub(75_000.0))
    assert intake.requirement.storage_gb == pytest.approx(2048.0)


def test_a_stated_size_is_not_reported_as_an_assumption() -> None:
    """It was in `assumed`, which told the reader the one figure that was
    actually theirs had been invented."""
    from whichcloud.intake import parse_description

    intake = parse_description(BATCH_DESCRIPTION, provider="gemini", client=_stub(75_000.0))
    assert "storage_gb" not in intake.assumed


def test_the_model_still_decides_when_nothing_is_stated() -> None:
    """The override must not become a second guesser. A description with no
    size in it leaves the model's figure alone, still marked assumed."""
    from whichcloud.intake import parse_description

    intake = parse_description(
        "a reporting system for the finance team", provider="gemini", client=_stub(123.0)
    )
    assert intake.requirement.storage_gb == pytest.approx(123.0)
    assert "storage_gb" in intake.assumed


# ── the /describe path ───────────────────────────────────────────────────
#
# The first fix landed in intake.py, which /recommend uses. The UI does not:
# /describe routes through llm_extract into Constraints and plan.py, so the
# fix missed the only path a user actually takes. These cover that one.


BATCH_DESC = BATCH_DESCRIPTION  # same sentence, read by the other reader


def test_phrase_tables_convert_the_unit() -> None:
    """`_number_near` matched "tb " and then recorded the bare number, so
    "about 2 TB" became 2.0 GB -- a 1024x under-count from a reader that
    matched the unit and dropped it."""
    from whichcloud.constraints import extract

    c = extract(BATCH_DESC)
    assert c.storage_gb == pytest.approx(2048.0)
    assert "storage_gb" in c.stated


def test_a_stated_size_overrides_the_model_on_the_describe_path() -> None:
    """The production failure: the model answered 75,000 GB and marked it
    assumed, and nothing checked it against the sentence that says 2 TB."""
    from whichcloud.llm_extract import _apply_stated_sizes
    from whichcloud.constraints import Constraints

    c = Constraints()
    c.storage_gb = 75_000.0
    _apply_stated_sizes(BATCH_DESC, c)

    assert c.storage_gb == pytest.approx(2048.0)
    assert "storage_gb" in c.stated


def test_a_stated_total_clears_the_derived_splits() -> None:
    """content + user_data are added together by _default_storage_gb. Left
    alongside a stated total they pile invented data on top of the real
    figure."""
    from whichcloud.llm_extract import _apply_stated_sizes
    from whichcloud.constraints import Constraints

    c = Constraints()
    c.storage_gb = 75_000.0
    c.content_storage_gb = 250.0
    c.user_data_gb = 40.0
    _apply_stated_sizes(BATCH_DESC, c)

    assert c.content_storage_gb == 0.0
    assert c.user_data_gb == 0.0


def test_describe_path_leaves_an_unstated_description_alone() -> None:
    from whichcloud.llm_extract import _apply_stated_sizes
    from whichcloud.constraints import Constraints

    c = Constraints()
    c.storage_gb = 123.0
    _apply_stated_sizes("a reporting system for the finance team", c)

    assert c.storage_gb == pytest.approx(123.0)
    assert "storage_gb" not in c.stated


# ── per-run input vs the accumulated estate ──────────────────────────────
#
# batch_etl reads storage_gb as the volume of ONE run and multiplies it by
# 30 runs and a curated copy -- 37.5x. That is right for "500 GB of sensor
# readings [each night]" and wrong for "we keep about 2 TB of history",
# which IS the estate. The second priced 76,800 GB of object storage,
# $1,875/mo, 97% of the estimate.


@pytest.mark.parametrize(
    "text",
    [
        "We keep about 2 TB of history.",
        "about 3 TB of archived records",
        "we retain 4 TB of data in total",
    ],
)
def test_recognises_an_accumulated_total(text: str) -> None:
    from whichcloud.constraints import stated_size_is_retained_total

    assert stated_size_is_retained_total(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "500 GB of sensor readings each night",
        "we load 500 GB per run",
        # Explicit per-cycle phrasing wins even when a total word is present,
        # because it is the more specific statement.
        "2 TB of history, loaded 500 GB per night",
        "a reporting system with no sizes in it",
    ],
)
def test_does_not_treat_per_run_input_as_a_total(text: str) -> None:
    from whichcloud.constraints import stated_size_is_retained_total

    assert stated_size_is_retained_total(text) is False


def test_a_stated_total_is_not_multiplied_by_retention() -> None:
    from whichcloud.constraints import Constraints
    from whichcloud.archetypes import batch_etl

    c = Constraints()
    c.storage_gb = 2048.0
    c.storage_is_retained_total = True

    total = batch_etl._raw_gb(c) + batch_etl._curated_gb(c)
    assert total == pytest.approx(2048.0), "raw + curated must land on the stated figure"


def test_a_per_run_figure_still_accumulates() -> None:
    """The flag must not flatten the archetype's whole sizing model."""
    from whichcloud.constraints import Constraints
    from whichcloud.archetypes import batch_etl

    c = Constraints()
    c.storage_gb = 500.0  # per run, nothing said about a total

    total = batch_etl._raw_gb(c) + batch_etl._curated_gb(c)
    assert total == pytest.approx(500.0 * 30 * 1.25)
