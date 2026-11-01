variable "environment" {
  description = "Deployment environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where Redis cache is placed"
  type        = string
}

variable "subnet_ids" {
  description = "Private Subnet IDs for Redis Subnet Group"
  type        = list(string)
}

variable "app_security_group_id" {
  description = "Security Group ID of the compute nodes permitted to access Redis"
  type        = string
}

variable "bucket_prefix" {
  description = "Prefix for S3 storage bucket name"
  type        = string
  default     = "whichcloud-artifacts"
}

variable "s3_versioning_status" {
  description = "S3 bucket versioning status: 'Suspended' for dev, 'Enabled' for prod"
  type        = string
  default     = "Suspended"
}

variable "cache_node_type" {
  description = "ElastiCache node type (cache.t4g.micro for dev, cache.m6g.large for prod)"
  type        = string
  default     = "cache.t4g.micro"
}

variable "num_cache_nodes" {
  description = "Number of cache nodes (1 for dev standalone, 2 or 3 for prod cluster)"
  type        = number
  default     = 1
}

variable "automatic_failover_enabled" {
  description = "Enable automatic multi-AZ failover for Redis (false for dev, true for prod)"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
