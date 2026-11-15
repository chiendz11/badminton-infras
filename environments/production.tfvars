aws_region                 = "ap-southeast-1"
environment                = "prod"
project_name               = "badminton"
vpc_cidr                   = "10.30.0.0/16"
node_instance_types        = ["t3.medium"]
node_min_size              = 1
node_desired_size          = 2
node_max_size              = 4
db_instance_class          = "db.t4g.micro"
db_allocated_storage       = 20
db_backup_retention_days   = 7
db_multi_az                = false
enable_nat_gateway         = true
single_nat_gateway         = true
enable_interface_endpoints = false
enable_ai_database         = true
# Resolve region-supported builds as a reviewed operator task before using Terraform.
postgres_engine_version = "REPLACE_WITH_POSTGRES_16_MINOR"
eks_addon_versions = {
  coredns                = "REPLACE_WITH_EXACT_EKS_BUILD"
  kube-proxy             = "REPLACE_WITH_EXACT_EKS_BUILD"
  vpc-cni                = "REPLACE_WITH_EXACT_EKS_BUILD"
  aws-ebs-csi-driver     = "REPLACE_WITH_EXACT_EKS_BUILD"
  eks-pod-identity-agent = "REPLACE_WITH_EXACT_EKS_BUILD"
}
