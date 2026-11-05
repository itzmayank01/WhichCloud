resource "aws_db_subnet_group" "db" {
  name        = "${var.environment}-db-subnet-group"
  subnet_ids  = var.subnet_ids
  description = "Subnet group for ${var.environment} PostgreSQL RDS"

  tags = merge(var.tags, {
    Name        = "${var.environment}-db-subnet-group"
    Environment = var.environment
  })
}

resource "aws_security_group" "db" {
  name        = "${var.environment}-db-sg"
  description = "Permit PostgreSQL access from app layer only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from application security group"
    from_port       = 5432
    to_port         = 5432
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
    Name        = "${var.environment}-db-sg"
    Environment = var.environment
  })
}

resource "aws_db_instance" "primary" {
  identifier                  = "${var.environment}-postgres-primary"
  engine                      = "postgres"
  engine_version              = "16.3"
  instance_class              = var.instance_class
  allocated_storage           = var.allocated_storage
  max_allocated_storage       = var.allocated_storage * 5
  storage_type                = "gp3"
  db_name                     = var.db_name
  username                    = "whichcloud"
  manage_master_user_password = true

  multi_az                   = var.multi_az
  db_subnet_group_name       = aws_db_subnet_group.db.name
  vpc_security_group_ids     = [aws_security_group.db.id]
  backup_retention_period    = var.backup_retention_period
  deletion_protection        = var.deletion_protection
  skip_final_snapshot        = var.environment == "prod" ? false : true
  final_snapshot_identifier  = var.environment == "prod" ? "${var.environment}-db-final-snapshot" : null
  storage_encrypted          = true
  auto_minor_version_upgrade = true

  tags = merge(var.tags, {
    Name        = "${var.environment}-postgres-primary"
    Role        = "Primary"
    Environment = var.environment
  })
}

resource "aws_db_instance" "replica" {
  count                      = var.read_replica_count
  identifier                 = "${var.environment}-postgres-replica-${count.index + 1}"
  replicate_source_db        = aws_db_instance.primary.identifier
  instance_class             = var.instance_class
  auto_minor_version_upgrade = true
  vpc_security_group_ids     = [aws_security_group.db.id]
  storage_encrypted          = true
  skip_final_snapshot        = true

  tags = merge(var.tags, {
    Name        = "${var.environment}-postgres-replica-${count.index + 1}"
    Role        = "ReadReplica"
    Environment = var.environment
  })
}

