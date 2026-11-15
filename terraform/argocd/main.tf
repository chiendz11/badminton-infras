variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}

variable "state_bucket_name" {
  type = string
}

variable "state_kms_key_arn" {
  type = string
}

variable "enable_gitops_root" {
  description = "Enable only after runtime secrets, image-updater credentials, and reviewed GitOps production manifests are configured."
  type        = bool
  default     = false
}

variable "gitops_repository_url" {
  type    = string
  default = "https://github.com/chiendz11/badminton-gitops.git"
}

variable "gitops_revision" {
  type    = string
  default = "main"
}

data "terraform_remote_state" "platform" {
  backend = "s3"
  config = {
    bucket     = var.state_bucket_name
    key        = "infrastructure/platform.tfstate"
    region     = var.aws_region
    encrypt    = true
    kms_key_id = var.state_kms_key_arn
  }
}

resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = "10.4.0"
  namespace        = "argocd"
  create_namespace = true
  atomic           = true
  cleanup_on_fail  = true
  timeout          = 900
  wait             = true
  max_history      = 10
  values           = [file("${path.module}/values.yaml")]
}

resource "helm_release" "root" {
  count      = var.enable_gitops_root ? 1 : 0
  name       = "badminton-root"
  namespace  = "argocd"
  chart      = "${path.module}/charts/root"
  atomic     = true
  timeout    = 300
  values     = [yamlencode({ repository = var.gitops_repository_url, revision = var.gitops_revision })]
  depends_on = [helm_release.argocd]
}
