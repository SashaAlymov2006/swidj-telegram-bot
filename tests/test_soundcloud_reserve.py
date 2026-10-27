import asyncio
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch,MagicMock,AsyncMock
from download_cache import DownloadCache
from media_recovery import download_with_reserve
from operations import Operation,OperationCancelled,_current
from recording_match import matches
from soundcloud_source import matching_track,download,public_url

YT='https://www.youtube.com/watch?v=liRLUgaUwh4'
SC='https://soundcloud.com/artist/exact-song'
HINT={'title':'Artist - Exact Song (Official Audio)','artist':'Artist - Topic','duration':218}
SONG={'title':'Exact Song','artist':'Artist','duration':218,'url':SC,'source_url':SC,'source':'SoundCloud'}

class Reserves(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,DOWNLOAD_CACHE_DIR=str(self.root/'cache'),TELEGRAM_TOKEN='',JAMENDO_CLIENT_ID='');self.env.start();self.addCleanup(self.env.stop)
        self.marker=_current.set(Operation(77));self.addCleanup(_current.reset,self.marker)
        self.cache=DownloadCache(self.root/'cache');self.audio=self.root/'source.mp3';self.audio.write_bytes(b'complete fixture')
    def unavailable(self,_):raise RuntimeError('YouTube unavailable')

    def test_order_disk_then_telegram_then_primary_then_sc_then_jamendo(self):
        from scratch import remove_owned_file
        self.cache.retain(77,YT,'audio-mp3-192',self.audio,SONG)
        with patch('media_recovery.recover_audio') as telegram:
            result=download_with_reserve(lambda _:self.fail('Primary called'),YT,HINT)
            telegram.assert_not_called();remove_owned_file(result[0])
        with self.cache.db() as db:db.execute('DELETE FROM media')
        with patch('media_recovery.recover_audio',return_value=(str(self.audio),SONG)),patch('soundcloud_source.matching_track') as sc:
            self.assertEqual(download_with_reserve(lambda _:self.fail('Primary called'),YT,HINT)[0],str(self.audio));sc.assert_not_called()
        events=[]
        with patch('media_recovery.recover_audio',return_value=None),patch('soundcloud_source.matching_track',side_effect=lambda hint:events.append('sc') or None),patch('jamendo_source.matching_track',side_effect=lambda hint:events.append('jamendo') or None):
            def primary(_):events.append('primary');raise RuntimeError('Original')
            with self.assertRaisesRegex(RuntimeError,'Original'):download_with_reserve(primary,YT,HINT)
        self.assertEqual(events,['primary','sc','jamendo'])

    def test_sc_success_cached_for_another_user_without_repeating_provider(self):
        from scratch import remove_owned_file
        with patch('soundcloud_source.matching_track',return_value=SONG),patch('soundcloud_source.download',return_value=(str(self.audio),SONG)),patch('jamendo_source.matching_track') as jam:
            result=download_with_reserve(self.unavailable,YT,HINT)
            self.assertEqual(result[1]['source'],'SoundCloud');jam.assert_not_called()
        _current.get().uid=78
        with patch('media_recovery.recover_audio',side_effect=AssertionError('Must reuse VPS')):
            result=download_with_reserve(lambda _:self.fail('Primary called'),YT,HINT)
            self.assertEqual(Path(result[0]).read_bytes(),self.audio.read_bytes());remove_owned_file(result[0])
        self.cache.telegram_set(123,77,SC,'public-file',metadata=SONG,public=True)
        self.assertEqual(self.cache.telegram_get(123,78,YT),'public-file')
        with self.cache.db() as db:db.execute('DELETE FROM media')
        self.assertEqual(self.cache.telegram_info(123,78,YT)['file_id'],'public-file')
        self.assertIsNone(self.cache.telegram_get(124,78,YT))

    def test_private_or_unverified_media_never_promoted(self):
        for url,metadata in [(YT,{}),('https://soundcloud.com/artist/secret?secret_token=x',{'_public_source':True}),('https://example.com/file',{'_public_source':True})]:
            self.cache.retain(77,url,'audio-mp3-192',self.audio,metadata)
            self.cache.telegram_set(123,77,url,'private-file',metadata={'title':'Private'})
            self.assertIsNone(self.cache.restore_public(url,'audio-mp3-192',self.root))
            self.assertIsNone(self.cache.telegram_get(123,78,url))

    def test_personal_edit_cannot_replace_a_shared_source_or_telegram_copy(self):
        self.cache.retain(77,SC,'audio-mp3-192',self.audio,dict(SONG,_public_source=True))
        self.assertTrue(self.cache.public_file(SC,self.audio))
        edited=self.root/'private.mp3';edited.write_bytes(b'personal remix')
        self.assertFalse(self.cache.public_file(SC,edited))
        self.cache.telegram_set(123,77,SC,'personal-edit',metadata=SONG)
        self.assertIsNone(self.cache.telegram_get(123,78,SC))
        self.cache.retain(77,SC,'audio-mp3-192',edited,SONG)
        self.assertIsNone(self.cache.restore_public(SC,'audio-mp3-192',self.root))

    def test_modified_shared_disk_file_is_not_served(self):
        self.cache.retain(77,SC,'audio-mp3-192',self.audio,dict(SONG,_public_source=True))
        next(self.cache.root.glob('*.mp3')).write_bytes(b'modified fixture')
        self.assertIsNone(self.cache.restore_public(SC,'audio-mp3-192',self.root))

    def test_sending_personal_edit_neither_reuses_nor_overwrites_public_telegram_id(self):
        from audio_presentation import send_music
        self.cache.retain(77,SC,'audio-mp3-192',self.audio,dict(SONG,_public_source=True))
        self.cache.telegram_set(123,77,SC,'original-public',metadata=SONG,public=True)
        edited=self.root/'private.mp3';edited.write_bytes(b'personal edit')
        bot=NS(id=123,send_audio=AsyncMock(return_value=NS(audio=NS(file_id='private-edit'))))
        with patch('audio_presentation.prepare_music',return_value=('My edit','Artist','edit.mp3',None,218)):
            asyncio.run(send_music(bot,77,edited,source_url=SC))
        self.assertNotIsInstance(bot.send_audio.await_args.kwargs['audio'],str)
        self.assertEqual(self.cache.telegram_get(123,78,SC),'original-public')

    def test_shared_jamendo_copy_keeps_attribution_when_telegram_id_is_reused(self):
        from audio_presentation import send_cached_music
        url='https://www.jamendo.com/track/123'
        license='https://creativecommons.org/licenses/by/4.0/'
        meta=dict(SONG,source='Jamendo',source_url=url,license_url=license,_public_source=True)
        self.cache.retain(77,url,'audio-mp3-192',self.audio,meta)
        self.cache.telegram_set(123,77,url,'licensed-public',metadata=meta,public=True)
        bot=NS(id=123,send_audio=AsyncMock(return_value=NS(audio=None)))
        asyncio.run(send_cached_music(bot,78,url))
        self.assertIn(license,bot.send_audio.await_args.kwargs['caption'])
        self.assertIn(url,bot.send_audio.await_args.kwargs['caption'])

    def test_primary_success_and_limits_and_cancel_do_not_search_reserve(self):
        with patch('soundcloud_source.matching_track') as sc:
            self.assertEqual(download_with_reserve(lambda _:(str(self.audio),{}),YT,HINT)[0],str(self.audio))
            for error in (ValueError('Too large'),OSError('Disk full'),OperationCancelled()):
                def primary(_,error=error):raise error
                with self.assertRaises(type(error)):download_with_reserve(primary,YT,HINT)
            sc.assert_not_called()

    def test_sc_failure_continues_to_jamendo_and_original_failure_kept(self):
        with patch('soundcloud_source.matching_track',side_effect=RuntimeError('SC down')),patch('jamendo_source.matching_track',return_value=None) as jam:
            with self.assertRaisesRegex(RuntimeError,'YouTube unavailable'):download_with_reserve(self.unavailable,YT,HINT)
            jam.assert_called_once()

    def test_recording_match_rejects_wrong_artist_remix_clip_and_ambiguous_results(self):
        self.assertTrue(matches(HINT,SONG))
        for changed in ({'artist':'Other'},{'title':'Exact Song Remix'},{'title':'Exact Song (Live)'},{'duration':30},{'duration':None}):self.assertFalse(matches(HINT,dict(SONG,**changed)))
        self.assertFalse(matches(dict(HINT,title='Exact Song (Official Slowed Audio)'),SONG))
        with patch('soundcloud_source.search',return_value=[SONG]):self.assertEqual(matching_track(HINT),SONG)
        with patch('soundcloud_source.search',return_value=[SONG,dict(SONG)]):self.assertIsNone(matching_track(HINT))
        for bad in ('https://soundcloud.com/a/b?secret_token=x','https://soundcloud.com.evil.test/a/b','https://user:pass@soundcloud.com/a/b','http://soundcloud.com/a/b'):self.assertFalse(public_url(bad))

    def test_real_download_checks_identity_and_measured_full_duration(self):
        def extract(url,download):
            (self.root/'soundcloud.mp3').write_bytes(b'encoded fixture')
            return dict(SONG,webpage_url=SC)
        with patch('soundcloud_source.yt_dlp.YoutubeDL') as ydl,patch('soundcloud_source.run_process',return_value=NS(stdout=json.dumps({'format':{'duration':218}}))):
            ydl.return_value.__enter__.return_value.extract_info.side_effect=extract
            path,info=download(SONG,self.root)
            self.assertTrue(info['_public_source']);self.assertEqual(info['source'],'SoundCloud')
            opts=ydl.call_args.args[0];self.assertIsNone(opts['cookiefile']);self.assertEqual(opts['allowed_extractors'],['soundcloud.*'])
        with patch('soundcloud_source.yt_dlp.YoutubeDL') as ydl,patch('soundcloud_source.run_process',return_value=NS(stdout=json.dumps({'format':{'duration':30}}))):
            ydl.return_value.__enter__.return_value.extract_info.side_effect=extract
            with self.assertRaisesRegex(ValueError,'Incomplete'):download(SONG,self.root)

    def test_search_outage_uses_sc_before_jamendo(self):
        from versions import find_versions
        with patch('versions.yt_dlp.YoutubeDL') as ydl,patch('soundcloud_source.search',return_value=[SONG]),patch('jamendo_source.search') as jam:
            ydl.return_value.__enter__.return_value.extract_info.side_effect=RuntimeError('YouTube down')
            self.assertEqual(find_versions('Artist Exact Song'),[SONG]);jam.assert_not_called()

    def test_cached_public_sc_search_survives_restarted_search_outage(self):
        from versions import find_versions
        with patch('versions.yt_dlp.YoutubeDL') as ydl,patch('soundcloud_source.search',return_value=[SONG]) as sc:
            ydl.return_value.__enter__.return_value.extract_info.side_effect=RuntimeError('Offline')
            self.assertEqual(find_versions('Artist Exact Song'),[SONG])
            sc.reset_mock();self.assertEqual(find_versions('Artist Exact Song'),[SONG]);sc.assert_not_called()

import test_miniapp as fixtures

class AppReserves(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.MiniApiTests.asyncSetUp

    async def test_sc_search_candidate_prepares_directly_without_youtube_resolution(self):
        source=Path(self.tmp.name)/'sc.mp3';source.write_bytes(b'complete fixture')
        self.favorites[77][0].update(url=SC,duration=218)
        self.bridge.audio_jobs.downloader=lambda _:(str(source),SONG)
        with patch('versions.find_versions',side_effect=AssertionError('SC must not route to YouTube')),patch('media_recovery.recover_audio',return_value=None):
            response=await self.client.post('/api/prepare',headers=self.headers,json={'track':'1'})
            self.assertEqual(response.status,200)
            job=self.bridge.audio_jobs.get(77,(await response.json())['job']);await job.task
        self.assertEqual(job.state,'ready');self.assertEqual(job.song['url'],SC)
        self.bridge.application.bot.send_message.assert_not_awaited()

    async def test_direct_app_audio_login_error_uses_reserve_but_video_does_not(self):
        source=Path(self.tmp.name)/'reserved.mp3';source.write_bytes(b'complete fixture')
        with patch.dict(os.environ,MINIAPP_URL='https://preview.example.test'),patch('media_recovery.recover_audio',return_value=None),patch('app_media.process',new=AsyncMock(return_value=b'{"error":"sourceLogin"}')),patch('media_recovery.download_with_reserve',return_value=(str(source),SONG)) as reserve:
            response=await self.client.post('/api/link',headers=self.headers,json={'url':YT,'mode':'audio'})
            self.assertEqual(response.status,200,await response.text());self.assertEqual((await response.json())['source'],'SoundCloud')
            self.assertEqual(reserve.call_args.args[-1],77)
            reserve.reset_mock()
            response=await self.client.post('/api/link',headers=self.headers,json={'url':YT,'mode':'video'})
            self.assertEqual(response.status,502);reserve.assert_not_called()

    async def test_cancelled_link_recovery_finishes_worker_before_releasing_slot(self):
        import threading,time
        from operations import checkpoint
        from app_media import audio_worker
        started=threading.Event();finished=threading.Event()
        def worker():
            try:
                started.set()
                while True:checkpoint();time.sleep(.01)
            finally:finished.set()
        task=asyncio.create_task(audio_worker(77,worker))
        while not started.is_set():await asyncio.sleep(.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertTrue(finished.is_set())

    async def test_failed_direct_youtube_audio_offers_fresh_search_after_exact_reserve(self):
        result=json.dumps({'error':'sourceLogin','recovery_query':'perfect ed sheeran'}).encode()
        with patch.dict(os.environ,MINIAPP_URL='https://preview.example.test'),patch('media_recovery.recover_audio',return_value=None),patch('app_media.process',new=AsyncMock(return_value=result)),patch('media_recovery.download_with_reserve',return_value=None) as reserve:
            response=await self.client.post('/api/link',headers=self.headers,json={'url':YT,'mode':'audio'})
            self.assertEqual(response.status,200)
            self.assertEqual(await response.json(),{'kind':'search','query':'perfect ed sheeran','source_search':'sc'})
            reserve.assert_called_once()
            reserve.reset_mock()
            response=await self.client.post('/api/link',headers=self.headers,json={'url':YT,'mode':'video'})
            self.assertEqual(response.status,502);reserve.assert_not_called()
