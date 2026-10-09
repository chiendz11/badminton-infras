# AWS deployment phases

These are operator instructions for a later deployment. They were not run during code implementation.

## 0. Bootstrap

1. Use an AWS account and operator identity authorized to create infrastructure. Inspect an existing account-wide GitHub OIDC provider; if it exists, reuse its ARN instead of creating a duplicate.
2. Copy `terraform/bootstrap/terraform.tfvars.example` to an ignored local `bootstrap.auto.tfvars` inside that root. Supply the globally unique bucket name, project name `badminton-prod`, repository and environment. Populate `bootstrap_runtime_secret_arns` with the existing broker/cache bootstrap secret ARNs described in `SECRETS.md`.
3. Run the first apply with local state:

```bash
terraform -chdir=terraform/bootstrap init
terraform -chdir=terraform/bootstrap plan
terraform -chdir=terraform/bootstrap apply
```

4. Copy `backend.tf.example` to `backend.tf`; copy/fill `backend.hcl.example`. Migrate **the same local state**, not an empty new state:

```bash
terraform -chdir=terraform/bootstrap init -migrate-state -backend-config=backend.hcl
```

5. Confirm the remote object exists and is versioned; keep the local migration backup secure. `backend.tf` is intentionally supplied by CI from the checked-in example; local operators may commit the non-secret backend declaration after migration if desired. State and actual backend configuration must remain ignored.
6. Set GitHub repository variables and environment protections described in `GITHUB_ACTIONS.md`. The apply role is AdministratorAccess because it creates IAM, EKS and networking. Its trust is restricted to this repository's protected `production` environment. Plan uses ReadOnlyAccess plus state locks and explicitly allow-listed bootstrap credentials. Review these privileges against your account's boundary policies.

## 1. Domain

Copy `environments/domain.tfvars.example` to a local file and replace all example domains. Fill `terraform/domain/backend.hcl`.

```bash
terraform -chdir=terraform/domain init -backend-config=backend.hcl
terraform -chdir=terraform/domain plan -var-file=../../environments/domain.local.tfvars
terraform -chdir=terraform/domain apply -var-file=../../environments/domain.local.tfvars
```

For a new zone, set `wait_for_certificate_validation=false` for the first apply, delegate the returned nameservers at your registrar, then apply again with validation enabled. For an existing zone, set `existing_zone_id` in the local variable file. Do not enable the public Ingress until the certificate is `ISSUED`. CI's default domain root creates/owns a zone; using an existing zone in CI requires supplying that same `existing_zone_id` consistently through a variable file or workflow customization.

The certificate covers the public hostname and a separate admin hostname. `/admin` redirects to that admin hostname because the current admin SPA builds with root paths. This preserves its routing without changing app source.

## 2. Cloud platform

Create existing Secrets Manager bootstrap credentials first. Copy `environments/platform.auto.tfvars.example` into the platform root as ignored `platform.auto.tfvars`, fill real values and trusted runner/operator CIDRs. Fill its backend file. The API endpoint is public with restricted CIDRs and also private; use a runner with a stable permitted egress IP or a runner inside the VPC. GitHub's generic hosted runner range is not automatically opened.

```bash
terraform -chdir=terraform/platform init -backend-config=backend.hcl
terraform -chdir=terraform/platform plan -var-file=../../environments/production.tfvars
terraform -chdir=terraform/platform apply -var-file=../../environments/production.tfvars
```

The first platform apply keeps Helm bootstrap disabled. The bootstrap apply role gets an EKS access entry. Then install Argo CD with the cluster already available:

```bash
terraform -chdir=terraform/platform plan -var-file=../../environments/production.tfvars -var=enable_argocd_bootstrap=true
terraform -chdir=terraform/platform apply -var-file=../../environments/production.tfvars -var=enable_argocd_bootstrap=true
```

Use the apply role for these Helm phases: local AWS AdministratorAccess alone does not grant Kubernetes authorization. Argo CD's UI is private; access it through an authorized operator session and port-forward when needed. Terraform's plan role has cluster view access plus an Argo namespace Role granting read-only access to Helm's release secrets; protect those credentials as state-sensitive material.

Provision per-service database roles and runtime secret values before releasing apps. RabbitMQ requires the `/badminton` virtual host, exchanges/queues/DLQs and limited application users. The initial broker admin credential is only for provisioning. Access the private management endpoint from a controlled VPC session with an explicitly granted operator security group rule; it is not open to the Internet or workloads. Atlas needs project database users and source NAT/private-network allow rules; destination CIDRs alone do not configure Atlas access.

## 3. Platform contract and root adoption

```bash
terraform -chdir=terraform/platform output -json > outputs.json
python scripts/build_platform_contract.py outputs.json --output platform-contract-v1.json
rm outputs.json
```

Submit the contract to GitOps's `platform-reconcile.yml`, review and merge its PR. Scheduled reconciliation refreshes endpoint-specific NetworkPolicy IPs; managed failover may require an immediate reconciliation/PR merge. Argo CD should only read the reviewed `main` branch.

After GitOps has real platform metadata, enable the root in a third platform apply:

```bash
terraform -chdir=terraform/platform apply -var-file=../../environments/production.tfvars -var=enable_argocd_bootstrap=true -var=enable_gitops_root=true
```

Persist the enablement flags in production configuration/GitHub variables before later applies. Otherwise a subsequent apply with the initial defaults proposes removing the Helm releases. Do not switch an adopted platform back to bootstrap-disabled values.

The platform receivers enable add-ons; workloads remain manual until their own signed release PR. After app CI publishes and signs real images, release each component through GitOps. No cluster admin access or kubeconfig is required by app CI.

## HA configuration

Set `db_multi_az=true`, disable single NAT, size nodes/cache appropriately and choose `CLUSTER_MULTI_AZ` for RabbitMQ when required. That broker mode requires `az_count=3`; the subnet layout supports two or three AZs. Prometheus uses an EBS-backed retained gp3 PVC. A three-AZ broker and managed data services carry costs even before workloads are released. Confirm engine/instance availability in the intended region when preparing the actual plan.
