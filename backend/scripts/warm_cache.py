#!/usr/bin/env python3
"""Pre-extract prompts into the constraints cache.

Written because every provider was quota-exhausted the day before a
demonstration, and the phrase-table fallback misses 85% of phrasings --
so an unwarmed live demo would either refuse everything or answer from
the reader that was replaced for being wrong.

Warming is not a cache optimisation here. It is how a demonstration
becomes reproducible: once a prompt is in the cache, its extraction is
fixed forever (first answer wins), so the plan shown on stage is the
plan that was rehearsed, regardless of what any provider does that
morning.

    python scripts/warm_cache.py                    # fixtures + probes + demo
    python scripts/warm_cache.py --prompt "..."     # one ad-hoc prompt
    python scripts/warm_cache.py --check            # report coverage only
    python scripts/warm_cache.py --export FILE      # dump cache to JSON
    python scripts/warm_cache.py --import FILE      # load a dumped cache
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whichcloud import llm_extract  # noqa: E402
from whichcloud.pricing import store  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
PROBES = ROOT / "tests" / "probes"
CACHE_EXPORT = ROOT / "tests" / "warm_cache.json"

#: Prompts a demonstration is likely to reach for that are not already a
#: fixture. Kept here rather than in a doc so warming them is one command
#: and cannot drift from what is actually shown.
DEMO_PROMPTS: list[tuple[str, str]] = [
    ("demo-hospital",
     "I manage IT for a 3-hospital group in Pune. We want to move patient "
     "appointments, records and lab reports online so doctors and front desk "
     "can access them from all three sites. About 450 staff use it, roughly "
     "6,000 record lookups a day, with peaks in the morning. Patient data "
     "must stay inside India and cannot be lost. Downtime during OPD hours "
     "is unacceptable. Budget is about $900 a month."),
    ("demo-startup",
     "We're a two-person startup building a booking site for yoga studios. "
     "Maybe 40 studios and 5,000 customers to start. We can't afford much, "
     "under $100 a month if possible."),
    ("demo-scaleup",
     "Our B2B analytics dashboard has grown to 900 customer accounts and "
     "about 300,000 API calls a day. Peaks during US business hours. We're "
     "on a single server and it's creaking. Budget is flexible, maybe "
     "$2,500 a month."),
    ("demo-migration",
     "We run 40 virtual machines in our own server room, a mix of Windows "
     "and Linux, some with attached storage. We want to move them to the "
     "cloud as-is before modernising later."),
    ("demo-vague",
     "We need to move to the cloud. What would it cost?"),
]


def _fixture_prompts() -> list[tuple[str, str]]:
    out = []
    for directory in (FIXTURES, PROBES):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            fx = yaml.safe_load(path.read_text())
            if not isinstance(fx, dict) or "prompt" not in fx:
                continue
            out.append((fx["id"], fx["prompt"]))
    return out


def _is_cached(prompt: str) -> bool:
    try:
        return store.cached_constraints(llm_extract.cache_key(prompt)) is not None
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prompt", help="warm a single ad-hoc prompt")
    ap.add_argument("--check", action="store_true", help="report coverage, warm nothing")
    ap.add_argument("--export", metavar="FILE", nargs="?", const=str(CACHE_EXPORT))
    ap.add_argument("--import", dest="import_", metavar="FILE", nargs="?",
                    const=str(CACHE_EXPORT))
    args = ap.parse_args()

    if args.import_:
        rows = json.loads(Path(args.import_).read_text())
        for row in rows:
            store.cache_constraints(
                row["key"], row["description"], row["reader"], row["model"],
                row["schema_version"], json.dumps(row["payload"]),
            )
        print(f"Imported {len(rows)} cached extraction(s) from {args.import_}")
        return 0

    targets = (
        [("ad-hoc", args.prompt)] if args.prompt
        else _fixture_prompts() + DEMO_PROMPTS
    )

    if args.export:
        rows = []
        for name, prompt in targets:
            key = llm_extract.cache_key(prompt)
            payload = store.cached_constraints(key)
            if payload is None:
                print(f"  ! {name}: not cached, skipped")
                continue
            rows.append({
                "key": key, "description": prompt,
                "reader": llm_extract.PRIMARY_PROVIDER,
                "model": llm_extract.PRIMARY_MODEL,
                "schema_version": llm_extract.SCHEMA_VERSION,
                "payload": json.loads(payload),
            })
        Path(args.export).write_text(json.dumps(rows, indent=2) + "\n")
        print(f"Exported {len(rows)} cached extraction(s) to {args.export}")
        return 0

    warmed = cached = failed = 0
    for name, prompt in targets:
        if _is_cached(prompt):
            cached += 1
            print(f"  = {name}: already cached")
            continue
        if args.check:
            failed += 1
            print(f"  ! {name}: NOT CACHED")
            continue
        try:
            _c, meta = llm_extract.extract(prompt, allow_fallback=False)
            warmed += 1
            flag = " [FAILOVER]" if meta.failover else ""
            print(f"  + {name}: {meta.archetype} via {meta.reader}{flag}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ! {name}: {type(exc).__name__} {str(exc)[:110]}")

    print(f"\n{cached} already cached, {warmed} newly warmed, {failed} failed.")
    if args.check and failed:
        print("Run without --check while a model is reachable to warm these.")
    return 1 if failed and not args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
