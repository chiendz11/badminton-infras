"""Private state and argument-array subprocesses for Badminton local cluster."""

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "local/.local"
CONTRACT = json.loads((ROOT / "local/config/contract.json").read_text())
CONTEXT, NAMESPACE = CONTRACT["context"], CONTRACT["namespace"]


def read(path):
    return json.loads(Path(path).read_text())


def private_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_json(path, value):
    private_write(path, json.dumps(value, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, *, capture=False, stdin=None):
    result = subprocess.run(args, input=stdin, text=True, capture_output=capture, check=True)
    return result.stdout if capture else None


def settings():
    value = read(LOCAL / "settings.json")
    if value.get("schema_version") != "1.0.0":
        raise ValueError("Invalid explicit local settings schema")
    return value


def checkout(key):
    return (ROOT / settings()[key]).resolve(strict=True)


def validate_context():
    kubeconfig = LOCAL / "kubeconfig"
    if not kubeconfig.is_file():
        raise ValueError("Private kubeconfig not found; run 'up' first")
    os.environ["KUBECONFIG"] = str(kubeconfig)
    actual = run(["kubectl", "config", "current-context"], capture=True).strip()
    if actual != CONTEXT:
        raise ValueError(f"Current context '{actual}' does not match cluster '{CONTEXT}'")


def kube(*args, namespace=None, stdin=None, capture=False):
    validate_context()
    command = ["kubectl", "--context=" + CONTEXT]
    if namespace:
        command += ["--namespace=" + namespace]
    command += list(args)
    return run(command, capture=capture, stdin=stdin)


def apply(documents, namespace=None):
    kube("apply", "-f", "-", namespace=namespace, stdin=yaml.safe_dump_all(documents))


def source_identity(checkout_path):
    checkout_path = Path(checkout_path).resolve()
    sha = run(["git", "-C", str(checkout_path), "rev-parse", "HEAD"], capture=True).strip()
    status = run(["git", "-C", str(checkout_path), "status", "--porcelain"], capture=True).strip()
    dirty = bool(status)
    snapshot = hashlib.sha256((sha + ("-dirty-" + hashlib.sha256(status.encode()).hexdigest() if dirty else "")).encode()).hexdigest()
    return sha, dirty, snapshot


def repository_url(remote):
    parsed = urlsplit(remote or "")
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or not parsed.path.endswith(".git"):
        raise ValueError("GitOps repository must be an explicit HTTPS .git URL")
    return remote

