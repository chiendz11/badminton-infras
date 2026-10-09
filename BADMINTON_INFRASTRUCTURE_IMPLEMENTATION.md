# Badminton Manager V2 — Infrastructure Implementation Guide

> Thiết kế dựa trên pattern của `chiendz11/iris-infrastructure`, nhưng bỏ các thành phần chỉ dành cho MLOps như Argo Workflows, Argo Events, KServe, Knative và MLflow. Repository này chịu trách nhiệm cho AWS foundation, EKS, managed infrastructure, IAM/OIDC, registry, secrets, domain và bootstrap Argo CD. Deployment/Service/HPA của application thuộc GitOps repo.

## 1. Ownership boundary

```text
badminton-infrastructure
= AWS + EKS + IAM + ECR + managed data services
+ Route53/ACM + Secrets Manager
+ Argo CD Helm install + root Application

badminton-gitops
= Kubernetes desired state
+ platform add-ons
+ application workloads
+ monitoring rules
+ ExternalSecret + NetworkPolicy
```

Không quản lý `kubernetes_deployment`, `kubernetes_service` của app bằng Terraform nếu Argo CD cũng quản lý chúng.

## 2. Deployable cần hỗ trợ

```text
web
admin
api-gateway
identity-service
booking-core
commerce-service
social-service
content-service
notification-service
storage-service
ai-service
```

Data boundary:

```text
Identity     -> PostgreSQL
Booking Core -> PostgreSQL
Commerce     -> PostgreSQL
Social       -> MongoDB
Content      -> MongoDB
Notification -> MongoDB
Storage      -> MongoDB metadata
Booking/Social/Identity -> Redis/Valkey
Domain events -> RabbitMQ
Storage -> Cloudinary
Booking -> PayOS
AI -> hosted/local LLM + Booking Core read-only API
```

AI là online FastAPI + LangChain + LangGraph service, nên runtime không cần Argo Workflow/KServe.

## 3. Repository tree

```text
badminton-infrastructure/
├── .github/
│   └── workflows/
│       ├── terraform.yml
│       ├── production-infra.yml
│       ├── reusable-foundation.yml
│       ├── reusable-domain.yml
│       ├── reusable-platform.yml
│       └── reusable-platform-handoff.yml
├── contracts/
│   └── platform-contract-v1.schema.json
├── docs/
│   ├── AWS_DEPLOYMENT.md
│   ├── TERRAFORM_DEPENDENCIES.md
│   ├── SECRETS.md
│   └── ROLLBACK_RUNBOOK.md
├── environments/
│   └── production.tfvars
├── scripts/
│   ├── build_platform_contract.py
│   └── validate_platform_contract.py
└── terraform/
    ├── bootstrap/
    ├── domain/
    └── platform/
        ├── versions.tf
        ├── variables.tf
        ├── locals.tf
        ├── network.tf
        ├── eks.tf
        ├── eks_storage.tf
        ├── database.tf
        ├── cache.tf
        ├── messaging.tf
        ├── registry.tf
        ├── secrets.tf
        ├── iam.tf
        ├── edge.tf
        ├── gitops_controller.tf
        ├── outputs.tf
        ├── argocd-chart-version.txt
        ├── argocd-values-production.yaml
        └── charts/argocd-root/
```

Có thể thêm `terraform/github-config` và `terraform/github-governance` sau khi phần cloud hoạt động ổn.

## 4. Dependency order

```text
bootstrap
  -> remote Terraform state + GitHub OIDC
domain
  -> Route53 + ACM
platform
  -> VPC + EKS + data services + ECR + IAM + Secrets + Argo CD
platform contract
  -> badminton-gitops
```

Nên tách state tối thiểu: `bootstrap`, `domain`, `platform`.

## 5. Bootstrap

`terraform/bootstrap` tạo:

```text
S3 state bucket
KMS key
GitHub Actions OIDC provider
Terraform plan role
Terraform apply role
```

Lần đầu có thể chạy local, giống pattern Iris. Sau đó GitHub Actions dùng OIDC, không lưu AWS access key dài hạn.

## 6. VPC

Giữ pattern `terraform-aws-modules/vpc/aws`:

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.0"

  name = local.name
  cidr = var.vpc_cidr
  azs  = local.azs

  private_subnets = [
    for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, i)
  ]

  public_subnets = [
    for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 8, i + 48)
  ]

  enable_nat_gateway   = var.enable_nat_gateway
  single_nat_gateway   = var.single_nat_gateway
  enable_dns_hostnames = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }
}
```

Topology:

```text
Internet
  -> public subnet / ALB
  -> private subnet / EKS
  -> private RDS, Redis, RabbitMQ
```

DB không public.

## 7. VPC endpoints

Có thể giữ các endpoint như Iris:

```text
S3 gateway
ECR API
ECR DKR
STS
Secrets Manager
CloudWatch Logs
EKS/EC2/ELB
```

Interface endpoints nên bật/tắt bằng variable vì có chi phí.

## 8. EKS

```hcl
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = local.name
  kubernetes_version = var.kubernetes_version

  endpoint_public_access = true
  enable_irsa            = true

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.private_subnets

  addons = {
    coredns                = { most_recent = true }
    kube-proxy             = { most_recent = true }
    vpc-cni                = { most_recent = true, before_compute = true }
    eks-pod-identity-agent = { most_recent = true, before_compute = true }
  }

  eks_managed_node_groups = {
    general = {
      instance_types = var.node_instance_types
      min_size       = var.node_min_size
      max_size       = var.node_max_size
      desired_size   = var.node_desired_size
      capacity_type  = "ON_DEMAND"
    }
  }
}
```

AI dùng hosted LLM thì không cần GPU node group. Chỉ thêm GPU khi benchmark local inference chứng minh cần.

## 9. EBS CSI

Terraform sở hữu EBS CSI addon + IAM. GitOps sở hữu StorageClass/PVC.

Cần nếu tự host stateful workload trên EKS như MongoDB/RabbitMQ/Redis hoặc workload cần PVC.

## 10. PostgreSQL

Domain target có ba ownership boundary:

```text
Identity PostgreSQL
Booking PostgreSQL
Commerce PostgreSQL
```

Production target nên dùng ba RDS instance độc lập. Có thể dùng `for_each`:

```hcl
locals {
  postgres_services = {
    identity = "identity"
    booking  = "booking"
    commerce = "commerce"
  }
}
```

Pseudo resource:

```hcl
resource "aws_db_instance" "postgres" {
  for_each = local.postgres_services

  identifier = "${local.name}-${each.key}"
  engine     = "postgres"

  instance_class              = var.db_instance_class
  allocated_storage           = var.db_allocated_storage
  storage_encrypted           = true
  publicly_accessible         = false
  username                    = var.db_username
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds[each.key].id]

  backup_retention_period = var.db_backup_retention_days
  deletion_protection     = var.environment == "prod"
}
```

`manage_master_user_password = true` giúp password nằm trong Secrets Manager thay vì tfvars/state.

Cost-saving demo có thể dùng một RDS server với ba logical DB, nhưng code vẫn phải giữ ownership riêng và không query chéo DB.

## 11. MongoDB

Các service cần Mongo:

```text
social
content
notification
storage metadata
```

Hai profile:

- Gần production: MongoDB Atlas managed.
- Demo tiết kiệm: MongoDB StatefulSet/Helm trong EKS, do GitOps quản lý.

Không tự động đổi sang DocumentDB nếu chưa kiểm tra compatibility với MongoDB/Mongoose.

## 12. Redis / Valkey

Dùng cho:

```text
Booking -> BullMQ/expiration/cache
Social  -> Socket.IO Redis Adapter
Identity -> session/rate limit/cache nếu cần
AI -> optional checkpoint/session cache
```

Production có thể dùng ElastiCache for Valkey/Redis.

```hcl
resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name}-cache"
  subnet_ids = module.vpc.private_subnets
}
```

Chỉ expose private endpoint.

## 13. RabbitMQ

Dùng cho async domain events:

```text
BookingConfirmed
BookingCancelled
PassTransferred
PassInterested
UserProfileUpdated
SaleCompleted
```

Không dùng RabbitMQ thay DB transaction cho `reserve slot` hay `create booking`.

Production: Amazon MQ for RabbitMQ. Demo: RabbitMQ Helm/StatefulSet ở GitOps.

## 14. ECR

Thay ECR ML-specific của Iris bằng:

```text
web
admin
api-gateway
identity-service
booking-core
commerce-service
social-service
content-service
notification-service
storage-service
ai-service
```

```hcl
locals {
  ecr_services = toset([
    "web", "admin", "api-gateway", "identity-service",
    "booking-core", "commerce-service", "social-service",
    "content-service", "notification-service",
    "storage-service", "ai-service",
  ])
}

resource "aws_ecr_repository" "services" {
  for_each = local.ecr_services

  name                 = "${local.name}/${each.key}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}
```

GitOps pin `repository@sha256:...`, không dùng `latest`.

## 15. GitHub OIDC publisher role

`badminton_system` là monorepo nên một application publisher role có thể push các ECR repo của project nhưng không có EKS admin.

Flow:

```text
GitHub Actions
  -> OIDC
  -> app publisher role
  -> ECR push
```

App CI không có quyền `kubectl apply`.

## 16. Secrets Manager

Terraform quản lý secret container/policy, không quản lý plaintext secret value nếu không cần.

Ví dụ:

```text
badminton/prod/payos
badminton/prod/cloudinary
badminton/prod/llm
badminton/prod/internal-service-auth
badminton/prod/rabbitmq
badminton/prod/redis
```

RDS master secret để AWS quản lý.

## 17. External Secrets IRSA

```text
AWS Secrets Manager
  -> External Secrets Operator (IRSA)
  -> Kubernetes Secret
  -> Pod
```

Policy chỉ cho đọc secret ARN của Badminton.

## 18. IRSA

Cần tối thiểu cho:

```text
external-secrets
external-dns
aws-load-balancer-controller
```

Workload app chỉ có IRSA khi thật sự gọi AWS API. Ví dụ storage-service chuyển sang S3 thì mới cấp S3 role riêng.

## 19. Domain/edge

Terraform/domain sở hữu:

```text
Route53 Hosted Zone
ACM certificate
DNS validation
```

GitOps sở hữu Ingress.

Target:

```text
https://badminton.example.com/
https://badminton.example.com/api/
wss://badminton.example.com/socket.io/
```

## 20. Argo CD bootstrap

Giữ pattern Iris:

```hcl
resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"

  namespace        = "argocd"
  create_namespace = true

  values = [
    file("${path.module}/argocd-values-production.yaml")
  ]
}

resource "helm_release" "argocd_root" {
  name      = "badminton-root"
  chart     = "${path.module}/charts/argocd-root"
  namespace = "argocd"

  depends_on = [helm_release.argocd]
}
```

Root Application trỏ tới:

```text
repo: chiendz11/badminton-gitops
path: applications
branch: main
```

Sau đó Terraform dừng quản lý workload.

## 21. Platform contract

Nên giữ pattern rất tốt từ Iris:

```text
terraform output -json
  -> build_platform_contract.py
  -> platform-contract-v1.json
  -> GitOps receiver
  -> protected PR
```

Contract chỉ chứa non-secret values:

```json
{
  "schema_version": "v1",
  "environment": "production",
  "aws_region": "ap-southeast-1",
  "cluster_name": "badminton-prod",
  "vpc_id": "vpc-...",
  "ecr": {
    "booking_core": ".../booking-core",
    "ai_service": ".../ai-service"
  },
  "database": {
    "identity_host": "...",
    "booking_host": "...",
    "commerce_host": "..."
  },
  "secret_arns": {
    "identity_db": "arn:...",
    "booking_db": "arn:...",
    "commerce_db": "arn:..."
  },
  "irsa": {
    "external_secrets": "arn:...",
    "external_dns": "arn:...",
    "aws_load_balancer_controller": "arn:..."
  },
  "public": {
    "domain": "badminton.example.com",
    "certificate_arn": "arn:..."
  }
}
```

Không chứa DB password, LLM key, PayOS key, Cloudinary key.

## 22. Outputs

`outputs.tf` nên expose:

```text
cluster_name
cluster_endpoint
vpc_id
aws_region
ecr_repository_urls

identity_rds_endpoint
booking_rds_endpoint
commerce_rds_endpoint

identity_rds_master_secret_arn
booking_rds_master_secret_arn
commerce_rds_master_secret_arn

redis_endpoint
rabbitmq_endpoint

external_secrets_role_arn
external_dns_role_arn
aws_load_balancer_controller_role_arn

public_domain_name
public_certificate_arn
route53_zone_id
```

## 23. Variables

Nhóm:

```text
General
Network
EKS
Database
Cache
Messaging
Domain
GitHub/OIDC
GitOps
Cost profile
```

Ví dụ:

```hcl
variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.30.0.0/16"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}
```

## 24. `production.tfvars`

Ví dụ:

```hcl
aws_region  = "ap-southeast-1"
environment = "prod"

vpc_cidr = "10.30.0.0/16"

node_instance_types = ["t3.medium"]
node_min_size       = 1
node_desired_size   = 2
node_max_size       = 4

db_instance_class        = "db.t4g.micro"
db_allocated_storage     = 20
db_backup_retention_days = 7
db_multi_az              = false

enable_nat_gateway = true
single_nat_gateway = true

enable_public_domain = true
public_domain_name   = "badminton.example.com"
```

Demo có thể Single-AZ/single NAT. Production thật cần review HA riêng.

## 25. CI Terraform

PR:

```text
terraform fmt -check
terraform init
terraform validate
tflint
security scan
terraform plan
```

Không apply trên PR.

Main:

```text
merge main
  -> production-infra.yml
  -> detect changed root
  -> protected Environment
  -> OIDC assume apply role
  -> refreshed plan
  -> apply
  -> build platform contract
  -> dispatch GitOps reconcile
```

Dùng concurrency để tránh hai production apply cùng lúc.

## 26. Deployment phases

```text
Phase 0: bootstrap
Phase 1: domain
Phase 2: platform
Phase 3: GitOps handoff
```

CLI:

```bash
terraform -chdir=terraform/bootstrap init -backend=false
terraform -chdir=terraform/bootstrap apply

terraform -chdir=terraform/domain init
terraform -chdir=terraform/domain plan
terraform -chdir=terraform/domain apply

terraform -chdir=terraform/platform init
terraform -chdir=terraform/platform plan   -var-file=../../environments/production.tfvars
```

Sau platform apply:

```text
Terraform outputs
  -> platform contract
  -> GitOps PR
  -> merge
  -> Argo CD
```

## 27. Network security

```text
ALB: public 443
EKS: private worker subnet
RDS: 5432 only from workload network
Redis: private only
RabbitMQ: private AMQPS only
```

Kubernetes east-west restrictions thuộc GitOps NetworkPolicy.

## 28. DB migration ownership

Terraform tạo database infrastructure, không chạy business schema migration.

```text
identity image -> prisma migrate deploy
booking image  -> prisma migrate deploy
commerce image -> prisma migrate deploy
```

GitOps có thể chạy Argo CD PreSync Job. Không cần Argo Workflow.

## 29. Backup tối thiểu

```text
RDS automated backups
final snapshot
deletion protection
Secrets Manager recovery window
ECR immutable digest
Terraform state versioning
```

Nếu self-host Mongo/RabbitMQ/Redis thì phải có volume backup + restore runbook riêng.

## 30. Monitoring boundary

Terraform không sở hữu app alert rules.

```text
App repo
  -> /metrics instrumentation

GitOps
  -> kube-prometheus-stack
  -> ServiceMonitor
  -> PrometheusRule
```

## 31. Từ Iris nên giữ

```text
remote state bootstrap
GitHub OIDC
VPC/EKS module
IRSA
EBS CSI
Route53 + ACM
immutable/scanned ECR
Secrets Manager
External Secrets IAM
AWS LB Controller IAM
ExternalDNS IAM
Argo CD Helm bootstrap
root Application
platform contract
PR plan / protected apply
```

## 32. Từ Iris phải bỏ

```text
DVC bucket
MLflow artifact bucket
SQS dataset event
Argo Events
training IRSA
MLflow RDS
KServe hostname
Knative
KServe
Argo Workflows
model-release publisher
training lifecycle
```

## 33. Resource mới của Badminton

```text
3 PostgreSQL ownership boundaries
Redis/Valkey
RabbitMQ
11 ECR repositories
PayOS secret
Cloudinary secret
LLM provider secret
MongoDB integration
```

## 34. Definition of Done

```text
terraform validate PASS
terraform plan reviewed

VPC ready
EKS Ready
node group Ready
EBS CSI Ready

RDS private
Redis private
RabbitMQ private

ECR created
OIDC publisher can push expected ECR only

Secrets containers exist
External Secrets role is least-privilege

Route53/ACM valid
Argo CD healthy
badminton-root exists

platform-contract-v1 generated
no secret plaintext in GitOps contract
```

## 35. Final flow

```text
GitHub
  ├─ badminton-infrastructure
  |      -> AWS/EKS/ArgoCD
  |
  └─ badminton_system
         -> CI -> ECR image digests

AWS/EKS + image digests
          |
          v
badminton-gitops
          |
          v
Argo CD
          |
          v
Kubernetes workloads
```

Quy tắc cuối: **Infrastructure repo quyết định cloud/platform nào tồn tại; không quyết định Pod app đang chạy image nào.**
