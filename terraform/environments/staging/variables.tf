variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "environment" {
  type    = string
  default = "staging"
}

variable "vpc_cidr" {
  type = string
}

variable "availability_zones" {
  type = list(string)
}

variable "enable_nat_gateway" {
  type    = bool
  default = true
}

variable "single_nat_gateway" {
  type    = bool
  default = true
}

variable "instance_type" {
  type = string
}

variable "min_capacity" {
  type = number
}

variable "max_capacity" {
  type = number
}

variable "desired_capacity" {
  type = number
}

variable "db_instance_class" {
  type = string
}

variable "db_allocated_storage" {
  type = number
}

variable "db_multi_az" {
  type = bool
}

variable "db_read_replica_count" {
  type = number
}

variable "db_backup_retention_period" {
  type = number
}

variable "db_deletion_protection" {
  type = bool
}

variable "cache_node_type" {
  type = string
}

variable "num_cache_nodes" {
  type = number
}

variable "cache_automatic_failover" {
  type = bool
}

variable "s3_versioning_status" {
  type = string
}
