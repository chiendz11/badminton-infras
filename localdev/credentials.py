"""Local credentials and Secrets generation for Badminton Local Demo."""

import json
import os
import secrets
from pathlib import Path

from .common import CONTRACT, LOCAL, NAMESPACE, ROOT, apply, kube, read, write_json

DEFAULT_PAT_PATH = ROOT.parent / "PAT.txt"
DEFAULT_GITOPS_USERNAME = "chiendz11"
IMAGE_UPDATER_SECRET_NAME = "badminton/prod/argocd-image-updater-git-creds"


def initialize():
    LOCAL.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(LOCAL, 0o700)
    for area in ("state", "receipts", "storage", "secrets"):
        (LOCAL / area).mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(LOCAL / area, 0o700)
    if not (LOCAL / "settings.json").exists():
        write_json(LOCAL / "settings.json", read(ROOT / "local/config/settings.example.json"))
    if not (LOCAL / "credentials.json").exists():
        value = {
            "postgres": {
                "booking_password": "booking_dev",
                "ai_password": "ai_dev",
                "identity_password": "identity_dev",
                "admin_password": secrets.token_hex(24),
            },
            "jwt_secret": secrets.token_hex(32),
            "metrics_token": "local-monitoring-only",
            "internal_service_token": "local-internal-token",
            "llm_api_key": "gsk_localmockdemo",
            "payos": {
                "client_id": "local-payos-client-id",
                "api_key": "local-payos-api-key",
                "checksum_key": "local-payos-checksum-key",
            },
        }
        write_json(LOCAL / "credentials.json", value)


def _read_private_token_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError(f"Private secret file must be a regular file with mode 600: {path}")
    token = path.read_text(encoding="utf-8").strip()
    if not token or len(token) > 4096 or any(ch.isspace() for ch in token):
        raise ValueError(f"Secret token in {path} is empty or contains invalid whitespace")
    return token


def _put_localstack_secrets(documents: dict[str, dict[str, str]]) -> None:
    """Write secret payloads to LocalStack Secrets Manager via stdin (never argv or logs)."""
    program = """import sys,json,boto3
c=boto3.client('secretsmanager',endpoint_url='http://localhost:4566',region_name='ap-southeast-1',aws_access_key_id='test',aws_secret_access_key='test')
for name,value in json.load(sys.stdin).items():
 payload=json.dumps(value)
 try:c.create_secret(Name=name,SecretString=payload)
 except c.exceptions.ResourceExistsException:c.put_secret_value(SecretId=name,SecretString=payload)
print('LocalStack Secrets Manager values synchronized (values not printed).')
"""
    kube(
        "exec", "-i", "deployment/localstack", "--", "python3", "-c", program,
        namespace="localstack",
        stdin=json.dumps(documents),
        capture=True,
    )


def seed_image_updater_secret(username: str, token: str) -> None:
    """Seed LocalStack Secrets Manager for ESO ExternalSecret argocd/argocd-image-updater-git-creds."""
    if not username or any(ch.isspace() for ch in username) or not token or any(ch.isspace() for ch in token):
        raise ValueError("GitHub username and PAT must be non-empty single-line strings")
    _put_localstack_secrets({
        IMAGE_UPDATER_SECRET_NAME: {
            "username": username,
            "password": token,
        },
    })
    print(f"Secret {IMAGE_UPDATER_SECRET_NAME} seeded in LocalStack Secrets Manager via stdin (value not logged).")


def _load_optional_image_updater_creds() -> tuple[str, str] | None:
    local_pat = LOCAL / "secrets/image-updater-pat"
    local_user = LOCAL / "secrets/image-updater-username"
    if local_pat.exists() or local_pat.is_symlink():
        token = _read_private_token_file(local_pat)
        username = DEFAULT_GITOPS_USERNAME
        if local_user.exists() or local_user.is_symlink():
            username = _read_private_token_file(local_user)
        return username, token
    if DEFAULT_PAT_PATH.exists() or DEFAULT_PAT_PATH.is_symlink():
        return DEFAULT_GITOPS_USERNAME, _read_private_token_file(DEFAULT_PAT_PATH)
    return None


def _load_or_upgrade_credentials() -> dict:
    """Load local credentials and replace weak dev-placeholder JWT secrets if present."""
    creds = read(LOCAL / "credentials.json")
    current = str(creds.get("jwt_secret", ""))
    if len(current) < 32 or "local-development" in current or "change-me" in current:
        creds["jwt_secret"] = secrets.token_hex(32)
        write_json(LOCAL / "credentials.json", creds)
    return creds


def seed_localstack_secrets():
    """Seed AWS Secrets Manager on LocalStack for parity with AWS Cloud."""
    creds = _load_or_upgrade_credentials()
    jwt_secret = creds["jwt_secret"]
    booking_pw = creds["postgres"].get("booking_password", "booking_dev")
    ai_pw = creds["postgres"].get("ai_password", "ai_dev")
    identity_pw = creds["postgres"].get("identity_password", "identity_dev")
    metrics_token = creds.get("metrics_token", "local-monitoring-only")
    internal_token = creds.get("internal_service_token", "local-internal-token")

    booking_db_url = f"postgresql://booking:{booking_pw}@postgres:5432/booking"
    ai_db_url = f"postgresql+psycopg://ai:{ai_pw}@postgres:5432/ai"
    identity_db_url = f"postgresql://identity:{identity_pw}@postgres:5432/identity?connect_timeout=3&pool_timeout=3"

    secrets_to_seed = {
        "badminton/prod/llm": {
            "api_key": creds.get("llm_api_key", "gsk_localmockdemo"),
        },
        "badminton/prod/ai-service-runtime": {
            "jwt_secret": jwt_secret,
            "metrics_token": metrics_token,
            "internal_service_token": internal_token,
            "database_url": ai_db_url,
            "redis_url": "redis://redis:6379/0",
        },
        "badminton/prod/booking-core-runtime": {
            "jwt_secret": jwt_secret,
            "metrics_token": metrics_token,
            "internal_service_token": internal_token,
            "database_url": booking_db_url,
            "redis_url": "redis://redis:6379/0",
            "rabbitmq_url": "amqp://guest:guest@rabbitmq:5672/",
        },
        "badminton/prod/api-gateway-runtime": {
            "jwt_secret": jwt_secret,
            "metrics_token": metrics_token,
            "internal_service_token": internal_token,
        },
        "badminton/prod/identity-service-runtime": {
            "jwt_secret": jwt_secret,
            "metrics_token": metrics_token,
            "internal_service_token": internal_token,
            "database_url": identity_db_url,
        },
        "badminton/prod/content-service-runtime": {
            "jwt_secret": jwt_secret,
            "metrics_token": metrics_token,
            "internal_service_token": internal_token,
            "mongodb_uri": "mongodb://mongo:27017/badminton_content",
        },
        "badminton/prod/payos": {
            "client_id": creds.get("payos", {}).get("client_id", "local-payos-client-id"),
            "api_key": creds.get("payos", {}).get("api_key", "local-payos-api-key"),
            "checksum_key": creds.get("payos", {}).get("checksum_key", "local-payos-checksum-key"),
        },
    }

    pat_creds = _load_optional_image_updater_creds()
    if pat_creds is not None:
        secrets_to_seed[IMAGE_UPDATER_SECRET_NAME] = {
            "username": pat_creds[0],
            "password": pat_creds[1],
        }

    try:
        _put_localstack_secrets(secrets_to_seed)
        print("LocalStack AWS Secrets Manager seeded successfully with parity secrets.")
    except Exception as exc:
        print(f"Warning: Could not seed LocalStack secrets: {exc}")


def install_secrets():
    for ns in (NAMESPACE, CONTRACT.get("argocd_namespace", "argocd"), "external-secrets"):
        apply([{
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": ns,
                "labels": {"badminton.io/bootstrap-owner": "infrastructure"},
            },
        }])

    creds = _load_or_upgrade_credentials()
    jwt_secret = creds["jwt_secret"]
    booking_pw = creds["postgres"].get("booking_password", "booking_dev")
    ai_pw = creds["postgres"].get("ai_password", "ai_dev")
    identity_pw = creds["postgres"].get("identity_password", "identity_dev")
    metrics_token = creds.get("metrics_token", "local-monitoring-only")
    internal_token = creds.get("internal_service_token", "local-internal-token")

    booking_db_url = f"postgresql://booking:{booking_pw}@postgres:5432/booking"
    ai_db_url = f"postgresql+psycopg://ai:{ai_pw}@postgres:5432/ai"
    identity_db_url = f"postgresql://identity:{identity_pw}@postgres:5432/identity?connect_timeout=3&pool_timeout=3"

    secrets_data = {
        "booking-database": {
            "POSTGRES_USER": "booking",
            "POSTGRES_PASSWORD": booking_pw,
            "POSTGRES_DB": "booking",
            "DATABASE_URL": booking_db_url,
        },
        "ai-database": {
            "POSTGRES_USER": "ai",
            "POSTGRES_PASSWORD": ai_pw,
            "POSTGRES_DB": "ai",
            "DATABASE_URL": ai_db_url,
        },
        "booking-core-secrets": {
            "DATABASE_URL": booking_db_url,
            "JWT_SECRET": jwt_secret,
            "METRICS_TOKEN": metrics_token,
            "INTERNAL_SERVICE_TOKEN": internal_token,
        },
        "ai-service-secrets": {
            "AI_DATABASE_URL": ai_db_url,
            "JWT_SECRET": jwt_secret,
            "METRICS_TOKEN": metrics_token,
            "INTERNAL_SERVICE_TOKEN": internal_token,
        },
        "api-gateway-secrets": {
            "JWT_SECRET": jwt_secret,
            "METRICS_TOKEN": metrics_token,
            "INTERNAL_SERVICE_TOKEN": internal_token,
        },
        "identity-service-secrets": {
            "DATABASE_URL": identity_db_url,
            "JWT_SECRET": jwt_secret,
            "METRICS_TOKEN": metrics_token,
            "INTERNAL_SERVICE_TOKEN": internal_token,
        },
        "content-service-secrets": {
            "JWT_SECRET": jwt_secret,
            "METRICS_TOKEN": metrics_token,
            "INTERNAL_SERVICE_TOKEN": internal_token,
        },
        "jwt-secret": {
            "JWT_SECRET": jwt_secret,
        },
    }

    for name, string_data in secrets_data.items():
        apply([{
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": name,
                "namespace": NAMESPACE,
                "labels": {"badminton.io/part-of": "badminton-local"},
            },
            "type": "Opaque",
            "stringData": string_data,
        }], namespace=NAMESPACE)

    print("Badminton local secrets created/updated in namespace", NAMESPACE)
    seed_localstack_secrets()
