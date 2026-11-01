output "s3_bucket_name" {
  description = "Name of the S3 storage bucket"
  value       = aws_s3_bucket.artifacts.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 storage bucket"
  value       = aws_s3_bucket.artifacts.arn
}

output "redis_primary_endpoint" {
  description = "Primary endpoint address for Redis"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_reader_endpoint" {
  description = "Reader endpoint address for Redis"
  value       = aws_elasticache_replication_group.redis.reader_endpoint_address
}
