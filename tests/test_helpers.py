import os
import re
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import scratch
from test_handlers import load_handler


class HelperTests(unittest.TestCase):
    def test_titles_and_filenames(self):
        clean = load_handler('clean_filename', {'re': re})
        self.assertEqual(clean(' A / B:*?  '), 'A B')
        title = load_handler('clean_title', {'re': re})
        self.assertEqual(title('Track (Official Video)'), 'Track')
        self.assertIsNone(title(None))

    def test_ffmpeg_available(self):
        load_handler('check_ffmpeg', {'subprocess': subprocess})()

    def test_cleanup_preserves_recent_files_and_nested_jobs(self):
        cleanup = load_handler('safe_cleanup', {'os': os, 'time': time})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / 'old';old.write_text('old')
            recent = root / 'recent';recent.write_text('recent')
            nested = root / 'job';nested.mkdir();(nested / 'active').write_text('active')
            os.utime(old, (time.time()-1200,)*2)
            with patch.object(scratch, "TEMP_ROOT", root):
                cleanup(directory)
            self.assertFalse(old.exists())
            self.assertTrue(recent.exists())
            self.assertTrue((nested / 'active').exists())
