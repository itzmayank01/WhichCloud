variable "environment" {
  description = "Deployment environment name (e.g. dev, staging, prod)"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "availability_zones" {
  description = "List of availability zones to span"
  type        = list(string)
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets (true for prod, false or single for dev)"
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Share a single NAT Gateway across all AZs to minimize dev cost"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Common resource tags"
  type        = map(string)
  default     = {}
}
