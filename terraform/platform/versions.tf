terraform {
  required_version = ">= 1.15.6, < 1.16.0"
  backend "s3" {
    key          = "infrastructure/platform.tfstate"
    use_lockfile = true
    encrypt      = true
  }
  required_providers {
    aws = { source = "hashicorp/aws", version = "6.61.0" }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = "badminton", Environment = "production", ManagedBy = "terraform" }
  }
}
