# GitHub Actions configuration

The workflows in `.github/workflows/` match the MaintAI 4-root gated CI/CD architecture (`ci.yml`, `terraform-plan.yml`, `apply.yml`).

## Workflows

1. **`ci.yml`** (on `push` / `pull_request` / `workflow_dispatch`):
   - Runs `python scripts/source_policy.py` to enforce zero `most_recent = true`, zero `aws_secretsmanager_secret_version`, and locked Terraform/chart versions.
   - Runs `terraform fmt -check -recursive` across `terraform/`.
   - Runs `terraform init -backend=false` + `terraform validate` across all 4 production roots (`bootstrap`, `domain`, `platform`, `argocd`) and `terraform/local`.
   - Runs `python -m localdev.checks` and `python -m unittest discover -s local/tests -p 'test_*.py' -v`.
2. **`terraform-plan.yml`** (on `pull_request` / `workflow_dispatch`):
   - Runs read-only `terraform plan` using `TERRAFORM_PLAN_ROLE_ARN` via OIDC (`scripts/terraform_run.py`) against AWS-only roots (`bootstrap`, `domain`, `platform`).
   - `terraform/argocd` live plan requires live EKS API + secret access and is performed inside the protected `apply.yml` workflow, not in PR speculative plan jobs.
3. **`apply.yml`** (manual `workflow_dispatch` only):
   - Requires `ENABLE_INFRA_AUTOMATION == 'true'`, branch `main`, protected GitHub Environment (`production`), and matching `expected_main_sha`.
   - Runs an explicit fresh plan + apply for a single selected `root` (`bootstrap`, `domain`, `platform`, or `argocd`) using `TERRAFORM_APPLY_ROLE_ARN`.

## GitHub Repository & Environment Setup

Create a protected environment named **`production`** restricted to branch `main` with manual reviewer approvals before enabling `apply.yml`.

Set these non-secret GitHub Variables:

| Variable | Description |
| --- | --- |
| `ENABLE_INFRA_AUTOMATION` | Set `true` only when ready for GitHub Actions plan/apply |
| `AWS_REGION` | `ap-southeast-1` |
| `TF_STATE_BUCKET` | Bootstrap-created encrypted S3 bucket |
| `TF_STATE_KMS_KEY_ARN` | Bootstrap-created KMS key ARN |
| `TERRAFORM_PLAN_ROLE_ARN` | Bootstrap read-only plan role ARN |
| `TERRAFORM_APPLY_ROLE_ARN` | Bootstrap protected apply role ARN |
| `TFVARS_BOOTSTRAP_JSON` | Non-secret JSON tfvars for `bootstrap` |
| `TFVARS_DOMAIN_JSON` | Non-secret JSON tfvars for `domain` |
| `TFVARS_PLATFORM_JSON` | Non-secret JSON tfvars for `platform` |
| `TFVARS_ARGOCD_JSON` | Non-secret JSON tfvars for `argocd` |

> No `AUTOMATION_APP_ID` / `AUTOMATION_APP_PRIVATE_KEY` cross-repo webhook dispatch is required by `badminton-infras`: metadata handoff uses AWS SSM Parameter Store, and image rollout PRs are proposed directly by Argo CD Image Updater (`argocd-image-updater-git-creds`) from inside the cluster.
