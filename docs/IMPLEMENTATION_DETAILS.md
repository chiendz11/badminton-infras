# Implementation details

## Delivered boundaries

| Area | Code |
| --- | --- |
| Remote state/OIDC | bootstrap root with local-first migration, KMS rotation, versioning, blocked public access, TLS-only bucket policy, exact GitHub subjects |
| Network | two/three AZ subnet layout; private worker/data subnets; public ALB subnets; optional cost-controlled interface endpoints; S3 gateway endpoint |
| EKS | v21 module, private workers, restricted public/private API, audit/control-plane logs, VPC CNI NetworkPolicy support, managed nodes, IRSA, role access entries |
| Storage | EBS CSI with its own role; GitOps owns gp3 StorageClass/PVC |
| PostgreSQL | independent identity/booking/commerce instances; optional enabled AI instance; forced SSL; encryption, backup retention, final snapshot, deletion protection |
| Cache | private TLS/at-rest-encrypted Valkey, AUTH from existing secret, configurable replicas/failover/backups |
| Messaging | private Amazon MQ RabbitMQ with AMQPS, bootstrap secret, retained operator-managed vhost/user/queue setup |
| Registry | 11 immutable ECR repos, scan on push, expire untagged leftovers while retaining tagged rollback history |
| IAM | exact service-account IRSA; ESO reads only application secrets; ExternalDNS modifies only the owned zone; vendored AWS LB controller policy; app push-only ECR role; GitOps image-read role |
| Secrets | PayOS/Cloudinary/LLM/OAuth/integration containers and 9 per-backend runtime containers; operator values, no plaintext tfvars |
| Argo | Helm chart/version/values, resource health customizations, read-only plan RBAC, separate root chart, main/applications target |
| Handoff | strict shared platform schema, non-secret output allow-list, protected apply, contract-only artifact, App-token dispatch |

## Adaptations to the app repository

Current code has web/admin/gateway/booking/AI. The six remaining deployables get infrastructure and GitOps templates but their app source/images are future work in `badminton_system`.

AI currently uses its own PostgreSQL, not Redis, for persistent conversation/checkpoint state. This is why the optional fourth DB defaults on and the GitOps receiver requires it for this runtime. Redis metadata remains available for a future checkpoint backend change. No GPU group, training platform, Argo Workflows/Events, KServe, Knative, MLflow or model lifecycle is included.

The admin root-path SPA gets a separate hostname covered by ACM. The public `/admin` path redirects there. This avoids claiming that an unmodified root-path build can run correctly under a prefix.

Broker defaults use RabbitMQ 4.2 with `mq.m7g.large`, consistent with the supported managed instance family. Managed messaging therefore does not have the same tiny-cost profile as a demo self-hosted broker. No self-hosted data profile was added because the chosen target is managed RDS/Valkey/MQ plus existing Atlas.

Infrastructure does not modify app source, app publisher workflows or existing Iris repositories. The application publisher/verifier roles and GitOps receiver contract are ready for a later app-side build/sign/publish producer. That producer must supply a distinct Prisma migration image digest for Node database services.

## Work still required before deployment

Supply real account/domain/runner CIDRs, create bootstrap credentials, migrate state, configure GitHub environment/App permissions and protections, provision service database users and managed MongoDB, populate runtime secrets, configure RabbitMQ users/vhost/topology, build/sign real app images and publish their release intents. Review actual plans, resources, sizing, scanner results and recovery procedures before cloud deployment.

No execution evidence is claimed: requested implementation omitted tests and cloud/Kubernetes validation. Terraform formatting is the only Terraform command run locally.
