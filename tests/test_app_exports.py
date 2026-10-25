from pathlib import Path
import os
import tempfile
import time
import unittest
from app_exports import ExportFiles

class ExportRetentionTests(unittest.TestCase):
    def test_budget_and_expiry_remove_only_managed_temporary_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'input.mp3';source.write_bytes(b'x'*30)
            cache=ExportFiles(root/'exports',budget=40)
            a,first=cache.retain(77,source,'A')
            protected=first['path'].parent/'keep-user-file.txt';protected.write_text('Keep')
            b,second=cache.retain(78,source,'B')
            self.assertIsNone(cache.get(a));self.assertIsNotNone(cache.get(b))
            self.assertTrue(protected.exists())
            second['expires']=time.time()-1
            os.utime(second['path'],(time.time()-4000,time.time()-4000))
            self.assertIsNone(cache.get(b));self.assertFalse(second['path'].exists())
            self.assertTrue(protected.exists())

    def test_link_export_can_exceed_cache_target_and_remains_downloadable(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'large.mp4';source.write_bytes(b'x'*80)
            cache=ExportFiles(root/'exports',budget=40)
            token,item=cache.retain(77,source,'Clip',feature='downloads')
            self.assertIsNotNone(cache.get(token))
            self.assertEqual(item['path'].stat().st_size,80)

    def test_filenames_are_safe_and_tokens_are_not_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'input.mp3';source.write_bytes(b'x')
            cache=ExportFiles(root/'exports')
            token,item=cache.retain(77,source,'../unsafe/name')
            self.assertEqual(len(token),32)
            self.assertNotIn('/',item['filename'])
            self.assertEqual(item['path'].parent,root/'exports'/'77')

    def test_hundred_megabyte_file_and_long_playback_ttl_are_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'large.mp4'
            with source.open('wb') as stream:stream.truncate(100*1024**2)
            cache=ExportFiles(root/'exports')
            token,item=cache.retain(77,source,'Large video',feature='downloads',ttl=7800)
            self.assertEqual(item['path'].stat().st_size,100*1024**2)
            os.utime(item['path'],(time.time()-4000,time.time()-4000))
            self.assertIsNotNone(cache.get(token))
