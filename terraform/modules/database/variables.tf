variable "environment" {
  description = "Deployment environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where database subnets live"
  type        = string
}

variable "subnet_ids" {
  description = "Private Subnet IDs for Database Subnet Group"
  type        = list(string)
}

variable "app_security_group_id" {
  description = "Security Group ID of the compute nodes permitted to access PostgreSQL"
  type        = string
}

variable "instance_class" {
  description = "RDS instance class (e.g. db.t4g.micro for dev, db.m6g.large for prod)"
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "multi_az" {
  description = "Enable Multi-AZ high-availability standby replica (false for dev, true for prod)"
  type        = bool
  default     = false
}

variable "read_replica_count" {
  description = "Count of read replicas to provision for read scale-out (0 for dev, 2 for prod)"
  type        = number
  default     = 0
}

variable "backup_retention_period" {
  description = "Automated backup retention in days (1 for dev, 30 for prod)"
  type        = number
  default     = 1
}

variable "deletion_protection" {
  description = "Prevent accidental DB deletion (false for dev, true for prod)"
  type        = bool
  default     = false
}

variable "db_name" {
  description = "Initial database name"
  type        = string
  default     = "whichcloud"
}

variable "tags" {
  description = "Common resource tags"
  type        = map(string)
  default     = {}
}
