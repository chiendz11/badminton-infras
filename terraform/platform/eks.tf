module "eks" {
  source                       = "terraform-aws-modules/eks/aws"
  version                      = "~> 21.0"
  name                         = local.name
  kubernetes_version           = var.kubernetes_version
  endpoint_public_access       = true
  endpoint_private_access      = true
  endpoint_public_access_cidrs = var.eks_public_access_cidrs
  enable_irsa                  = true
  vpc_id                       = module.vpc.vpc_id
  subnet_ids                   = module.vpc.private_subnets
  control_plane_subnet_ids     = module.vpc.private_subnets
  enabled_log_types            = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  addons = {
    coredns    = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni = {
      most_recent          = true
      before_compute       = true
      configuration_values = jsonencode({ enableNetworkPolicy = "true" })
    }
    eks-pod-identity-agent = { most_recent = true, before_compute = true }
  }
  access_entries = {
    terraform_plan = {
      principal_arn     = data.terraform_remote_state.bootstrap.outputs.terraform_plan_role_arn
      kubernetes_groups = ["terraform-plan"]
      policy_associations = {
        view = {
          policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy"
          access_scope = { type = "cluster" }
        }
      }
    }
    terraform_apply = {
      principal_arn = data.terraform_remote_state.bootstrap.outputs.terraform_apply_role_arn
      policy_associations = {
        admin = {
          policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = { type = "cluster" }
        }
      }
    }
  }
  eks_managed_node_groups = {
    general = {
      instance_types   = var.node_instance_types
      min_size         = var.node_min_size
      max_size         = var.node_max_size
      desired_size     = var.node_desired_size
      capacity_type    = "ON_DEMAND"
      metadata_options = { http_endpoint = "enabled", http_tokens = "required", http_put_response_hop_limit = 1 }
    }
  }
}
