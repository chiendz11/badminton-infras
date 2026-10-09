variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}
variable "environment" {
  type    = string
  default = "prod"
}
variable "project_name" {
  type    = string
  default = "badminton"
}
variable "state_bucket_name" {
  type = string
}
variable "state_kms_key_arn" {
  type = string
}
variable "vpc_cidr" {
  type    = string
  default = "10.30.0.0/16"
}
variable "az_count" {
  type    = number
  default = 2
  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "This subnet layout supports two or three availability zones."
  }
}
variable "enable_nat_gateway" {
  type    = bool
  default = true
}
variable "single_nat_gateway" {
  type    = bool
  default = true
}
variable "enable_interface_endpoints" {
  type    = bool
  default = false
}
variable "kubernetes_version" {
  type    = string
  default = "1.35"
}
variable "eks_public_access_cidrs" {
  type = list(string)
  validation {
    condition     = length(var.eks_public_access_cidrs) > 0 && !contains(var.eks_public_access_cidrs, "0.0.0.0/0")
    error_message = "Provide trusted runner/operator CIDRs; unrestricted EKS public access is forbidden."
  }
}
variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}
variable "node_min_size" {
  type    = number
  default = 1
}
variable "node_desired_size" {
  type    = number
  default = 2
}
variable "node_max_size" {
  type    = number
  default = 4
}
variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}
variable "db_allocated_storage" {
  type    = number
  default = 20
}
variable "db_backup_retention_days" {
  type    = number
  default = 7
}
variable "db_multi_az" {
  type    = bool
  default = false
}
variable "enable_ai_database" {
  type    = bool
  default = true
}
variable "db_username" {
  type    = string
  default = "badminton_admin"
}
variable "cache_node_type" {
  type    = string
  default = "cache.t4g.micro"
}
variable "cache_node_count" {
  type    = number
  default = 2
}
variable "cache_engine_version" {
  type    = string
  default = "8.0"
}
variable "rabbitmq_engine_version" {
  type    = string
  default = "4.2"
}
variable "rabbitmq_instance_type" {
  type    = string
  default = "mq.m7g.large"
}
variable "rabbitmq_deployment_mode" {
  type    = string
  default = "SINGLE_INSTANCE"
}
variable "github_repository" {
  type    = string
  default = "chiendz11/badminton-infras"
}
variable "app_repository" {
  type    = string
  default = "chiendz11/badminton_system"
}
variable "gitops_repository" {
  type    = string
  default = "chiendz11/badminton-gitops"
}
variable "gitops_revision" {
  type    = string
  default = "main"
}
variable "enable_argocd_bootstrap" {
  type    = bool
  default = true
}
variable "enable_gitops_root" {
  type    = bool
  default = false
}
variable "rabbitmq_credentials_secret_arn" {
  type = string
}
variable "redis_credentials_secret_arn" {
  type        = string
  description = "Existing secret JSON with password for ElastiCache AUTH; sensitive value is stored in encrypted Terraform state."
}
variable "mongodb_allowed_cidrs" {
  type        = list(string)
  default     = []
  description = "Explicit Atlas/managed MongoDB destination CIDRs; Mongo workloads remain gated when empty."
}
