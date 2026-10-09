data "aws_secretsmanager_secret_version" "redis" {
  secret_id = var.redis_credentials_secret_arn
}
resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name}-cache"
  subnet_ids = module.vpc.private_subnets
}
resource "aws_security_group" "cache" {
  name_prefix = "${local.name}-cache-"
  vpc_id      = module.vpc.vpc_id
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}
resource "aws_elasticache_replication_group" "main" {
  replication_group_id       = "${local.name}-cache"
  description                = "Private Badminton Valkey"
  engine                     = "valkey"
  engine_version             = var.cache_engine_version
  parameter_group_name       = "default.valkey8"
  node_type                  = var.cache_node_type
  num_cache_clusters         = var.cache_node_count
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.cache.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = jsondecode(data.aws_secretsmanager_secret_version.redis.secret_string)["password"]
  automatic_failover_enabled = var.cache_node_count > 1
  multi_az_enabled           = var.cache_node_count > 1
  snapshot_retention_limit   = 7
}
