"""Offline CI tests for private local state and operator safety."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from localdev import common, credentials


class LocalOperatorSafety(unittest.TestCase):
    def test_fixed_kube_api_port_keeps_the_k3d_proxy_enabled(self):
        config = yaml.safe_load((common.ROOT / "local/config/k3d.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["kubeAPI"]["hostIP"], "127.0.0.1")
        self.assertFalse(config["options"]["k3d"]["disableLoadbalancer"])

    def test_initialization_preserves_existing_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            local = Path(folder) / ".local"
            with patch.object(credentials, "LOCAL", local):
                credentials.initialize()
                before = (local / "credentials.json").read_bytes()
                credentials.initialize()
                self.assertEqual((local / "credentials.json").read_bytes(), before)
                self.assertTrue((local / "credentials.json").is_file())
                self.assertEqual(local.stat().st_mode & 0o777, 0o700)

    def test_remote_context_is_rejected_before_any_kubectl_call(self):
        with tempfile.TemporaryDirectory() as folder:
            local = Path(folder)
            (local / "kubeconfig").write_text(
                json.dumps({"current-context": "prod-cluster"}),
                encoding="utf-8",
            )
            with patch.object(common, "LOCAL", local), patch.object(common, "run", return_value="prod-cluster"):
                with self.assertRaisesRegex(ValueError, "does not match cluster"):
                    common.kube("get", "pods")

    def test_dirty_source_has_a_distinct_snapshot_without_fabricating_a_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for command in (
                ["init", "-q"],
                ["config", "user.email", "fixture@badminton.invalid"],
                ["config", "user.name", "Local fixture"],
            ):
                subprocess.run(["git", "-C", str(root), *command], check=True)
            (root / "source.py").write_text("version = 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            first = common.source_identity(root)
            (root / "source.py").write_text("version = 2\n", encoding="utf-8")
            second = common.source_identity(root)
            self.assertEqual(first[0], second[0])
            self.assertFalse(first[1])
            self.assertTrue(second[1])
            self.assertNotEqual(first[2], second[2])

    def test_remote_url_cannot_contain_credentials_or_a_local_path(self):
        for value in (
            "file:///tmp/repository.git",
            "https://user:secret@example.invalid/repo.git",
            "ssh://example.invalid/repo.git",
        ):
            with self.assertRaises(ValueError):
                common.repository_url(value)


if __name__ == "__main__":
    unittest.main()
