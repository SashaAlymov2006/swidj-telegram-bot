import asyncio
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from telegram.error import BadRequest
from download_cache import DownloadCache, source_key
from audio_presentation import send_cached_music, send_music

URL='https://www.youtube.com/watch?v=liRLUgaUwh4'


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.cache=DownloadCache(self.root/'cache',limit=12)
        self.source=self.root/'source.mp3';self.source.write_bytes(b'12345678')
        self.out=self.root/'out';self.out.mkdir()
    def tearDown(self):self.tmp.cleanup()
    def test_restart_exact_recording_user_and_quality_isolation(self):
        self.cache.retain(12,URL,'audio',self.source,{'title':'Track','url':'secret','http_headers':{'x':'secret'}})
        fresh=DownloadCache(self.root/'cache',limit=12)
        result=fresh.restore(12,'https://youtu.be/liRLUgaUwh4?si=tracking','audio',self.out)
        self.assertEqual(Path(result[0]).read_bytes(),self.source.read_bytes())
        self.assertEqual(result[1],{'title':'Track'})
        self.assertIsNone(fresh.restore(13,URL,'audio',self.out))
        self.assertIsNone(fresh.restore(12,URL,'video-720',self.out))
    def test_eviction_preserves_telegram_index(self):
        self.cache.retain(12,URL,'audio',self.source,{})
        self.cache.telegram_set(9,12,URL,'telegram-file')
        other=URL.replace('liRLUgaUwh4','7DVM7DYJX1c')
        self.cache.retain(12,other,'audio',self.source,{})
        self.assertIsNone(self.cache.restore(12,URL,'audio',self.out))
        self.assertEqual(self.cache.telegram_get(9,12,URL),'telegram-file')
        self.assertIsNone(self.cache.telegram_get(10,12,URL))
        self.assertIsNone(self.cache.telegram_get(9,13,URL))
        self.assertLessEqual(sum(p.stat().st_size for p in (self.root/'cache').glob('*.mp3')),12)
    def test_expired_and_missing_files_are_misses(self):
        self.cache.retain(12,URL,'audio',self.source,{})
        with self.cache.db() as db:db.execute('UPDATE media SET touched=0')
        self.assertIsNone(self.cache.restore(12,URL,'audio',self.out))
    def test_non_url_search_and_local_paths_not_cached(self):
        for url in ('ytsearch1:track','file:///etc/passwd','https://example.com/private','https://user:pass@youtube.com/watch?v=liRLUgaUwh4'):
            self.assertIsNone(source_key(url))
    def test_reuse_does_not_open_media_or_prepare_tags(self):
        self.cache.telegram_set(9,12,URL,'telegram-file')
        bot=SimpleNamespace(id=9,send_audio=AsyncMock(return_value=SimpleNamespace(audio=None)))
        with patch.dict(os.environ,DOWNLOAD_CACHE_DIR=str(self.cache.root)),patch('audio_presentation.prepare_music',side_effect=AssertionError('No local file needed')):
            result=asyncio.run(send_music(bot,12,self.root/'missing.mp3','Track','Artist',source_url=URL))
        self.assertIsNotNone(result)
        self.assertEqual(bot.send_audio.await_args.kwargs['audio'],'telegram-file')
    def test_invalid_telegram_id_removed(self):
        self.cache.telegram_set(9,12,URL,'stale')
        bot=SimpleNamespace(id=9,send_audio=AsyncMock(side_effect=BadRequest('Wrong file identifier')))
        with patch.dict(os.environ,DOWNLOAD_CACHE_DIR=str(self.cache.root)):
            self.assertIsNone(asyncio.run(send_cached_music(bot,12,URL)))
        self.assertIsNone(self.cache.telegram_get(9,12,URL))
    def test_successful_upload_records_id_and_failure_does_not(self):
        bot=SimpleNamespace(id=9,send_audio=AsyncMock(return_value=SimpleNamespace(audio=SimpleNamespace(file_id='new-file'))))
        with patch.dict(os.environ,DOWNLOAD_CACHE_DIR=str(self.cache.root)),patch('audio_presentation.prepare_music',return_value=('Track','Artist','track.mp3',None,3)):
            asyncio.run(send_music(bot,12,self.source,source_url=URL))
        self.assertEqual(self.cache.telegram_get(9,12,URL),'new-file')


if __name__=='__main__':unittest.main()
