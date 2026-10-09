# GitHub Actions configuration

The workflows are committed code, not executed infrastructure changes. First bootstrap/migrate state locally. Create an environment named `production`, restrict it to main, and configure approval protection before enabling apply workflows. Terraform apply uses the environment OIDC subject `repo:chiendz11/badminton-infras:environment:production`.

## Variables

Set these repository variables (PR plan jobs do not use the protected apply environment):

| Variable | Value |
| --- | --- |
| AWS_REGION | ap-southeast-1 |
| TF_STATE_BUCKET | Bootstrap-created bucket |
| TF_STATE_KMS_KEY_ARN | Bootstrap-created KMS ARN |
| TF_PLAN_ROLE_ARN | Bootstrap plan role |
| TF_APPLY_ROLE_ARN | Bootstrap apply role |
| GITHUB_OIDC_PROVIDER_ARN | Created/reused account provider ARN |
| EKS_PUBLIC_ACCESS_CIDRS | JSON list of trusted stable runner/operator CIDRs |
| RABBITMQ_BOOTSTRAP_SECRET_ARN | Existing broker provisioning secret |
| REDIS_BOOTSTRAP_SECRET_ARN | Existing cache AUTH secret |
| BOOTSTRAP_RUNTIME_SECRET_ARNS | JSON list containing only those two ARNs |
| DNS_ZONE_NAME | Real owned parent zone |
| PUBLIC_DOMAIN_NAME | Real public app hostname |
| ADMIN_DOMAIN_NAME | Real admin hostname |
| MONGODB_ALLOWED_CIDRS | JSON list of actual managed MongoDB destination ranges, default [] |
| ENABLE_ARGOCD_BOOTSTRAP | Initially false; true after initial EKS apply |
| ENABLE_GITOPS_ROOT | Initially false; true after GitOps platform PR merge |
| AUTOMATION_APP_ID | GitHub App installed on badminton-gitops |

Set `AUTOMATION_APP_PRIVATE_KEY` as a protected environment secret. The dispatch App needs only the permission required for repository_dispatch on `badminton-gitops` (repository Contents write). Give the GitOps PR automation the separately described read/proposal permissions there; use separate Apps if deployment governance requires stricter separation.

The OIDC plan subject is limited to this repository's pull requests; fork PRs are skipped. Treat same-repository PR authors as trusted AWS state readers: speculative Terraform can read its allowed secret/state data. Bootstrap's general plan role has broad AWS ReadOnlyAccess plus native lockfile write access, not cloud mutation rights. Terraform plan requires existing bootstrap/domain dependencies; the first deployment must use the documented phase order.

## Workflows

- `terraform.yml`: PR format/init/validate/TFLint/security scan/speculative plan. Never applies. Actual Terraform plans can contain sensitive material even when CLI redacts it; no binary plan or raw outputs are uploaded.
- `production-infra.yml`: main changes or manual main dispatch; detects roots; bootstrap changes cascade through domain/platform, domain changes through platform. Production concurrency serializes applies.
- `reusable-foundation.yml`: uses migrated remote bootstrap state; creates the backend declaration from the example. It is not an empty-account initializer.
- `reusable-domain.yml`: plans/applies the domain root after protected approval.
- `reusable-platform.yml`: refreshes a plan after environment approval, applies that plan, builds a non-secret contract and uploads only the contract artifact.
- `reusable-platform-handoff.yml`: validates contract metadata, creates a short-lived GitHub App token and dispatches `platform-contract-v1` to GitOps. It never invokes kubectl.

PR plan runners must be able to reach a live EKS API once Helm resources exist. The initial workflow uses `ubuntu-latest`; replace with your trusted VPC/static-egress runner label where required by the endpoint CIDR allow-list. Argo bootstrap grants the plan identity cluster view and read-only release-secret access in `argocd`; apply identity has cluster administration.

The initial sources and workflow security scan have not been run. The initial security ignore file waives no findings. Review the first scan, including AWS-managed encryption and the CIDR-restricted public EKS API, and address or explicitly document policy exceptions before making checks required. Branch protection and environment rules are operational configuration, not provisioned by these repositories.
