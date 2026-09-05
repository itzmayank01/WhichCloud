# WhichCloud audit

    cd backend && .venv/bin/python -m audit

Architecture correctness and cost accuracy are scored **separately**, because
they are independent failures. A correct architecture can be priced wrong; a
wrong architecture can be priced perfectly. One number hides which of the two
is broken.

## Phases

| module | what it answers |
|---|---|
| `phase0_triage` | Is the resolver deriving architectures, or emitting a template? |
| `phase0_sensitivity` | Does adding one clause to a description move the shape? |
| `phase1_architecture` | How far are we from the vendors' published references? |
| `phase2_cost` | Does the arithmetic between rate and total hold? |
| `phase3_consistency` | Seven checks needing no external reference. |
| `phase3_drivers` | Which LINE drives each C3 and C6 failure. |
| `phase3_inversion` | Is any tier dearer at a lower budget? |
| `__main__` | The scorecard. |

## Two things to know before reading a score

**Intake is cached.** `audit/.intake-cache.json` holds the extracted
requirement per fixture. The audit has to run descriptions through the real
model path -- that is the half of the pipeline in question -- but
re-extracting every run costs money and introduces model drift that is
indistinguishable from a code regression. Delete the file or pass `--refresh`
to re-extract.

**Phase 2 does not compare against the vendor calculators**, and the module
docstring says why at length. Briefly: a saved-estimate URL cannot be
fabricated, and this catalog is ingested from the same pricing APIs the
calculators are built on, so most of that comparison would re-test the ingest.
What it tests instead is the arithmetic between rate and total, which is where
estimates actually go wrong.

## Adding a fixture

1. Add it to `fixtures/requirements.py` with `forbidden` and `required` roles.
   Both matter: an audit that only checks for presence cannot catch a default
   leaking in.
2. Add `fixtures/architecture/<ID>-<name>.json` with the expected role set per
   provider and a **live** source URL for each. An expected value with no
   source is a guess, and worse than no test.
3. Map any new node kind in `roles.py`. Unmapped kinds are reported as
   `?kind`, never silently ignored.
