"""The local operator verifies receipts and seeds Image Updater PAT into LocalStack via stdin."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from localdev import cli, credentials


class PolicyHandoff(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "receipts").mkdir()
        self.app = self.root / "app"

    def test_prepare_verifies_application_source_and_receipts(self):
        with (
            patch.object(cli, "LOCAL", self.root),
            patch.object(cli, "checkout", return_value=self.app),
            patch.object(cli, "verify_application_source") as verify,
        ):
            cli.prepare(SimpleNamespace())
            verify.assert_called_once()
            self.assertEqual(verify.call_args.args[0], self.app)
            self.assertTrue((self.root / "release-receipts.json").exists())

    def test_image_updater_pat_requires_private_file_and_writes_via_stdin(self):
        token_file = self.root / "pat.txt"
        token_file.write_text("github_pat_example_secret_12345\n", encoding="utf-8")
        os.chmod(token_file, 0o644)
        with patch.object(cli, "validate_context"):
            with self.assertRaisesRegex(ValueError, "chmod 600"):
                cli.install_image_updater_pat(
                    SimpleNamespace(username="chiendz11", token_file=str(token_file), stdin=False)
                )

        os.chmod(token_file, 0o600)
        with (
            patch.object(cli, "LOCAL", self.root),
            patch.object(credentials, "LOCAL", self.root),
            patch.object(cli, "validate_context"),
            patch.object(credentials, "kube") as mock_kube,
        ):
            cli.install_image_updater_pat(
                SimpleNamespace(username="chiendz11", token_file=str(token_file), stdin=False)
            )
            mock_kube.assert_called_once()
            self.assertEqual(mock_kube.call_args.kwargs["namespace"], "localstack")
            payload = json.loads(mock_kube.call_args.kwargs["stdin"])
            self.assertIn("badminton/prod/argocd-image-updater-git-creds", payload)
            entry = payload["badminton/prod/argocd-image-updater-git-creds"]
            self.assertEqual(entry["username"], "chiendz11")
            self.assertEqual(entry["password"], "github_pat_example_secret_12345")
            self.assertEqual((self.root / "secrets/image-updater-pat").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
