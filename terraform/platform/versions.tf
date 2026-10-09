terraform {
  required_version = ">= 1.10.0, < 2.0.0"
  backend "s3" {
    key          = "infrastructure/platform.tfstate"
    use_lockfile = true
    encrypt      = true
  }
  required_providers {
    aws  = { source = "hashicorp/aws", version = "~> 6.0" }
    helm = { source = "hashicorp/helm", version = "3.2.0" }
  }
}
provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = "badminton", Environment = "prod", ManagedBy = "terraform" }
  }
}
