"""The Azure pricing adapter's 429 backoff, which never ran.

`_paged` retries a rate-limited Retail Prices response with exponential
backoff -- except `time` was never imported in that module, so the moment
Azure answered 429 the retry raised

    NameError: name 'time' is not defined

instead of sleeping. The handler was dead code in both of its branches:
the status-code check and the HTTPStatusError except clause.

It stayed hidden because it only fires when Azure actually rate-limits,
which is intermittent -- CI passed for weeks and then failed on a run
that happened to get a 429. The same path is what the weekly price
ingestion walks, so a rate-limited ingest crashed rather than backing
off.

These tests drive the retry without network and without sleeping.
"""

from __future__ import annotations

import httpx
import pytest

from whichcloud.pricing import azure


class _Response:
    def __init__(self, status: int, payload: dict | None = None) -> None:
        self.status_code = status
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.invalid/prices")
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=request, response=self  # type: ignore[arg-type]
            )

    def json(self) -> dict:
        return self._payload


def _client_returning(responses: list[_Response], seen: list[int]):
    """An httpx.Client stand-in that hands back `responses` in order."""

    class _Client:
        def __init__(self, *_a, **_k) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_a) -> bool:
            return False

        def get(self, _url, params=None):
            seen.append(1)
            return responses[min(len(seen) - 1, len(responses) - 1)]

    return _Client


@pytest.fixture
def no_sleep(monkeypatch):
    """Record the backoff instead of serving it, so the test is instant."""
    slept: list[float] = []
    monkeypatch.setattr(azure.time, "sleep", slept.append)
    return slept


def test_a_rate_limited_page_is_retried_instead_of_raising(monkeypatch, no_sleep):
    """The regression itself: before `import time`, this raised NameError."""
    seen: list[int] = []
    page = {"Items": [{"skuName": "S1"}], "NextPageLink": None}
    monkeypatch.setattr(
        azure.httpx,
        "Client",
        _client_returning([_Response(429), _Response(200, page)], seen),
    )

    assert list(azure._paged("anything")) == [{"skuName": "S1"}]
    assert len(seen) == 2, "the 429 was not retried"
    assert no_sleep == [1.0]


def test_the_backoff_is_exponential_and_bounded(monkeypatch, no_sleep):
    """Three 429s back off 1s, 2s, 4s; the fourth attempt is the last."""
    seen: list[int] = []
    page = {"Items": [{"skuName": "S2"}], "NextPageLink": None}
    monkeypatch.setattr(
        azure.httpx,
        "Client",
        _client_returning(
            [_Response(429), _Response(429), _Response(429), _Response(200, page)],
            seen,
        ),
    )

    assert list(azure._paged("anything")) == [{"skuName": "S2"}]
    assert no_sleep == [1.0, 2.0, 4.0]


def test_a_429_that_never_clears_is_raised_not_retried_forever(monkeypatch, no_sleep):
    """After the fourth attempt the 429 is allowed through as an error.
    A retry loop with no exit is worse than a failure that says so."""
    seen: list[int] = []
    monkeypatch.setattr(
        azure.httpx, "Client", _client_returning([_Response(429)], seen)
    )

    with pytest.raises(httpx.HTTPStatusError):
        list(azure._paged("anything"))
    assert no_sleep == [1.0, 2.0, 4.0], "backed off the wrong number of times"


def test_a_non_429_error_is_not_retried(monkeypatch, no_sleep):
    """Backoff is for rate limiting. Retrying a 400 just delays the error."""
    seen: list[int] = []
    monkeypatch.setattr(
        azure.httpx, "Client", _client_returning([_Response(400)], seen)
    )

    with pytest.raises(httpx.HTTPStatusError):
        list(azure._paged("anything"))
    assert no_sleep == []
    assert len(seen) == 1
