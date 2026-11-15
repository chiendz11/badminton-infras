terraform {
  required_version = ">= 1.15.6, < 1.16.0"
  backend "s3" {
    key          = "infrastructure/argocd.tfstate"
    use_lockfile = true
    encrypt      = true
  }
  required_providers {
    aws  = { source = "hashicorp/aws", version = "6.61.0" }
    helm = { source = "hashicorp/helm", version = "3.2.0" }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = "badminton", Environment = "production", ManagedBy = "terraform" }
  }
}

provider "helm" {
  kubernetes = {
    host                   = data.terraform_remote_state.platform.outputs.eks_endpoint
    cluster_ca_certificate = base64decode(data.terraform_remote_state.platform.outputs.eks_ca)
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", data.terraform_remote_state.platform.outputs.eks_name, "--region", var.aws_region]
    }
  }
}
