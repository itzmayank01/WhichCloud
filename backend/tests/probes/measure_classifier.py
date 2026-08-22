#!/usr/bin/env python3
"""Score the classifier over the 50-prompt set, per archetype.

An overall figure hides the thing that matters for Part 2: web_app
accuracy says nothing about whether batch_etl or realtime classify, and
those are what the next six archetypes depend on being routed to.

    python tests/probes/measure_classifier.py                 # LLM
    python tests/probes/measure_classifier.py --reader phrases
    python tests/probes/measure_classifier.py --resume        # skip cached

Every call is cached, so a run interrupted by a token budget can be
resumed without re-spending what it already paid for.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from whichcloud.archetype import UNKNOWN, classify  # noqa: E402
from whichcloud import llm_extract  # noqa: E402

from measurement_set import ADVERSARIAL, GENUINE  # noqa: E402

RESULTS_PATH = Path(__file__).parent / "measurement_results.json"


def _classify(prompt: str, use_llm: bool) -> tuple[str, float, str]:
    if not use_llm:
        name, why = classify(prompt)
        return name, 0.0, why
    _c, meta = llm_extract.extract(prompt, use_cache=True, allow_fallback=False)
    return meta.archetype, meta.archetype_confidence, meta.evidence_verdict


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reader", choices=("llm", "phrases"), default="llm")
    ap.add_argument("--report-only", action="store_true",
                    help="reprint from measurement_results.json, no calls")
    ap.add_argument("--resume", action="store_true",
                    help="skip prompts already scored in measurement_results.json")
    args = ap.parse_args()
    use_llm = args.reader == "llm"

    prior = {}
    if (args.resume or args.report_only) and RESULTS_PATH.exists():
        prior = json.loads(RESULTS_PATH.read_text()).get(args.reader, {})
    if args.report_only:
        _report(prior, args.reader, 0)
        return 0

    rows: dict[str, dict] = dict(prior)
    unreachable = 0

    print(f"=== GENUINE ({len(GENUINE)}) — reader={args.reader} ===\n")
    for pid, truth, style, prompt in GENUINE:
        if pid in rows:
            continue
        try:
            got, conf, why = _classify(prompt, use_llm)
        except Exception as exc:  # noqa: BLE001
            unreachable += 1
            print(f"  ! {pid}: {str(exc)[:80]}")
            continue
        rows[pid] = {"truth": truth, "got": got, "style": style,
                     "confidence": conf, "why": why, "kind": "genuine"}
        mark = "ok  " if got == truth else ("UNK " if got == UNKNOWN else "WRONG")
        print(f"  {mark} {pid:6s} {truth:13s} -> {got:15s} {conf:.2f}")

    print(f"\n=== ADVERSARIAL ({len(ADVERSARIAL)}) — should be unknown ===\n")
    for pid, mode, prompt in ADVERSARIAL:
        if pid in rows:
            continue
        try:
            got, conf, why = _classify(prompt, use_llm)
        except Exception as exc:  # noqa: BLE001
            unreachable += 1
            print(f"  ! {pid}: {str(exc)[:80]}")
            continue
        # A multi-shape prompt describes two workloads, so the correct
        # refusal is COMPOSITE (name both), not UNKNOWN (cannot tell what
        # this is). Every other adversarial mode should be UNKNOWN.
        want = "composite" if mode == "multi-shape" else UNKNOWN
        rows[pid] = {"truth": want, "got": got, "style": mode,
                     "confidence": conf, "why": why, "kind": "adversarial"}
        mark = "ok  " if got == want else "WRONG"
        print(f"  {mark} {pid:6s} {mode:17s} -> {got:15s} {conf:.2f}")

    _report(rows, args.reader, unreachable)

    stored = json.loads(RESULTS_PATH.read_text()) if RESULTS_PATH.exists() else {}
    stored[args.reader] = rows
    RESULTS_PATH.write_text(json.dumps(stored, indent=2, sort_keys=True) + "\n")
    print(f"\nWrote {RESULTS_PATH}")
    return 0


def _report(rows: dict[str, dict], reader: str, unreachable: int) -> None:
    genuine = {k: v for k, v in rows.items() if v["kind"] == "genuine"}
    adversarial = {k: v for k, v in rows.items() if v["kind"] == "adversarial"}

    print("\n" + "=" * 72)
    print(f"CLASSIFIER ACCURACY — {reader}, {len(rows)} prompt(s) scored")
    print("=" * 72)

    by_arch: dict[str, list[bool]] = defaultdict(list)
    for v in genuine.values():
        by_arch[v["truth"]].append(v["got"] == v["truth"])
    print(f"\n{'archetype':16s} {'correct':>9s} {'accuracy':>9s}")
    print("-" * 38)
    for arch in sorted(by_arch):
        hits = by_arch[arch]
        print(f"{arch:16s} {sum(hits):>4}/{len(hits):<4} "
              f"{100.0*sum(hits)/len(hits):>8.0f}%")

    by_style: dict[str, list[bool]] = defaultdict(list)
    for v in genuine.values():
        by_style[v["style"]].append(v["got"] == v["truth"])
    print(f"\n{'style':20s} {'correct':>9s}")
    print("-" * 32)
    for style in sorted(by_style):
        hits = by_style[style]
        print(f"{style:20s} {sum(hits):>4}/{len(hits):<4}")

    def _refused(v):
        # multi-shape is refused by composite; others by unknown.
        return v["got"] == v["truth"]
    by_mode: dict[str, list[bool]] = defaultdict(list)
    for v in adversarial.values():
        by_mode[v["style"]].append(_refused(v))
    if by_mode:
        print(f"\n{'adversarial mode':20s} {'refused':>9s}")
        print("-" * 32)
        for mode in sorted(by_mode):
            hits = by_mode[mode]
            print(f"{mode:20s} {sum(hits):>4}/{len(hits):<4}")

    if genuine:
        correct = sum(v["got"] == v["truth"] for v in genuine.values())
        false_unknown = sum(v["got"] == UNKNOWN for v in genuine.values())
        misrouted = len(genuine) - correct - false_unknown
        print(f"\n{'GENUINE':22s} {correct}/{len(genuine)} correct")
        print(f"{'  false-unknown':22s} {100.0*false_unknown/len(genuine):.0f}%"
              "   (priceable workload refused)")
        print(f"{'  MISROUTED':22s} {100.0*misrouted/len(genuine):.0f}%"
              "   (named as the WRONG shape — worse than a refusal)")
    if adversarial:
        refused = sum(_refused(v) for v in adversarial.values())
        print(f"{'ADVERSARIAL':22s} {refused}/{len(adversarial)} refused")
        print(f"{'  false-confident':22s} "
              f"{100.0*(len(adversarial)-refused)/len(adversarial):.0f}%")
    if unreachable:
        print(f"\n{unreachable} prompt(s) unscored — no model reachable. "
              "Re-run with --resume when quota returns.")


if __name__ == "__main__":
    raise SystemExit(main())
