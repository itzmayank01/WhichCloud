# Knowledge Base — the moat

This directory is the only part of WhichCloud you cannot download from GitHub.
Everything else (Infracost, diagrams, Claude, Postgres) is off-the-shelf.
**This is the project.**

## What lives here

- `techniques/` — one YAML file per optimization technique
- `service-mappings/` — AWS ↔ GCP ↔ Azure service equivalents

## Technique schema

Each entry answers four questions the engine needs:
**What is it? When does it apply? What does it save? How do I adopt it?**

```yaml
id: kebab-case-unique-id
name: Human readable name
category: compute | storage | network | database | memory | orchestration
summary: One sentence a non-expert understands.

applies_when:            # engine matches these against the Requirement Object
  workload_type: [web, api, batch]
  traffic_pattern: [spiky]
  min_monthly_spend_usd: 50

savings:
  typical_pct: 30        # realistic, not best-case
  confidence: high | medium | low
  basis: Where this number comes from — cite a source.

tradeoffs:               # be honest; this is what builds trust
  - Requires ARM-compatible container images

implemented_by:          # the "repo" idea — the actual tool
  - name: Karpenter
    url: https://github.com/aws/karpenter
    type: tool | kernel-feature | managed-service

providers: [aws, gcp, azure]
obviousness: low | medium | high   # low = the good stuff nobody knows
```

## Curation rules

1. **Honest savings numbers.** `typical_pct` is what a real user gets, not the vendor's headline.
2. **Always list tradeoffs.** A technique with no downside is a technique you haven't understood.
3. **Prefer `obviousness: low`.** Rightsizing is table stakes. zram is why someone uses us.
4. **Every entry needs `implemented_by`.** Advice without a tool is not actionable.
5. **Cite the basis** for savings claims so they're defensible in review.

## Target for v1

20–30 entries. Quality over quantity — each one hand-verified.
