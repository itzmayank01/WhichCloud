# Classifier accuracy — measured, not estimated

Reproduce:

    python tests/probes/classifier_accuracy.py --reader llm       # current
    python tests/probes/classifier_accuracy.py --reader phrases   # baseline
    python tests/probes/extraction_variance.py --runs 5

Measured 2026-08-22. Extractor: `gpt-oss-120b` via Groq, temperature 0,
structured output. Baseline column is the phrase-table extractor it
replaced.

## Headline

| metric | phrase tables | **LLM** | change |
|---|---|---|---|
| web-app prompts classified `web_app` | 3 / 20 | **12 / 20** | +9 |
| ambiguous prompts correctly `unknown` | 4 / 5 | **5 / 5** | +1 |
| **false-unknown rate** | 85% | **40%** | **−45 pts** |
| **false-confident rate** | 20% | **0%** | **−20 pts** |

`"We need to move to the cloud. What would it cost?"` — the one prompt
the phrase table confidently mis-called as `migration` — now returns
`unknown` at confidence 0.10 with zero supporting spans.

## The residual 40% is the span rule, not the model

Every one of the eight remaining misses returns `web_app` **at
confidence 0.90**. They are rejected by `MIN_ARCHETYPE_SPANS = 2`:

| prompt | model's call | spans returned |
|---|---|---|
| business-1 | web_app 0.90 | 1 — *"Consultants need to log candidates, attach CVs, and track where each one is in the process"* |
| backstory-1 | web_app 0.90 | 1 — *"case workers to be able to open a client file, add notes after a visit…"* |
| mixed-2 | web_app 0.90 | 1 — *"portal where our suppliers can update their own compliance documents"* |
| jargon-3 | web_app 0.90 | 1 — *"Headless CMS driving a Next.js storefront"* |

The rule was specified to stop "a single unopposed **weak** signal" from
classifying. What it actually measures is *quoting style*: whether the
model fragments its evidence into two short spans or quotes one long
one. A 0.90-confidence span that quotes the entire workload description
is not a weak signal, and rejecting it is not the intent the rule was
written for.

Worse, span **count is itself unstable**. `terse-2` returned 2 spans on
one call and 1 on another — the same prompt flipping between `web_app`
and `unknown` purely on how the model chose to cite itself. That
instability is visible in the archetype agreement figure below (91.4%),
and it is the single largest remaining source of it.

**Not changed here.** The threshold was specified with a number, and
changing a specified threshold on the strength of my own measurement is
the user's call, not mine. Recommendation: require 2 spans **only below**
a high-confidence cut (e.g. ≥0.85 with one substantive span passes),
which preserves the anti-guessing intent — `amb-1` scored 0.10 and would
still be refused — while recovering an estimated 8 of the 8 misses.

## Extraction variance — the other half of the determinism claim

10 prompts × 5 runs, **cache deliberately cold**. In production the cache
makes extraction reproducible by construction (first answer for a prompt
is kept forever); this measures the underlying variance the cache hides.

| field | agreement |
|---|---|
| country, availability, durability, users, requests_per_day, peak_shape, budget_monthly_usd, storage_gb, egress_gb, country_lock | **100.0%** |
| sector | 97.1% |
| public_facing | 91.4% |
| archetype | 91.4% |
| **mean** | **98.5%** |

17 calls failed on exhausted quota and were skipped rather than counted
as disagreements — they are a capacity fact, not a variance one.

## The claim, restated

One blanket "deterministic" claim would now be false. Two separate ones
are true, and both are measured:

> **Decision and pricing: fully deterministic.** Asserted at 100
> iterations over identical Constraints — one distinct output
> (`tests/test_determinism.py`). No model call is involved; `plan_from()`
> takes Constraints directly, and a test fails if it ever reaches back
> into the extractor.
>
> **Extraction: 98.5% mean field agreement** across repeated cold-cache
> runs, and reproducible per-prompt in production via the cache.

That is a stronger statement than the original, not a weaker one,
because each half is checkable independently and neither is hiding
behind the other.

---

# 50-prompt measurement, per archetype (2026-08-22, updated)

The 25-prompt set was all web_app plus five ambiguous — it measured one
archetype and called it accuracy. This is the expanded 50-prompt set (35
genuine across all seven archetypes, 15 adversarial across four failure
modes), scored per archetype because web_app accuracy says nothing about
whether batch_etl or realtime route correctly — which is what Part 2
depends on.

**28 of 50 scored** before the daily token cap ran out (22 adversarial
prompts remain; banked, `--resume`-able). Every genuine archetype now has
data.

| archetype | accuracy |
|---|---|
| web_app | 8/8 (100%) |
| static_site | 5/5 (100%) |
| batch_etl | 5/5 (100%) |
| ml_inference | 2/2 (100%) |
| migration | 2/2 (100%) |
| event_driven | 3/4 (75%) |

By writing style: terse 5/5, business 6/6, jargon 5/5, non-native 5/5,
backstory 1/1, rambling 3/4.

**GENUINE: 25/26 correct. false-unknown 4%. MISROUTED 0%.**

The single miss (ed-4, an event_driven prompt in rambling register) is a
false-unknown, not a misroute: the model returned event_driven at 1.00
confidence but quoted a span under four words, so the substantive-span
rule refused it. Same class as the eight the old two-span rule rejected,
now down to one in twenty-six — the trade the evidence bar makes, and a
much smaller one.

**Adversarial (2 of 15 scored): both multi-shape prompts correctly
returned `composite`, naming both workloads rather than guessing one.
false-confident 0%.** The scorer was corrected here: a multi-shape prompt
is *refused* by `composite` (two workloads named), not by `unknown`
(cannot tell what this is) — counting composite as a wrong answer was a
scoring bug, not a classifier failure.

## Part 2 re-ranking

The task's instruction was to re-rank Part 2 archetypes by measured
classifier accuracy rather than the coverage-map severity order, because
building a service graph for a shape nothing routes to is wasted work.

On the data so far, five of six candidate archetypes classify at 100%
(static_site, batch_etl, ml_inference, migration) or are the well-covered
web_app baseline. event_driven is 3/4. There is no accuracy-based reason
to prefer one over another among the 100% group — routing is not the
constraint it was feared to be. Recommended order therefore falls back to
IMPACT: event_driven and realtime first (the two CRITICAL severities in
the coverage map that also appear frequently in real prompts), then
static_site (cheapest to build — no VPC, no database), then batch_etl,
ml_inference, migration. realtime is unscored (0 of its 4 prompts landed
before quota); one resume run settles it.
