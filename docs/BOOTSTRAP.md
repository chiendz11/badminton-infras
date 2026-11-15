# Future Bootstrap Order (4-Root AWS Production)

Follow this sequence to stand up AWS Production safely:

1. **Day zero (`terraform/bootstrap`)**:
   - Copy `environments/bootstrap.tfvars.example` to a git-ignored file and supply your AWS bucket name, GitHub OIDC provider ARN (reuse existing account OIDC provider if present), and `bootstrap_runtime_secret_arns`.
   - Apply `terraform/bootstrap` with initial local state, then copy `terraform/bootstrap/backend.tf.example` -> `backend.tf` and migrate that **same state** into encrypted S3 (`terraform -chdir=terraform/bootstrap init -migrate-state -backend-config=backend.hcl`).
2. **Domain (`terraform/domain`)**:
   - Configure Route53 zone (`existing_zone_id` or new delegated subdomain zone).
   - Run first apply with `wait_for_certificate_validation = false`, delegate NS records if new, then re-apply with `true` to complete ACM DNS validation for both public and admin hostnames.
3. **Platform (`terraform/platform`)**:
   - Supply exact pinned EKS add-on versions, PostgreSQL minor versions, trusted `eks_public_access_cidrs`, `mongodb_allowed_cidrs`, and `environments/production.tfvars`.
   - `terraform/platform` provisions VPC, EKS, RDS (Identity, Booking, Commerce, optional AI), TLS Valkey, RabbitMQ, 11 ECR repositories, IRSA roles (including `image-updater` read-only ECR role), secret *shells* (`aws_secretsmanager_secret`), and publishes non-secret handoff metadata to **AWS SSM Parameter Store** (`/badminton/prod/platform-metadata`).
4. **Database & Secret Seeding (Out-of-band)**:
   - Seed real runtime secrets into AWS Secrets Manager containers (DB credentials, JWT secrets, RabbitMQ `/badminton` vhost credentials, Valkey AUTH, Atlas URIs, Gemini key).
   - Seed `argocd-image-updater-git-creds` (fine-grained GitHub PAT with `Contents: write` + `Pull requests: write` on `chiendz11/badminton-gitops`) for automated ECR image PR updates.
   - Provision PostgreSQL schemas/owners and run initial migrations before enabling workloads in GitOps.
5. **Argo CD Bootstrap (`terraform/argocd`)**:
   - Copy `environments/argocd.tfvars.example` to a git-ignored file.
   - First apply with `enable_gitops_root = false` to deploy Argo CD Helm release (`10.4.0`) + RBAC + IRSA bindings.
   - Once `chiendz11/badminton-gitops` `main` holds reviewed platform & add-on manifests (including `ImageUpdater` CRD pointing at ECR) and secrets are seeded in AWS Secrets Manager, apply `terraform/argocd` with `enable_gitops_root = true` to deploy the root `Application`.

## Automated Validation in CI

- `scripts/source_policy.py` blocks `most_recent = true`, `aws_secretsmanager_secret_version`, and unpinned versions.
- `terraform fmt -check -recursive` and `terraform validate` run across all four roots (`bootstrap`, `domain`, `platform`, `argocd`) plus `terraform/local`.
- Live PR `terraform plan` runs only on AWS-only roots (`bootstrap`, `domain`, `platform`); `terraform/argocd` plans inside the protected `apply.yml` workflow where live EKS API credentials are available.
