"""Azure Terraform, generated from a priced architecture.

The third sibling, for the same reason as the second: the resource graph
differs in SHAPE, and rendering it as renamed AWS resources would produce a
plan that applies cleanly and builds the wrong thing.

Where Azure genuinely diverges:

  * everything lives in a RESOURCE GROUP. It is the deletion and access
    boundary, it is mandatory, and AWS has no equivalent -- so it is the
    first resource in the file rather than an afterthought.
  * a virtual network and its subnets are REGIONAL and span every zone. An
    availability zone is a property of the resource that occupies them
    (`zones = ["1","2","3"]` on the scale set), not of the subnet. This is
    the trap: translating an AWS design literally produces one subnet per
    zone, which on Azure buys nothing.
  * a subnet may have at most ONE NAT gateway, so a single-subnet design has
    exactly one however many zones the compute spans.
  * Application Gateway needs its own DEDICATED subnet -- no other resource
    may share it -- and it is both the load balancer and, at WAF_v2, the web
    application firewall. One resource does the work of two on AWS.
  * PostgreSQL Flexible Server on a private address needs a DELEGATED subnet
    and a private DNS zone linked to the network. Without both, the apply
    fails; there is no AWS step that corresponds to this.
  * high availability is `high_availability { mode = "ZoneRedundant" }`, and
    naming a standby zone different from the primary's is what makes it real.
"""

from __future__ import annotations

import re

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

# Flexible Server tier prefixes. Azure spells the tier into the SKU name
# itself, so the tier is not a separate argument the way it is on RDS.
_BURSTABLE = "B"
_GENERAL_PURPOSE = "GP"
_MEMORY_OPTIMISED = "MO"


def _flexible_server_sku(catalog_sku: str) -> str:
    """Catalog SKU -> a Flexible Server `sku_name`.

    The catalog stores what the price list calls things ("B4ms",
    "Ddsv5-4vcore"); Azure's API wants "<tier>_Standard_<vm size>". The two
    are not the same string, and passing the catalog's spelling straight
    through would fail at apply time with a SKU-not-found -- late, and after
    the resource group already exists.
    """
    sku = catalog_sku.split(":")[0]

    # Burstable: "B4ms", and the price list shouts some of them ("B1MS").
    if m := re.fullmatch(r"B(\d+)([A-Za-z]+)", sku):
        return f"{_BURSTABLE}_Standard_B{m.group(1)}{m.group(2).lower()}"

    # vCore series: "Ddsv5-4vcore" -> D + 4 + ds + _v5.
    if m := re.fullmatch(r"([A-Z])([a-z]*)v(\d+)-(\d+)vcore", sku):
        letter, mid, version, vcpu = m.groups()
        # E is the memory-optimised family; D is general purpose.
        tier = _MEMORY_OPTIMISED if letter == "E" else _GENERAL_PURPOSE
        return f"{tier}_Standard_{letter}{vcpu}{mid}_v{version}"

    # Unrecognised: hand it back untouched rather than inventing a name. The
    # README says to check it, which beats a confident wrong answer.
    return sku


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


def _zones(spec: ArchitectureSpec) -> list[str]:
    """Which zones the compute spreads over.

    Zone-redundant means the scale set names more than one. One zone named is
    the same availability as none named, so a single-zone design says nothing
    and lets Azure place it.
    """
    if not spec.database_multi_az and spec.compute_count < 2:
        return []
    return ["1", "2", "3"] if spec.compute_count >= 3 else ["1", "2"]


def generate(spec: ArchitectureSpec, estimate: Estimate) -> dict[str, str]:
    """Azure. Returns {filename: contents} for a downloadable project."""
    has_compute = spec.compute_count > 0
    has_db = bool(spec.database_vcpu)
    has_storage = spec.storage_gb > 0
    has_gateway = spec.load_balancer or spec.waf_rule_count is not None
    has_network = has_compute or has_db or has_gateway

    vm_size = _sku_for(estimate, prefix="Compute") or "Standard_D2s_v5"
    db_sku = _flexible_server_sku(
        _sku_for(estimate, prefix="Database", exclude="replica") or "Ddsv5-2vcore"
    )
    # Flexible Server's floor is 32 GiB, and it only grows -- it cannot be
    # shrunk after creation, so rounding up is the safe direction.
    db_storage_mb = max(32768, int(spec.db_storage_gb) * 1024)

    return {
        "variables.tf": _variables_tf(
            region=estimate.region,
            vm_size=vm_size,
            db_sku=db_sku,
            db_storage_mb=db_storage_mb,
            compute_count=spec.compute_count,
            has_compute=has_compute,
            has_db=has_db,
        ),
        "main.tf": _main_tf(
            spec=spec,
            has_network=has_network,
            has_compute=has_compute,
            has_db=has_db,
            has_storage=has_storage,
            has_gateway=has_gateway,
        ),
        "outputs.tf": _outputs_tf(
            has_network=has_network,
            has_db=has_db,
            has_storage=has_storage,
            has_gateway=has_gateway,
        ),
        "terraform.tfvars.example": _tfvars(
            region=estimate.region,
            vm_size=vm_size,
            db_sku=db_sku,
            compute_count=spec.compute_count,
            has_compute=has_compute,
            has_db=has_db,
        ),
        "README.md": _readme(
            spec=spec,
            estimate=estimate,
            has_db=has_db,
            has_gateway=has_gateway,
            db_sku=db_sku,
        ),
    }


def _variables_tf(*, region, vm_size, db_sku, db_storage_mb, compute_count,
                  has_compute, has_db) -> str:
    out = [
        'variable "location" {\n'
        '  description = "Azure region. Every resource here is regional and\\n'
        'inherits this, including the virtual network -- which, unlike a\\n'
        'Google VPC, does not span regions."\n'
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
            'variable "vm_size" {\n'
            '  description = "Virtual machine size, as priced."\n'
            "  type        = string\n"
            f'  default     = "{vm_size}"\n'
            "}\n"
        )
        out.append(
            'variable "instance_count" {\n'
            '  description = "Instances in the scale set. The scale set\\n'
            'distributes these across the zones it names; the subnet plays no\\n'
            "part in that, because an Azure subnet is not zonal.\"\n"
            "  type        = number\n"
            f"  default     = {max(1, compute_count)}\n"
            "}\n"
        )
        out.append(
            'variable "ssh_public_key" {\n'
            '  description = "OpenSSH public key for the admin user. No\\n'
            'default: a scale set will not build without one, and a key\\n'
            'checked into a repository is not a key."\n'
            "  type        = string\n"
            "}\n"
        )
    if has_db:
        out.append(
            'variable "db_sku" {\n'
            '  description = "Flexible Server SKU, as priced. Azure spells the\\n'
            'tier into the name: B_ burstable, GP_ general purpose, MO_ memory\\n'
            'optimised."\n'
            "  type        = string\n"
            f'  default     = "{db_sku}"\n'
            "}\n"
        )
        out.append(
            'variable "db_storage_mb" {\n'
            '  description = "Flexible Server storage. This can grow and\\n'
            'cannot shrink, so start close to what you need."\n'
            "  type        = number\n"
            f"  default     = {db_storage_mb}\n"
            "}\n"
        )
        out.append(
            'variable "db_administrator_password" {\n'
            '  description = "Administrator password. No default, and it does\\n'
            'not belong in terraform.tfvars either -- pass it from a secret\\n'
            "store or TF_VAR_db_administrator_password.\"\n"
            "  type        = string\n"
            "  sensitive   = true\n"
            "}\n"
        )
    return "\n".join(out)


def _main_tf(*, spec, has_network, has_compute, has_db, has_storage, has_gateway) -> str:
    zones = _zones(spec)
    zones_hcl = ", ".join(f'"{z}"' for z in zones)

    blocks = [
        "terraform {\n"
        '  required_version = ">= 1.5.0"\n'
        "  required_providers {\n"
        "    azurerm = {\n"
        '      source  = "hashicorp/azurerm"\n'
        '      version = "~> 3.100"\n'
        "    }\n"
        "    random = {\n"
        '      source  = "hashicorp/random"\n'
        '      version = "~> 3.6"\n'
        "    }\n"
        "  }\n"
        "}\n",
        'provider "azurerm" {\n'
        "  features {}\n"
        "}\n",
        "# Everything below lives in this. A resource group is the unit Azure\n"
        "# deletes, bills and grants access by, it is mandatory, and there is\n"
        "# no AWS resource that corresponds to it -- which is why it comes\n"
        "# first rather than being folded into tags.\n"
        'resource "azurerm_resource_group" "main" {\n'
        "  name     = \"${var.name}-rg\"\n"
        "  location = var.location\n"
        "}\n",
    ]

    if has_network:
        blocks.append(
            "# The virtual network is REGIONAL and spans every zone in the\n"
            "# region, and so does each subnet inside it. There is deliberately\n"
            "# no subnet-per-zone here: on Azure a zone is a property of the\n"
            "# resource, declared on the scale set below, not of the subnet.\n"
            'resource "azurerm_virtual_network" "main" {\n'
            "  name                = var.name\n"
            "  resource_group_name = azurerm_resource_group.main.name\n"
            "  location            = azurerm_resource_group.main.location\n"
            '  address_space       = ["10.0.0.0/16"]\n'
            "}\n"
        )
        blocks.append(
            'resource "azurerm_subnet" "app" {\n'
            "  name                 = \"${var.name}-app\"\n"
            "  resource_group_name  = azurerm_resource_group.main.name\n"
            "  virtual_network_name = azurerm_virtual_network.main.name\n"
            '  address_prefixes     = ["10.0.0.0/20"]\n'
            "}\n"
        )
        blocks.append(
            "# A network security group is a standalone resource that is then\n"
            "# ASSOCIATED with a subnet or an interface. It is not an argument\n"
            "# on the thing it protects, the way a security group is attached\n"
            "# to an AWS instance.\n"
            'resource "azurerm_network_security_group" "app" {\n'
            "  name                = \"${var.name}-app-nsg\"\n"
            "  resource_group_name = azurerm_resource_group.main.name\n"
            "  location            = azurerm_resource_group.main.location\n"
            "}\n\n"
            'resource "azurerm_subnet_network_security_group_association" "app" {\n'
            "  subnet_id                 = azurerm_subnet.app.id\n"
            "  network_security_group_id = azurerm_network_security_group.app.id\n"
            "}\n"
        )
        blocks.append(
            "# ONE NAT gateway. A subnet accepts at most one, so the count\n"
            "# follows the number of subnets that need outbound access -- not\n"
            "# the number of zones, which is what it would follow on AWS.\n"
            'resource "azurerm_public_ip" "nat" {\n'
            "  name                = \"${var.name}-nat-ip\"\n"
            "  resource_group_name = azurerm_resource_group.main.name\n"
            "  location            = azurerm_resource_group.main.location\n"
            '  allocation_method   = "Static"\n'
            '  sku                 = "Standard"\n'
            "}\n\n"
            'resource "azurerm_nat_gateway" "main" {\n'
            "  name                = \"${var.name}-nat\"\n"
            "  resource_group_name = azurerm_resource_group.main.name\n"
            "  location            = azurerm_resource_group.main.location\n"
            '  sku_name            = "Standard"\n'
            "}\n\n"
            'resource "azurerm_nat_gateway_public_ip_association" "main" {\n'
            "  nat_gateway_id       = azurerm_nat_gateway.main.id\n"
            "  public_ip_address_id = azurerm_public_ip.nat.id\n"
            "}\n\n"
            'resource "azurerm_subnet_nat_gateway_association" "app" {\n'
            "  subnet_id      = azurerm_subnet.app.id\n"
            "  nat_gateway_id = azurerm_nat_gateway.main.id\n"
            "}\n"
        )

    if has_gateway:
        is_waf = spec.waf_rule_count is not None
        sku = "WAF_v2" if is_waf else "Standard_v2"
        blocks.append(
            "# Application Gateway insists on a subnet of its own: no other\n"
            "# resource may occupy it. That constraint is why this subnet\n"
            "# exists at all.\n"
            'resource "azurerm_subnet" "gateway" {\n'
            "  name                 = \"${var.name}-gateway\"\n"
            "  resource_group_name  = azurerm_resource_group.main.name\n"
            "  virtual_network_name = azurerm_virtual_network.main.name\n"
            '  address_prefixes     = ["10.0.16.0/24"]\n'
            "}\n\n"
            'resource "azurerm_public_ip" "gateway" {\n'
            "  name                = \"${var.name}-gateway-ip\"\n"
            "  resource_group_name = azurerm_resource_group.main.name\n"
            "  location            = azurerm_resource_group.main.location\n"
            '  allocation_method   = "Static"\n'
            '  sku                 = "Standard"\n'
            + (f"  zones               = [{zones_hcl}]\n" if zones else "")
            + "}\n"
        )
        waf_note = (
            "# SKU WAF_v2: on Azure the web application firewall is not a\n"
            "# separate service in front of the load balancer, it is a mode of\n"
            "# the load balancer. One resource, where AWS bills two.\n"
            if is_waf
            else "# Layer 7. Standard_v2 is the same gateway without the\n"
            "# firewall -- switching to WAF_v2 turns it on in place.\n"
        )
        waf_block = (
            "  waf_configuration {\n"
            "    enabled          = true\n"
            '    firewall_mode    = "Prevention"\n'
            '    rule_set_type    = "OWASP"\n'
            '    rule_set_version = "3.2"\n'
            "  }\n"
            if is_waf
            else ""
        )
        blocks.append(
            waf_note
            + 'resource "azurerm_application_gateway" "main" {\n'
            "  name                = \"${var.name}-agw\"\n"
            "  resource_group_name = azurerm_resource_group.main.name\n"
            "  location            = azurerm_resource_group.main.location\n"
            + (f"  zones               = [{zones_hcl}]\n" if zones else "")
            + "\n"
            "  sku {\n"
            f'    name     = "{sku}"\n'
            f'    tier     = "{sku}"\n'
            "    capacity = 2\n"
            "  }\n\n"
            + waf_block
            + ("\n" if waf_block else "")
            + "  gateway_ip_configuration {\n"
            '    name      = "gateway-ip-config"\n'
            "    subnet_id = azurerm_subnet.gateway.id\n"
            "  }\n\n"
            "  frontend_port {\n"
            '    name = "http"\n'
            "    port = 80\n"
            "  }\n\n"
            "  frontend_ip_configuration {\n"
            '    name                 = "frontend"\n'
            "    public_ip_address_id = azurerm_public_ip.gateway.id\n"
            "  }\n\n"
            "  # Empty here on purpose: the scale set joins itself to this\n"
            "  # pool, rather than the pool listing addresses that do not\n"
            "  # exist yet.\n"
            "  backend_address_pool {\n"
            '    name = "app"\n'
            "  }\n\n"
            "  backend_http_settings {\n"
            '    name                  = "http"\n'
            "    port                  = 80\n"
            '    protocol              = "Http"\n'
            '    cookie_based_affinity = "Disabled"\n'
            "    request_timeout       = 30\n"
            "  }\n\n"
            "  http_listener {\n"
            '    name                           = "http"\n'
            '    frontend_ip_configuration_name = "frontend"\n'
            '    frontend_port_name             = "http"\n'
            '    protocol                       = "Http"\n'
            "  }\n\n"
            "  request_routing_rule {\n"
            '    name                       = "http"\n'
            '    rule_type                  = "Basic"\n'
            '    http_listener_name         = "http"\n'
            '    backend_address_pool_name  = "app"\n'
            '    backend_http_settings_name = "http"\n'
            "    priority                   = 100\n"
            "  }\n"
            "}\n"
        )

    if has_compute:
        zone_note = (
            "# `zones` is where high availability actually lives. The subnet\n"
            "# above spans the whole region; naming zones HERE is what spreads\n"
            "# the instances across them.\n"
            if zones
            else "# No zones named: Azure places these wherever it likes, and a\n"
            "# zone failure is an outage.\n"
        )
        # terraform fmt aligns the `=` across a block, so the width depends
        # on whether the longest attribute -- the gateway pool -- is there at
        # all. Computing it keeps the output canonically formatted either way.
        ip_config = [
            ("name", '"internal"'),
            ("primary", "true"),
            ("subnet_id", "azurerm_subnet.app.id"),
        ]
        if has_gateway:
            ip_config.append(
                (
                    "application_gateway_backend_address_pool_ids",
                    "[one(azurerm_application_gateway.main.backend_address_pool).id]",
                )
            )
        width = max(len(k) for k, _ in ip_config)
        pool = "".join(f"      {k.ljust(width)} = {v}\n" for k, v in ip_config)
        blocks.append(
            zone_note
            + 'resource "azurerm_linux_virtual_machine_scale_set" "app" {\n'
            "  name                = \"${var.name}-vmss\"\n"
            "  resource_group_name = azurerm_resource_group.main.name\n"
            "  location            = azurerm_resource_group.main.location\n"
            "  sku                 = var.vm_size\n"
            "  instances           = var.instance_count\n"
            '  admin_username      = "azureuser"\n'
            + (f"  zones               = [{zones_hcl}]\n" if zones else "")
            + '  upgrade_mode        = "Automatic"\n\n'
            "  admin_ssh_key {\n"
            '    username   = "azureuser"\n'
            "    public_key = var.ssh_public_key\n"
            "  }\n\n"
            "  source_image_reference {\n"
            '    publisher = "Canonical"\n'
            '    offer     = "0001-com-ubuntu-server-jammy"\n'
            '    sku       = "22_04-lts-gen2"\n'
            '    version   = "latest"\n'
            "  }\n\n"
            "  os_disk {\n"
            '    caching              = "ReadWrite"\n'
            '    storage_account_type = "Premium_LRS"\n'
            "  }\n\n"
            "  network_interface {\n"
            '    name    = "primary"\n'
            "    primary = true\n\n"
            "    ip_configuration {\n"
            + pool
            + "      # No public_ip_address block: these reach the internet\n"
            "      # through the NAT gateway and are reached through the\n"
            "      # gateway, so they need no address of their own.\n"
            "    }\n"
            "  }\n"
            "}\n"
        )

    if has_db:
        blocks.append(
            "# A Flexible Server on a private address needs a subnet DELEGATED\n"
            "# to it -- delegation hands the subnet to the service, so nothing\n"
            "# else can live there -- plus a private DNS zone linked to the\n"
            "# network. Both are required, and neither has an AWS counterpart.\n"
            'resource "azurerm_subnet" "database" {\n'
            "  name                 = \"${var.name}-db\"\n"
            "  resource_group_name  = azurerm_resource_group.main.name\n"
            "  virtual_network_name = azurerm_virtual_network.main.name\n"
            '  address_prefixes     = ["10.0.17.0/24"]\n\n'
            "  delegation {\n"
            '    name = "flexible-server"\n'
            "    service_delegation {\n"
            '      name = "Microsoft.DBforPostgreSQL/flexibleServers"\n'
            "      actions = [\n"
            '        "Microsoft.Network/virtualNetworks/subnets/join/action",\n'
            "      ]\n"
            "    }\n"
            "  }\n"
            "}\n\n"
            'resource "azurerm_private_dns_zone" "database" {\n'
            "  name                = \"${var.name}.postgres.database.azure.com\"\n"
            "  resource_group_name = azurerm_resource_group.main.name\n"
            "}\n\n"
            'resource "azurerm_private_dns_zone_virtual_network_link" "database" {\n'
            "  name                  = \"${var.name}-db-link\"\n"
            "  resource_group_name   = azurerm_resource_group.main.name\n"
            "  private_dns_zone_name = azurerm_private_dns_zone.database.name\n"
            "  virtual_network_id    = azurerm_virtual_network.main.id\n"
            "}\n"
        )
        ha_note = (
            "# ZoneRedundant, with the standby named in a DIFFERENT zone from\n"
            "# the primary. Naming the same zone twice is accepted and buys\n"
            "# nothing, which is the quiet way this setting goes wrong.\n"
            if spec.database_multi_az
            else "# No high_availability block: one server in one zone. A zone\n"
            "# failure takes the database with it.\n"
        )
        ha_block = (
            "\n  high_availability {\n"
            '    mode                      = "ZoneRedundant"\n'
            '    standby_availability_zone = "2"\n'
            "  }\n"
            if spec.database_multi_az
            else ""
        )
        blocks.append(
            ha_note
            + 'resource "azurerm_postgresql_flexible_server" "main" {\n'
            "  name                          = \"${var.name}-pg\"\n"
            "  resource_group_name           = azurerm_resource_group.main.name\n"
            "  location                      = azurerm_resource_group.main.location\n"
            '  version                       = "15"\n'
            "  sku_name                      = var.db_sku\n"
            "  storage_mb                    = var.db_storage_mb\n"
            '  zone                          = "1"\n'
            '  administrator_login           = "pgadmin"\n'
            "  administrator_password        = var.db_administrator_password\n"
            "  delegated_subnet_id           = azurerm_subnet.database.id\n"
            "  private_dns_zone_id           = azurerm_private_dns_zone.database.id\n"
            "  public_network_access_enabled = false\n"
            "  backup_retention_days         = 7\n"
            + ha_block
            + "\n  depends_on = [azurerm_private_dns_zone_virtual_network_link.database]\n"
            "}\n"
        )

    if has_storage:
        blocks.append(
            "# A storage account name is globally unique across all of Azure\n"
            "# and allows only lowercase letters and digits, 3-24 of them --\n"
            "# hence the suffix rather than a readable name.\n"
            'resource "random_string" "storage" {\n'
            "  length  = 8\n"
            "  special = false\n"
            "  upper   = false\n"
            "}\n\n"
            'resource "azurerm_storage_account" "main" {\n'
            "  name                     = \"${replace(var.name, \"-\", \"\")}${random_string.storage.result}\"\n"
            "  resource_group_name      = azurerm_resource_group.main.name\n"
            "  location                 = azurerm_resource_group.main.location\n"
            '  account_tier             = "Standard"\n'
            + (
                '  account_replication_type = "ZRS"\n'
                if spec.database_multi_az
                else '  account_replication_type = "LRS"\n'
            )
            + "  min_tls_version          = \"TLS1_2\"\n"
            "}\n\n"
            'resource "azurerm_storage_container" "main" {\n'
            "  name                  = \"${var.name}-data\"\n"
            "  storage_account_name  = azurerm_storage_account.main.name\n"
            '  container_access_type = "private"\n'
            "}\n"
        )

    return "\n".join(blocks)


def _outputs_tf(*, has_network, has_db, has_storage, has_gateway) -> str:
    out = [
        'output "resource_group_name" {\n'
        "  value       = azurerm_resource_group.main.name\n"
        '  description = "Delete this and everything above goes with it."\n'
        "}\n"
    ]
    if has_network:
        out.append(
            'output "virtual_network_name" {\n'
            "  value = azurerm_virtual_network.main.name\n"
            "}\n"
        )
    if has_gateway:
        out.append(
            'output "gateway_ip" {\n'
            "  value       = azurerm_public_ip.gateway.ip_address\n"
            '  description = "Public address of the Application Gateway."\n'
            "}\n"
        )
    if has_db:
        out.append(
            'output "database_fqdn" {\n'
            "  value       = azurerm_postgresql_flexible_server.main.fqdn\n"
            '  description = "Resolvable only from inside the network."\n'
            "}\n"
        )
    if has_storage:
        out.append(
            'output "storage_account_name" {\n'
            "  value = azurerm_storage_account.main.name\n"
            "}\n"
        )
    return "\n".join(out)


def _tfvars(*, region, vm_size, db_sku, compute_count, has_compute, has_db) -> str:
    lines = [
        "# Copy to terraform.tfvars.",
        f'location = "{region}"',
    ]
    if has_compute:
        lines.append(f'vm_size        = "{vm_size}"')
        lines.append(f"instance_count = {max(1, compute_count)}")
        lines.append('# ssh_public_key = "ssh-ed25519 AAAA... you@example.com"')
    if has_db:
        lines.append(f'db_sku = "{db_sku}"')
        lines.append(
            "# db_administrator_password: do NOT put it here. Export it as\n"
            "# TF_VAR_db_administrator_password, or read it from a secret store."
        )
    return "\n".join(lines) + "\n"


def _readme(*, spec, estimate, has_db, has_gateway, db_sku) -> str:
    missing = _not_generated(spec, estimate)
    zones = _zones(spec)
    lines = [
        "# WhichCloud — Azure Terraform",
        "",
        f"Priced at **${estimate.total_monthly:,.2f}/month** in `{estimate.region}`.",
        "",
        "## What this builds",
        "",
        "- A **resource group**. Everything else is inside it, and deleting it",
        "  deletes all of this. Azure has no resource without one.",
        "- A **regional** virtual network. Its subnets span every zone in the",
        "  region — there is no subnet-per-zone here, because on Azure a zone",
        "  is a property of the resource, not of the subnet.",
    ]
    if spec.compute_count:
        lines.append(
            f"- A scale set of {spec.compute_count} instance(s)"
            + (
                f", spread across zones {', '.join(zones)}. That `zones` "
                "argument is where the availability actually comes from."
                if zones
                else ", in no particular zone."
            )
        )
    if has_gateway:
        lines.append(
            "- An **Application Gateway** in a subnet of its own — it will not"
            + " share one — "
            + (
                "at `WAF_v2`, so it is the load balancer **and** the web "
                "application firewall in a single resource."
                if spec.waf_rule_count is not None
                else "at `Standard_v2`."
            )
        )
    if has_db:
        lines.append(
            f"- PostgreSQL Flexible Server (`{db_sku}`) on a private address, "
            + (
                "`ZoneRedundant` with a standby in a second zone."
                if spec.database_multi_az
                else "single zone, no standby."
            )
        )
        lines.append(
            "  This needs a **delegated subnet** and a **private DNS zone**, "
            "both created here. Neither has an AWS counterpart."
        )
    lines += [
        "",
        "## Before you apply",
        "",
        "1. `az login`, and select the subscription you mean to bill.",
        "2. `ssh_public_key` has no default. The scale set will not build",
        "   without one.",
        "3. `db_administrator_password` has no default and does **not** belong",
        "   in `terraform.tfvars`. Export `TF_VAR_db_administrator_password`.",
        "4. Register the providers this uses if the subscription is new:",
        "   `Microsoft.Network`, `Microsoft.Compute`, `Microsoft.DBforPostgreSQL`,",
        "   `Microsoft.Storage`.",
        "",
    ]
    nat_priced = next(
        (i.label for i in estimate.items if i.label.startswith("NAT gateway ×")), None
    )
    if nat_priced and not nat_priced.endswith("× 1"):
        lines += [
            "## Where this differs from the estimate",
            "",
            f"The estimate prices `{nat_priced}`; this project builds **one**.",
            "A subnet accepts at most one NAT gateway, and this design has one",
            "subnet needing outbound access. Buying more would mean more",
            "subnets, not more resilience for these. The plan therefore costs",
            "slightly less than the figure above.",
            "",
        ]
    lines += ["## Priced but not generated", ""]
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
        "TLS certificate, no monitoring, no role assignments beyond defaults",
        "and no application. Review it before applying.",
        "",
    ]
    return "\n".join(lines)
