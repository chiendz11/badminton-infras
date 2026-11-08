"""Local credentials and Secrets generation for Badminton Local Demo."""

import json
import os
import secrets
from pathlib import Path

from .common import CONTRACT, LOCAL, NAMESPACE, ROOT, apply, kube, read, write_json


def initialize():
    LOCAL.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(LOCAL, 0o700)
    for area in ("state", "receipts", "storage"):
        (LOCAL / area).mkdir(parents=True, exist_ok=True, mode=0o700)
    if not (LOCAL / "settings.json").exists():
        write_json(LOCAL / "settings.json", read(ROOT / "local/config/settings.example.json"))
    if not (LOCAL / "credentials.json").exists():
        value = {
            "postgres": {
                "booking_password": "booking_dev",
                "ai_password": "ai_dev",
                "admin_password": secrets.token_hex(24)
            },
            "jwt_secret": "local-development-only-change-me-32-chars",
            "metrics_token": "local-monitoring-only",
            "llm_api_key": "gsk_localmockdemo",
            "payos": {
                "client_id": "local-payos-client-id",
                "api_key": "local-payos-api-key",
                "checksum_key": "local-payos-checksum-key"
            }
        }
        write_json(LOCAL / "credentials.json", value)


def seed_localstack_secrets():
    """Seed AWS Secrets Manager on LocalStack for parity with AWS Cloud."""
    creds = read(LOCAL / "credentials.json")
    jwt_secret = creds.get("jwt_secret", "local-development-only-change-me-32-chars")
    booking_pw = creds["postgres"].get("booking_password", "booking_dev")
    ai_pw = creds["postgres"].get("ai_password", "ai_dev")
    metrics_token = creds.get("metrics_token", "local-monitoring-only")

    booking_db_url = f"postgresql://booking:{booking_pw}@postgres:5432/booking"
    ai_db_url = f"postgresql+psycopg://ai:{ai_pw}@postgres:5432/ai"

    secrets_to_seed = {
        "badminton/prod/llm": {
            "api_key": creds.get("llm_api_key", "gsk_localmockdemo")
        },
        "badminton/prod/ai-service-runtime": {
            "jwt_secret": jwt_secret,
            "metrics_token": metrics_token,
            "internal_service_token": "local-internal-token",
            "database_url": ai_db_url,
            "redis_url": "redis://redis:6379/0"
        },
        "badminton/prod/booking-core-runtime": {
            "jwt_secret": jwt_secret,
            "metrics_token": metrics_token,
            "internal_service_token": "local-internal-token",
            "database_url": booking_db_url,
            "redis_url": "redis://redis:6379/0",
            "rabbitmq_url": "amqp://guest:guest@rabbitmq:5672/"
        },
        "badminton/prod/api-gateway-runtime": {
            "jwt_secret": jwt_secret,
            "metrics_token": metrics_token,
            "internal_service_token": "local-internal-token"
        },
        "badminton/prod/payos": {
            "client_id": creds.get("payos", {}).get("client_id", "local-payos-client-id"),
            "api_key": creds.get("payos", {}).get("api_key", "local-payos-api-key"),
            "checksum_key": creds.get("payos", {}).get("checksum_key", "local-payos-checksum-key")
        }
    }

    try:
        for sec_name, sec_dict in secrets_to_seed.items():
            payload = json.dumps(sec_dict)
            try:
                kube(
                    "exec", "-n", "localstack", "deployment/localstack", "--",
                    "awslocal", "secretsmanager", "create-secret",
                    "--name", sec_name,
                    "--secret-string", payload,
                    capture=True
                )
            except Exception:
                kube(
                    "exec", "-n", "localstack", "deployment/localstack", "--",
                    "awslocal", "secretsmanager", "put-secret-value",
                    "--secret-id", sec_name,
                    "--secret-string", payload,
                    capture=True
                )
        print("LocalStack AWS Secrets Manager seeded successfully with parity secrets.")
    except Exception as exc:
        print(f"Warning: Could not seed LocalStack secrets: {exc}")


def install_secrets():
    for ns in (NAMESPACE, CONTRACT.get("argocd_namespace", "argocd")):
        apply([{
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": ns,
                "labels": {"badminton.io/bootstrap-owner": "infrastructure"}
            }
        }])

    creds = read(LOCAL / "credentials.json")
    jwt_secret = creds.get("jwt_secret", "local-development-only-change-me-32-chars")
    booking_pw = creds["postgres"].get("booking_password", "booking_dev")
    ai_pw = creds["postgres"].get("ai_password", "ai_dev")
    metrics_token = creds.get("metrics_token", "local-monitoring-only")

    booking_db_url = f"postgresql://booking:{booking_pw}@postgres:5432/booking"
    ai_db_url = f"postgresql+psycopg://ai:{ai_pw}@postgres:5432/ai"

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
        },
        "ai-service-secrets": {
            "AI_DATABASE_URL": ai_db_url,
            "JWT_SECRET": jwt_secret,
            "METRICS_TOKEN": metrics_token,
        },
        "api-gateway-secrets": {
            "JWT_SECRET": jwt_secret,
            "METRICS_TOKEN": metrics_token,
        },
        "jwt-secret": {
            "JWT_SECRET": jwt_secret,
        }
    }

    for name, string_data in secrets_data.items():
        apply([{
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": name,
                "namespace": NAMESPACE,
                "labels": {"badminton.io/part-of": "badminton-local"}
            },
            "type": "Opaque",
            "stringData": string_data
        }], namespace=NAMESPACE)

    print("Badminton local secrets created/updated in namespace", NAMESPACE)
    seed_localstack_secrets()
