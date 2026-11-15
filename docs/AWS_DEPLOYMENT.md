# AWS deployment phases

See [docs/BOOTSTRAP.md](BOOTSTRAP.md) for the concise checklist and [docs/TERRAFORM_DEPENDENCIES.md](TERRAFORM_DEPENDENCIES.md) for root ownership. These are operator instructions for AWS deployment; none are executed by offline CI.

## 0. Bootstrap (`terraform/bootstrap`)

1. Inspect whether the AWS account already has a GitHub OIDC provider; reuse its ARN if present.
2. Copy `environments/bootstrap.tfvars.example` to a git-ignored local `.tfvars` file and supply bucket name, project name (`badminton-prod`), GitHub repo (`chiendz11/badminton-infras`), and `bootstrap_runtime_secret_arns`.
3. Run the initial apply with local state, then copy `terraform/bootstrap/backend.tf.example` -> `backend.tf` and migrate that **same state** into encrypted S3:

```bash
terraform -chdir=terraform/bootstrap init
terraform -chdir=terraform/bootstrap apply -var-file=../../environments/bootstrap.local.tfvars
# copy backend.tf.example -> backend.tf and configure backend.hcl
terraform -chdir=terraform/bootstrap init -migrate-state -backend-config=backend.hcl
```

## 1. Domain (`terraform/domain`)

1. Provide `dns_zone_name`, `public_domain_name`, `admin_domain_name`, or `existing_zone_id`.
2. For a new delegated zone, apply once with `wait_for_certificate_validation = false`, delegate the NS records at your parent zone/registrar, then apply with `wait_for_certificate_validation = true` to finish ACM DNS validation for both public and admin hostnames.

## 2. Cloud platform (`terraform/platform`)

1. Seed Secrets Manager bootstrap container metadata if required and supply trusted `eks_public_access_cidrs` and `mongodb_allowed_cidrs`.
2. Apply `terraform/platform` with `environments/production.tfvars`:

```bash
terraform -chdir=terraform/platform init -backend-config=backend.hcl
terraform -chdir=terraform/platform apply -var-file=../../environments/production.tfvars
```

`terraform/platform` creates:
- VPC, EKS cluster + EBS CSI + worker node groups
- RDS PostgreSQL (`identity`, `booking`, `commerce`, optional `ai`), TLS Valkey, RabbitMQ (`mq.m7g.*`)
- 11 immutable/scanned ECR repositories (`api-gateway`, `identity-service`, `booking-core`, `content-service`, `ai-service`, `commerce-service`, `social-service`, `notification-service`, `storage-service`, `web`, `admin`)
- IRSA roles (`aws-load-balancer-controller`, `external-secrets`, `external-dns`, `image-updater`)
- Empty `aws_secretsmanager_secret` containers (never `aws_secretsmanager_secret_version`)
- Non-secret SSM Parameter Store metadata at `/badminton/prod/platform-metadata`

## 3. Seed Secrets, Schemas & Image Updater Credentials (Out-of-Band)

1. Populate Secrets Manager containers out-of-band with real DB passwords, JWT secrets, RabbitMQ `/badminton` vhost credentials, Valkey AUTH, MongoDB Atlas URIs, and AI keys.
2. Seed `argocd-image-updater-git-creds` in `argocd` namespace (or via ExternalSecret) with a fine-grained GitHub PAT (`Contents: write` + `Pull requests: write` on `chiendz11/badminton-gitops`) for ECR -> GitOps PR automation.
3. Provision per-service PostgreSQL roles/schemas and run Prisma/Alembic migrations before syncing application workloads.

## 4. Argo CD Bootstrap (`terraform/argocd`)

1. Copy `environments/argocd.tfvars.example` to a git-ignored `.tfvars` file and configure `terraform/argocd/backend.hcl`.
2. Deploy Argo CD with root adoption disabled initially (`enable_gitops_root = false`):

```bash
terraform -chdir=terraform/argocd init -backend-config=backend.hcl
terraform -chdir=terraform/argocd apply -var-file=../../environments/argocd.local.tfvars
```

3. Once `chiendz11/badminton-gitops` `main` holds reviewed production manifests (`bootstrap/production/` -> `applications/`) and ExternalSecrets/Secrets Manager values are ready, enable `enable_gitops_root = true` and re-apply `terraform/argocd`:

```bash
terraform -chdir=terraform/argocd apply -var-file=../../environments/argocd.local.tfvars -var=enable_gitops_root=true
```

## HA configuration

Set `db_multi_az = true`, disable `single_nat_gateway`, scale cache/node groups appropriately, and choose `CLUSTER_MULTI_AZ` for RabbitMQ (`az_count = 3`).
