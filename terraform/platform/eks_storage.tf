resource "aws_eks_addon" "ebs_csi" {
  cluster_name                = module.eks.cluster_name
  addon_name                  = "aws-ebs-csi-driver"
  addon_version               = var.eks_addon_versions["aws-ebs-csi-driver"]
  service_account_role_arn    = aws_iam_role.service_account["ebs_csi"].arn
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "PRESERVE"
  depends_on                  = [aws_iam_role_policy_attachment.ebs_csi, module.eks]
}
