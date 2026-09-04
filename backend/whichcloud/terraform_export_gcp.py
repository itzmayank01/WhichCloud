"""Google Cloud Terraform, generated from a priced architecture.

A sibling of terraform_export rather than a parameterisation of it, because
the two resource graphs differ in SHAPE and not merely in resource names --
the same differences this codebase already had to model in the diagram:

  * a Google VPC network is GLOBAL. One network spans every region, so there
    is no per-region network to create and the subnet carries the CIDR.
  * a subnet is REGIONAL and spans the zones, so there is no subnet-per-zone
    and no zonal routing table.
  * Cloud NAT is ONE regional configuration on a Cloud Router, not a gateway
    per zone. An AWS three-zone design buys three NAT gateways; the Google
    equivalent buys one router and one NAT.
  * the external Application Load Balancer is GLOBAL and anycast, so it is a
    global forwarding rule and backend service rather than a regional load
    balancer inside the network.
  * instances are managed by a REGIONAL instance group manager, which is what
    actually spreads them across zones -- the thing "multi-AZ" names on AWS.

Rendering those as renamed AWS resources would produce a plan that applies
cleanly and builds the wrong architecture, which is the failure mode this
module exists to avoid.
"""

from __future__ import annotations

from .estimator import ArchitectureSpec, Estimate

# Resource prefixes this generator turns into real Terraform. Anything the
# estimate priced outside this set is listed in the README rather than dropped:
# a project that silently omits half its bill is worse than one that says so.
_GENERATED_PREFIXES = (
    "Compute",
    "Database",
    "Object storage",
    "Load balancer",
    "NAT gateway",
    "NAT data",
)


def _sku_for(estimate: Estimate, *, prefix: str, exclude: str | None = None) -> str | None:
    for item in estimate.items:
        if not item.label.startswith(prefix):
            continue
        if exclude and exclude in item.label:
            continue
        return item.sku.split(":")[0]
    return None


def _not_generated(spec: ArchitectureSpec, estimate: Estimate) -> list[str]:
    missing = [
        item.label
        for item in estimate.items
        if not any(item.label.startswith(p) for p in _GENERATED_PREFIXES)
    ]
    if spec.database_read_replicas > 0:
        missing.append(f"Database read replica × {spec.database_read_replicas}")
    return missing


def generate(spec: ArchitectureSpec, estimate: Estimate) -> dict[str, str]:
    """Google Cloud. Returns {filename: contents} for a downloadable project."""
    has_compute = spec.compute_count > 0
    has_db = bool(spec.database_vcpu)
    has_storage = spec.storage_gb > 0
    has_lb = spec.load_balancer
    has_network = has_compute or has_db or has_lb

    machine_type = _sku_for(estimate, prefix="Compute") or "n2d-standard-2"
    db_tier = _sku_for(estimate, prefix="Database", exclude="replica") or "db-custom-2-8192"

    return {
        "variables.tf": _variables_tf(
            region=estimate.region,
            machine_type=machine_type,
            db_tier=db_tier,
            compute_count=spec.compute_count,
            storage_gb=spec.storage_gb,
            has_compute=has_compute,
            has_db=has_db,
            has_storage=has_storage,
        ),
        "main.tf": _main_tf(
            spec=spec,
            has_network=has_network,
            has_compute=has_compute,
            has_db=has_db,
            has_storage=has_storage,
            has_lb=has_lb,
        ),
        "outputs.tf": _outputs_tf(
            has_network=has_network, has_db=has_db, has_storage=has_storage, has_lb=has_lb
        ),
        "terraform.tfvars.example": _tfvars(
            region=estimate.region,
            machine_type=machine_type,
            db_tier=db_tier,
            compute_count=spec.compute_count,
            has_compute=has_compute,
            has_db=has_db,
        ),
        "README.md": _readme(spec=spec, estimate=estimate, has_db=has_db, has_lb=has_lb),
    }


def _variables_tf(*, region, machine_type, db_tier, compute_count, storage_gb,
                  has_compute, has_db, has_storage) -> str:
    out = [
        'variable "project_id" {\n'
        '  description = "Google Cloud project to deploy into. A project is a\\n'
        'hard boundary on Google Cloud -- quotas, IAM and billing all attach to\\n'
        'it -- so it has no default."\n'
        "  type        = string\n"
        "}\n",
        'variable "region" {\n'
        '  description = "Region for the subnet, Cloud NAT and Cloud SQL."\n'
        "  type        = string\n"
        f'  default     = "{region}"\n'
        "}\n",
        'variable "name" {\n'
        '  description = "Prefix for every resource name."\n'
        "  type        = string\n"
        '  default     = "whichcloud"\n'
        "}\n",
    ]
    if has_compute:
        out.append(
            'variable "machine_type" {\n'
            '  description = "Compute Engine machine type, as priced."\n'
            "  type        = string\n"
            f'  default     = "{machine_type}"\n'
            "}\n"
        )
        out.append(
            'variable "instance_count" {\n'
            '  description = "Target size of the regional managed instance\\n'
            'group. Regional, so the group spreads these across the zones in\\n'
            'the region -- that distribution is what survives a zone failure."\n'
            "  type        = number\n"
            f"  default     = {max(1, compute_count)}\n"
            "}\n"
        )
    if has_db:
        out.append(
            'variable "db_tier" {\n'
            '  description = "Cloud SQL machine tier, as priced."\n'
            "  type        = string\n"
            f'  default     = "{db_tier}"\n'
            "}\n"
        )
    if has_storage:
        out.append(
            'variable "storage_class" {\n'
            '  description = "Default storage class for the bucket."\n'
            "  type        = string\n"
            '  default     = "STANDARD"\n'
            "}\n"
        )
    return "\n".join(out)


def _main_tf(*, spec, has_network, has_compute, has_db, has_storage, has_lb) -> str:
    blocks = [
        "terraform {\n"
        '  required_version = ">= 1.5.0"\n'
        "  required_providers {\n"
        "    google = {\n"
        '      source  = "hashicorp/google"\n'
        '      version = "~> 5.0"\n'
        "    }\n"
        "  }\n"
        "}\n",
        'provider "google" {\n'
        "  project = var.project_id\n"
        "  region  = var.region\n"
        "}\n",
    ]

    if has_network:
        blocks.append(
            "# The network is GLOBAL. It is not created per region, and it\n"
            "# carries no CIDR of its own -- the subnet does. This is the one\n"
            "# structural difference from an AWS VPC that changes the file\n"
            "# rather than just the resource name.\n"
            'resource "google_compute_network" "main" {\n'
            "  name                    = var.name\n"
            "  auto_create_subnetworks = false\n"
            "}\n"
        )
        blocks.append(
            "# The subnet is REGIONAL and spans every zone in the region, so\n"
            "# there is one, not one per zone.\n"
            'resource "google_compute_subnetwork" "main" {\n'
            "  name                     = \"${var.name}-subnet\"\n"
            '  ip_cidr_range            = "10.0.0.0/20"\n'
            "  region                   = var.region\n"
            "  network                  = google_compute_network.main.id\n"
            "  private_ip_google_access = true\n"
            "}\n"
        )
        blocks.append(
            "# ONE Cloud NAT, on ONE Cloud Router, serving the whole region.\n"
            "# There is no per-zone Cloud NAT to create: an AWS design spanning\n"
            "# three zones buys three NAT gateways, the Google equivalent buys\n"
            "# this pair.\n"
            'resource "google_compute_router" "main" {\n'
            "  name    = \"${var.name}-router\"\n"
            "  region  = var.region\n"
            "  network = google_compute_network.main.id\n"
            "}\n\n"
            'resource "google_compute_router_nat" "main" {\n'
            "  name                               = \"${var.name}-nat\"\n"
            "  router                             = google_compute_router.main.name\n"
            "  region                             = var.region\n"
            '  nat_ip_allocate_option             = "AUTO_ONLY"\n'
            '  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"\n'
            "}\n"
        )
        blocks.append(
            "# Firewall rules are VPC-level on Google Cloud, not attached to an\n"
            "# instance the way a security group is.\n"
            'resource "google_compute_firewall" "health_checks" {\n'
            "  name    = \"${var.name}-allow-health-checks\"\n"
            "  network = google_compute_network.main.name\n"
            "  allow {\n"
            '    protocol = "tcp"\n'
            '    ports    = ["80"]\n'
            "  }\n"
            "  # Google's health checkers and the global load balancer answer\n"
            "  # from these ranges.\n"
            '  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]\n'
            "}\n"
        )

    if has_compute:
        blocks.append(
            'resource "google_compute_instance_template" "app" {\n'
            "  name_prefix  = \"${var.name}-app-\"\n"
            "  machine_type = var.machine_type\n"
            "  disk {\n"
            '    source_image = "debian-cloud/debian-12"\n'
            "    auto_delete  = true\n"
            "    boot         = true\n"
            "  }\n"
            "  network_interface {\n"
            "    subnetwork = google_compute_subnetwork.main.id\n"
            "    # No access_config block: instances have no public address and\n"
            "    # reach the internet through Cloud NAT.\n"
            "  }\n"
            "  lifecycle {\n"
            "    create_before_destroy = true\n"
            "  }\n"
            "}\n"
        )
        blocks.append(
            'resource "google_compute_health_check" "app" {\n'
            "  name = \"${var.name}-hc\"\n"
            "  http_health_check {\n"
            "    port = 80\n"
            "  }\n"
            "}\n"
        )
        blocks.append(
            "# REGIONAL manager, not zonal. This is what spreads instances\n"
            "# across the region's zones, and is the resource that actually\n"
            "# delivers what \"survives a zone failure\" means here.\n"
            'resource "google_compute_region_instance_group_manager" "app" {\n'
            "  name               = \"${var.name}-mig\"\n"
            "  region             = var.region\n"
            "  base_instance_name = var.name\n"
            "  target_size        = var.instance_count\n"
            "  version {\n"
            "    instance_template = google_compute_instance_template.app.id\n"
            "  }\n"
            "  named_port {\n"
            '    name = "http"\n'
            "    port = 80\n"
            "  }\n"
            "  auto_healing_policies {\n"
            "    health_check      = google_compute_health_check.app.id\n"
            "    initial_delay_sec = 300\n"
            "  }\n"
            "}\n"
        )

    if has_lb and has_compute:
        blocks.append(
            "# The external Application Load Balancer is GLOBAL and anycast:\n"
            "# one address answered from every point of presence. It is not a\n"
            "# regional resource and does not live inside the network, which is\n"
            "# why it is a global forwarding rule rather than a load balancer\n"
            "# attached to a subnet.\n"
            'resource "google_compute_backend_service" "app" {\n'
            "  name          = \"${var.name}-backend\"\n"
            '  protocol      = "HTTP"\n'
            '  port_name     = "http"\n'
            "  health_checks = [google_compute_health_check.app.id]\n"
            "  backend {\n"
            "    group          = google_compute_region_instance_group_manager.app.instance_group\n"
            '    balancing_mode = "UTILIZATION"\n'
            "  }\n"
            "}\n\n"
            'resource "google_compute_url_map" "app" {\n'
            "  name            = \"${var.name}-urlmap\"\n"
            "  default_service = google_compute_backend_service.app.id\n"
            "}\n\n"
            'resource "google_compute_target_http_proxy" "app" {\n'
            "  name    = \"${var.name}-proxy\"\n"
            "  url_map = google_compute_url_map.app.id\n"
            "}\n\n"
            'resource "google_compute_global_forwarding_rule" "app" {\n'
            "  name       = \"${var.name}-fr\"\n"
            "  target     = google_compute_target_http_proxy.app.id\n"
            '  port_range = "80"\n'
            "}\n"
        )

    if has_db:
        availability = "REGIONAL" if spec.database_multi_az else "ZONAL"
        note = (
            "# availability_type = REGIONAL is Cloud SQL's high availability:\n"
            "# a standby in another zone of the same region with automatic\n"
            "# failover. Google's word for it is regional, not multi-AZ, and\n"
            "# the two are the same arrangement under different names.\n"
            if spec.database_multi_az
            else "# ZONAL: one zone, no standby. A zone failure is an outage.\n"
        )
        blocks.append(
            note
            + 'resource "google_sql_database_instance" "main" {\n'
            "  name             = \"${var.name}-db\"\n"
            '  database_version = "POSTGRES_15"\n'
            "  region           = var.region\n"
            "  settings {\n"
            "    tier              = var.db_tier\n"
            f'    availability_type = "{availability}"\n'
            "    ip_configuration {\n"
            "      ipv4_enabled    = false\n"
            "      private_network = google_compute_network.main.id\n"
            "    }\n"
            "    backup_configuration {\n"
            "      enabled                        = true\n"
            "      point_in_time_recovery_enabled = true\n"
            "    }\n"
            "  }\n"
            "  deletion_protection = true\n"
            "}\n"
        )

    if has_storage:
        blocks.append(
            'resource "google_storage_bucket" "main" {\n'
            "  name                        = \"${var.name}-${var.project_id}\"\n"
            "  location                    = var.region\n"
            "  storage_class               = var.storage_class\n"
            "  uniform_bucket_level_access = true\n"
            "  versioning {\n"
            "    enabled = true\n"
            "  }\n"
            "}\n"
        )

    return "\n".join(blocks)


def _outputs_tf(*, has_network, has_db, has_storage, has_lb) -> str:
    out = []
    if has_network:
        out.append(
            'output "network_name" {\n'
            "  value       = google_compute_network.main.name\n"
            '  description = "The global VPC network."\n'
            "}\n"
        )
    if has_lb:
        out.append(
            'output "load_balancer_ip" {\n'
            "  value       = google_compute_global_forwarding_rule.app.ip_address\n"
            '  description = "Anycast address of the global load balancer."\n'
            "}\n"
        )
    if has_db:
        out.append(
            'output "database_connection_name" {\n'
            "  value       = google_sql_database_instance.main.connection_name\n"
            '  description = "Pass to the Cloud SQL Auth Proxy."\n'
            "}\n"
        )
    if has_storage:
        out.append(
            'output "bucket_name" {\n'
            "  value = google_storage_bucket.main.name\n"
            "}\n"
        )
    return "\n".join(out)


def _tfvars(*, region, machine_type, db_tier, compute_count, has_compute, has_db) -> str:
    lines = [
        "# Copy to terraform.tfvars and set project_id.",
        'project_id = "your-project-id"',
        f'region     = "{region}"',
    ]
    if has_compute:
        lines.append(f'machine_type   = "{machine_type}"')
        lines.append(f"instance_count = {max(1, compute_count)}")
    if has_db:
        lines.append(f'db_tier = "{db_tier}"')
    return "\n".join(lines) + "\n"


def _readme(*, spec, estimate, has_db, has_lb) -> str:
    missing = _not_generated(spec, estimate)
    lines = [
        "# WhichCloud — Google Cloud Terraform",
        "",
        f"Priced at **${estimate.total_monthly:,.2f}/month** in `{estimate.region}`.",
        "",
        "## What this builds",
        "",
        "- A **global** VPC network with one **regional** subnet.",
        "- **One** Cloud NAT on one Cloud Router for the whole region. An AWS",
        "  design spanning three zones buys three NAT gateways; this is the",
        "  Google equivalent, and it is one resource, not three.",
    ]
    if spec.compute_count:
        lines.append(
            f"- A **regional** managed instance group of {spec.compute_count} "
            "instance(s). Regional is what spreads them across zones."
        )
    if has_lb:
        lines.append("- A **global** anycast HTTP load balancer, outside any region.")
    if has_db:
        lines.append(
            "- Cloud SQL for PostgreSQL, "
            + (
                "`REGIONAL` — a standby in a second zone with automatic failover."
                if spec.database_multi_az
                else "`ZONAL` — single zone, no standby."
            )
        )
    lines += [
        "",
        "## Before you apply",
        "",
        "1. `project_id` has no default. Set it in `terraform.tfvars`.",
        "2. Enable the APIs this needs: `compute.googleapis.com`,",
        "   `sqladmin.googleapis.com`, `servicenetworking.googleapis.com`.",
        "3. Cloud SQL with a private IP needs a private services access",
        "   connection on the network first. Terraform will fail without it.",
        "4. The database has `deletion_protection = true`. That is deliberate.",
        "",
        "## Priced but not generated",
        "",
    ]
    if missing:
        lines.append(
            "These are in the estimate and are **not** in this project, so the "
            "plan costs less than the figure above:"
        )
        lines += [f"- {name}" for name in missing]
    else:
        lines.append("Nothing — every priced line has a resource here.")
    lines += [
        "",
        "This is a starting point, not a production deployment. It has no",
        "IAM beyond defaults, no TLS certificate, no monitoring and no",
        "application. Review it before applying.",
        "",
    ]
    return "\n".join(lines)
