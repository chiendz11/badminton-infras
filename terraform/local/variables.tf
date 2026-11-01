variable "cluster_name" {
  type        = string
  default     = "badminton-local"
  description = "Name of the local k3d Kubernetes cluster"
}

variable "gitops_repository" {
  type        = string
  default     = "https://github.com/chiendz11/badminton-gitops.git"
  description = "GitOps repository URL for Argo CD applications"
}

variable "gitops_revision" {
  type        = string
  default     = "feat/local-demo"
  description = "Git revision for Argo CD applications in badminton-gitops"
}

