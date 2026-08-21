# Coverage map — six shapes the engine has never been shown

Diagnosis only. Nothing in `whichcloud/` changed to produce this file. All
six probes were run through `whichcloud.plan.build()` unmodified, on
2026-08-21, against the current `main` (commit `537138c` and this
session's uncommitted probe files only).

**Headline finding: `plan.py` has exactly one shape.** Every probe below —
a static brochure site, a nightly batch job, an event queue, an ML
endpoint, a WebSocket chat backend, a VM lift-and-shift — comes back as
some variation of *EC2/Fargate compute in front of an RDS-family
relational database*, because that is the only spec `_spec_for()` knows
how to build. The engine's own `archetype` field (added last task)
correctly says `unknown` on all six, every time, for the same reason:
none of the six prompts state a `requests_per_day` figure the extractor
recognizes, so there is no evidence this is a request-serving web/API
workload — and it prices one anyway. `archetype: unknown` is an honest,
accurate signal. It is also a *generic* one: it never says *which* shape
would fit, and on four of six probes something else in the output (a
false-positive HA trigger, a stated reliability promise going unmatched,
a fully-costed line item) makes the wrong bill look more considered, not
less — actively working against the reader noticing the note.

---

## PROBE-1 — static-site

> Marketing site for our design studio. About 30,000 visitors a month,
> mostly from India. It's just pages and images, no login, no database.
> We want it cheap.

**shape_expected:** S3 + CloudFront + Route 53. No VPC, no NAT, no database.

### Constraints (stated vs assumed)

| field | value | source | evidence |
|---|---|---|---|
| country | `IN` | **stated** | named 'india' |
| sector | `other` | assumed | — |
| availability | `low` | assumed | — |
| durability | `normal` | assumed | — |
| users | `0` | assumed | — |
| requests_per_day | `0` | assumed | — |
| peak_shape | `flat` | assumed | — |
| budget_monthly_usd | `0.0` | assumed | — |
| storage_gb | `0.0` | assumed | — |
| egress_gb | `0.0` | assumed | — |
| public_facing | `True` | **stated** | 'visitor' |

`country_lock`: False.

### Sizing

avg_rps **0.0000**, peak_rps **0.0000**, load_tier **trivial**. "30,000
visitors a month" never reaches the rate model — no unit in the
requests_per_day phrase table matches "visitors" (or "visits" attached to
"a month" rather than "a day"), so the entire sizing basis is the
zero-traffic floor, not a low-but-nonzero rate.

`load.included`: `['network', 'waf']` — CDN and WAF both gate on
(fired because public_facing=True and, for CDN, the description's
"images" plausibly reads as a static-asset signal).
`network_topology`: **public_simple** — correctly no NAT, no VPC flow logs.
`archetype`: **unknown** — "no request volume was stated... review before use."

### Components produced, per tier

**Tier 1 — $73.61/mo:** Compute×1 ($16.35), **Database** ($15.33), Object
storage ($12.50), Egress ($10.93), Monitoring ($9.00), Gateway endpoints
(free), WAF Web ACL + rules ($8.00), Audit logging ($0), TLS ($0), DNS
zone ($0.50), KMS ($1.00).

**Tier 2 — $121.53/mo:** same, minus standalone EC2 (moved to Fargate),
plus CDN data transfer ($10.90), Secrets, Threat detection ×2, Tracing,
Security posture.

**Tier 3 — $121.53/mo:** identical to Tier 2 (no pattern diff — `no_further_improvement` fires; this workload never crosses a rung the engine has a further move for).

### Assessment

**WRONG_SHAPE.** No S3 static-website hosting concept exists in this
engine; "Object storage $12.50" is generic S3 storage priced alongside a
running compute instance and a relational database, not a
CloudFront-fronted static site. The user said "no login, no database" in
plain words and was billed $15.33/mo for a database and $16.35/mo for a
compute instance to serve *pages and images*.

**First wrong decision:** `plan.build()` calls `_spec_for()`
unconditionally. There is no point in the pipeline — including after
`_classify_archetype()` returns `unknown` — where the engine can choose
*not* to build the compute+RDS shape. The architecture is fixed before
extraction runs; only its size and add-ons vary.

**Severity: HIGH.** The bill is modest and `archetype: unknown` is
present and accurate; a reader who checks the note is warned, even if
weakly.

---

## PROBE-2 — batch-etl

> Every night we pull about 500 GB of sensor readings off our factory
> machines and turn them into next-day reports. Nobody uses it during the
> day. If a night's run fails we can rerun it in the morning.

**shape_expected:** S3 + Glue or Batch + Step Functions + Athena.
Scheduled, not always-on. No load balancer.

### Constraints

| field | value | source | evidence |
|---|---|---|---|
| country | `''` | assumed | — |
| sector | `other` | assumed | — |
| availability | `low` | assumed | — |
| durability | `normal` | assumed | — |
| users | `0` | assumed | — |
| requests_per_day | `0` | assumed | — |
| peak_shape | `morning` | **stated** | 'morning' |
| budget_monthly_usd | `0.0` | assumed | — |
| storage_gb | `500.0` | **stated** | '500 gb of' |
| egress_gb | `0.0` | assumed | — |
| public_facing | `False` | assumed | — |

`peak_shape=morning` is itself a small mis-tag: "morning" matched because
"reports" are produced overnight and consumed the next morning, but the
peak-shape multiplier this field drives (×10) is meant for a live
traffic curve, not a once-a-night batch run — the field exists to answer
a question this workload doesn't have an answer to.

### Sizing

avg_rps **0.0**, peak_rps **0.0**, load_tier **trivial**.
`load.included`: `[]` — nothing gated on. Notably, `_ASYNC_HINTS`
includes "batch", "overnight", "scheduled job" — but the prompt text says
"every night" and "next-day reports", never the literal words "batch" or
"overnight", so `asynchronous` stays False and "Message queue: not added
... nothing ... is asynchronous, batched or long-running" is the recorded
(accurate-to-its-own-logic, wrong-in-substance) reason.
`network_topology`: public_simple. `archetype`: unknown.

### Components produced, per tier

**Tier 1 — $65.61/mo:** Compute×1 (**730 hours, $16.35** — billed for
the full month, not the ~1-2 hours/night this job actually runs),
Database ($15.33), Object storage ($12.50, correctly reflecting the
500GB stated), Egress ($10.93), Monitoring ($9.00), the usual zero-cost
governance lines.

**Tier 2/3 — $102.63/mo:** adds Fargate (still full-month billing),
Secrets, Threat detection, Tracing, Security posture.

### Assessment

**WRONG_SHAPE.** A continuously-running server plus a relational database
for a job that executes once nightly and is otherwise idle 22+ hours a
day. `ArchitectureSpec.compute_duty_cycle` — *"Fraction of the month
compute actually runs. 1.0 = always on. Scale-to-zero lowers this."* —
exists specifically for this case and is never set by `plan.py`; every
spec it builds defaults to `1.0`. The field to represent this workload
correctly is already built and already priced correctly by the
estimator; nothing in the decision layer ever reaches for it.

**First wrong decision:** same single-shape point as Probe 1, compounded
by `compute_duty_cycle` sitting unused.

**Severity: HIGH.** `archetype: unknown` is present; no false-positive
amplifier pushes this one further.

---

## PROBE-3 — event-webhook

> We receive payment webhooks from three providers, roughly 40,000 a day
> in unpredictable bursts. Each one triggers a few database writes and an
> email. We cannot drop a single one.

**shape_expected:** API Gateway + SQS + Lambda + DynamoDB or RDS. Queue is
the durability mechanism.

### Constraints

| field | value | source | evidence |
|---|---|---|---|
| country | `''` | assumed | — |
| sector | `fintech` | **stated** | 'payment' |
| availability | `low` | assumed | — |
| durability | `normal` | **assumed — see below** | — |
| users | `0` | assumed | — |
| requests_per_day | `0` | assumed | — |
| peak_shape | `spiky` | **stated** | 'burst' |
| budget_monthly_usd | `0.0` | assumed | — |
| storage_gb | `0.0` | assumed | — |
| egress_gb | `0.0` | assumed | — |
| public_facing | `False` | assumed | — |

**The load-bearing miss is `durability`.** The prompt states, in plain
English, "we cannot drop a single one" — an explicit, unambiguous
reliability promise. `_DURABILITY_HIGH` matches "cannot be lost", "must
not lose", "cannot lose" — not "cannot drop". The phrase never fires.
`durability` is classified `normal`/assumed, indistinguishable in the
output from a workload that never mentioned reliability at all. Every
rung-1 durability control this engine actually has — backup,
cross-region copy, object lock — stays off as a direct consequence.

### Sizing

avg_rps **0.0**, peak_rps **0.0**, load_tier **trivial**. "40,000 a day"
is never captured: no unit word in the requests_per_day phrase table
matches "webhooks", and the number sits three words away from "a day"
with no attached noun the extractor looks for.
`network_topology`: public_simple (a direct consequence of the missed
durability signal — the topology gate reads `durability == normal` as
one of its three qualifying conditions). `archetype`: unknown.

### Components produced, per tier

**Tier 1 — $65.61/mo:** Compute×1, Database, Object storage, Egress,
Monitoring, the usual zero-cost lines. **No queue. No backup. No
cross-region copy.**

**Tier 2/3 — $102.63/mo:** adds Fargate, Secrets, Threat detection,
Tracing, Security posture. Still no queue, no durability controls.

### Assessment

**WRONG_SHAPE**, and the more consequential failure of the six so far:
this is not just an architecture mismatch, it is a stated hard
requirement — "cannot drop a single one" — silently and completely
unmet, with nothing in the output specifically calling that out. (It
surfaces only as one more `low`-confidence entry in `assumed_fields`,
generic and indistinguishable from every other unstated field.)

**First wrong decision:** two, compounding. (a) No event-ingestion shape
exists in the codebase — `ArchitectureSpec` has `stream_shards` (Kinesis)
and `kafka_broker_count` (MSK) as real, priced fields, and `plan.py`
never sets either; there is no SQS/Lambda/API Gateway path at all. (b)
`_DURABILITY_HIGH` doesn't recognize "cannot drop" — a synonym gap in
the same phrase table already flagged for gaps last session ("cannot
lose" is there; "cannot drop" is not).

**Severity: CRITICAL.** The bill is plausible and complete-looking. The
one thing the user explicitly said must never happen (dropping an event)
has no protection in the design and no specific warning saying so.

---

## PROBE-4 — ml-inference

> We have a trained model that scores loan applications. About 50
> predictions a second during business hours, almost none at night.

**shape_expected:** SageMaker endpoint or GPU/inference instances with
autoscaling.

### Constraints

| field | value | source | evidence |
|---|---|---|---|
| country | `''` | assumed | — |
| sector | `fintech` | **stated** | 'loan' |
| availability | `high` | **stated — false positive, see below** | 'business hours' |
| durability | `normal` | assumed | — |
| users | `0` | assumed | — |
| requests_per_day | `0` | assumed | — |
| peak_shape | `evening` | **stated** | 'night' |
| budget_monthly_usd | `0.0` | assumed | — |
| storage_gb | `0.0` | assumed | — |
| egress_gb | `0.0` | assumed | — |
| public_facing | `False` | assumed | — |

**`availability=high` is a false positive.** "50 predictions a second
during business hours" describes *when load is high*, not an uptime/SLA
promise — but `_AVAILABILITY_HIGH` contains the bare phrase "business
hours" with no way to distinguish "must stay up during business hours"
from "is busiest during business hours". The two meanings collide on one
phrase.

### Sizing

avg_rps **0.0**, peak_rps **0.0**, load_tier **trivial**. "50 predictions
a second" is never captured as a rate — there is no unit word for
"predictions" in the phrase table, and even if there were, the extractor
has no path from "N per second" to `requests_per_day` (it only parses
daily/monthly figures). A workload whose defining number is a per-second
rate is read as having stated no volume at all.

### Components produced, per tier

**Tier 1 — $235.60/mo:** Compute×2 ($32.70), **Database Multi-AZ**
($30.66), Object storage, Egress, Monitoring, **Load balancer** ($17.45),
**NAT gateway×2** ($81.76 + $5.60 processing), VPC flow logs ($33.50),
governance lines. `network_topology`: **private_standard** — "availability=high" is the stated reason.

**Tier 2/3 — $302.33/mo:** same shape on Fargate, plus Secrets, Threat
detection, Tracing, Security posture, still with the NAT/flow-logs/LB
baseline.

No GPU or accelerated-instance category exists anywhere in
`ArchitectureSpec` — there is no field this workload could have been
correctly represented by even with perfect extraction.

### Assessment

**WRONG_SHAPE**, and the false positive makes it worse rather than
better: the bill is a genuinely well-formed, Multi-AZ, load-balanced,
NAT-and-flow-logs-protected HA web stack — the kind of design that
*looks* like the product of careful engineering judgment. A reader
comparing this against "review before use" in a generic archetype note
is being asked to distrust the more convincing signal (a $302/mo
production-grade architecture) in favor of the less convincing one (one
line of caveat text).

**First wrong decision:** two. (a) `_AVAILABILITY_HIGH`'s "business
hours" entry does not disambiguate uptime requirements from traffic
timing. (b) No GPU/inference-instance concept exists in
`ArchitectureSpec` or `estimator.py` — this is a hard structural gap, not
an extraction miss; nothing downstream of a perfect extraction could have
produced the right shape.

**Severity: CRITICAL.** Most expensive, most convincing-looking wrong
answer of the six.

---

## PROBE-5 — realtime-chat

> In-app chat for our 100,000 users. Messages must arrive instantly and
> history must be searchable.

**shape_expected:** WebSocket API + DynamoDB + OpenSearch.
Connection-based, not request-based.

### Constraints

| field | value | source | evidence |
|---|---|---|---|
| country | `''` | assumed | — |
| sector | `other` | assumed | — |
| availability | `low` | assumed | — |
| durability | `normal` | assumed | — |
| users | `100000` | **stated** | '100,000 users' |
| requests_per_day | `0` | assumed | — |
| peak_shape | `flat` | assumed | — |
| budget_monthly_usd | `0.0` | assumed | — |
| storage_gb | `0.0` | assumed | — |
| egress_gb | `0.0` | assumed | — |
| public_facing | `False` | assumed | — |

"Must arrive instantly" and "must be searchable" — the two sentences
that actually define this workload's shape — produce no signal
anywhere: no availability trigger, no durability trigger, no component
gate. They are simply not phrases any table in this engine looks for.

### Sizing

avg_rps **0.0**, peak_rps **0.0**, load_tier **trivial** — despite
100,000 stated users, because sizing reads `requests_per_day` exclusively
and this workload's load is connection-based, a concept the rate model
has no field for.

### Components produced, per tier

**Tier 1 — $65.61/mo:** the same generic Compute+Database+Storage
baseline as every other trivial-tier probe. The 100,000 users have no
effect here at all.

**Tier 2/3 — $332.63/mo:** adds **Authentication (MAU) $230.00** — the
one place the stated `users=100000` actually reaches a price, via
Cognito. No DynamoDB, no WebSocket/connection billing, no search.
`ArchitectureSpec.search_node_count` (OpenSearch) is a real field,
already priced by `estimator.py` (confirmed working for the
`ecommerce-scale` regression fixture's read-heavy path) — `plan.py`
never sets it here or anywhere else.

### Assessment

**WRONG_SHAPE.** The $230/mo Cognito line is a real cost tied to a real
stated number, which makes Tier 2/3's $332.63 read as a bill that *did*
account for scale — while the two words that actually describe this
system's requirements ("instantly", "searchable") produced nothing.

**First wrong decision:** `ArchitectureSpec.search_node_count` exists and
is priced, but nothing in `plan.py`'s `_spec_for()` ever sets it —
the search capability this workload explicitly asked for has a working,
tested pricing path that the decision layer simply never reaches. No
WebSocket/connection-based compute or billing concept exists anywhere in
the codebase; this part is a structural gap, not a wiring gap.

**Severity: CRITICAL.** The partial, real signal (Cognito billing on the
stated user count) makes the bill look tailored to this specific
workload, which is exactly the condition under which a generic "review
before use" note is least likely to be heeded.

---

## PROBE-6 — vm-migration

> We run 40 virtual machines in our own server room — a mix of Windows
> and Linux, some with attached storage. We want to move them to the
> cloud as-is before modernising later.

**shape_expected:** EC2 lift-and-shift with EBS, sized from existing VMs.
No greenfield redesign.

### Constraints

| field | value | source | evidence |
|---|---|---|---|
| country | `''` | assumed | — |
| sector | `other` | assumed | — |
| availability | `low` | assumed | — |
| durability | `normal` | assumed | — |
| users | `0` | assumed | — |
| requests_per_day | `0` | assumed | — |
| peak_shape | `flat` | assumed | — |
| budget_monthly_usd | `0.0` | assumed | — |
| storage_gb | `0.0` | assumed | — |
| egress_gb | `0.0` | assumed | — |
| public_facing | `False` | assumed | — |

"40 virtual machines" never becomes a number anywhere in the Constraints
object — "virtual machines" is not in the `users` unit-phrase list, so
the one figure that should size this entire plan (40 VMs) is discarded
on the way in, not merely under-weighted.

### Sizing

avg_rps **0.0**, peak_rps **0.0**, load_tier **trivial** — the plan is
sized as if for a single small application, not a 40-machine estate.

**x86 requirement missed.** `_X86_REQUIRED` requires the literal phrase
"windows server"; the prompt says "a mix of Windows and Linux" — bare
"Windows", no match. `requires_x86` is False, so the engine defaults to
**Graviton/ARM64** compute. For an as-is lift-and-shift of existing
Windows (and likely x86 Linux) VM images, this is not a cost
optimization, it is a probably-non-functional recommendation: most
legacy on-prem Windows Server images will not run unmodified on ARM64,
which directly contradicts "move them to the cloud as-is."

### Components produced, per tier

**Tier 1 — $65.61/mo:** Compute×**1** (ARM64), Database, Object storage
(the generic 500GB default — no per-VM disk sizing, no attempt to read
"some with attached storage" as an EBS requirement), Egress, Monitoring,
the usual zero-cost lines.

**Tier 2/3 — $102.63/mo:** same shape on Fargate — notably, Fargate
tasks cannot run Windows or arbitrary legacy VM images at all, which is
a second, independent way Tier 2/3 specifically cannot represent this
workload even in outline.

### Assessment

**WRONG_SHAPE**, and the only probe of the six where acting on the
output risks non-functional infrastructure rather than just an
inflated or misdirected bill: one Graviton compute instance, sized for
near-zero traffic, priced at $65.61/mo, standing in for a 40-machine
mixed-OS estate that explicitly needs to run as-is.

**First wrong decision:** three, compounding. (a) No unit phrase reads
"40 virtual machines" as a fleet size — the number 40 is discarded
entirely, not underestimated. (b) `_X86_REQUIRED` needs "windows server"
verbatim; bare "Windows" doesn't match, so ARM64 is recommended for a
workload that very likely cannot run on it. (c) No lift-and-shift /
lread-count-of-existing-machines concept, and no EBS-style
attached-storage modeling, exists anywhere in `plan.py`.

**Severity: CRITICAL.** The only probe where the recommended
infrastructure would plausibly fail to run the actual workload if
provisioned as specified — a bill that isn't just wrong, but broken.

---

## Summary

| probe | verdict | first wrong decision | severity |
|---|---|---|---|
| static-site | WRONG_SHAPE | Single hardcoded shape: `_spec_for()` always builds compute+RDS regardless of `archetype` | HIGH |
| batch-etl | WRONG_SHAPE | Single hardcoded shape, compounded by unused `compute_duty_cycle` (billed 730h for a nightly job) | HIGH |
| event-webhook | WRONG_SHAPE | No queue/event-ingestion shape exists; `_DURABILITY_HIGH` doesn't match "cannot drop" so a stated reliability promise is silently unmet | **CRITICAL** |
| ml-inference | WRONG_SHAPE | `_AVAILABILITY_HIGH`'s "business hours" false-positives on a traffic-timing statement; no GPU/inference-instance concept exists at all | **CRITICAL** |
| realtime-chat | WRONG_SHAPE | `search_node_count` (OpenSearch) exists and is priced but `plan.py` never sets it; no WebSocket/connection billing concept exists; Cognito line makes the wrong bill look tailored | **CRITICAL** |
| vm-migration | WRONG_SHAPE | "40 virtual machines" never becomes a number; `_X86_REQUIRED` misses bare "Windows", recommending ARM64 for an as-is legacy migration | **CRITICAL** |

**Verdict distribution:** 6 WRONG_SHAPE, 0 CORRECT, 0 SILENT_DEFAULT
(the `archetype: unknown` disclosure added last task technically
disqualifies all six from the stricter SILENT_DEFAULT category — a
signal is present every time), 0 CRASHED.

**Severity distribution:** 2 HIGH, 4 CRITICAL.

**The pattern across all six:** this is a single-shape engine
(compute + relational database + object storage) being asked about six
workloads that don't have that shape. `archetype: unknown` is accurate
and fires every time it should, but it is one generic sentence competing
against a fully-priced, professionally-formatted, line-itemed bill — and
on four of six probes, something else in the output (a false-positive HA
trigger, a real cost line tied to a real stated number, a
well-formed-looking Multi-AZ stack) actively makes the wrong answer look
*more* considered, not less. The gap is not in the disclosure mechanism;
last task's `archetype` field is doing exactly what it was built to do.
The gap is that there is nothing behind it — one shape, always built,
regardless of what `archetype` says about whether it fits.
