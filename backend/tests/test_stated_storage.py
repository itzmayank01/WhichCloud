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
