"""Part 4: measure the classifier's false-unknown rate.

Removing the web_app fallback was correct -- it was a silent default
wearing a disclaimer -- but it moved the risk. Before, an unrecognised
prompt got a confident wrong bill. Now it gets a refusal. That is
strictly better, and it is only acceptable if refusals are RARE for
workloads the engine genuinely can price.

Every prompt tested up to now was written by whoever was also writing
the phrase table, which measures nothing. These 25 are written to defeat
it: terse, rambling, jargon-heavy, non-native phrasings, pure business
language with no technical vocabulary, and workloads buried in backstory.

The misses are NOT to be patched into the phrase table. Patching them
would make this number meaningless -- it would measure how well the
table fits 20 prompts someone already showed it, which is the exact
mistake this file exists to stop making. The miss list is evidence for
the LLM-extractor decision, and the percentages are what goes in the
project report.

    python tests/probes/classifier_accuracy.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from whichcloud.archetype import UNKNOWN, classify  # noqa: E402
from whichcloud.llm_extract import extract  # noqa: E402


def _classify(prompt: str, use_llm: bool) -> tuple[str, str]:
    """Either reader, same interface, so the two are directly comparable."""
    if not use_llm:
        return classify(prompt)
    _c, meta = extract(prompt, use_cache=True, allow_fallback=False)
    return meta.archetype, (
        f"confidence {meta.archetype_confidence:.2f}, "
        f"{len(meta.archetype_spans)} span(s): {meta.archetype_spans[:3]}"
    )

#: 20 workloads that ARE web apps -- request-serving, database-backed,
#: the one shape this engine can actually price. Every one of these
#: SHOULD classify web_app. Styles are labelled so the miss list can say
#: which register of writing the table fails on, not just which prompt.
WEB_APP_PROMPTS: list[tuple[str, str, str]] = [
    ("terse-1", "terse",
     "Job board. 5k listings. Postgres. Need pricing."),
    ("terse-2", "terse",
     "CRUD app, 200 daily actives, MySQL, London."),
    ("terse-3", "terse",
     "Need to host a customer support ticketing system for 40 agents."),
    ("rambling-1", "rambling",
     "So we've been running our little community group for about six years "
     "now and everything has been on spreadsheets which frankly is a "
     "nightmare, people email me changes and I copy them across, and we "
     "finally got a grant so we want something proper where members can "
     "sign in and see their own details and renew, maybe 3,000 members, "
     "nothing fancy, we're in Manchester."),
    ("rambling-2", "rambling",
     "My brother-in-law set up our original system years ago and it's been "
     "limping along, it's a thing where our drivers log what they picked "
     "up and dropped off, and then the office can look at it later and "
     "invoice from it. Around 60 drivers. It falls over about once a month "
     "and we lose a day of entries which causes arguments with customers."),
    ("jargon-1", "jargon-heavy",
     "Multi-tenant B2B SaaS, REST API + SPA frontend, Postgres with "
     "row-level security, RBAC, ~800 tenants, target p95 under 300ms, "
     "SOC2 on the roadmap."),
    ("jargon-2", "jargon-heavy",
     "Stateless microservice fleet behind an ALB, service mesh, blue/green "
     "deploys, RDS Aurora backing store, 12k RPM sustained."),
    ("jargon-3", "jargon-heavy",
     "Headless CMS driving a Next.js storefront, ISR, Redis session store, "
     "Stripe integration, roughly 90k monthly actives."),
    ("nonnative-1", "non-native phrasing",
     "We are making one system for our society members, they will do login "
     "and see their bill and pay online. Total members near about 12,000. "
     "Server should not go down at month end when everyone is paying."),
    ("nonnative-2", "non-native phrasing",
     "Sir, we need the online system for our coaching institute. Students "
     "will login, see the test result, download the material. Around 4000 "
     "students are there. Budget is low only."),
    ("nonnative-3", "non-native phrasing",
     "We want make software for our transport company office use. Staff "
     "will enter the trip details daily and manager will check. Maybe 80 "
     "staff. It must work in Dubai and India both office."),
    ("business-1", "business language, no technical terms",
     "We're a recruitment agency and we want to stop paying for the "
     "off-the-shelf product we use. Consultants need to log candidates, "
     "attach CVs, and track where each one is in the process. 35 "
     "consultants, and it needs to be available whenever they're working."),
    ("business-2", "business language, no technical terms",
     "Our members need somewhere to submit their annual returns and see "
     "what they've submitted before. About 9,000 members submit once a "
     "year, mostly in the last two weeks before the deadline."),
    ("business-3", "business language, no technical terms",
     "We run a small chain of veterinary practices and want one place for "
     "all the animal records instead of each branch keeping its own. Six "
     "branches, around 70 staff between them."),
    ("business-4", "business language, no technical terms",
     "We need somewhere for our franchisees to place their weekly stock "
     "orders and see what they've been invoiced. 120 franchisees."),
    ("backstory-1", "workload buried in backstory",
     "I took over IT here in March after the previous person left "
     "suddenly. The board has been talking about digitising for three "
     "years and nothing happened. There's a lot of politics about which "
     "department owns what. Anyway, what we actually need is for our case "
     "workers to be able to open a client file, add notes after a visit, "
     "and have the supervisor sign it off. About 200 case workers."),
    ("backstory-2", "workload buried in backstory",
     "We got burned by a consultancy last year who quoted us a fortune and "
     "delivered a prototype that didn't work, so the finance director is "
     "sceptical about the whole thing. I need to go back with a realistic "
     "number. The thing itself is not complicated: our reps place orders "
     "on behalf of customers and the warehouse picks from that list. "
     "Around 400 orders a day."),
    ("backstory-3", "workload buried in backstory",
     "Long story short, our current provider is being acquired and they've "
     "told us the product is end-of-life in 18 months. It handles bookings "
     "for our studios — customers pick a class, pay, and get a reminder. "
     "About 15,000 bookings a month across nine locations."),
    ("mixed-1", "mixed register",
     "Internal expenses thing. People upload a photo of a receipt, it goes "
     "to their manager, manager approves, finance exports it monthly. "
     "~500 employees. Can't be down at month end."),
    ("mixed-2", "mixed register",
     "Looking to build a portal where our suppliers can update their own "
     "compliance documents rather than emailing them to us. Roughly 600 "
     "suppliers, each updating a handful of documents a year."),
]

#: 5 prompts that SHOULD be unknown -- genuinely underdetermined, or
#: balanced between two shapes. A classifier that confidently names one
#: of these is guessing, and guessing is what the refusal path exists to
#: prevent.
AMBIGUOUS_PROMPTS: list[tuple[str, str]] = [
    ("amb-1", "We need to move to the cloud. What would it cost?"),
    ("amb-2", "Something modern and scalable, budget around $2,000 a month."),
    ("amb-3",
     "We have some data and we need to do something with it. Not sure "
     "what yet, exploring options."),
    ("amb-4",
     "Our systems are a mess and we want to start again properly. There "
     "are several different things involved."),
    ("amb-5",
     "It needs to handle files, and also send things out, and there's a "
     "reporting side to it as well."),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--reader", choices=("llm", "phrases"), default="llm")
    args = ap.parse_args()
    use_llm = args.reader == "llm"

    print("=" * 78)
    print(f"CLASSIFIER ACCURACY ({args.reader}) — false-unknown / false-confident")
    print("=" * 78)

    misses: list[tuple[str, str, str, str]] = []
    correct = 0
    print("\n--- 20 web-app prompts (should classify web_app) ---\n")
    for pid, style, prompt in WEB_APP_PROMPTS:
        got, evidence = _classify(prompt, use_llm)
        ok = got == "web_app"
        correct += ok
        mark = "  ok " if ok else "MISS "
        print(f"{mark} {pid:14s} {style:34s} -> {got}")
        if not ok:
            misses.append((pid, style, got, prompt))

    amb_correct = 0
    false_confident: list[tuple[str, str]] = []
    print("\n--- 5 ambiguous prompts (should classify unknown) ---\n")
    for pid, prompt in AMBIGUOUS_PROMPTS:
        got, evidence = _classify(prompt, use_llm)
        ok = got == UNKNOWN
        amb_correct += ok
        mark = "  ok " if ok else "WRONG"
        print(f"{mark} {pid:8s} -> {got:16s} {evidence}")
        if not ok:
            false_confident.append((pid, got))

    n_web, n_amb = len(WEB_APP_PROMPTS), len(AMBIGUOUS_PROMPTS)
    false_unknown_rate = 100.0 * (n_web - correct) / n_web
    false_confident_rate = 100.0 * len(false_confident) / n_amb

    if misses:
        print("\n--- misses: what each fell to, and the phrase that would "
              "have caught it ---")
        print("    (NOT to be patched in -- see this file's docstring)\n")
        for pid, style, got, prompt in misses:
            print(f"  {pid} [{style}] -> {got}")
            print(f"     would need: {_suggested_phrase(prompt)}")

    print("\n" + "=" * 78)
    print(f"web-app prompts classified web_app : {correct}/{n_web}")
    print(f"ambiguous prompts returning unknown: {amb_correct}/{n_amb}")
    print(f"FALSE-UNKNOWN RATE   : {false_unknown_rate:.0f}%  "
          f"(priceable workloads wrongly refused)")
    print(f"FALSE-CONFIDENT RATE : {false_confident_rate:.0f}%  "
          f"(underdetermined workloads confidently named)")
    print("=" * 78)
    return 0


def _suggested_phrase(prompt: str) -> str:
    """The phrase a human would add to catch this one. Printed as
    evidence of how open-ended the tail is -- twenty prompts produced
    twenty different near-misses -- not as a patch list."""
    lowered = prompt.lower()
    for candidate in (
        "log candidates", "submit their annual returns", "animal records",
        "place their weekly stock orders", "open a client file",
        "place orders", "bookings for our studios", "upload a photo of a receipt",
        "update their own compliance", "see their bill", "see the test result",
        "enter the trip details", "job board", "crud app", "ticketing system",
        "members can sign in", "log what they picked up", "multi-tenant",
        "microservice", "headless cms",
    ):
        if candidate in lowered:
            return repr(candidate)
    return "(no single obvious phrase — the workload is only implied)"


if __name__ == "__main__":
    raise SystemExit(main())
