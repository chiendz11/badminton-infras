# Amazon MQ's provider requires a password. The existing secret value is
# sensitive but enters encrypted Terraform state; never emit raw outputs.
data "aws_secretsmanager_secret_version" "rabbitmq" {
  secret_id = var.rabbitmq_credentials_secret_arn
}
resource "aws_security_group" "rabbitmq" {
  name_prefix = "${local.name}-rabbitmq-"
  vpc_id      = module.vpc.vpc_id
  ingress {
    from_port       = 5671
    to_port         = 5671
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}
resource "aws_mq_broker" "rabbitmq" {
  lifecycle {
    precondition {
      condition     = var.rabbitmq_deployment_mode == "SINGLE_INSTANCE" || var.az_count == 3
      error_message = "RabbitMQ CLUSTER_MULTI_AZ requires three private subnets in separate AZs."
    }
  }
  broker_name                = "${local.name}-rabbitmq"
  engine_type                = "RabbitMQ"
  engine_version             = var.rabbitmq_engine_version
  host_instance_type         = var.rabbitmq_instance_type
  deployment_mode            = var.rabbitmq_deployment_mode
  publicly_accessible        = false
  subnet_ids                 = var.rabbitmq_deployment_mode == "SINGLE_INSTANCE" ? [module.vpc.private_subnets[0]] : module.vpc.private_subnets
  security_groups            = [aws_security_group.rabbitmq.id]
  auto_minor_version_upgrade = true
  encryption_options { use_aws_owned_key = true }
  logs { general = true }
  user {
    username = jsondecode(data.aws_secretsmanager_secret_version.rabbitmq.secret_string)["username"]
    password = jsondecode(data.aws_secretsmanager_secret_version.rabbitmq.secret_string)["password"]
  }
}
