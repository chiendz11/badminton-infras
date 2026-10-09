data "aws_availability_zones" "available" { state = "available" }
data "aws_caller_identity" "current" {}
data "terraform_remote_state" "bootstrap" {
  backend = "s3"
  config = {
    bucket     = var.state_bucket_name
    key        = "infrastructure/bootstrap.tfstate"
    region     = var.aws_region
    kms_key_id = var.state_kms_key_arn
  }
}
data "terraform_remote_state" "domain" {
  backend = "s3"
  config = {
    bucket     = var.state_bucket_name
    key        = "infrastructure/domain.tfstate"
    region     = var.aws_region
    kms_key_id = var.state_kms_key_arn
  }
}
locals {
  name              = "${var.project_name}-${var.environment}"
  azs               = slice(data.aws_availability_zones.available.names, 0, var.az_count)
  postgres_services = merge({ identity = "identity", booking = "booking", commerce = "commerce" }, var.enable_ai_database ? { ai = "ai" } : {})
  ecr_services      = toset(["web", "admin", "api-gateway", "identity-service", "booking-core", "commerce-service", "social-service", "content-service", "notification-service", "storage-service", "ai-service"])
  secret_names      = toset(["payos", "cloudinary", "llm", "internal-service-auth", "rabbitmq", "redis", "mongodb", "oauth", "api-gateway-runtime", "identity-service-runtime", "booking-core-runtime", "commerce-service-runtime", "social-service-runtime", "content-service-runtime", "notification-service-runtime", "storage-service-runtime", "ai-service-runtime"])
  service_accounts = {
    external_secrets             = { namespace = "external-secrets", name = "external-secrets" }
    external_dns                 = { namespace = "external-dns", name = "external-dns" }
    aws_load_balancer_controller = { namespace = "kube-system", name = "aws-load-balancer-controller" }
    ebs_csi                      = { namespace = "kube-system", name = "ebs-csi-controller-sa" }
  }
}
