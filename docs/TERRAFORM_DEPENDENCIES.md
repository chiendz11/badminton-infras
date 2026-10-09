# Terraform state and ownership

| Root | State object | Owner |
| --- | --- | --- |
| bootstrap | infrastructure/bootstrap.tfstate | State bucket/KMS, GitHub OIDC, plan/apply IAM |
| domain | infrastructure/domain.tfstate | Route53 zone, public/admin ACM certificate |
| platform | infrastructure/platform.tfstate | VPC/EKS, data services, ECR, IRSA, secrets, Argo CD |

Bootstrap begins locally once, then migrates into the state bucket it created. Domain does not depend on a live Kubernetes API. Platform reads only bootstrap/domain metadata through `terraform_remote_state` and emits the non-secret v1 contract.

Terraform applies cloud resources before enabling Helm. Argo's CRDs are installed by the `argocd` release before the separate `argocd_root` chart creates the root Application. Initially disable root adoption until the GitOps main branch contains real platform state.

GitOps owns StorageClass/PVC resources and all application Deployments, Services, Ingress, policies, autoscaling and alerts. Terraform owns EBS CSI and IAM. GitOps owns platform namespaces; Terraform creates `argocd` once for Helm bootstrap. No application workload is managed by both tools.

Provider constraints: Terraform >=1.10, AWS ~>6, Helm 3.2.0. VPC ~>6 and EKS ~>21. Argo Helm chart 10.4.0 is stored in a version file. Provider lock files are not fabricated; create/review them during the first authorized init. Most-recent EKS managed add-ons follow the selected Kubernetes release; set explicit add-on versions if your deployment policy requires fully fixed add-ons.

Both repositories carry the same strict platform schema. Change both copies together when extending v1. Additional properties are rejected so password/key fields cannot accidentally enter the handoff. Individual workload image releases use a separate GitOps-owned schema.
