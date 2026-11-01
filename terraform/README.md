# Infrastructure-as-Code Multi-Environment Deployment
### Project ID: P74 | Student: Mayank Thakur (500123412, Section B3)

This directory contains reusable, production-ready Terraform modules and environment configurations demonstrating **cloud-specific architectural behavior and parameterized differences**.

## Directory Structure

```
terraform/
├── modules/
│   ├── vpc/             # Parameterized networking (single vs multi-AZ NAT, CIDR, subnets)
│   ├── compute/         # ALB, Launch Templates, Auto Scaling Group with target tracking
│   ├── database/        # PostgreSQL RDS (single vs Multi-AZ standby, read replicas, retention)
│   ├── storage_cache/   # S3 versioning & ElastiCache Redis (standalone vs clustered)
│   └── monitoring/      # CloudWatch CPU & 5xx error alarms, SNS notification topic
└── environments/
    ├── dev/             # Minimal cost footprint (t4g.small, single AZ, no replicas, $48.50/mo)
    ├── staging/         # Pre-prod validation (t4g.medium, 2 AZs, 1 read replica, $215.80/mo)
    └── prod/            # High Availability (c6g.xlarge, 3 AZs, Multi-AZ RDS + 2 replicas, $684.20/mo)
```

## Parameter Matrix Comparison

| Parameter | Development (`dev`) | Staging (`staging`) | Production (`prod`) | Architectural Justification |
|---|---|---|---|---|
| **VPC CIDR** | `10.0.0.0/16` | `10.2.0.0/16` | `10.1.0.0/16` | Strict network segregation prevents cross-env pollution |
| **Availability Zones** | 2 (`ap-south-1a`, `1b`) | 2 (`ap-south-1a`, `1b`) | 3 (`ap-south-1a`, `1b`, `1c`) | 99.99% multi-AZ SLA in Prod; low-cost in Dev |
| **NAT Gateways** | 1 (shared across AZs) | 1 (shared across AZs) | 3 (1 dedicated per AZ) | Production fault isolation against single AZ gateway loss |
| **Compute Instance Type**| `t4g.small` (ARM Graviton) | `t4g.medium` | `c6g.xlarge` (Compute-optimized) | Cost optimization in Dev; peak sustained throughput in Prod |
| **Auto Scaling (Min/Max)**| Min 1 / Max 2 | Min 2 / Max 4 | Min 3 / Max 12 | Elastic scaling for sudden traffic spikes in Prod |
| **Database Instance** | `db.t4g.micro` | `db.t4g.small` | `db.m6g.large` | Low IOPS in Dev; memory & compute heavy query performance in Prod |
| **RDS Multi-AZ Standby** | `false` | `true` | `true` | Sub-60s automated failover without data loss in Prod |
| **Read Replicas** | 0 | 1 | 2 (across distinct AZs) | Offloads analytics and read-heavy queries from primary writer |
| **Backup Retention** | 1 day | 7 days | 30 days (with PITR) | Compliance & disaster recovery requirements |
| **Deletion Protection** | `false` | `false` | `true` | Prevents catastrophic human error or terraform destroy in Prod |
| **Redis Cache** | `cache.t4g.micro` (1 node) | `cache.t4g.small` (2 nodes) | `cache.m6g.large` (3-node cluster) | Automated cache failover & high hit ratio in Prod |
| **S3 Versioning** | `Suspended` | `Enabled` | `Enabled` (with Lifecycle) | Immutable audit trails and accidental overwrite protection |
| **Estimated Monthly** | **\$48.50** | **\$215.80** | **\$684.20** | **14x cost difference** matching SLA and resilience trade-offs |

## Quick Start Commands

```bash
# 1. Initialize Terraform for an environment
cd terraform/environments/dev
terraform init

# 2. Plan deployment with parameterized variables
terraform plan -var-file="terraform.tfvars"

# 3. Apply deployment
terraform apply -var-file="terraform.tfvars" -auto-approve
```
