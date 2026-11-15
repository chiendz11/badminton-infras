"""Badminton Local Operator CLI.

Explicit operations for cluster lifecycle, builds, imports, migrations, Argo CD, and Image Updater PAT injection.
"""

import argparse
import getpass
import hashlib
import json
import os
import re
import sys
import urllib.request
import uuid
from pathlib import Path

import yaml

from .checks import verify_application_source
from .common import (
    CONTEXT, CONTRACT, LOCAL, NAMESPACE, ROOT, apply, checkout,
    digest, kube, private_write, read, repository_url, run, settings,
    source_identity, validate_context, write_json,
)
from .credentials import initialize, install_secrets, seed_image_updater_secret, seed_localstack_secrets


def pins():
    return read(ROOT / "local/versions/platform.lock.json")


def up():
    initialize()
    version = run(["k3d", "version"], capture=True)
    if not re.search(r"k3d version v" + re.escape(pins()["k3d_version"]) + r"(?:\s|$)", version):
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
        "--kubeconfig-update-default=false", "--kubeconfig-switch-context=false",
    ])
    kubeconfig_content = run(["k3d", "kubeconfig", "get", CONTRACT["cluster_name"]], capture=True)
    private_write(LOCAL / "kubeconfig", kubeconfig_content)
    write_json(LOCAL / "cluster-owner.json", {
        "schema_version": "1.0.0",
        "context": CONTEXT,
        "cluster_name": CONTRACT["cluster_name"],
        "config_sha256": digest(LOCAL / "k3d.yaml"),
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
        *extra, str(source / context),
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
        "build_context": context,
    }
    (LOCAL / "receipts").mkdir(parents=True, exist_ok=True)
    write_json(LOCAL / "receipts" / f"{component}.json", receipt)
    print(f"Image receipt generated: {alias}")
    return receipt


def build(args):
    source = checkout("app_checkout")
    verify_application_source(source, read(ROOT / "local/versions/app-source.lock.json"))
    catalog = read(ROOT / "local/config/runtime-catalog.json")["components"]
    names = args.component or [name for name, val in catalog.items() if val.get("source_status") == "implemented"]

    for name in names:
        val = catalog[name]
        image_receipt(name, source, val["dockerfile"], val["context"], [], args.allow_dirty)

        if name == "booking-core" and val.get("migration") and val["migration"].get("target"):
            mig_extra = ["--target", val["migration"]["target"]]
            image_receipt("booking-core-migrations", source, val["dockerfile"], val["context"], mig_extra, args.allow_dirty)
        if name == "identity-service" and val.get("migration") and val["migration"].get("target"):
            mig_extra = ["--target", val["migration"]["target"]]
            image_receipt("identity-service-migrations", source, val["dockerfile"], val["context"], mig_extra, args.allow_dirty)


def import_images(args):
    validate_context()
    catalog = read(ROOT / "local/config/runtime-catalog.json")["components"]
    names = args.component or [name for name, val in catalog.items() if val.get("source_status") == "implemented"]
    if not args.component:
        if "booking-core" in names and (LOCAL / "receipts" / "booking-core-migrations.json").is_file():
            names.append("booking-core-migrations")
        if "identity-service" in names and (LOCAL / "receipts" / "identity-service-migrations.json").is_file():
            names.append("identity-service-migrations")

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


def prepare(args):
    """Verify local image receipts against app-source lock without mutating GitOps directly."""
    receipts = {p.stem: read(p) for p in (LOCAL / "receipts").glob("*.json")}
    for value in receipts.values():
        if value.get("imported_context") != CONTEXT:
            raise ValueError("Import all selected image receipts into this cluster first")
    verify_application_source(checkout("app_checkout"), read(ROOT / "local/versions/app-source.lock.json"))
    bundle = LOCAL / "release-receipts.json"
    write_json(bundle, receipts)
    print(
        "Verified local image receipts and source policy; Pure Declarative manifests in badminton-gitops "
        "are updated via environments/local/apps/kustomization.yaml / Argo CD Image Updater PRs."
    )


def _load_pinned_manifest(upstream):
    """Fetch, verify SHA-256, and pin images for an upstream component manifest."""
    if not upstream.get("image_pins_complete"):
        raise ValueError("Installer still has unresolved upstream image identities")
    with urllib.request.urlopen(upstream["url"], timeout=30) as response:
        raw = response.read(5_000_001)
    if hashlib.sha256(raw).hexdigest() != upstream["sha256"]:
        raise ValueError("Installer bytes differ from the reviewed pinned version")
    documents = [doc for doc in yaml.safe_load_all(raw) if isinstance(doc, dict)]

    def replace_images(value):
        if isinstance(value, dict):
            image = value.get("image")
            if isinstance(image, str):
                for orig, pinned in upstream["images"].items():
                    if image == orig or image.startswith(orig.split(":")[0]):
                        value["image"] = pinned
            for item in value.values():
                replace_images(item)
        elif isinstance(value, list):
            for item in value:
                replace_images(item)

    replace_images(documents)
    return documents


def install_image_updater_pat(args):
    """Store Image Updater PAT privately (0600) and seed LocalStack Secrets Manager via stdin."""
    validate_context()
    username = args.username.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", username):
        raise ValueError("Invalid GitHub username")
    if args.token_file:
        path = Path(args.token_file)
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError("PAT file must be a private regular file (chmod 600)")
        token = path.read_text(encoding="utf-8").strip()
    elif args.stdin:
        token = sys.stdin.read(4097).strip()
    else:
        token = getpass.getpass("GitHub Fine-grained PAT: ").strip()
    if not token or len(token) > 4096 or any(ch.isspace() for ch in token):
        raise ValueError("GitHub Fine-grained PAT is empty or invalid")
    for filename, value in (("image-updater-username", username), ("image-updater-pat", token)):
        target = LOCAL / "secrets" / filename
        private_write(target, value + "\n")
        os.chmod(target, 0o600)
    seed_image_updater_secret(username, token)
    print(
        "ExternalSecret argocd/argocd-image-updater-git-creds will sync from LocalStack "
        "badminton/prod/argocd-image-updater-git-creds."
    )


def bootstrap_argocd():
    validate_context()
    config = settings()
    remote = repository_url(config["gitops_repository"])
    revision = config["gitops_revision"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,100}", revision) or ".." in revision:
        raise ValueError("Invalid explicit Git revision")
    gitops = checkout("gitops_checkout")
    head = run(["git", "-C", str(gitops), "rev-parse", "HEAD"], capture=True).strip()
    if run(["git", "-C", str(gitops), "status", "--porcelain"], capture=True).strip():
        raise ValueError("GitOps changes must be committed and pushed before bootstrap")
    advertised = run(["git", "ls-remote", remote, "refs/heads/" + revision], capture=True).split()
    if not advertised or advertised[0] != head:
        raise ValueError("Remote branch does not contain the reviewed local HEAD")
    required = (
        "applications/local/kustomization.yaml",
        "applications/local/image-updater.yaml",
        "applications/local/image-updater-git-creds.yaml",
        "environments/local/platform/kustomization.yaml",
        "environments/local/apps/kustomization.yaml",
    )
    for rel in required:
        if not (gitops / rel).is_file():
            raise ValueError("GitOps checkout missing Pure Declarative local Kustomize root: " + rel)

    install_secrets()
    all_pins = pins()
    documents = _load_pinned_manifest(all_pins["argocd"])
    for doc in documents:
        if doc.get("kind") == "ConfigMap" and doc.get("metadata", {}).get("name") == "argocd-cm":
            doc.setdefault("data", {})["resource.customizations.health.networking.k8s.io_Ingress"] = (
                'hs = {}\nhs.status = "Healthy"\nreturn hs\n'
            )

    apply([{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "argocd"}}])
    kube("apply", "--server-side", "--field-manager=badminton-bootstrap", "-f", "-", namespace="argocd", stdin=yaml.safe_dump_all(documents))

    print("Waiting for Argo CD repo-server and application-controller...")
    kube("rollout", "status", "deployment/argocd-repo-server", "--timeout=300s", namespace="argocd")
    kube("rollout", "status", "statefulset/argocd-application-controller", "--timeout=300s", namespace="argocd")

    updater_docs = _load_pinned_manifest(all_pins["argocd_image_updater"])
    for doc in updater_docs:
        if doc.get("kind") == "ConfigMap" and doc.get("metadata", {}).get("name") == "argocd-image-updater-config":
            doc.setdefault("data", {}).update({
                "git.user": "argocd-image-updater[bot]",
                "git.email": "argocd-image-updater[bot]@users.noreply.github.com",
                "interval": "2m",
                "log.level": "info",
            })
    kube("apply", "--server-side", "--field-manager=badminton-bootstrap", "-f", "-", namespace="argocd", stdin=yaml.safe_dump_all(updater_docs))
    kube("rollout", "status", "deployment/argocd-image-updater-controller", "--timeout=300s", namespace="argocd")

    for manifest in ("localstack.yaml", "cluster-secret-store.yaml"):
        manifest_path = ROOT / "local/manifests" / manifest
        if manifest_path.exists():
            kube("apply", "-f", str(manifest_path))
    kube("rollout", "status", "deployment/localstack", "--timeout=120s", namespace="localstack")
    seed_localstack_secrets()

    local_apps = gitops / "applications/local"
    kube("apply", "-k", str(local_apps), namespace="argocd")
    kube(
        "patch",
        "svc",
        "argocd-server",
        "-n",
        "argocd",
        "-p",
        '{"spec": {"type": "NodePort", "ports": [{"name": "http", "port": 80, "protocol": "TCP", "targetPort": 8080}, {"name": "https", "port": 443, "protocol": "TCP", "targetPort": 8080, "nodePort": 30443}]}}',
    )
    print("Argo CD + Argo CD Image Updater follow static local applications in badminton-gitops.")


def migrate():
    validate_context()
    print("Running database migrations for Badminton services...")

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
                        "envFrom": [{"secretRef": {"name": "booking-core-secrets"}}],
                    }],
                }
            },
        },
    }
    apply([b_job], namespace=NAMESPACE)
    print(f"Waiting for {b_job_name} to finish...")
    kube("wait", "--for=condition=complete", f"job/{b_job_name}", "--timeout=300s", namespace=NAMESPACE)
    print("Booking Core migrations and seed finished.")

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
                        "envFrom": [{"secretRef": {"name": "ai-service-secrets"}}],
                    }],
                }
            },
        },
    }
    apply([ai_job], namespace=NAMESPACE)
    print(f"Waiting for {ai_job_name} to finish...")
    kube("wait", "--for=condition=complete", f"job/{ai_job_name}", "--timeout=300s", namespace=NAMESPACE)
    print("AI Service migrations finished.")

    id_receipt_path = LOCAL / "receipts" / "identity-service-migrations.json"
    if id_receipt_path.is_file():
        id_receipt = read(id_receipt_path)
        id_job_name = f"identity-migrate-{uuid.uuid4().hex[:8]}"
        id_job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": id_job_name, "namespace": NAMESPACE, "labels": {"app": "identity-service"}},
            "spec": {
                "backoffLimit": 1,
                "activeDeadlineSeconds": 300,
                "ttlSecondsAfterFinished": 86400,
                "template": {
                    "metadata": {"labels": {"app": "identity-service"}},
                    "spec": {
                        "restartPolicy": "Never",
                        "automountServiceAccountToken": False,
                        "containers": [{
                            "name": "migrate",
                            "image": id_receipt["image"],
                            "imagePullPolicy": "Never",
                            "command": ["node", "node_modules/prisma/build/index.js", "migrate", "deploy"],
                            "envFrom": [{"secretRef": {"name": "identity-service-secrets"}}],
                        }],
                    },
                },
            },
        }
        apply([id_job], namespace=NAMESPACE)
        print(f"Waiting for {id_job_name} to finish...")
        kube("wait", "--for=condition=complete", f"job/{id_job_name}", "--timeout=300s", namespace=NAMESPACE)
        print("Identity Service migrations finished.")


def forward(args):
    validate_context()
    targets = {
        "argocd": ("service/argocd-server", "19443:443", "argocd"),
        "gateway": ("service/api-gateway", "18081:8081", NAMESPACE),
        "web": ("service/web", "18082:80", NAMESPACE),
        "admin": ("service/admin", "18083:80", NAMESPACE),
        "postgres": ("service/postgres", "15432:5432", NAMESPACE),
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
    build_cmd.add_argument("--allow-dirty", action="store_true", default=False)

    import_cmd = sub.add_parser("import-images")
    import_cmd.add_argument("--component", action="append")

    sub.add_parser("prepare")

    pat_cmd = sub.add_parser("image-updater-pat")
    pat_cmd.add_argument("--username", default="chiendz11")
    pat_cmd.add_argument("--token-file")
    pat_cmd.add_argument("--stdin", action="store_true")

    fwd_cmd = sub.add_parser("forward")
    fwd_cmd.add_argument("target", choices=["argocd", "gateway", "web", "admin", "postgres"])

    args = parser.parse_args(argv)
    try:
        if args.operation == "init":
            initialize()
        elif args.operation == "up":
            up()
        elif args.operation == "secrets":
            install_secrets()
        elif args.operation == "build":
            build(args)
        elif args.operation == "import-images":
            import_images(args)
        elif args.operation == "prepare":
            prepare(args)
        elif args.operation == "image-updater-pat":
            install_image_updater_pat(args)
        elif args.operation == "bootstrap-argocd":
            bootstrap_argocd()
        elif args.operation == "migrate":
            migrate()
        elif args.operation == "forward":
            forward(args)
        elif args.operation == "status":
            status()
        elif args.operation == "delete":
            delete()
        return 0
    except Exception as e:
        print(f"Error during operation '{args.operation}': {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
