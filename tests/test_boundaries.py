"""Files and provider-boundary regressions, no live services."""
import tempfile
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import scratch


class ScratchTests(unittest.TestCase):
    def make_symlink(self, link, target, **kwargs):
        try:
            link.symlink_to(target, **kwargs)
        except OSError as exc:
            if getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows account lacks symbolic-link privilege')
            raise

    def test_shared_paths_symlinks_and_retained_audio_are_not_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'owned'
            root.mkdir()
            other = Path(d) / 'other'; other.write_text('keep')
            old = root / 'expired'; old.write_text('delete')
            retained = root / 'retained'; retained.write_text('keep')
            link = root / 'link'; self.make_symlink(link, other)
            for file in (old, retained, other): os.utime(file, (1, 1))
            with patch.object(scratch, 'TEMP_ROOT', root):
                self.assertEqual(scratch.cleanup(root, protected=[retained]), 1)
                self.assertTrue(retained.exists())
                self.assertTrue(other.exists())
                self.assertTrue(link.is_symlink())
                for forbidden in (Path(d), Path('/tmp'), Path('/workspace/SwiDJ/downloads')):
                    with self.assertRaises(ValueError): scratch.cleanup(forbidden)
                scratch.remove_owned_file(other)
                self.assertTrue(other.exists())

    def test_symlink_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'link'; self.make_symlink(root, Path(d), target_is_directory=True)
            with patch.object(scratch, 'TEMP_ROOT', root), self.assertRaises(ValueError):
                scratch.scratch_root()
