"""Offline CI checks for Badminton Local Development & Contracts. Never calls Docker, kubectl or AWS."""

import argparse
import ast
import hashlib
import re
import subprocess
from pathlib import Path

from .common import ROOT, read


def verify_application_source(app: Path, lock: dict) -> None:
    """Verify both the reviewed Git revision and its selected interface bytes."""
    if lock.get("schema_version") != "1.0.0" or lock.get("source_repository") != "chiendz11/badminton_system":
        raise ValueError("Unexpected application source lock identity")
    sha = lock.get("source_git_sha", "")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha) or not lock.get("files"):
        raise ValueError("Application source lock requires a real revision and file hashes")
    actual = subprocess.check_output(["git", "-C", str(app), "rev-parse", "HEAD"], text=True).strip()
    if actual != sha:
        raise ValueError("Application checkout HEAD differs from the reviewed source lock")
    for name, expected in lock["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid application source lock entry: " + name)
        if hashlib.sha256((app / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("Application interface drift requires review: " + name)


def check(app=None, companion=None) -> None:
    for path in (ROOT / "localdev").glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    contract = read(ROOT / "local/config/contract.json")
    if contract.get("cluster_name") != "badminton-local":
        raise ValueError("Unexpected cluster name in contract")
    if contract.get("namespace") != "badminton":
        raise ValueError("Unexpected namespace in contract")

    catalog = read(ROOT / "local/config/runtime-catalog.json")["components"]
    for comp in ("booking-core", "ai-service", "api-gateway", "content-service", "identity-service", "web", "admin"):
        if comp not in catalog:
            raise ValueError(f"Component {comp} missing in runtime catalog")

    source = (ROOT / "localdev/cli.py").read_text(encoding="utf-8")
    if "use-context" in source or "terraform" in source.lower():
        raise ValueError("Local operator must not change current context or call Terraform")

    if app:
        verify_application_source(app, read(ROOT / "local/versions/app-source.lock.json"))
    if companion:
        required = (
            "applications/local/kustomization.yaml",
            "applications/local/image-updater.yaml",
            "environments/local/platform/kustomization.yaml",
            "environments/local/observability/kustomization.yaml",
            "environments/local/apps/kustomization.yaml",
        )
        for rel in required:
            if not (companion / rel).is_file():
                raise ValueError("Missing Pure Declarative GitOps manifest: " + rel)

    print("Badminton local source, contract, and operator safety checks passed.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-root", type=Path)
    parser.add_argument("--gitops-root", type=Path)
    args = parser.parse_args()
    check(args.app_root, args.gitops_root)


if __name__ == "__main__":
    main()
