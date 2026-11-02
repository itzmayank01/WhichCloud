terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "WhichCloud"
      Environment = var.environment
      Owner       = "Mayank Thakur"
      SAP_ID      = "500123412"
      ManagedBy   = "Terraform"
    }
  }
}

module "vpc" {
  source = "../../modules/vpc"

  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  enable_nat_gateway = var.enable_nat_gateway
  single_nat_gateway = var.single_nat_gateway
}

module "compute" {
  source = "../../modules/compute"

  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  public_subnet_ids  = module.vpc.public_subnet_ids
  private_subnet_ids = module.vpc.private_subnet_ids
  instance_type      = var.instance_type
  min_capacity       = var.min_capacity
  max_capacity       = var.max_capacity
  desired_capacity   = var.desired_capacity
}

module "database" {
  source = "../../modules/database"

  environment             = var.environment
  vpc_id                  = module.vpc.vpc_id
  subnet_ids              = module.vpc.private_subnet_ids
  app_security_group_id   = module.compute.security_group_id
  instance_class          = var.db_instance_class
  allocated_storage       = var.db_allocated_storage
  multi_az                = var.db_multi_az
  read_replica_count      = var.db_read_replica_count
  backup_retention_period = var.db_backup_retention_period
  deletion_protection     = var.db_deletion_protection
}

module "storage_cache" {
  source = "../../modules/storage_cache"

  environment                = var.environment
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.private_subnet_ids
  app_security_group_id      = module.compute.security_group_id
  s3_versioning_status       = var.s3_versioning_status
  cache_node_type            = var.cache_node_type
  num_cache_nodes            = var.num_cache_nodes
  automatic_failover_enabled = var.cache_automatic_failover
}

module "monitoring" {
  source = "../../modules/monitoring"

  environment      = var.environment
  alb_arn          = module.compute.alb_arn
  target_group_arn = module.compute.target_group_arn
  asg_name         = module.compute.asg_name
  db_instance_id   = "${var.environment}-postgres-primary"
}

