# Classifier accuracy — measured, not estimated

Run `python tests/probes/classifier_accuracy.py` to reproduce. Measured
2026-08-22 against the phrase-table classifier in `whichcloud/archetype.py`.

## Headline

| metric | value |
|---|---|
| web-app prompts classified `web_app` | **3 / 20** |
| ambiguous prompts correctly `unknown` | 4 / 5 |
| **false-unknown rate** (priceable workloads wrongly refused) | **85%** |
| **false-confident rate** (underdetermined workloads confidently named) | **20%** |

## What this measures

Removing the `web_app` fallback was correct — it was a silent default
wearing a disclaimer. But it moved the risk rather than removing it.
Before, an unrecognised prompt got a confident wrong bill; now it gets a
refusal. That trade is only acceptable if refusals are *rare* for
workloads the engine can genuinely price.

They are not. **85% of real web-app descriptions are refused.**

Every prompt the classifier had been tested on until now was written by
whoever was also writing the phrase table, which measures nothing. These
20 were written to defeat it, across six registers.

## The miss list, by register

| register | hit rate | what it missed on |
|---|---|---|
| terse | 0/3 | "Job board. 5k listings. Postgres." — names the tech, never the shape |
| rambling | 0/2 | workload appears once, mid-paragraph, in the user's own words |
| jargon-heavy | 2/3 | hit on "SaaS"/"storefront"; missed "stateless microservice fleet" |
| non-native phrasing | 0/3 | "they will do login and see their bill" |
| business language | 0/4 | "consultants need to log candidates, attach CVs" |
| workload buried in backstory | 0/3 | real requirement is sentence 4 of 5 |
| mixed register | 1/2 | hit "portal"; missed "upload a photo of a receipt" |

The phrase each miss *would* have needed is printed by the script. They
are **not** patched in — patching them would make this number measure how
well the table fits 20 prompts someone already showed it, which is the
exact mistake the measurement exists to prevent.

Note the shape of that list: twenty prompts produced twenty different
near-misses, with almost no overlap. That is the argument. The tail is
not long, it is unbounded — every real user writes their own phrasing,
and a table can only ever contain phrasings someone already thought of.

## The one false-confident

`"We need to move to the cloud. What would it cost?"` → **`migration`**,
on a single matched phrase (`"move to the cloud"`), unopposed.

It is not wrong that the phrase appears. It is wrong that one weak signal
with nothing to compete against clears the bar — the prompt never says
what is being moved, and "we need to move to the cloud" is how a great
many people open *any* infrastructure conversation. The tie rule catches
two-signal ambiguity; it cannot catch one-signal underdetermination.

## What this is evidence for

The recorded follow-up — replacing the phrase-table extractor with an
LLM extractor at temperature 0 returning the Constraints schema as
structured output — is no longer a nice-to-have. At an 85% false-unknown
rate the current classifier refuses roughly six of every seven genuine
web-app workloads, which makes the engine unusable for its own primary
archetype however correct its pricing is.

The decision layer is already structured to accept that swap: `classify()`
takes the raw description and returns `(archetype, evidence)`, and
nothing downstream of it reads the phrase tables. Two caveats from the
earlier structural review still stand — `build_load()`, `_requires_x86()`
and `network_topology.decide()` each still read the raw description
directly for their own gates, so a full swap means promoting those
signals into `Constraints` fields too.
