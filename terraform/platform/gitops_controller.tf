provider "helm" {
  kubernetes = {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name, "--region", var.aws_region]
    }
  }
}
resource "helm_release" "argocd" {
  count            = var.enable_argocd_bootstrap ? 1 : 0
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = trimspace(file("${path.module}/argocd-chart-version.txt"))
  namespace        = "argocd"
  create_namespace = true
  atomic           = true
  cleanup_on_fail  = true
  timeout          = 900
  wait             = true
  values           = [file("${path.module}/argocd-values-production.yaml")]
  depends_on       = [module.eks, aws_eks_addon.ebs_csi]
}
resource "helm_release" "argocd_root" {
  count      = var.enable_argocd_bootstrap && var.enable_gitops_root ? 1 : 0
  name       = "badminton-root"
  chart      = "${path.module}/charts/argocd-root"
  namespace  = "argocd"
  values     = [yamlencode({ repoURL = "https://github.com/${var.gitops_repository}.git", targetRevision = var.gitops_revision })]
  depends_on = [helm_release.argocd]
}
