# Secrets and service boundaries

Terraform creates secret containers with 30-day recovery windows. An operator populates values in AWS Secrets Manager using a secure session. Never commit plaintext, encoded credentials, local value files or Terraform state. The contract contains ARNs and endpoints only.

## Before platform apply

Supply two existing bootstrap secrets under names different from Terraform-owned `badminton/prod/*` containers:

| Existing secret | JSON properties | Consumer |
| --- | --- | --- |
| bootstrap/badminton-rabbitmq | username, password | Amazon MQ provisioning |
| bootstrap/badminton-redis | password | Valkey AUTH token provisioning |

Use a valid ElastiCache AUTH token (16–128 characters with supported characters) and Amazon MQ password. Terraform's provider needs their values. The sensitive data sources and managed credentials therefore enter **encrypted Terraform state**; this implementation does not claim they are absent from state. Only the apply role and explicitly allow-listed plan role read these bootstrap secrets. External Secrets cannot read them.

RDS passwords use `manage_master_user_password=true` and AWS-managed Secrets Manager rotation. Master secret ARNs are output metadata; External Secrets deliberately does **not** receive permission to read RDS master credentials. Create per-service DB users with the appropriate ownership/migration privileges, and store their connection strings in service runtime secrets. Future password rotations must also update the corresponding runtime secret and restart applications if they do not reload environment variables.

## Terraform-owned application containers

| Name under badminton/prod/ | Expected properties |
| --- | --- |
| payos | client_id, api_key, checksum_key |
| cloudinary | cloud_name, api_key, api_secret |
| llm | api_key |
| oauth | client_id, client_secret |
| internal-service-auth | internal auth material for future consumers |
| rabbitmq | app connection configuration; never initial broker admin credentials |
| redis | app connection configuration |
| mongodb | optional operator-managed integration metadata/credentials |
| each backend `<component>-runtime` | jwt_secret, metrics_token, internal_service_token, plus required dependency URLs |

The initial GitOps manifests consume **per-component** runtime URLs rather than giving every application a shared data credential. Shared redis/rabbitmq/mongodb/internal containers are reserved for operator integration and are not indiscriminately mounted into Pods.

| Component | Additional runtime properties |
| --- | --- |
| identity-service | database_url, redis_url, rabbitmq_url |
| booking-core | database_url, redis_url, rabbitmq_url |
| commerce-service | database_url, rabbitmq_url |
| social-service | mongodb_uri, redis_url |
| content-service | mongodb_uri |
| notification-service | mongodb_uri, rabbitmq_url |
| storage-service | mongodb_uri |
| ai-service | database_url, redis_url |
| api-gateway | no DB or payment credentials |

Database URLs for Node services use `postgresql://.../<own-db>?sslmode=require` or stricter verified TLS when a trusted CA bundle is supplied. AI uses `postgresql+psycopg://.../ai?sslmode=require`. The AI host must be its **own** RDS, not Booking RDS. Redis URLs use `rediss://` with matching credentials; RabbitMQ uses `amqps://` and percent-encoded `/badminton` vhost. MongoDB credentials are distinct by service/database. Avoid putting credentials into the platform endpoints/ConfigMaps.

The current application verifies HMAC JWTs, so `jwt_secret` must match the issuing identity service and the consumers' issuer/audience. It must be at least 32 characters and must not use development values. Each service has its own metrics token; ServiceMonitor uses that service's generated Kubernetes Secret. The shared issuer secret is an application compatibility requirement; signing-key/public-key separation requires a future app change.

## ESO permissions and lifecycle

ESO's IRSA trust binds exactly to `external-secrets/external-secrets`. Its policy can read only project application secret ARNs. The ClusterSecretStore is restricted to `badminton` consumers. Workload Pods do not get AWS API roles automatically.

ESO creates one Kubernetes Secret per workload, with `creationPolicy=Orphan`. For database services the ExternalSecret is a PreSync hook that must report `Ready=True` before the migration Job runs. Keeping the Secret after hook recreation avoids deleting a running workload's credentials. Orphaned secrets should be cleaned up deliberately when a service is permanently removed.

Secret rotation happens in AWS. ESO refreshes hourly; environment-variable consumers need a controlled rolling restart. Do not print payloads or AWS secret values in GitHub Actions logs. GitHub App private keys live in GitHub environment secrets, not this repository or the platform contract.
