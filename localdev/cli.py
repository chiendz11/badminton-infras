"""Badminton Local Operator CLI.

Explicit operations for cluster lifecycle, builds, imports, migrations and Argo CD.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

import yaml

from .common import (
    CONTEXT, CONTRACT, LOCAL, NAMESPACE, ROOT, apply, checkout,
    digest, kube, private_write, read, repository_url, run, settings,
    source_identity, validate_context, write_json
)
from .credentials import initialize, install_secrets


def pins():
    return read(ROOT / "local/versions/platform.lock.json")


def up():
    initialize()
    version = run(["k3d", "version"], capture=True)
    if "v" + pins()["k3d_version"] not in version:
        raise ValueError(f"k3d version differs from the reviewed local pin v{pins()['k3d_version']}")
    
    names = [item["name"] for item in json.loads(run(["k3d", "cluster", "list", "-o", "json"], capture=True))]
    if CONTRACT["cluster_name"] in names:
        if not (LOCAL / "cluster-owner.json").exists():
            raise ValueError(f"Existing cluster {CONTRACT['cluster_name']} belongs to another bootstrap")
        validate_context()
        run(["k3d", "cluster", "start", CONTRACT["cluster_name"]])
        print(f"Cluster {CONTRACT['cluster_name']} started.")
        return

    config = (ROOT / "local/config/k3d.yaml").read_text()
    for token, value in {
        "__IMAGE_K3S__": pins()["images"]["k3s"]["image"],
        "__LOCAL_STATE__": str(LOCAL / "state"),
        "__LOCAL_DATA__": str(LOCAL / "storage"),
    }.items():
        config = config.replace(token, value)
    
    private_write(LOCAL / "k3d.yaml", config)
    run([
        "k3d", "cluster", "create", "--config", str(LOCAL / "k3d.yaml"),
        "--kubeconfig-update-default=false", "--kubeconfig-switch-context=false"
    ])
    kubeconfig_content = run(["k3d", "kubeconfig", "get", CONTRACT["cluster_name"]], capture=True)
    private_write(LOCAL / "kubeconfig", kubeconfig_content)
    write_json(LOCAL / "cluster-owner.json", {
        "schema_version": "1.0.0",
        "context": CONTEXT,
        "cluster_name": CONTRACT["cluster_name"],
        "config_sha256": digest(LOCAL / "k3d.yaml")
    })
    validate_context()
    print("Cluster created with private kubeconfig; no platform/app manifests applied yet.")


def image_receipt(component, source, dockerfile, context, extra=(), allow_dirty=False):
    sha, dirty, snapshot = source_identity(source)
    if dirty and not allow_dirty:
        raise ValueError(f"Source in {source} is dirty; commit it or use --allow-dirty")
    
    path = source / dockerfile
    temporary = f"badminton-local/{component}:build-{snapshot[:16]}"
    build_cmd = [
        "docker", "build", "--file", str(path), "--tag", temporary,
        "--label", f"org.opencontainers.image.revision={sha}",
        "--label", f"badminton.io/source-snapshot={snapshot}",
        *extra, str(source / context)
    ]
    print(f"Building image for {component}...")
    run(build_cmd)

    identity = json.loads(run(["docker", "image", "inspect", temporary], capture=True))[0]["Id"]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", identity):
        raise ValueError("Docker did not return an actual image identity")
    
    alias = f"badminton-local/{component}:image-{identity[7:]}"
    run(["docker", "tag", identity, alias])
    receipt = {
        "schema_version": "1.0.0",
        "component": component,
        "image": alias,
        "image_id": identity,
        "source_git_sha": sha,
        "source_dirty": dirty,
        "source_snapshot_sha256": snapshot,
        "dockerfile": dockerfile,
        "dockerfile_sha256": digest(path),
        "build_context": context
    }
    (LOCAL / "receipts").mkdir(parents=True, exist_ok=True)
    write_json(LOCAL / "receipts" / f"{component}.json", receipt)
    print(f"Image receipt generated: {alias}")
    return receipt


def build(args):
    source = checkout("app_checkout")
    catalog = read(ROOT / "local/config/runtime-catalog.json")["components"]
    names = args.component or [name for name, val in catalog.items() if val.get("source_status") == "implemented"]
    
    for name in names:
        val = catalog[name]
        extra = []
        if name in {"web", "admin"}:
            extra = ["--build-arg", "VITE_API_GATEWAY_URL=http://127.0.0.1:18081"]
        image_receipt(name, source, val["dockerfile"], val["context"], extra, args.allow_dirty)
        
        # Build migration helper if defined
        if name == "booking-core" and val.get("migration") and val["migration"].get("target"):
            mig_extra = ["--target", val["migration"]["target"]]
            image_receipt("booking-core-migrations", source, val["dockerfile"], val["context"], mig_extra, args.allow_dirty)


def import_images(args):
    validate_context()
    catalog = read(ROOT / "local/config/runtime-catalog.json")["components"]
    names = args.component or [name for name, val in catalog.items() if val.get("source_status") == "implemented"]
    if not args.component and "booking-core" in names:
        names.append("booking-core-migrations")

    images_to_import = []
    for name in names:
        receipt_file = LOCAL / "receipts" / f"{name}.json"
        if not receipt_file.is_file():
            raise ValueError(f"No receipt for component {name}; run 'build' first")
        receipt = read(receipt_file)
        images_to_import.append(receipt["image"])
        receipt["imported_context"] = CONTEXT
        write_json(receipt_file, receipt)

    print(f"Importing {len(images_to_import)} image(s) into {CONTRACT['cluster_name']}...")
    run(["k3d", "image", "import", *images_to_import, "-c", CONTRACT["cluster_name"]])
    print("Images successfully imported into k3d cluster.")


def bootstrap_argocd():
    validate_context()
    config = settings()
    remote = repository_url(config["gitops_repository"])
    revision = config["gitops_revision"]

    install_secrets()
    upstream = pins()["argocd"]
    print(f"Downloading and preparing Argo CD {upstream['version']}...")
    with urllib.request.urlopen(upstream["url"], timeout=30) as resp:
        raw = resp.read(3_000_001)
    if hashlib.sha256(raw).hexdigest() != upstream["sha256"]:
        raise ValueError("Argo CD installer checksum mismatch")
    
    documents = list(yaml.safe_load_all(raw))

    def replace_images(value):
        if isinstance(value, dict):
            if isinstance(value.get("image"), str):
                for orig, pinned in upstream["images"].items():
                    if value["image"] == orig or value["image"].startswith(orig.split(":")[0]):
                        value["image"] = pinned
            for item in value.values():
                replace_images(item)
        elif isinstance(value, list):
            for item in value:
                replace_images(item)

    replace_images(documents)
    apply([{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "argocd"}}])
    kube("apply", "--server-side", "--field-manager=badminton-bootstrap", "-f", "-", namespace="argocd", stdin=yaml.safe_dump_all(documents))
    
    print("Waiting for Argo CD repo-server and application-controller...")
    kube("rollout", "status", "deployment/argocd-repo-server", "--timeout=300s", namespace="argocd")
    kube("rollout", "status", "statefulset/argocd-application-controller", "--timeout=300s", namespace="argocd")

    project = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "AppProject",
        "metadata": {"name": "badminton-local", "namespace": "argocd"},
        "spec": {
            "sourceRepos": [remote],
            "destinations": [{"server": "https://kubernetes.default.svc", "namespace": NAMESPACE}],
            "clusterResourceWhitelist": [{"group": "", "kind": "Namespace"}],
            "namespaceResourceBlacklist": [
                {"group": "argoproj.io", "kind": "Application"},
                {"group": "argoproj.io", "kind": "AppProject"}
            ]
        }
    }

    applications = []
    for app_name, app_path in CONTRACT["applications"].items():
        applications.append({
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {"name": f"badminton-local-{app_name}", "namespace": "argocd"},
            "spec": {
                "project": "badminton-local",
                "source": {"repoURL": remote, "targetRevision": revision, "path": app_path},
                "destination": {"server": "https://kubernetes.default.svc", "namespace": NAMESPACE},
                "syncPolicy": {
                    "automated": {"prune": False, "selfHeal": True},
                    "syncOptions": ["CreateNamespace=false", "FailOnSharedResource=true"]
                }
            }
        })

    kube("apply", "-f", "-", namespace="argocd", stdin=yaml.safe_dump_all([project, *applications]))
    print(f"Argo CD bootstrapped; applications 'badminton-local-platform' and 'badminton-local-apps' configured.")


def migrate():
    validate_context()
    print("Running database migrations for Badminton services...")
    
    # 1. Booking-Core migration & seed
    b_receipt = read(LOCAL / "receipts" / "booking-core-migrations.json")
    b_job_name = f"booking-migrate-{uuid.uuid4().hex[:8]}"
    b_job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": b_job_name, "namespace": NAMESPACE},
        "spec": {
            "backoffLimit": 1,
            "activeDeadlineSeconds": 300,
            "ttlSecondsAfterFinished": 86400,
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "containers": [{
                        "name": "migrate",
                        "image": b_receipt["image"],
                        "imagePullPolicy": "Never",
                        "command": ["sh", "-c", "pnpm --filter @badminton/booking-core prisma:migrate:deploy && pnpm --filter @badminton/booking-core seed"],
                        "envFrom": [{"secretRef": {"name": "booking-core-secrets"}}]
                    }]
                }
            }
        }
    }
    apply([b_job], namespace=NAMESPACE)
    print(f"Waiting for {b_job_name} to finish...")
    kube("wait", "--for=condition=complete", f"job/{b_job_name}", "--timeout=300s", namespace=NAMESPACE)
    print("Booking Core migrations and seed finished.")

    # 2. AI-Service migration
    ai_receipt = read(LOCAL / "receipts" / "ai-service.json")
    ai_job_name = f"ai-migrate-{uuid.uuid4().hex[:8]}"
    ai_job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": ai_job_name, "namespace": NAMESPACE},
        "spec": {
            "backoffLimit": 1,
            "activeDeadlineSeconds": 300,
            "ttlSecondsAfterFinished": 86400,
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "containers": [{
                        "name": "migrate",
                        "image": ai_receipt["image"],
                        "imagePullPolicy": "Never",
                        "command": ["sh", "-c", "alembic upgrade head && python -m app.migrate"],
                        "envFrom": [{"secretRef": {"name": "ai-service-secrets"}}]
                    }]
                }
            }
        }
    }
    apply([ai_job], namespace=NAMESPACE)
    print(f"Waiting for {ai_job_name} to finish...")
    kube("wait", "--for=condition=complete", f"job/{ai_job_name}", "--timeout=300s", namespace=NAMESPACE)
    print("AI Service migrations finished.")


def prepare(args):
    """Update GitOps desired state with actual local image receipts."""
    gitops = checkout("gitops_checkout")
    folder = gitops / "environments/local/apps"
    folder.mkdir(parents=True, exist_ok=True)
    
    receipts_dir = LOCAL / "receipts"
    catalog = read(ROOT / "local/config/runtime-catalog.json")["components"]
    enabled = [name for name, val in catalog.items() if val.get("source_status") == "implemented"]

    image_overrides = []
    selected_receipts = {}
    for name in enabled:
        r_file = receipts_dir / f"{name}.json"
        if not r_file.exists():
            continue
        r = read(r_file)
        repo, tag = r["image"].rsplit(":", 1)
        image_overrides.append({
            "name": f"registry.invalid/badminton-local/{name}",
            "newName": repo,
            "newTag": tag
        })
        selected_receipts[name] = r

    kustomize = {
        "apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization",
        "namespace": NAMESPACE,
        "resources": [
            "../../../local/workloads/booking-core",
            "../../../local/workloads/ai-service",
            "../../../local/workloads/api-gateway",
            "../../../local/workloads/web",
            "../../../local/workloads/admin"
        ],
        "images": image_overrides
    }
    (folder / "kustomization.yaml").write_text(yaml.safe_dump(kustomize, sort_keys=False))
    (folder / "release.json").write_text(json.dumps({
        "schema_version": "1.0.0",
        "images": selected_receipts
    }, indent=2) + "\n")
    print(f"Updated GitOps local apps desired state at {folder}")


def forward(args):
    validate_context()
    targets = {
        "argocd": ("service/argocd-server", "19443:443", "argocd"),
        "gateway": ("service/api-gateway", "18081:8081", NAMESPACE),
        "web": ("service/web", "18082:80", NAMESPACE),
        "admin": ("service/admin", "18083:80", NAMESPACE),
        "postgres": ("service/postgres", "15432:5432", NAMESPACE)
    }
    svc, port_map, ns = targets[args.target]
    print(f"Forwarding {svc} {port_map} in namespace {ns}... (Ctrl+C to stop)")
    kube("port-forward", "--address=127.0.0.1", svc, port_map, namespace=ns)


def status():
    validate_context()
    print("=== Nodes ===")
    kube("get", "nodes")
    print("\n=== Pods in 'badminton' ===")
    kube("get", "pods", "-o", "wide", namespace=NAMESPACE)
    print("\n=== Services in 'badminton' ===")
    kube("get", "services", namespace=NAMESPACE)
    print("\n=== Argo CD Applications ===")
    try:
        kube("get", "applications", "-n", "argocd")
    except Exception:
        print("Argo CD CRDs or Applications not installed yet.")


def delete():
    run(["k3d", "cluster", "delete", CONTRACT["cluster_name"]])
    if (LOCAL / "cluster-owner.json").exists():
        (LOCAL / "cluster-owner.json").unlink()
    print(f"Cluster {CONTRACT['cluster_name']} deleted.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Badminton Local Development & Demo Automation")
    sub = parser.add_subparsers(dest="operation", required=True)

    for name in ("init", "up", "secrets", "bootstrap-argocd", "migrate", "status", "delete"):
        sub.add_parser(name)

    build_cmd = sub.add_parser("build")
    build_cmd.add_argument("--component", action="append")
    build_cmd.add_argument("--allow-dirty", action="store_true", default=True)

    import_cmd = sub.add_parser("import-images")
    import_cmd.add_argument("--component", action="append")

    sub.add_parser("prepare")

    fwd_cmd = sub.add_parser("forward")
    fwd_cmd.add_argument("target", choices=["argocd", "gateway", "web", "admin", "postgres"])

    args = parser.parse_args(argv)
    try:
        if args.operation == "init": initialize()
        elif args.operation == "up": up()
        elif args.operation == "secrets": install_secrets()
        elif args.operation == "build": build(args)
        elif args.operation == "import-images": import_images(args)
        elif args.operation == "prepare": prepare(args)
        elif args.operation == "bootstrap-argocd": bootstrap_argocd()
        elif args.operation == "migrate": migrate()
        elif args.operation == "forward": forward(args)
        elif args.operation == "status": status()
        elif args.operation == "delete": delete()
        return 0
    except Exception as e:
        print(f"Error during operation '{args.operation}': {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

