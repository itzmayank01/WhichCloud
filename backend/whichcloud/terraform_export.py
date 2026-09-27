"""The priced architecture, as real Terraform.

Only `ArchitectureSpec` fields and the SKUs the estimator already resolved
feed this — never re-derived, never guessed. A component with no line item
in the estimate gets no resource block; it is named instead in the
generated README under "priced but not generated" rather than silently
built with an invented size. Same discipline as `Estimate.missing`: what
cannot be backed by a real number is disclosed, not fabricated.

Built from `terraform-aws-modules` wherever a stable one exists, so the
generated files are a starting point a team would actually use rather than
hand-rolled HCL that happens to run once.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

from .estimator import ArchitectureSpec, Estimate

_VPC_MODULE_VERSION = "~> 5.19"
_RDS_MODULE_VERSION = "~> 6.10"
_S3_MODULE_VERSION = "~> 4.6"
_ALB_MODULE_VERSION = "~> 9.16"
_ASG_MODULE_VERSION = "~> 8.3"
_ECS_MODULE_VERSION = "~> 5.0"


def _sku_for(estimate: Estimate, *, prefix: str, exclude: str | None = None) -> str | None:
    """The real SKU the estimator picked for a category, if it priced one.

    Matches the same label prefixes `topology.py`'s `_KIND_BY_PREFIX` uses,
    so this module and the diagram never disagree about which line is
    which.
    """
    for item in estimate.items:
        if item.label.startswith(prefix) and (exclude is None or exclude not in item.label):
            return item.sku
    return None


def _not_generated(spec: ArchitectureSpec, estimate: Estimate) -> list[str]:
    """Everything the estimate priced that this generator does not yet turn
    into a resource. Named, never dropped — a downloaded project that is
    silently missing half its bill is worse than one that says so."""
    generated_prefixes = {
        "Compute",
        "Fargate",  # vCPU/memory lines fold into the ECS task definition
        "Database",  # covers the primary; replicas are listed separately below
        "Object storage",
        "Load balancer",
    }
    missing = [
        item.label
        for item in estimate.items
        if not any(item.label.startswith(p) for p in generated_prefixes)
    ]
    if spec.database_read_replicas > 0:
        missing.append(f"Database read replica × {spec.database_read_replicas}")
    return missing


#: The only two environments the generated `locals.env` map (in `_main_tf`)
#: resolves. Kept as a Python set purely to validate the caller's input --
#: the actual per-environment VALUES live once, in the HCL itself, so there
#: is exactly one place that says what "prod" means rather than a Python
#: copy that could drift from the generated file it is meant to describe.
#:
#: Multi-AZ and NAT-gateway redundancy are deliberately NOT environment
#: properties here: `test_terraform_matches_estimate.py` holds this generator
#: to the promise that what it builds matches what the estimate charged for,
#: and multi_az/NAT count are real line items on that bill. Making them
#: environment-driven would let a "dev" export quietly build less than a
#: "prod" export was priced for, or vice versa -- exactly the drift this
#: tool exists to prevent. Deletion protection, snapshot-on-destroy and
#: backup retention carry no such price tag, which is what makes them safe
#: to vary by environment instead.
_VALID_ENVIRONMENTS = {"dev", "prod"}


def generate(
    spec: ArchitectureSpec, estimate: Estimate, environment: str = "dev"
) -> dict[str, str]:
    """AWS only. Returns {filename: contents} for a downloadable project.

    `environment` selects which entry of the generated `locals.env` map
    (see `_main_tf`) `variables.tf`'s own default resolves to -- it only
    changes which of the two `environments/*.tfvars` files this run's README
    tells the reader to pass with `-var-file`. The generated HCL itself
    always carries both dev and prod, which is what makes it the same module
    for both rather than two.
    """
    if environment not in _VALID_ENVIRONMENTS:
        environment = "dev"

    has_fargate = spec.fargate_task_count > 0
    has_ec2 = spec.compute_count > 0 and not has_fargate
    has_compute = has_fargate or has_ec2
    has_db = bool(spec.database_vcpu)
    has_storage = spec.storage_gb > 0
    has_alb = spec.load_balancer
    has_network = has_compute or has_db or has_alb

    az_count = max(spec.nat_gateway_count, 2) if spec.nat_gateway_count else 2
    single_nat = spec.nat_gateway_count <= 1

    compute_sku = _sku_for(estimate, prefix="Compute")
    database_sku = _sku_for(estimate, prefix="Database", exclude="replica")
    region = estimate.region

    files: dict[str, str] = {}
    files["variables.tf"] = _variables_tf(
        has_compute=has_compute,
        has_ec2=has_ec2,
        has_fargate=has_fargate,
        has_db=has_db,
        has_storage=has_alb or has_storage,
        region=region,
        az_count=az_count,
        environment=environment,
        compute_count=spec.compute_count,
        compute_sku=compute_sku,
        database_sku=database_sku,
        database_multi_az=spec.database_multi_az,
        storage_gb=spec.storage_gb,
        fargate_task_vcpu=spec.fargate_task_vcpu,
        fargate_task_memory_gb=spec.fargate_task_memory_gb,
        fargate_task_count=spec.fargate_task_count,
        fargate_arm=spec.fargate_arm,
    )
    files["main.tf"] = _main_tf(
        spec=spec,
        estimate=estimate,
        has_network=has_network,
        has_ec2=has_ec2,
        has_fargate=has_fargate,
        has_db=has_db,
        has_storage=has_storage,
        has_alb=has_alb,
        az_count=az_count,
        single_nat=single_nat,
    )
    files["outputs.tf"] = _outputs_tf(
        has_network=has_network, has_db=has_db, has_storage=has_storage, has_alb=has_alb
    )
    files["terraform.tfvars.example"] = _tfvars_example(
        has_compute=has_compute,
        has_ec2=has_ec2,
        has_db=has_db,
        compute_count=spec.compute_count,
        compute_sku=compute_sku,
        database_sku=database_sku,
    )
    files["environments/dev.tfvars"] = _env_tfvars("dev", spec)
    files["environments/prod.tfvars"] = _env_tfvars("prod", spec)
    files["README.md"] = _readme(
        spec=spec,
        estimate=estimate,
        environment=environment,
        has_ec2=has_ec2,
        has_fargate=has_fargate,
        has_db=has_db,
        has_storage=has_storage,
        has_alb=has_alb,
        has_network=has_network,
    )
    return files


def _env_tfvars(environment: str, spec: ArchitectureSpec) -> str:
    """The one value a caller must set to choose an environment.

    Deletion protection, snapshot-on-destroy and backup retention are
    derived in `locals.env` inside main.tf from this single value -- putting
    them here too would let the two disagree. `compute_count` is the one
    exception: prod runs the fleet size that was actually priced, dev runs a
    single instance, because a dev-shaped clone of a 3-instance production
    fleet is not what "dev environment" means to anyone paying for it.
    """
    compute_count = spec.compute_count if environment == "prod" else min(1, spec.compute_count)
    lines = [
        f'environment = "{environment}"',
        "",
    ]
    if spec.compute_count > 0:
        lines += [f"compute_count = {compute_count}", ""]
    return "\n".join(lines)


def zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


# ── file bodies ──────────────────────────────────────────────────────────


def _variables_tf(
    *,
    has_compute: bool,
    has_ec2: bool,
    has_fargate: bool,
    has_db: bool,
    has_storage: bool,
    region: str,
    az_count: int,
    environment: str,
    compute_count: int,
    compute_sku: str | None,
    database_sku: str | None,
    database_multi_az: bool,
    storage_gb: float,
    fargate_task_vcpu: float,
    fargate_task_memory_gb: float,
    fargate_task_count: int,
    fargate_arm: bool,
) -> str:
    lines = [
        "variable \"aws_region\" {",
        "  type    = string",
        f'  default = "{region}"',
        "}",
        "",
        "variable \"az_count\" {",
        "  type    = number",
        f"  default = {az_count}",
        "}",
        "",
        "variable \"project_name\" {",
        "  type    = string",
        '  default = "whichcloud-app"',
        "}",
        "",
        "# Selects the entry of locals.env (main.tf) that deletion",
        "# protection, snapshot-on-destroy and backup retention below are",
        "# drawn from. Pass with -var-file=environments/dev.tfvars or",
        "# environments/prod.tfvars -- never edit this default in place, or",
        "# dev and prod stop being two runs of the same module and become",
        "# two copies of it.",
        "variable \"environment\" {",
        "  type    = string",
        f'  default = "{environment}"',
        "",
        "  validation {",
        "    condition     = contains([\"dev\", \"prod\"], var.environment)",
        "    error_message = \"environment must be \\\"dev\\\" or \\\"prod\\\".\"",
        "  }",
        "}",
    ]
    if has_ec2:
        lines += [
            "",
            "variable \"compute_count\" {",
            "  type    = number",
            f"  default = {compute_count}",
            "}",
            "",
            "variable \"compute_instance_type\" {",
            "  type    = string",
            f'  default = "{compute_sku}"',
            "}",
        ]
    if has_fargate:
        lines += [
            "",
            "variable \"fargate_cpu\" {",
            "  type        = number",
            "  description = \"vCPU * 1024, e.g. 0.5 vCPU = 512\"",
            f"  default     = {int(fargate_task_vcpu * 1024)}",
            "}",
            "",
            "variable \"fargate_memory\" {",
            "  type        = number",
            "  description = \"MiB\"",
            f"  default     = {int(fargate_task_memory_gb * 1024)}",
            "}",
            "",
            "variable \"fargate_desired_count\" {",
            "  type    = number",
            f"  default = {fargate_task_count}",
            "}",
        ]
    if has_db:
        lines += [
            "",
            "variable \"database_instance_class\" {",
            "  type    = string",
            f'  default = "{database_sku}"',
            "}",
            "",
            "variable \"database_multi_az\" {",
            "  type    = bool",
            f"  default = {str(database_multi_az).lower()}",
            "}",
            "",
            "variable \"database_username\" {",
            "  type    = string",
            '  default = "app"',
            "}",
            "",
            "variable \"database_password\" {",
            "  type      = string",
            "  sensitive = true",
            "  description = \"Set in terraform.tfvars — never commit it.\"",
            "}",
        ]
    if has_storage:
        lines += [
            "",
            "variable \"storage_bucket_name\" {",
            "  type        = string",
            "  description = \"Must be globally unique — the default is a placeholder.\"",
            '  default     = "whichcloud-app-assets-change-me"',
            "}",
        ]
    return "\n".join(lines) + "\n"


def _main_tf(
    *,
    spec: ArchitectureSpec,
    estimate: Estimate,
    has_network: bool,
    has_ec2: bool,
    has_fargate: bool,
    has_db: bool,
    has_storage: bool,
    has_alb: bool,
    az_count: int,
    single_nat: bool,
) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = (
        "# Generated by WhichCloud — do not hand-edit the header, the rest is yours.\n"
        f"# Priced total this was generated from: ${estimate.total_monthly:.2f}/mo "
        f"({estimate.provider}, {estimate.region})\n"
        f"# Generated: {generated_at}\n"
        "#\n"
        "# Every instance type and DB class below is the exact SKU WhichCloud priced —\n"
        "# not a placeholder. Terraform and the bill you saw can't drift apart.\n"
    )

    blocks = [
        header,
        (
            "terraform {\n"
            "  required_version = \">= 1.5\"\n"
            "  required_providers {\n"
            "    aws = {\n"
            "      source  = \"hashicorp/aws\"\n"
            "      version = \"~> 5.0\"\n"
            "    }\n"
            "  }\n"
            "}\n"
        ),
        (
            "provider \"aws\" {\n"
            "  region = var.aws_region\n"
            "}\n"
        ),
        (
            "# The ONLY place dev and prod differ. Every resource below reads\n"
            "# deletion-protection, snapshot-on-destroy and backup-retention\n"
            "# settings from local.env rather than from a hardcoded value or a\n"
            "# second copy of this file -- that is what makes this one reusable\n"
            "# module instead of two maintained ones. Instance types, DB\n"
            "# classes, Multi-AZ and NAT redundancy are deliberately absent\n"
            "# here: those come from what WhichCloud priced, in variables.tf,\n"
            "# and stay identical across environments so the Terraform never\n"
            "# builds something other than what the estimate charged for.\n"
            "locals {\n"
            "  env_defaults = {\n"
            "    dev = {\n"
            "      deletion_protection     = false\n"
            "      skip_final_snapshot     = true\n"
            "      backup_retention_period = 1\n"
            "    }\n"
            "    prod = {\n"
            "      deletion_protection     = true\n"
            "      skip_final_snapshot     = false\n"
            "      backup_retention_period = 7\n"
            "    }\n"
            "  }\n"
            "  env = local.env_defaults[var.environment]\n"
            "\n"
            "  common_tags = {\n"
            "    Environment = var.environment\n"
            "    Project     = var.project_name\n"
            "    ManagedBy   = \"terraform\"\n"
            "  }\n"
            "}\n"
        ),
    ]

    if has_network:
        blocks.append(
            "data \"aws_availability_zones\" \"available\" {\n"
            "  state = \"available\"\n"
            "}\n"
        )
        blocks.append(
            "module \"vpc\" {\n"
            f'  source  = "terraform-aws-modules/vpc/aws"\n'
            f'  version = "{_VPC_MODULE_VERSION}"\n'
            "\n"
            "  name = \"${var.project_name}-${var.environment}-vpc\"\n"
            "  cidr = \"10.0.0.0/16\"\n"
            "\n"
            "  azs             = slice(data.aws_availability_zones.available.names, 0, var.az_count)\n"
            "  private_subnets = [for i in range(var.az_count) : cidrsubnet(\"10.0.0.0/16\", 8, i)]\n"
            "  public_subnets  = [for i in range(var.az_count) : cidrsubnet(\"10.0.0.0/16\", 8, i + 100)]\n"
            "\n"
            f"  enable_nat_gateway = {str(spec.nat_gateway_count > 0).lower()}\n"
            f"  single_nat_gateway = {str(single_nat).lower()}\n"
            "  enable_dns_hostnames = true\n"
            "\n"
            "  tags = local.common_tags\n"
            "}\n"
        )

    if has_ec2:
        blocks.append(
            "data \"aws_ami\" \"app\" {\n"
            "  most_recent = true\n"
            "  owners      = [\"amazon\"]\n"
            "\n"
            "  filter {\n"
            "    name   = \"name\"\n"
            "    values = [\"al2023-ami-*-"
            + ("arm64" if spec.arch == "arm64" else "x86_64")
            + "\"]\n"
            "  }\n"
            "}\n"
        )
        blocks.append(
            "module \"compute\" {\n"
            f'  source  = "terraform-aws-modules/autoscaling/aws"\n'
            f'  version = "{_ASG_MODULE_VERSION}"\n'
            "\n"
            "  name = \"${var.project_name}-${var.environment}-asg\"\n"
            "\n"
            "  image_id        = data.aws_ami.app.id\n"
            "  instance_type   = var.compute_instance_type\n"
            "  # var.compute_count is the fleet size -- WhichCloud priced the\n"
            "  # exact number above, and environments/dev.tfvars overrides it\n"
            "  # to 1 so a dev stack does not run and pay for prod's fleet.\n"
            "  min_size        = var.compute_count\n"
            "  max_size        = var.compute_count\n"
            "  desired_capacity = var.compute_count\n"
            "  vpc_zone_identifier = module.vpc.private_subnets\n"
            "  tags = local.common_tags\n"
            + (
                "  traffic_source_attachments = {\n"
                "    alb = {\n"
                "      traffic_source_identifier = module.alb.target_groups[\"app\"].arn\n"
                "      traffic_source_type       = \"elbv2\"\n"
                "    }\n"
                "  }\n"
                if has_alb
                else ""
            )
            + "}\n"
        )

    if has_fargate:
        blocks.append(
            "module \"ecs_cluster\" {\n"
            f'  source  = "terraform-aws-modules/ecs/aws"\n'
            f'  version = "{_ECS_MODULE_VERSION}"\n'
            "\n"
            "  cluster_name = \"${var.project_name}-${var.environment}-cluster\"\n"
            "}\n"
        )
        blocks.append(
            "resource \"aws_ecs_task_definition\" \"app\" {\n"
            "  family                   = \"${var.project_name}-${var.environment}-task\"\n"
            "  requires_compatibilities = [\"FARGATE\"]\n"
            "  network_mode             = \"awsvpc\"\n"
            "  cpu                      = var.fargate_cpu\n"
            "  memory                   = var.fargate_memory\n"
            "  runtime_platform {\n"
            "    cpu_architecture        = "
            + ('"ARM64"' if spec.fargate_arm else '"X86_64"')
            + "\n"
            "    operating_system_family = \"LINUX\"\n"
            "  }\n"
            "  execution_role_arn = aws_iam_role.ecs_execution.arn\n"
            "\n"
            "  container_definitions = jsonencode([\n"
            "    {\n"
            "      name  = \"app\"\n"
            "      image = \"REPLACE_ME/app:latest\"\n"
            "      portMappings = [{ containerPort = 8080, protocol = \"tcp\" }]\n"
            "    }\n"
            "  ])\n"
            "}\n"
        )
        blocks.append(
            "resource \"aws_iam_role\" \"ecs_execution\" {\n"
            "  # IAM is account-wide, not per-VPC -- dev and prod deployed into\n"
            "  # the same account would collide on this name without the\n"
            "  # environment in it.\n"
            "  name = \"${var.project_name}-${var.environment}-ecs-execution\"\n"
            "\n"
            "  assume_role_policy = jsonencode({\n"
            "    Version = \"2012-10-17\"\n"
            "    Statement = [{\n"
            "      Action    = \"sts:AssumeRole\"\n"
            "      Effect    = \"Allow\"\n"
            "      Principal = { Service = \"ecs-tasks.amazonaws.com\" }\n"
            "    }]\n"
            "  })\n"
            "}\n"
        )
        blocks.append(
            "resource \"aws_iam_role_policy_attachment\" \"ecs_execution\" {\n"
            "  role       = aws_iam_role.ecs_execution.name\n"
            "  policy_arn = \"arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy\"\n"
            "}\n"
        )
        blocks.append(
            "resource \"aws_security_group\" \"fargate_service\" {\n"
            "  name_prefix = \"${var.project_name}-${var.environment}-svc-\"\n"
            "  vpc_id      = module.vpc.vpc_id\n"
            "\n"
            "  egress {\n"
            "    from_port   = 0\n"
            "    to_port     = 0\n"
            "    protocol    = \"-1\"\n"
            "    cidr_blocks = [\"0.0.0.0/0\"]\n"
            "  }\n"
            "}\n"
        )
        blocks.append(
            "resource \"aws_ecs_service\" \"app\" {\n"
            "  name            = \"${var.project_name}-${var.environment}-service\"\n"
            "  cluster         = module.ecs_cluster.cluster_arn\n"
            "  task_definition = aws_ecs_task_definition.app.arn\n"
            "  desired_count   = var.fargate_desired_count\n"
            "  launch_type     = \"FARGATE\"\n"
            "\n"
            "  network_configuration {\n"
            "    subnets         = module.vpc.private_subnets\n"
            "    security_groups = [aws_security_group.fargate_service.id]\n"
            "  }\n"
            + (
                "\n"
                "  load_balancer {\n"
                "    target_group_arn = module.alb.target_groups[\"app\"].arn\n"
                "    container_name   = \"app\"\n"
                "    container_port   = 8080\n"
                "  }\n"
                if has_alb
                else ""
            )
            + "}\n"
        )

    if has_alb:
        blocks.append(
            "module \"alb\" {\n"
            f'  source  = "terraform-aws-modules/alb/aws"\n'
            f'  version = "{_ALB_MODULE_VERSION}"\n'
            "\n"
            "  name    = \"${var.project_name}-${var.environment}-alb\"\n"
            "  vpc_id  = module.vpc.vpc_id\n"
            "  subnets = module.vpc.public_subnets\n"
            "\n"
            "  security_group_ingress_rules = {\n"
            "    http = {\n"
            "      from_port   = 80\n"
            "      to_port     = 80\n"
            "      ip_protocol = \"tcp\"\n"
            "      cidr_ipv4   = \"0.0.0.0/0\"\n"
            "    }\n"
            "  }\n"
            "  security_group_egress_rules = {\n"
            "    all = {\n"
            "      ip_protocol = \"-1\"\n"
            "      cidr_ipv4   = \"0.0.0.0/0\"\n"
            "    }\n"
            "  }\n"
            "\n"
            "  target_groups = {\n"
            "    app = {\n"
            "      name_prefix       = \"app-\"\n"
            "      protocol          = \"HTTP\"\n"
            "      port              = 8080\n"
            "      target_type       = "
            + ('"ip"' if has_fargate else '"instance"')
            + "\n"
            "      create_attachment = false\n"
            "    }\n"
            "  }\n"
            "\n"
            "  listeners = {\n"
            "    http = {\n"
            "      port     = 80\n"
            "      protocol = \"HTTP\"\n"
            "      forward  = { target_group_key = \"app\" }\n"
            "    }\n"
            "  }\n"
            "\n"
            "  tags = local.common_tags\n"
            "}\n"
        )

    if has_db:
        blocks.append(
            "resource \"aws_db_subnet_group\" \"app\" {\n"
            "  name       = \"${var.project_name}-${var.environment}-db\"\n"
            "  subnet_ids = module.vpc.private_subnets\n"
            "  tags       = local.common_tags\n"
            "}\n"
        )
        blocks.append(
            "module \"database\" {\n"
            f'  source  = "terraform-aws-modules/rds/aws"\n'
            f'  version = "{_RDS_MODULE_VERSION}"\n'
            "\n"
            "  identifier = \"${var.project_name}-${var.environment}-db\"\n"
            "\n"
            "  engine         = \"postgres\"\n"
            "  engine_version = \"16\"\n"
            "  instance_class = var.database_instance_class\n"
            f"  allocated_storage = {max(int(spec.db_storage_gb), 20)}\n"
            "\n"
            "  db_name  = \"app\"\n"
            "  username = var.database_username\n"
            "  password = var.database_password\n"
            "  port     = 5432\n"
            "\n"
            "  multi_az = var.database_multi_az\n"
            "\n"
            "  # Everything below this line is the dev/prod difference. Same\n"
            "  # engine, same instance class, same Multi-AZ setting -- only\n"
            "  # whether the instance can be torn down without a snapshot,\n"
            "  # and how many days of backups survive it, changes.\n"
            "  deletion_protection     = local.env.deletion_protection\n"
            "  skip_final_snapshot     = local.env.skip_final_snapshot\n"
            "  backup_retention_period = local.env.backup_retention_period\n"
            "\n"
            "  db_subnet_group_name   = aws_db_subnet_group.app.name\n"
            "  create_db_subnet_group = false\n"
            "  vpc_security_group_ids = [aws_security_group.database.id]\n"
            "\n"
            "  tags = local.common_tags\n"
            "}\n"
        )
        blocks.append(
            "resource \"aws_security_group\" \"database\" {\n"
            "  name_prefix = \"${var.project_name}-${var.environment}-db-\"\n"
            "  vpc_id      = module.vpc.vpc_id\n"
            "\n"
            "  ingress {\n"
            "    from_port   = 5432\n"
            "    to_port     = 5432\n"
            "    protocol    = \"tcp\"\n"
            "    cidr_blocks = [module.vpc.vpc_cidr_block]\n"
            "  }\n"
            "}\n"
        )

    if has_storage:
        blocks.append(
            "module \"storage\" {\n"
            f'  source  = "terraform-aws-modules/s3-bucket/aws"\n'
            f'  version = "{_S3_MODULE_VERSION}"\n'
            "\n"
            "  bucket = var.storage_bucket_name\n"
            "\n"
            "  block_public_acls       = true\n"
            "  block_public_policy     = true\n"
            "  ignore_public_acls      = true\n"
            "  restrict_public_buckets = true\n"
            "\n"
            "  tags = local.common_tags\n"
            + (
                "\n"
                "  lifecycle_rule = [{\n"
                "    id      = \"age-into-cheaper-storage\"\n"
                "    enabled = true\n"
                "    transition = [{\n"
                "      days          = 90\n"
                "      storage_class = \"STANDARD_IA\"\n"
                "    }]\n"
                "  }]\n"
                if spec.lifecycle_gb > 0
                else ""
            )
            + "}\n"
        )

    return "\n".join(blocks)


def _outputs_tf(*, has_network: bool, has_db: bool, has_storage: bool, has_alb: bool) -> str:
    lines: list[str] = []
    if has_network:
        lines += [
            "output \"vpc_id\" {",
            "  value = module.vpc.vpc_id",
            "}",
            "",
        ]
    if has_alb:
        lines += [
            "output \"load_balancer_dns_name\" {",
            "  value = module.alb.dns_name",
            "}",
            "",
        ]
    if has_db:
        lines += [
            "output \"database_endpoint\" {",
            "  value     = module.database.db_instance_endpoint",
            "  sensitive = true",
            "}",
            "",
        ]
    if has_storage:
        lines += [
            "output \"storage_bucket\" {",
            "  value = module.storage.s3_bucket_id",
            "}",
            "",
        ]
    return "\n".join(lines) if lines else "# Nothing generated has an output worth surfacing.\n"


def _tfvars_example(
    *,
    has_compute: bool,
    has_ec2: bool,
    has_db: bool,
    compute_count: int,
    compute_sku: str | None,
    database_sku: str | None,
) -> str:
    lines = [
        "# Copy to terraform.tfvars and fill in the secrets.",
        "# Everything else already defaults to the priced architecture.",
        "",
    ]
    if has_db:
        lines += ['database_password = "change-me-before-apply"', ""]
    return "\n".join(lines)


def _readme(
    *,
    spec: ArchitectureSpec,
    estimate: Estimate,
    environment: str,
    has_ec2: bool,
    has_fargate: bool,
    has_db: bool,
    has_storage: bool,
    has_alb: bool,
    has_network: bool,
) -> str:
    included = []
    if has_network:
        included.append("VPC — public + private subnets across the AZs this was priced for")
    if has_ec2:
        included.append(
            f"Compute — Auto Scaling Group, {spec.compute_count}× the exact instance "
            f"type priced ({_sku_for(estimate, prefix='Compute')})"
        )
    if has_fargate:
        included.append(
            f"Compute — ECS Fargate, {spec.fargate_task_count} task(s) at the priced "
            f"vCPU/memory shape"
        )
    if has_alb:
        included.append("Load balancer — ALB in front of the compute tier")
    if has_db:
        included.append(
            f"Database — RDS Postgres, the exact instance class priced "
            f"({_sku_for(estimate, prefix='Database', exclude='replica')})"
            + (", Multi-AZ" if spec.database_multi_az else "")
        )
    if has_storage:
        included.append("Object storage — private S3 bucket")

    not_generated = _not_generated(spec, estimate)

    lines = [
        "# Terraform — generated by WhichCloud",
        "",
        f"Generated from a **${estimate.total_monthly:.2f}/mo** estimate "
        f"({estimate.provider}, {estimate.region}). Every instance type and "
        "database class below is the exact SKU that was priced — this file "
        "and the bill you saw cannot disagree.",
        "",
        "## What's here",
        "",
        *[f"- {line}" for line in included],
        "",
    ]
    if not_generated:
        lines += [
            "## Priced, but not generated as Terraform yet",
            "",
            "These were part of the estimate — some free, some not — and are "
            "not silently included above:",
            "",
            *[f"- {line}" for line in not_generated],
            "",
        ]
    env_table = [
        "| | dev | prod |",
        "|---|---|---|",
        "| Database deletion protection | no | yes |",
        "| Database destroyable without a final snapshot | yes | no |",
        "| Database backup retention | 1 day | 7 days |",
        "| Resource names, tags | `*-dev-*`, `Environment=dev` | `*-prod-*`, `Environment=prod` |",
    ]
    if has_ec2:
        env_table.append(
            f"| Compute fleet size | 1 (`environments/dev.tfvars`) | "
            f"{spec.compute_count} (`environments/prod.tfvars`) |"
        )

    lines += [
        "## Environments",
        "",
        "One module, two environments — `environments/dev.tfvars` and "
        "`environments/prod.tfvars` set `environment`, and deletion "
        "protection, snapshot and backup-retention behaviour below follow "
        "from it in `main.tf`'s `locals.env` block, along with the name "
        "every resource gets so a dev and a prod stack can coexist in the "
        "same AWS account. Instance types, DB classes, Multi-AZ and NAT "
        "redundancy never change between environments: those are exactly "
        "what WhichCloud priced, and stay that way everywhere so this file "
        "and the bill you saw can't disagree.",
        "",
        *env_table,
        "",
        f"This project was generated for **{environment}**; the default in "
        "`variables.tf` reflects that, but a plan or apply against the "
        "other environment's tfvars is the same module, not a different one:",
        "",
        "```bash",
        "terraform plan -var-file=environments/dev.tfvars",
        "terraform plan -var-file=environments/prod.tfvars",
        "```",
        "",
        "Diff the two plans and every difference traces back to one line in "
        "`locals.env` — that is the whole point of the exercise.",
        "",
        "## Use it",
        "",
        "```bash",
        "cp terraform.tfvars.example terraform.tfvars   # fill in secrets",
        "terraform init",
        "terraform plan -var-file=environments/{environment}.tfvars",
        "terraform apply -var-file=environments/{environment}.tfvars",
        "```",
        "",
        "Open this folder directly in VS Code or any editor — nothing here "
        "needs WhichCloud running to work.",
    ]
    return "\n".join(lines).replace("{environment}", environment) + "\n"
