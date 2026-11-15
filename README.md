# badminton-infras

AWS foundation, local k3d + LocalStack bootstrap, and Argo CD bootstrap for **Badminton Manager V2**, refactored along the 4-root Terraform + Pure GitOps architecture (`Maint-infrastructure` / `MaintAI-gitops` pattern).

Application code and image builds: [`chiendz11/badminton_system`](https://github.com/chiendz11/badminton_system).
Kubernetes desired state (Pure Declarative Kustomize): [`chiendz11/badminton-gitops`](https://github.com/chiendz11/badminton-gitops).

```text
terraform/
├── bootstrap/    # Encrypted versioned S3 state bucket, KMS key, GitHub OIDC, plan/apply roles
├── domain/       # Route53 public hosted zone + DNS-validated ACM certificate (public + admin)
├── platform/     # VPC, EKS, EBS CSI, PostgreSQL RDS, TLS Valkey, RabbitMQ, ECR (11), IRSA, SSM metadata, Secret containers
├── argocd/       # Argo CD Helm release + Image Updater IRSA/credentials + separately gated root Application
└── local/        # Local k3d + LocalStack + CoreDNS + Argo CD GitOps bootstrap
scripts/          # source_policy.py (static guardrails) & terraform_run.py (explicit plan/apply wrapper)
local/            # k3d config, tool/image/app-source locks, ExternalSecrets ClusterSecretStore, LocalStack & unit tests
localdev/         # Python CLI: init, up, secrets, build, import-images, bootstrap-argocd, image-updater-pat, migrate, status, delete
environments/     # Non-secret tfvars & examples (bootstrap, argocd, production)
.github/workflows/# ci.yml (policy + fmt + validate + local tests), terraform-plan.yml (PR plan), apply.yml (gated manual apply)
docs/             # AWS deployment, state dependencies, secrets, GitHub Actions, rollback, parity
```

## Architecture Ownership Boundary

- **`badminton-infras` (this repo)**: AWS/EKS infrastructure, IAM/IRSA, secret *shells* (`aws_secretsmanager_secret` — zero secret values in Terraform state), non-secret metadata handoff via **AWS SSM Parameter Store** (`/badminton/prod/platform-metadata`), Argo CD Helm bootstrap, root `Application` pointer, and Local `k3d` + LocalStack + `argocd-image-updater-git-creds` bootstrap.
- **`badminton-gitops`**: All in-cluster Kubernetes add-ons (External Secrets Operator, AWS Load Balancer Controller, ExternalDNS, Metrics Server, Argo CD Image Updater) and application desired state (`Deployments`, `Services`, `Ingress`, `ExternalSecrets`, `NetworkPolicies`, `ImageUpdater` CRDs).
- **`badminton_system`**: Application source code, schema migrations, and CI builds pushing immutable tags/digests (`sha-<40>`) to GHCR / ECR.

> Note: Three independent RDS PostgreSQL instances cover Identity, Booking, and Commerce (plus optional AI PostgreSQL). MongoDB uses managed Atlas (`mongodb_allowed_cidrs`); no secret values (`aws_secretsmanager_secret_version`) or `most_recent = true` data sources exist in Terraform.

## Quick Links

- Local Runbook: [local/README.md](local/README.md) & [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md)
- Bootstrap Order: [docs/BOOTSTRAP.md](docs/BOOTSTRAP.md) & [docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md)
- State Dependencies: [docs/TERRAFORM_DEPENDENCIES.md](docs/TERRAFORM_DEPENDENCIES.md)
- GitHub Actions & OIDC: [docs/GITHUB_ACTIONS.md](docs/GITHUB_ACTIONS.md)
- Secrets Management: [docs/SECRETS.md](docs/SECRETS.md)
- Local vs AWS Parity: [docs/LOCAL_VS_AWS_CLOUD_PARITY.md](docs/LOCAL_VS_AWS_CLOUD_PARITY.md)
- Rollback Runbook: [docs/ROLLBACK_RUNBOOK.md](docs/ROLLBACK_RUNBOOK.md)
