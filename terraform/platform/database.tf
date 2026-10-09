resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-postgres"
  subnet_ids = module.vpc.private_subnets
}
resource "aws_security_group" "rds" {
  for_each    = local.postgres_services
  name_prefix = "${local.name}-${each.key}-rds-"
  vpc_id      = module.vpc.vpc_id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}
resource "aws_db_parameter_group" "postgres" {
  name_prefix = "${local.name}-postgres-"
  family      = "postgres16"
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}
resource "aws_db_instance" "postgres" {
  for_each                    = local.postgres_services
  identifier                  = "${local.name}-${each.key}"
  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = var.db_instance_class
  allocated_storage           = var.db_allocated_storage
  max_allocated_storage       = var.db_allocated_storage * 5
  storage_encrypted           = true
  publicly_accessible         = false
  db_name                     = each.value
  username                    = var.db_username
  manage_master_user_password = true
  db_subnet_group_name        = aws_db_subnet_group.main.name
  vpc_security_group_ids      = [aws_security_group.rds[each.key].id]
  parameter_group_name        = aws_db_parameter_group.postgres.name
  multi_az                    = var.db_multi_az
  backup_retention_period     = var.db_backup_retention_days
  deletion_protection         = var.environment == "prod"
  skip_final_snapshot         = false
  final_snapshot_identifier   = "${local.name}-${each.key}-final"
  copy_tags_to_snapshot       = true
  auto_minor_version_upgrade  = true
}
