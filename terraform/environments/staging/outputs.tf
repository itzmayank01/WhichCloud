output "alb_dns_name" {
  description = "Application URL (ALB)"
  value       = module.compute.alb_dns_name
}

output "database_primary_endpoint" {
  description = "Primary PostgreSQL Endpoint"
  value       = module.database.endpoint
}

output "database_replica_endpoints" {
  description = "Read Replica PostgreSQL Endpoints"
  value       = module.database.replica_endpoints
}

output "redis_primary_endpoint" {
  description = "Redis Cache Primary Endpoint"
  value       = module.storage_cache.redis_primary_endpoint
}

output "s3_bucket_name" {
  description = "Artifact Storage S3 Bucket"
  value       = module.storage_cache.s3_bucket_name
}
