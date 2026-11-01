output "alb_dns_name" {
  description = "Application URL (ALB)"
  value       = module.compute.alb_dns_name
}

output "database_primary_endpoint" {
  description = "Primary PostgreSQL Endpoint"
  value       = module.database.endpoint
}

output "redis_primary_endpoint" {
  description = "Redis Cache Endpoint"
  value       = module.storage_cache.redis_primary_endpoint
}

output "s3_bucket_name" {
  description = "Artifact Storage S3 Bucket"
  value       = module.storage_cache.s3_bucket_name
}
