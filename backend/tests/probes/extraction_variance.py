"""Measure what moving extraction to a model actually costs in stability.

The decision layer's determinism is ASSERTED (tests/test_determinism.py,
100 iterations, one distinct output). Extraction's cannot be -- it is a
property of a model, not of this code -- so it is MEASURED here instead,
per field, with the cache deliberately cold.

Reporting these as two separate statements is more honest than one
blanket "deterministic" claim, and it is the only version that survives
contact with how the system actually works:

    decision and pricing : fully deterministic
    extraction           : X% field agreement across repeated runs

Cache OFF on purpose. In production the cache makes extraction
reproducible by construction -- the first answer for a prompt is the one
kept forever. This measures the underlying variance the cache is hiding,
which is the number worth knowing when deciding how much to trust a
first read.

    python tests/probes/extraction_variance.py [--runs 5]
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from whichcloud.constraints import REQUIRED  # noqa: E402
from whichcloud.llm_extract import extract  # noqa: E402

from classifier_accuracy import AMBIGUOUS_PROMPTS, WEB_APP_PROMPTS  # noqa: E402

FIELDS = REQUIRED + ("country_lock",)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0, help="first N prompts only")
    args = ap.parse_args()

    prompts = [(pid, text) for pid, _style, text in WEB_APP_PROMPTS]
    prompts += [(pid, text) for pid, text in AMBIGUOUS_PROMPTS]
    if args.limit:
        prompts = prompts[: args.limit]

    # field -> [agreement fraction per prompt]
    agreement: dict[str, list[float]] = {f: [] for f in FIELDS}
    archetype_agreement: list[float] = []
    failures = 0

    for pid, text in prompts:
        observations: list[dict] = []
        for _ in range(args.runs):
            try:
                c, m = extract(text, use_cache=False, allow_fallback=False)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  ! {pid}: {type(exc).__name__} {str(exc)[:90]}")
                continue
            observations.append(
                {f: repr(getattr(c, f)) for f in FIELDS} | {"__archetype": m.archetype}
            )
        if len(observations) < 2:
            continue

        for f in FIELDS:
            counts = Counter(o[f] for o in observations)
            agreement[f].append(counts.most_common(1)[0][1] / len(observations))
        counts = Counter(o["__archetype"] for o in observations)
        archetype_agreement.append(counts.most_common(1)[0][1] / len(observations))
        print(f"  {pid:14s} archetype {counts.most_common(1)[0][0]:14s} "
              f"{counts.most_common(1)[0][1]}/{len(observations)}")

    print("\n" + "=" * 70)
    print(f"EXTRACTION VARIANCE — {len(prompts)} prompts x {args.runs} runs, cold cache")
    print("=" * 70)
    print(f"{'field':22s} {'agreement':>10s}")
    print("-" * 34)
    overall = []
    for f in FIELDS:
        if not agreement[f]:
            continue
        rate = 100.0 * sum(agreement[f]) / len(agreement[f])
        overall.append(rate)
        print(f"{f:22s} {rate:9.1f}%")
    if archetype_agreement:
        arch_rate = 100.0 * sum(archetype_agreement) / len(archetype_agreement)
        print(f"{'archetype':22s} {arch_rate:9.1f}%")
        overall.append(arch_rate)
    if overall:
        print("-" * 34)
        print(f"{'MEAN':22s} {sum(overall)/len(overall):9.1f}%")
    if failures:
        print(f"\n{failures} call(s) failed and were skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
