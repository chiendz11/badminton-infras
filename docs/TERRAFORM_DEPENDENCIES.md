# Terraform state and ownership

Production infrastructure is divided into **4 independent Terraform state roots** along blast-radius boundaries:

| Root | State object | Owner |
| --- | --- | --- |
| `terraform/bootstrap` | `infrastructure/bootstrap.tfstate` | S3 state bucket/KMS, GitHub OIDC provider, `plan`/`apply` IAM roles |
| `terraform/domain` | `infrastructure/domain.tfstate` | Route53 public zone, ACM certificate (`public` + `admin` hostnames) |
| `terraform/platform` | `infrastructure/platform.tfstate` | VPC/EKS, RDS, Valkey, RabbitMQ, ECR (11), IRSA (including `image-updater`), empty Secrets Manager containers, SSM `/badminton/prod/platform-metadata` |
| `terraform/argocd` | `infrastructure/argocd.tfstate` | Argo CD Helm release + Image Updater AWS/Git credentials setup + gated Root `Application` (`enable_gitops_root`) |

## Handoff & Dependency Flow

1. **`bootstrap`** begins locally once, then migrates its state into the encrypted S3 bucket it created.
2. **`domain`** reads `bootstrap` state only if shared OIDC/IAM rules apply; it does not depend on Kubernetes.
3. **`platform`** reads `domain` metadata via `terraform_remote_state` and writes non-secret infrastructure metadata (endpoints, VPC/CIDR metadata, IRSA ARNs, KMS keys, ECR URLs, Secrets Manager container ARNs) to **AWS SSM Parameter Store** (`/badminton/prod/platform-metadata`) and Terraform outputs. No cross-repo contract compiler or GitHub webhook dispatch is used.
4. **`argocd`** reads `platform` remote state (`cluster_name`, `eks_cluster_endpoint`, `eks_cluster_ca`, IRSA ARNs) using AWS EKS `exec` authentication. Keep `enable_gitops_root = false` until `badminton-gitops` `main` holds reviewed manifests and `argocd-image-updater-git-creds` has been seeded in cluster / Secrets Manager.

## Terraform vs GitOps Split

- **Terraform owns**: Cloud VPC/EKS, RDS/Valkey/RabbitMQ, ECR repositories, EBS CSI driver, IRSA roles, empty Secrets Manager containers, and the `argocd` Helm bootstrap + root `Application` pointer.
- **GitOps (`badminton-gitops`) owns**: StorageClass/PVC definitions, add-on Helm releases (`external-secrets`, `aws-load-balancer-controller`, `external-dns`, `cert-manager`, `metrics-server`, `kube-prometheus-stack`, `argocd-image-updater`), `ImageUpdater` CRDs, `ClusterSecretStore`, `ExternalSecrets`, `NetworkPolicies`, and all workload Deployments/Services/Ingress.

## Version & Policy Constraints

- Exact Terraform constraint: `>= 1.15.6, < 1.16.0` (`.terraform-version` = `1.15.6`).
- AWS provider pinned to `~> 6.0`; Helm `= 3.2.0`; Kubernetes `= 3.0.1`; EKS module `21.15.1`; VPC module `6.6.0`; Argo CD Helm chart pinned to `10.4.0` in `terraform/argocd/main.tf`.
- `scripts/source_policy.py` forbids `most_recent = true` and `aws_secretsmanager_secret_version` across `terraform/`.
