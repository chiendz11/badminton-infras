variable "aws_region" { type = string }
variable "state_bucket_name" { type = string }
variable "project_name" { type = string }
variable "github_repository" { type = string }
variable "github_environment" { type = string }
variable "bootstrap_runtime_secret_arns" {
  type        = list(string)
  default     = []
  description = "Only pre-existing broker/cache credentials needed to plan the platform."
}
variable "existing_github_oidc_provider_arn" {
  type        = string
  default     = null
  description = "Reuse the account-wide GitHub OIDC provider if one already exists."
}
