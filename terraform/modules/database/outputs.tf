output "endpoint" {
  description = "The connection endpoint for the Primary PostgreSQL instance"
  value       = aws_db_instance.primary.endpoint
}

output "address" {
  description = "The hostname of the Primary PostgreSQL instance"
  value       = aws_db_instance.primary.address
}

output "port" {
  description = "The database port"
  value       = aws_db_instance.primary.port
}

output "replica_endpoints" {
  description = "List of read replica endpoints"
  value       = aws_db_instance.replica[*].endpoint
}

output "db_security_group_id" {
  description = "Security Group ID of the RDS database"
  value       = aws_security_group.db.id
}

