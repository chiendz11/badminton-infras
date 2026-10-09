# Infrastructure rollback and recovery

1. Identify whether the fault is an app image/config, data schema or cloud resource. App image/config recovery belongs to GitOps; do not change Terraform to choose an application digest.
2. For cloud configuration, prepare a fix/revert PR and review a fresh Terraform plan. Reverting code is not sufficient when a resource's engine/version cannot downgrade or replacement destroys data.
3. Preserve RDS automated backups, final snapshots and deletion protection. Restore a snapshot/PITR to a new private instance, validate business data using the approved recovery procedure, then hand off new endpoint metadata and rotate/update the per-service runtime connection secret.
4. Refresh the platform contract and merge GitOps's reconcile PR. The endpoint-specific NetworkPolicies must match a restored/failover endpoint's current IPs.
5. Never blindly replace remote Terraform state. S3 state objects are versioned and KMS-encrypted; inspect the relevant historical version with controlled operator access, preserve the current object and lock state, and restore only after reviewing resource drift. Keep bootstrap KMS and state bucket protected.
6. For lost Argo resources, restore the Helm releases with the apply role, then the root Application. GitOps main reconstructs desired state; externally populated secrets remain in Secrets Manager. Do not enable the root before the reviewed platform configuration is present.
7. Managed MongoDB/Atlas backups and restores are controlled by Atlas and service owners; enable and verify them before production use. This profile does not implement self-hosted Mongo/RabbitMQ/Redis volume recovery.
8. Never turn deletion protection or destroy guards off merely to make a plan pass. Recovery and resource destruction require an explicit operator decision outside this initial coding task.

Database schema recovery must follow the application's expand/deploy/contract migration plan. An older image cannot reverse a destructive business migration. The GitOps recovery workflow restores a verified historical image through review, not data.
