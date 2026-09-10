"""What corresponds across clouds, and what refuses to.

A cross-cloud total is only meaningful over services that answer the same
question. This module loads the equivalence table and gives the
comparison layer one thing to ask: may these two be compared, and with
what caveat.

WHY THE REFUSAL MATTERS MORE THAN THE MAPPING.
The previous behaviour summed whatever each cloud happened to price and
ranked the totals. AWS priced twenty-one components; Azure and GCP had
adapters for seven. So their totals were lower for a reason that had
nothing to do with being cheaper, and the ranking put "$336" above "$649"
and called it the winner. `comparableTotals` in the frontend already
worked around this by intersecting line items -- but an intersection is a
guess about equivalence made from label text, and this table is the
actual answer.

A service with confidence `none` is not compared. A service with
`partial` is compared with its caveat attached. Neither is silently
substituted, because a forced pairing is invisible in a way a gap is not.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "knowledge-base" / "service-mappings"

#: Comparison is sound at these levels. `partial` still compares, but the
#: caveat travels with the number.
COMPARABLE = frozenset({"exact", "close", "partial"})

#: Levels that carry a warning the interface must show.
CAVEATED = frozenset({"close", "partial"})

_LEVELS = ("exact", "close", "partial", "none")


class MappingError(ValueError):
    """A malformed mapping file. Never swallowed -- a comparison table
    that fails to load must stop the comparison, not quietly allow every
    pairing."""


@dataclass(frozen=True, slots=True)
class Mapping:
    id: str
    role: str
    confidence: str
    maps_cleanly: str
    does_not_map: str
    #: provider -> (service name, catalog category). A provider absent
    #: from this dict has no equivalent worth naming.
    services: dict[str, tuple[str, str]]

    @property
    def comparable(self) -> bool:
        return self.confidence in COMPARABLE

    @property
    def caveated(self) -> bool:
        return self.confidence in CAVEATED

    def covers(self, provider: str) -> bool:
        return provider in self.services

    def category(self, provider: str) -> str:
        entry = self.services.get(provider)
        return entry[1] if entry else ""


def _parse(entry: dict, path: Path) -> Mapping:
    for field in ("id", "role", "confidence"):
        if field not in entry:
            raise MappingError(f"{path.name}: a mapping is missing {field!r}")
    confidence = str(entry["confidence"]).strip().lower()
    if confidence not in _LEVELS:
        raise MappingError(
            f"{path.name}: {entry['id']}: confidence {confidence!r} is not "
            f"one of {_LEVELS}"
        )

    services: dict[str, tuple[str, str]] = {}
    for provider in ("aws", "gcp", "azure"):
        block = entry.get(provider)
        if not block:
            continue  # explicitly no equivalent
        if not isinstance(block, dict) or "service" not in block:
            raise MappingError(
                f"{path.name}: {entry['id']}: {provider} must be null or a "
                f"mapping with a `service`"
            )
        services[provider] = (
            str(block["service"]),
            str(block.get("sku_category", "")),
        )

    # A mapping claiming full equivalence while naming fewer than all
    # three providers is contradicting itself.
    if confidence in ("exact", "close") and len(services) < 3:
        raise MappingError(
            f"{path.name}: {entry['id']}: confidence {confidence!r} claims a "
            f"clean mapping but names only {sorted(services)}. Use `partial` "
            f"or `none`."
        )
    if confidence == "none" and len(services) > 1:
        raise MappingError(
            f"{path.name}: {entry['id']}: confidence 'none' means no "
            f"equivalent, but {sorted(services)} are named"
        )
    if confidence != "none" and not entry.get("does_not_map"):
        raise MappingError(
            f"{path.name}: {entry['id']}: every comparable mapping must say "
            f"what does NOT map. A mapping with no caveat has not been "
            f"thought about."
        )

    return Mapping(
        id=str(entry["id"]),
        role=str(entry["role"]).strip(),
        confidence=confidence,
        maps_cleanly=str(entry.get("maps_cleanly", "")).strip(),
        does_not_map=str(entry.get("does_not_map", "")).strip(),
        services=services,
    )


@lru_cache(maxsize=1)
def load(directory: str | None = None) -> tuple[Mapping, ...]:
    """Every mapping. A malformed file stops the load."""
    path = Path(directory) if directory else DEFAULT_DIR
    if not path.is_dir():
        return ()
    out: list[Mapping] = []
    for file in sorted(path.glob("*.yaml")):
        try:
            doc = yaml.safe_load(file.read_text()) or {}
        except yaml.YAMLError as exc:
            raise MappingError(f"{file.name}: invalid YAML — {exc}") from exc
        for entry in doc.get("mappings") or []:
            out.append(_parse(entry, file))
    return tuple(out)


def by_category(provider: str, category: str) -> Mapping | None:
    """The mapping covering one provider's catalog category."""
    for mapping in load():
        if mapping.category(provider) == category and category:
            return mapping
    return None


@dataclass(frozen=True, slots=True)
class Verdict:
    """Whether two clouds may be compared on one service, and why not."""

    comparable: bool
    confidence: str
    reason: str
    caveat: str = ""


def may_compare(category: str, providers: tuple[str, ...]) -> Verdict:
    """Whether this catalog category may be compared across providers.

    An UNMAPPED category refuses. That is deliberate and is the stricter
    of the two possible defaults: a category nobody has written a mapping
    for is one nobody has checked the equivalence of, and comparing it
    would be exactly the silent substitution this table exists to stop.
    """
    mapping = None
    for provider in providers:
        mapping = mapping or by_category(provider, category)
    if mapping is None:
        return Verdict(
            comparable=False,
            confidence="unmapped",
            reason=(
                f"{category!r} has no cross-cloud mapping, so there is "
                f"nothing establishing that these clouds' versions of it "
                f"answer the same question. Compared totals would differ "
                f"for a reason that is not price."
            ),
        )
    if not mapping.comparable:
        missing = [p for p in providers if not mapping.covers(p)]
        return Verdict(
            comparable=False,
            confidence=mapping.confidence,
            reason=(
                f"{mapping.role} has no equivalent on "
                f"{', '.join(missing) or 'one of these clouds'}. "
                f"{mapping.does_not_map}"
            ),
        )
    missing = [p for p in providers if not mapping.covers(p)]
    if missing:
        return Verdict(
            comparable=False,
            confidence=mapping.confidence,
            reason=(
                f"{mapping.role} is not priced on {', '.join(missing)} in "
                f"this catalog, so a total including it is not like-for-like."
            ),
        )
    return Verdict(
        comparable=True,
        confidence=mapping.confidence,
        reason="",
        caveat=mapping.does_not_map if mapping.caveated else "",
    )


def coverage() -> dict:
    """What the table covers, for the interface to report honestly."""
    entries = load()
    return {
        "total": len(entries),
        "by_confidence": {
            level: sum(1 for m in entries if m.confidence == level)
            for level in _LEVELS
        },
        "no_equivalent": [
            {"id": m.id, "role": m.role, "why": m.does_not_map}
            for m in entries if m.confidence == "none"
        ],
    }
