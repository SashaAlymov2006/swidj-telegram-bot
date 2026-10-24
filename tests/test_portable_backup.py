import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import backup_local
import restore_local


class PortableBackupTests(unittest.TestCase):
    def test_source_archive_excludes_secrets_and_normalizes_pycharm_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            destination = Path(directory) / "backups"
            root.mkdir()
            (root / "bot.py").write_text("print('hello')", encoding="utf-8")
            (root / ".env").write_text("TELEGRAM_TOKEN=123456:private-test-token-value\nOWNER_USER_IDS=77,78\n")
            (root / ".env.example").write_text("TELEGRAM_TOKEN=\n")
            (root / ".run").mkdir()
            (root / ".run/Run.xml").write_text('<option name="SDK_HOME" value="old-machine-python" />')
            with patch.object(backup_local, "ROOT", root):
                archive = backup_local.create_backup(destination, source_only=True)
            with zipfile.ZipFile(archive) as bundle:
                self.assertNotIn("project/.env", bundle.namelist())
                self.assertEqual(bundle.testzip(), None)
                self.assertNotIn(b"old-machine", bundle.read("project/.run/Run.xml"))
                manifest = json.loads(bundle.read("manifest.json"))
                self.assertEqual(manifest["owner_user_ids"], [77, 78])
                self.assertFalse(manifest["runtime_included"])
            self.assertTrue((destination / "SwiDJ-latest.zip").is_file())

    def test_secret_in_source_aborts_without_replacing_last_good_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project";root.mkdir()
            dest = Path(directory) / "backups";dest.mkdir()
            (dest / "SwiDJ-latest.zip").write_bytes(b"last-good")
            secret = "123456:private-test-token-value"
            (root / ".env").write_text("TELEGRAM_TOKEN=" + secret)
            (root / "bad.py").write_text("token = " + repr(secret))
            with patch.object(backup_local, "ROOT", root), self.assertRaises(RuntimeError):
                backup_local.create_backup(dest, source_only=True)
            self.assertEqual((dest / "SwiDJ-latest.zip").read_bytes(), b"last-good")

    def test_restore_rejects_modified_source_before_touching_docker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project";root.mkdir()
            (root / "bot.py").write_text("changed")
            (root.parent / "manifest.json").write_text(json.dumps({
                "project": "SwiDJ", "backup_version": 1, "files": {"project/bot.py": "bad-hash"}}))
            with patch.object(restore_local, "ROOT", root), patch.object(restore_local, "docker_cli") as docker:
                with self.assertRaises(RuntimeError):
                    restore_local.restore()
                docker.assert_not_called()

    def test_parallel_source_backups_keep_valid_latest_archive(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"; root.mkdir()
            dest = Path(directory) / "backups"
            (root / "bot.py").write_text("print('safe')")
            with patch.object(backup_local, "ROOT", root):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: backup_local.create_backup(dest, source_only=True), range(2)))
            self.assertEqual(len(set(results)), 2)
            with zipfile.ZipFile(dest / "SwiDJ-latest.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read("project/bot.py"), b"print('safe')")
