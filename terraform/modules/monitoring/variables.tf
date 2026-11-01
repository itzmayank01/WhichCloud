variable "environment" {
  description = "Deployment environment name"
  type        = string
}

variable "alb_arn" {
  description = "ARN of the Application Load Balancer"
  type        = string
}

variable "target_group_arn" {
  description = "ARN of the ALB Target Group"
  type        = string
}

variable "asg_name" {
  description = "Name of the Auto Scaling Group"
  type        = string
}

variable "db_instance_id" {
  description = "Identifier of the RDS PostgreSQL instance"
  type        = string
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
