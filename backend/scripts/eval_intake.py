#!/usr/bin/env python3
"""Score the plain-English intake against hand-written expectations.

Shipping an LLM feature without a way to measure it is how you end up unable
to tell whether a prompt change helped. This runs every fixture in
tests/fixtures/intake_examples.py through Claude and reports per-field
accuracy, so a prompt edit can be judged rather than guessed at.

Only the fields each description genuinely determines are scored — see the
fixture file for why.

    export ANTHROPIC_API_KEY=...
    python scripts/eval_intake.py
    python scripts/eval_intake.py --only ecommerce-spiky
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fixtures.intake_examples import EXAMPLES  # noqa: E402
from whichcloud.intake import IntakeError, parse_description  # noqa: E402

BOLD, DIM, GREEN, YELLOW, RED, RESET = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m",
)


def actual_value(intake, field: str):
    req = intake.requirement
    if field == "compliance":
        return list(req.compliance)
    if field == "provider_preference":
        return req.provider_preference or "none"
    return getattr(req, field)


def matches(expected, actual) -> bool:
    if isinstance(expected, list):
        return sorted(map(str.upper, expected)) == sorted(
            map(str.upper, actual or [])
        )
    if isinstance(expected, float):
        # Volumes are approximations in prose ("about 8 TB"); accept 10%.
        if actual is None:
            return False
        return abs(float(actual) - expected) <= max(expected * 0.1, 0.01)
    return expected == actual


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="run a single example by id")
    args = ap.parse_args()

    cases = [e for e in EXAMPLES if not args.only or e["id"] == args.only]
    if not cases:
        print(f"{RED}No example named {args.only!r}{RESET}")
        return 1

    print(f"\n{BOLD}WhichCloud · intake evaluation{RESET}")
    print(f"{DIM}{len(cases)} descriptions, scoring only the fields each one "
          f"actually determines{RESET}\n")

    total_fields = 0
    correct_fields = 0
    failures = 0

    for case in cases:
        print(f"{BOLD}{case['id']}{RESET}")
        print(f"  {DIM}{case['description'][:88]}…{RESET}")

        try:
            intake = parse_description(case["description"])
        except IntakeError as exc:
            print(f"  {RED}✗ {exc}{RESET}\n")
            failures += 1
            continue

        wrong = []
        for field, expected in case["expected"].items():
            total_fields += 1
            actual = actual_value(intake, field)
            if matches(expected, actual):
                correct_fields += 1
            else:
                wrong.append((field, expected, actual))

        scored = len(case["expected"])
        hit = scored - len(wrong)
        colour = GREEN if not wrong else YELLOW
        print(f"  {colour}{hit}/{scored} fields{RESET}")
        for field, expected, actual in wrong:
            print(f"    {RED}{field}: expected {expected!r}, got {actual!r}{RESET}")

        if intake.assumed:
            print(f"  {DIM}assumed: {', '.join(intake.assumed)}{RESET}")
        if intake.clarifying_question:
            print(f"  {DIM}asks: {intake.clarifying_question}{RESET}")
        print()

    if not total_fields:
        print(f"{RED}Nothing scored.{RESET}")
        return 1

    pct = correct_fields / total_fields * 100
    print(f"{BOLD}{'─' * 66}{RESET}")
    print(f"{BOLD}{correct_fields}/{total_fields} fields correct ({pct:.0f}%){RESET}")
    if failures:
        print(f"{RED}{failures} description(s) failed outright{RESET}")

    if pct >= 90 and not failures:
        print(f"{GREEN}✓ Intake is extracting reliably.{RESET}\n")
        return 0
    if pct >= 75:
        print(f"{YELLOW}⚠ Usable, but the prompt needs tuning.{RESET}\n")
        return 0
    print(f"{RED}✗ Extraction is not reliable enough to build on.{RESET}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
