# Service mappings — what genuinely corresponds, and what does not

Cross-cloud comparison is only meaningful over services that answer the
same question. This directory is the table that decides which those are,
and — more importantly — which they are not.

## The rule that shapes these files

**Where no true equivalent exists, say so.** A forced pairing is worse
than a gap, because a gap is visible and a forced pairing is not. The
comparison layer refuses to compare a service whose mapping is
`none`, and labels one whose mapping is `partial` rather than
silently substituting a rough analogue and presenting the difference as
a price difference.

That refusal is the point. The previous behaviour summed whatever each
cloud happened to price and ranked the totals, which put "$336" above
"$649" and called it the winner — when the $336 was lower because seven
of the twenty-one components had no adapter on that cloud, not because
anything was cheaper.

## Confidence labels

| label | meaning |
|---|---|
| `exact` | Same billing model, same operational shape. A like-for-like comparison is sound. |
| `close` | Same job, materially different billing or limits. Comparable, with the difference stated. |
| `partial` | Overlapping but not interchangeable. One side carries capability or cost the other does not. |
| `none` | No equivalent worth naming. The comparison must refuse rather than approximate. |

## Schema

```yaml
id: kebab-case
role: the question all three answer, in one line
aws:   { service: str, sku_category: str }
gcp:   { service: str, sku_category: str }   # or `null` when none exists
azure: { service: str, sku_category: str }
confidence: exact | close | partial | none
maps_cleanly: what genuinely corresponds
does_not_map: what does NOT, named specifically
```

`sku_category` is this catalog's own category, so a mapping claiming a
category the catalog does not carry fails a test rather than producing a
comparison against nothing.
