from pathlib import Path
import tempfile
import unittest
from youtube_session import cookie_snapshot


class CookieSnapshotTests(unittest.TestCase):
    def test_writes_to_download_cookie_jar_do_not_change_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.txt';source.write_text('private fixture')
            with cookie_snapshot(source) as name:
                copied=Path(name)
                self.assertEqual(copied.read_text(),'private fixture')
                copied.write_text('updated downloader jar')
                self.assertEqual(source.read_text(),'private fixture')
            self.assertFalse(copied.exists())

    def test_exception_cleans_up_private_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.txt';source.write_text('fixture')
            with self.assertRaises(RuntimeError):
                with cookie_snapshot(source) as name:
                    copied=Path(name)
                    raise RuntimeError('fixture')
            self.assertFalse(copied.exists())

    def test_absent_configuration_does_not_require_cookie_file(self):
        with cookie_snapshot(None) as name:self.assertIsNone(name)

    def test_concurrent_request_snapshots_are_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.txt';source.write_text('fixture')
            with cookie_snapshot(source) as first,cookie_snapshot(source) as second:
                self.assertNotEqual(first,second)
                Path(first).write_text('updated')
                self.assertEqual(Path(second).read_text(),'fixture')
