# badminton-infras

AWS foundation and Argo CD bootstrap for Badminton Manager V2. The repository name follows the user's requested `badminton-infras`; the attached guide calls this boundary `badminton-infrastructure`.

Application code and builds: [`chiendz11/badminton_system`](https://github.com/chiendz11/badminton_system). Kubernetes desired state: [`chiendz11/badminton-gitops`](https://github.com/chiendz11/badminton-gitops).

## Implemented

- `terraform/bootstrap`: versioned, private, KMS-encrypted S3 state; native state locks; shared/reusable GitHub OIDC provider; separate plan/apply roles.
- `terraform/domain`: create/reuse Route53 public zone; ACM certificate for the public and admin hostnames; DNS validation.
- `terraform/platform`: VPC with private workers and data, EKS, network policy support, EBS CSI, managed PostgreSQL, TLS/authenticated Valkey, private RabbitMQ, 11 immutable/scanned ECR repositories, secret containers, IRSA, application image publisher and read-only GitOps image verifier.
- Argo CD Helm bootstrap and a separate root Application chart. No application Deployments/Services are managed by Terraform.
- Non-secret platform contract builder, schema and validator, plus protected GitHub Actions apply/handoff workflows.

Three independent RDS instances cover Identity, Booking and Commerce. A fourth optional instance is enabled for the **current** AI runtime, which persists conversations and LangGraph checkpoints in its own PostgreSQL. AI never receives Booking database credentials. MongoDB uses an existing managed Atlas deployment, configured through per-service runtime secrets and an explicit destination CIDR allow-list; this repository does not create an Atlas account or substitute DocumentDB.

## Start here

Read [AWS deployment](docs/AWS_DEPLOYMENT.md), [state dependencies](docs/TERRAFORM_DEPENDENCIES.md), [secrets](docs/SECRETS.md), [GitHub configuration](docs/GITHUB_ACTIONS.md), and [rollback](docs/ROLLBACK_RUNBOOK.md). [Implementation details](docs/IMPLEMENTATION_DETAILS.md) records the chosen profile and differences from the source guide.

The committed values describe a first implementation, with Single-AZ RDS and a single NAT gateway. They are configurable starting values. Argo bootstrap and root adoption are initially disabled in `environments/production.tfvars` to support staged installation. Domain, trusted EKS runner CIDRs, bootstrap credentials and actual AWS account values must be supplied by the operator.

## Verification status

No tests, Terraform init/validate/plan/apply, Kubernetes builds or deployments were run during implementation, at the user's request. Terraform source was formatted. Workflow files define structural checks for future PRs; they have not been executed or represented as passing. No AWS resources were created.

## Source documents and references

- [User infrastructure guide](BADMINTON_INFRASTRUCTURE_IMPLEMENTATION.md): design source, not a deployment instruction.
- [EKS module v21](https://github.com/terraform-aws-modules/terraform-aws-eks/blob/master/docs/UPGRADE-21.0.md).
- [Amazon MQ engine management](https://docs.aws.amazon.com/amazon-mq/latest/developer-guide/rabbitmq-version-management.html): RabbitMQ 4.2 uses the `mq.m7g` instance family; the default is `mq.m7g.large`, rather than an incompatible demo `mq.t3.micro`.
- [AWS Load Balancer Controller policy v2.14.0](https://github.com/kubernetes-sigs/aws-load-balancer-controller/blob/v2.14.0/docs/install/iam_policy.json): vendored verbatim under `terraform/platform/policies` to match chart `1.14.0`.
