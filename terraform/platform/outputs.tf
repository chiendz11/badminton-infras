output "cluster_name" {
  value = module.eks.cluster_name
}
output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}
output "vpc_id" {
  value = module.vpc.vpc_id
}
output "vpc_cidr" {
  value = var.vpc_cidr
}
output "aws_region" {
  value = var.aws_region
}
output "ecr_repository_urls" {
  value = { for service, repo in aws_ecr_repository.services : service => repo.repository_url }
}
output "database" {
  value = { for service, db in aws_db_instance.postgres : service => { host = db.address, port = db.port, name = db.db_name, secret_arn = db.master_user_secret[0].secret_arn } }
}
output "redis_endpoint" {
  value = aws_elasticache_replication_group.main.primary_endpoint_address
}
output "rabbitmq_endpoint" {
  value = aws_mq_broker.rabbitmq.instances[0].endpoints[0]
}
output "secret_arns" {
  value = { for key, secret in aws_secretsmanager_secret.application : key => secret.arn }
}
output "irsa" {
  value = { for key in ["external_secrets", "external_dns", "aws_load_balancer_controller"] : key => aws_iam_role.service_account[key].arn }
}
output "public_domain_name" {
  value = local.public_domain_name
}
output "admin_domain_name" {
  value = local.admin_domain_name
}
output "public_certificate_arn" {
  value = local.public_certificate_arn
}
output "route53_zone_id" {
  value = local.route53_zone_id
}
output "app_publisher_role_arn" {
  value = aws_iam_role.app_publisher.arn
}
output "identity_rds_endpoint" {
  value = aws_db_instance.postgres["identity"].address
}
output "identity_rds_master_secret_arn" {
  value = aws_db_instance.postgres["identity"].master_user_secret[0].secret_arn
}
output "booking_rds_endpoint" {
  value = aws_db_instance.postgres["booking"].address
}
output "booking_rds_master_secret_arn" {
  value = aws_db_instance.postgres["booking"].master_user_secret[0].secret_arn
}
output "commerce_rds_endpoint" {
  value = aws_db_instance.postgres["commerce"].address
}
output "commerce_rds_master_secret_arn" {
  value = aws_db_instance.postgres["commerce"].master_user_secret[0].secret_arn
}
output "external_secrets_role_arn" {
  value = aws_iam_role.service_account["external_secrets"].arn
}
output "external_dns_role_arn" {
  value = aws_iam_role.service_account["external_dns"].arn
}
output "aws_load_balancer_controller_role_arn" {
  value = aws_iam_role.service_account["aws_load_balancer_controller"].arn
}

output "mongodb_allowed_cidrs" {
  value = var.mongodb_allowed_cidrs
}
output "gitops_release_verifier_role_arn" {
  value = aws_iam_role.gitops_verifier.arn
}
