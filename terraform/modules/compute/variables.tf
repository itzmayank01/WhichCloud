variable "environment" {
  description = "Deployment environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where compute resources are placed"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private Subnet IDs for backend application nodes"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "Public Subnet IDs for the Application Load Balancer"
  type        = list(string)
}

variable "instance_type" {
  description = "EC2 Instance type (parameterized: dev=t4g.small, prod=c6g.xlarge)"
  type        = string
  default     = "t4g.small"
}

variable "min_capacity" {
  description = "Minimum count of instances in Auto Scaling Group"
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "Maximum count of instances in Auto Scaling Group"
  type        = number
  default     = 2
}

variable "desired_capacity" {
  description = "Desired count of instances in Auto Scaling Group"
  type        = number
  default     = 1
}

variable "target_cpu_utilization" {
  description = "Target average CPU utilization percentage for auto scaling policy"
  type        = number
  default     = 70.0
}

variable "tags" {
  description = "Common tags"
  type        = map(string)
  default     = {}
}

