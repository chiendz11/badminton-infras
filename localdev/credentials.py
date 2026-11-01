"""Local credentials and Secrets generation for Badminton Local Demo."""

import json
import os
import secrets
from pathlib import Path

from .common import CONTRACT, LOCAL, NAMESPACE, ROOT, apply, read, write_json


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
            "metrics_token": "local-monitoring-only"
        }
        write_json(LOCAL / "credentials.json", value)


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

