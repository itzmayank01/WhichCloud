# S3 Bucket
resource "aws_s3_bucket" "artifacts" {
  bucket_prefix = "${var.bucket_prefix}-${var.environment}-"
  force_destroy = var.environment == "prod" ? false : true

  tags = merge(var.tags, {
    Name        = "${var.environment}-artifacts-bucket"
    Environment = var.environment
  })
}

resource "aws_s3_bucket_versioning" "versioning" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = var.s3_versioning_status
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "encryption" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "block" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Redis ElastiCache
resource "aws_security_group" "redis" {
  name        = "${var.environment}-redis-sg"
  description = "Security Group for ${var.environment} Redis cache"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Redis port from compute cluster"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.app_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name        = "${var.environment}-redis-sg"
    Environment = var.environment
  })
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.environment}-redis-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(var.tags, {
    Name        = "${var.environment}-redis-subnet-group"
    Environment = var.environment
  })
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${var.environment}-redis-cluster"
  description                = "WhichCloud Redis Cache for ${var.environment}"
  node_type                  = var.cache_node_type
  num_cache_clusters         = var.num_cache_nodes
  parameter_group_name       = "default.redis7"
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.redis.id]
  automatic_failover_enabled = var.automatic_failover_enabled
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  tags = merge(var.tags, {
    Name        = "${var.environment}-redis"
    Environment = var.environment
  })
}

