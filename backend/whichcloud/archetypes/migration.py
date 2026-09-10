"""Moving existing servers to the cloud as they are, before redesigning them.

PROBE-6, verbatim:

    "We run 40 virtual machines in our own server room — a mix of Windows
     and Linux, some with attached storage. We want to move them to the
     cloud as-is before modernising later."

Severity CRITICAL, and the only probe of the six where acting on the
output risked infrastructure that WOULD NOT RUN rather than a bill that
was merely wrong. Three compounding failures:

  "40 virtual machines"   no field existed, so the number was DISCARDED
                          -- not underestimated, discarded -- and the
                          plan was sized as one small application.
  "a mix of Windows"      `_X86_REQUIRED` needed the literal phrase
                          "windows server", so bare "Windows" did not
                          match and the engine recommended GRAVITON for
                          legacy Windows images that do not run on ARM.
  "as-is"                 tiers 2 and 3 moved the workload to Fargate,
                          which cannot run Windows or arbitrary legacy VM
                          images at all.

The first two are fixed upstream (Part 2: the source-estate fields, and
`_force_x86_where_required`). This module fixes the third and turns all
of them into assertions.

SIZED FROM AN INVENTORY, NOT FROM TRAFFIC.
Every other archetype starts from a rate. This one starts from what
already exists: how many machines, with how many vCPUs, how much RAM and
how much disk between them. A traffic estimate is not merely a worse
input here, it is an input about a different thing -- nobody migrating
forty machines knows or cares what their aggregate request rate is.

WHAT THE TIERS BUY
Deliberately NOT "more modern". The prompt says "as-is before modernising
later", so a tier that re-platforms the workload is answering a question
that was explicitly deferred. The progression is about how the estate is
OPERATED and RECOVERED, which is what actually improves during a
lift-and-shift.
"""

from __future__ import annotations

import math

from whichcloud.archetypes.base import (
    ArchetypeGraph, Candidate, Forbidden, SizingDriver, resilience_wanted,
)
from whichcloud.estimator import ArchitectureSpec

#: Per-machine defaults, used only for machines the inventory did not
#: describe. Deliberately modest: a general-purpose 2 vCPU / 8 GB server
#: is what an unremarkable on-premises VM usually is, and inflating the
#: default would quietly inflate the whole estate.
DEFAULT_VCPU_PER_VM = 2
DEFAULT_RAM_PER_VM_GB = 8.0
DEFAULT_DISK_PER_VM_GB = 100.0

#: How much of an estate's attached disk is actually in use, for backup
#: sizing. Provisioned disk is not consumed disk, and backing up the
#: provisioned figure would overstate every migration.
DISK_USED_SHARE = 0.6


def _vm_count(constraints) -> int:
    return max(1, int(constraints.source_vm_count or 1))


def _total_vcpu(constraints) -> int:
    stated = int(constraints.source_vcpu_total or 0)
    return stated or _vm_count(constraints) * DEFAULT_VCPU_PER_VM


def _total_ram_gb(constraints) -> float:
    stated = float(constraints.source_ram_gb_total or 0)
    return stated or _vm_count(constraints) * DEFAULT_RAM_PER_VM_GB


def _total_disk_gb(constraints) -> float:
    stated = float(constraints.source_disk_gb_total or 0)
    return stated or _vm_count(constraints) * DEFAULT_DISK_PER_VM_GB


def _per_machine(constraints) -> tuple[int, float]:
    """vCPU and RAM for one machine, rounded UP.

    An estate is rarely uniform, and the average machine is the honest
    thing to price when the inventory gives totals. Rounding up rather
    than down: an instance a shade too small does not run the workload,
    and this archetype's whole failure mode is recommending capacity
    that cannot do the job.
    """
    count = _vm_count(constraints)
    vcpu = max(1, math.ceil(_total_vcpu(constraints) / count))
    ram = max(1.0, _total_ram_gb(constraints) / count)
    return vcpu, ram


def _describe(constraints, load) -> str:
    count = _vm_count(constraints)
    vcpu, ram = _per_machine(constraints)
    stated = "stated" if "source_vm_count" in constraints.stated else "assumed"
    os_note = constraints.source_os
    arch = (
        "x86 required" if constraints.requires_x86()
        else f"architecture {constraints.cpu_architecture}"
    )
    return (
        f"{count} machines ({stated}), {_total_vcpu(constraints)} vCPU and "
        f"{_total_ram_gb(constraints):,.0f} GB RAM in total "
        f"(~{vcpu} vCPU / {ram:,.0f} GB each), "
        f"{_total_disk_gb(constraints):,.0f} GB attached disk, "
        f"OS {os_note}, {arch}"
    )


SIZING = SizingDriver(
    name="source VM inventory",
    fields=(
        "source_vm_count", "source_vcpu_total", "source_ram_gb_total",
        "source_disk_gb_total", "source_os",
    ),
    describe=_describe,
)


CANDIDATES = (
    # ── compute: one instance per source machine ──
    Candidate("Amazon EC2", "compute", "compute",
              "One instance per source machine, sized from that machine's "
              "own vCPU and RAM, running the same operating system.",
              instead_of="a re-platformed design the prompt explicitly "
                         "deferred with 'before modernising later'"),
    # ── store ──
    Candidate("Amazon EBS", "store", "block_storage",
              "Block storage attached to each instance, replacing the "
              "disks the machines already have.",
              instead_of="object storage, which is not a disk and cannot "
                         "be booted from"),
    Candidate("Amazon S3", "store", "storage",
              "Staging for the machine images during the move."),
    Candidate("S3 requests", "store", "s3_requests", "Image upload."),
    Candidate("S3 lifecycle tiering", "store", "storage_lifecycle",
              "Migration artefacts, kept for rollback but not at hot rates."),
    Candidate("Egress", "store", "network",
              "Traffic leaving the estate."),
    # ── network ──
    Candidate("NAT gateway", "edge", "nat",
              "Outbound access for machines in private subnets — patching, "
              "licence activation, agent check-in."),
    Candidate("VPC endpoints", "edge", "endpoint",
              "Private routes to S3 and CloudWatch, so that traffic does "
              "not pay NAT data processing."),
    Candidate("Amazon Route 53", "edge", "dns",
              "The names the estate is reached by."),
    Candidate("AWS Certificate Manager", "edge", "tls",
              "Certificates for anything the estate publishes."),
    # ── ops ──
    Candidate("Amazon CloudWatch", "ops", "monitoring",
              "Per-instance metrics, replacing whatever watched the "
              "server room."),
    Candidate("AWS CloudTrail", "ops", "audit",
              "Who changed which instance."),
    Candidate("Amazon VPC flow logs", "ops", "flowlogs",
              "What the estate talks to — usually unknown at move time, "
              "and the thing that makes modernising later possible."),
    # ── security ──
    Candidate("AWS KMS", "security", "kms",
              "Volume encryption, which on-premises disks rarely had."),
    Candidate("AWS Secrets Manager", "security", "secrets",
              "Credentials that were in configuration files on the hosts."),
    Candidate("Amazon GuardDuty", "security", "threat",
              "Detection across the estate."),
    Candidate("AWS Security Hub", "security", "posture",
              "Configuration drift across forty machines."),
    # ── resilience ──
    Candidate("AWS Backup", "resilience", "backup",
              "Volume snapshots, replacing the tape or the script."),
    Candidate("Cross-region backup copy", "resilience", "backup_copy",
              "Snapshots in a second region."),
    Candidate("S3 Object Lock", "resilience", "storage",
              "Immutable snapshots — the control that survives ransomware "
              "reaching the estate's own credentials."),
)


def _uses_arm(spec: ArchitectureSpec) -> bool:
    return spec.arch == "arm64" or (spec.fargate_task_count > 0 and spec.fargate_arm)


FORBIDDEN = (
    Forbidden(
        "ARM instances",
        "Legacy Windows Server images and x86-licensed software do not "
        "run on ARM at all. Recommending Graviton here is not an "
        "expensive answer, it is infrastructure that would fail to boot "
        "the machines it stands in for — the one failure worse than a "
        "wrong price.",
        _uses_arm,
    ),
    Forbidden(
        "serverless compute",
        "Fargate cannot run Windows or arbitrary legacy VM images. The "
        "prompt says 'as-is before modernising later', so a tier that "
        "re-platforms the workload answers a question that was "
        "explicitly deferred.",
        lambda spec: spec.fargate_task_count > 0
        or spec.lambda_invocations_per_month > 0,
    ),
    Forbidden(
        "managed relational database",
        "A lift-and-shift keeps its database on a machine, because that "
        "is what 'as-is' means. Moving it to a managed engine is a "
        "migration of its own, with its own version and extension "
        "compatibility work, and it is not what was asked for.",
        lambda spec: bool(spec.database_vcpu),
    ),
)


def build(*, tier_level, constraints, load, region, **_) -> ArchitectureSpec:
    """One tier of a lift-and-shift."""
    count = _vm_count(constraints)
    vcpu, ram = _per_machine(constraints)
    disk = _total_disk_gb(constraints)

    operated = tier_level >= 2     # the estate becomes manageable
    resilient = resilience_wanted(constraints, tier_level)

    # ARM IS NEVER CHOSEN HERE UNLESS THE ESTATE SAID IT CAN BE.
    # `arm_ok` has to be positively stated -- `unknown` is not consent,
    # and this is the archetype where guessing wrong means the machines
    # do not boot.
    arm_permitted = constraints.cpu_architecture == "arm_ok"

    return ArchitectureSpec(
        name=f"tier_{tier_level}",
        region=region,
        # ── one instance per source machine ──
        compute_count=count,
        compute_vcpu=vcpu,
        compute_memory_gb=ram,
        # x86_64 EXPLICITLY, not None.
        #
        # This is the bug INV-15 caught in the first draft of this file.
        # `arch=None` does not mean "x86" -- it means "no constraint", so
        # the cheapest-instance query happily returned t4g.large, a
        # Graviton machine, for an estate that cannot boot on ARM. The
        # absence of a preference is not the presence of a requirement,
        # and on this archetype that difference is whether the forty
        # machines start.
        arch="arm64" if arm_permitted else "x86_64",
        # An estate runs. There is no duty cycle to claim.
        compute_duty_cycle=1.0,
        # Nothing is re-platformed.
        fargate_task_count=0,
        database_vcpu=None,
        database_memory_gb=None,
        # ── the disks ──
        block_storage_gb=disk,
        storage_gb=disk * 0.1,
        s3_put_requests=count * 100,
        # ── the network the estate sits in ──
        private_subnets=True,
        nat_gateway_count=2 if constraints.availability == "high" else 1,
        nat_gb_processed=max(10.0, count * 2.0),
        gateway_endpoints=2,
        vpc_endpoints=3 if operated else 0,
        vpc_endpoint_gb=count * 1.0 if operated else 0.0,
        egress_gb=float(constraints.egress_gb or count * 2.0),
        dns_hosted_zones=1,
        dns_monthly_queries=max(10_000.0, count * 5_000.0),
        tls_certificate=True,
        load_balancer=False,
        serves_requests=False,
        # ── ops and resilience on every tier ──
        monitored_metrics=count * 3,
        audit_logging=True,
        backup_gb=(
            0.0 if constraints.durability == "ephemeral"
            else disk * DISK_USED_SHARE
        ),
        backup_retention_days=(
            0 if constraints.durability == "ephemeral" else 30
        ),
        # ── tier 2: the estate becomes operable rather than merely moved ──
        kms_key_count=1 if operated else None,
        secret_count=max(2, count // 10) if operated else 0,
        flowlog_gb=count * 0.5 if operated else 0.0,
        threat_detection=operated,
        # ── tier 3: posture across the estate, archived artefacts ──
        posture_monthly_checks=float(count * 30) if tier_level >= 3 else 0.0,
        lifecycle_gb=disk * 0.05 if tier_level >= 3 else 0.0,
        # ── a stated durability requirement applies on every tier ──
        object_lock=resilient,
        backup_copy_gb=disk * DISK_USED_SHARE if resilient else 0.0,
        backup_seed_gb=disk * DISK_USED_SHARE if resilient else 0.0,
        backup_transfer_gb=disk * 0.05 if resilient else 0.0,
    )


GRAPH = ArchetypeGraph(
    name="migration",
    summary="Moving existing servers or virtual machines to the cloud as "
            "they are, before redesigning them.",
    sources=(
        "AWS Prescriptive Guidance on rehosting: one instance per source "
        "machine, sized from the source's own vCPU/RAM, operating system "
        "preserved",
        "AWS Application Migration Service documentation: block storage "
        "replicated per volume, cutover without re-platforming",
        "Well-Architected operational excellence pillar: flow logs and "
        "configuration monitoring as the prerequisite for modernising an "
        "estate you did not design",
    ),
    sizing=SIZING,
    candidates=CANDIDATES,
    forbidden=FORBIDDEN,
    build=build,
    # An estate, not a request path. The only real flows are the disks
    # attached to the machines and the route out for patching.
    flow=(
        ("users", "dns", "resolves"),
        ("dns", "compute", ""),
        ("compute", "block_storage", "attached disks"),
        ("compute", "nat", "patching, licensing"),
        ("compute", "storage", "migration staging"),
        ("compute", "network", "egress"),
    ),
    tier_notes={
        2: "Operability: machines moved and left alone → volume "
           "encryption, credentials out of config files, flow logs "
           "recording what the estate actually talks to, and threat "
           "detection — removes 'we cannot modernise because we do not "
           "know what calls what', which is what strands a lift-and-shift.",
        3: "Recovery and posture: snapshots in one region → immutable "
           "snapshots copied elsewhere, with configuration drift watched "
           "across every machine — removes ransomware reaching the "
           "estate's own backups, and removes forty machines drifting "
           "apart unobserved.",
    },
)
