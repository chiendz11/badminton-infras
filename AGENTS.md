# badminton-infras — Engineering & Operational Boundaries

Read `README.md`, `docs/TERRAFORM_DEPENDENCIES.md`, `docs/BOOTSTRAP.md`, and `local/README.md` before modifying Terraform or `localdev/`.

## Ownership & Strict Invariants

1. **4-Root Production Terraform Separation**:
   - `terraform/bootstrap`: Remote state bucket/KMS, GitHub OIDC provider, CI `plan` / `apply` IAM roles.
   - `terraform/domain`: Route53 zone + ACM wildcard/SAN certificate validation.
   - `terraform/platform`: VPC, EKS, EBS CSI, PostgreSQL RDS, Valkey, RabbitMQ, ECR (11 immutable/scanned repos), IRSA (`aws-load-balancer-controller`, `external-secrets`, `external-dns`, `image-updater`), empty `aws_secretsmanager_secret` containers, and SSM Parameter Store (`/badminton/prod/platform-metadata`) handoff.
   - `terraform/argocd`: Argo CD Helm release + Image Updater credentials/IRSA binding + separately gated root `Application` (`enable_gitops_root`, `false` by default).
   - No `most_recent = true`, no `aws_secretsmanager_secret_version`, and no mutable provider/chart version ranges are permitted (`scripts/source_policy.py` enforces this in CI).
2. **GitOps Boundary**:
   - Terraform owns cloud resources, EKS, IAM, and Argo CD Helm bootstrap ONLY.
   - `../badminton-gitops` owns all in-cluster add-ons (`external-secrets`, `argocd-image-updater`, `aws-load-balancer-controller`, etc.), `ClusterSecretStore` (prod), `ExternalSecrets`, `NetworkPolicies`, and application manifests.
   - Do not apply the same Kubernetes resource or CRD from both Terraform/`localdev` and `badminton-gitops`.
   - Specifically for local `k3d`: `badminton-infras/local/manifests/cluster-secret-store.yaml` owns `Secret/localstack-creds` and `ClusterSecretStore/aws-secrets-manager`, whereas `badminton-gitops` owns `local/platform/*`, `environments/local/apps/*`, and `ImageUpdater` CRDs.
3. **Zero Plaintext Secrets in Git or State**:
   - Never commit `.tfvars` with real values, `terraform.tfstate*`, kubeconfigs (`local/.local/*`), PAT tokens, or `aws_secretsmanager_secret_version`.
   - Local Image Updater PATs must only be written imperatively to the cluster (`python3 -m localdev image-updater-pat --token ...` or `make local-image-updater-pat`).
4. **Source Synchronization**:
   - Do not alter `../MaintAI-gitops` or `../Maint-infrastructure`.
   - `local/versions/app-source.lock.json` tracks the reviewed `chiendz11/badminton_system` commit (`38b4a74cea88d69c271b3a4608b5e38754797b86`).
