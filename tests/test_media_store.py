import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from media_store import MediaStore
from state_store import StateStore


class MediaStoreTests(unittest.TestCase):
    def setUp(self):
        self.files = tempfile.TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        self.root = Path(self.files.name)
        self.scratch = self.root / 'ephemeral'
        self.scratch.mkdir()
        self.source = self.scratch / 'source.mp3'
        self.source.write_bytes(b'owned-test-audio' * 100)
        self.store = MediaStore(self.root / 'persistent' / 'audio')

    def test_new_process_restores_audio_after_ephemeral_storage_removed(self):
        retained = self.store.retain(77, self.source)
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        state = self.root / 'persistent' / 'state.sqlite3'
        StateStore(state).save_named('sessions', 77, {'last_audio_path': retained})
        shutil.rmtree(self.scratch)
        code = '''import hashlib,sys
from pathlib import Path
from state_store import StateStore
session=StateStore(sys.argv[1]).load_named('sessions')[77]
assert hashlib.sha256(Path(session['last_audio_path']).read_bytes()).hexdigest()==sys.argv[2]
'''
        completed = subprocess.run([sys.executable, '-c', code, str(state), digest],
                                   capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        if os.name != 'nt':
            self.assertEqual(Path(retained).stat().st_mode & 0o777, 0o600)

    def test_uncommitted_replacement_preserves_previous_and_pruning_is_user_isolated(self):
        old = self.store.retain(77, self.source)
        other = self.store.retain(88, self.source)
        state = StateStore(self.root / 'persistent' / 'state.sqlite3')
        state.save_named('sessions', 77, {'last_audio_path': old})
        new = self.store.retain(77, self.source)
        self.assertTrue(Path(old).exists())
        self.assertEqual(state.load_named('sessions')[77]['last_audio_path'], old)
        state.save_named('sessions', 77, {'last_audio_path': new})
        self.assertEqual(self.store.prune(77, new), 1)
        self.assertFalse(Path(old).exists())
        self.assertTrue(Path(new).exists())
        self.assertTrue(Path(other).exists())
        self.assertEqual(self.store.prune(77, other), 0)
        self.assertTrue(Path(new).exists())

    def test_failed_copy_leaves_previous_source_and_no_partial_files(self):
        retained = self.store.retain(77, self.source)
        with patch('media_store.shutil.copyfileobj', side_effect=OSError('disk-full fixture')):
            with self.assertRaises(OSError): self.store.retain(77, self.source)
        self.assertTrue(Path(retained).exists())
        self.assertTrue(self.source.exists())
        self.assertEqual(len(list(self.store.user_directory(77).iterdir())), 1)

    def test_rejects_untrusted_ids_and_empty_sources(self):
        for uid in (True, -1, 0, '77', '../77'):
            with self.assertRaises(ValueError): self.store.retain(uid, self.source)
        self.source.write_bytes(b'')
        with self.assertRaises(ValueError): self.store.retain(77, self.source)

    def test_rejects_symlink_user_directory(self):
        self.store.root.mkdir(parents=True)
        try:
            (self.store.root / '77').symlink_to(self.scratch, target_is_directory=True)
        except OSError as exc:
            if getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows account lacks symbolic-link privilege')
            raise
        with self.assertRaises(ValueError): self.store.retain(77, self.source)
        (self.store.root / '77').unlink()
