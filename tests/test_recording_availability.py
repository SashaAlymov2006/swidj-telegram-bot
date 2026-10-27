import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
import recording_availability as availability
from operations import OperationCancelled


SC={'url':'https://soundcloud.com/artist/song','title':'Song','artist':'Artist','duration':210}


class AvailabilityTests(unittest.TestCase):
    def setUp(self):availability._cache.clear()

    def response(self,body=b'ID3audio',status=206):
        response=MagicMock();response.__enter__.return_value=response
        response.status_code=status;response.iter_content.return_value=iter([body])
        return response

    def test_checks_real_audio_bytes_and_does_not_forward_credentials(self):
        with patch('recording_availability.requests.get',return_value=self.response()) as request:
            self.assertTrue(availability._sample('https://cf-media.sndcdn.com/audio.mp3','soundcloud',{'Cookie':'secret','Authorization':'secret','User-Agent':'Public UA'}))
        headers=request.call_args.kwargs['headers']
        self.assertNotIn('Cookie',headers);self.assertNotIn('Authorization',headers)
        self.assertEqual(headers['Range'],'bytes=0-8191')
        self.assertFalse(request.call_args.kwargs['allow_redirects'])
        with patch('recording_availability.requests.get',return_value=self.response(b'<html>blocked</html>')):
            self.assertFalse(availability._sample('https://cf-media.sndcdn.com/audio.mp3','soundcloud'))
        with patch('recording_availability.requests.get',return_value=self.response(bytes.fromhex('1a45dfa3')+b'webm')):
            self.assertTrue(availability._sample('https://media.googlevideo.com/audio','youtube'))

    def test_rejects_private_unexpected_hosts_and_redirects(self):
        with patch('recording_availability.requests.get') as request:
            for url in ('https://127.0.0.1/audio','https://sndcdn.com.evil.test/audio','http://cf-media.sndcdn.com/audio','https://user:secret@cf-media.sndcdn.com/audio','https://cf-media.sndcdn.com:8080/audio'):
                self.assertFalse(availability._sample(url,'soundcloud'))
            request.assert_not_called()
        with patch('recording_availability.requests.get',return_value=self.response(status=302)):
            self.assertFalse(availability._sample('https://cf-media.sndcdn.com/audio','soundcloud'))

    def test_hls_checks_media_segment_and_rejects_keyed_or_external_playlist(self):
        responses=[self.response(b'#EXTM3U\n#EXTINF:10,\nsegment.mp3\n'),self.response()]
        with patch('recording_availability.requests.get',side_effect=responses) as request:
            self.assertTrue(availability._sample('https://cf-media.sndcdn.com/stream/list.m3u8','soundcloud'))
        self.assertEqual(request.call_args.args[0],'https://cf-media.sndcdn.com/stream/segment.mp3')
        with patch('recording_availability.requests.get',return_value=self.response(b'#EXTM3U\nhttps://127.0.0.1/private\n')) as request:
            self.assertFalse(availability._sample('https://cf-media.sndcdn.com/list.m3u8','soundcloud'))
            self.assertEqual(request.call_count,1)

    def test_soundcloud_rejects_drm_previews_and_missing_full_duration(self):
        manager=MagicMock();manager.__enter__.return_value=manager
        base=dict(duration=210,url='https://cf-media.sndcdn.com/song.mp3',format_id='http_mp3')
        with patch('yt_dlp.YoutubeDL',return_value=manager) as ydl,patch('recording_availability._sample',return_value=True) as sample:
            for change in ({'has_drm':True},{'duration':30},{'format_id':'preview'},{'availability':'premium_only'}):
                manager.extract_info.return_value=dict(base,**change)
                self.assertFalse(availability._remote(SC))
            sample.assert_not_called()
            manager.extract_info.return_value=base
            self.assertTrue(availability._remote(SC))
        self.assertIsNone(ydl.call_args.args[0]['cookiefile'])
        self.assertEqual(ydl.call_args.args[0]['allowed_extractors'],['soundcloud.*'])

    def test_verified_cache_skips_remote_and_corrupt_cache_can_retry_source(self):
        with patch('recording_availability._cached',return_value=True),patch('recording_availability._remote') as remote:
            self.assertTrue(availability.available(SC,77));remote.assert_not_called()
        availability._cache.clear()
        with patch('recording_availability._cached',side_effect=ValueError('bad cache')),patch('recording_availability._remote',return_value=True) as remote:
            self.assertTrue(availability.available(SC,77));self.assertTrue(availability.available(SC,77))
            self.assertEqual(remote.call_count,1)
        with patch('recording_availability._cached',return_value=False),patch('recording_availability._remote',return_value=False) as remote:
            self.assertFalse(availability.available(SC,78));self.assertEqual(remote.call_count,1)

    def test_cancel_is_not_cached_and_worker_slot_is_released(self):
        with patch('recording_availability._cached',return_value=False),patch('recording_availability._remote',side_effect=OperationCancelled()):
            with self.assertRaises(OperationCancelled):availability.available(SC,77)
        with patch('recording_availability._cached',return_value=False),patch('recording_availability._remote',return_value=True):
            self.assertTrue(availability.available(SC,77))

    def test_selection_omits_failed_candidates_and_backfills_three(self):
        rows=[dict(SC,url=SC['url']+str(index)) for index in range(6)]
        with patch('recording_availability.available',side_effect=lambda item,uid:item['url'] in {rows[i]['url'] for i in (1,3,4)}) as probe:
            result=availability.verified_choices(rows,'Song Artist',77)
        self.assertEqual([s['url'] for s in result],[rows[i]['url'] for i in (1,3,4)])
        self.assertLessEqual(probe.call_count,6)

    def test_parallel_checks_keep_owner_context_and_rank_order(self):
        import threading
        from operations import Operation,_current
        rows=[dict(SC,url=SC['url']+str(i)) for i in range(2)]
        barrier=threading.Barrier(2)
        operation=Operation(77);marker=_current.set(operation)
        def check(item,uid):
            self.assertIs(_current.get(),operation)
            barrier.wait(timeout=2)
            return True
        try:
            with patch('recording_availability.available',side_effect=check):
                self.assertEqual(availability.verified_choices(rows,'Song Artist',77),rows)
        finally:_current.reset(marker)

    def test_youtube_probe_uses_bounded_real_downloader_test_and_cleans_sample(self):
        import yt_dlp
        settings={};paths=[]
        manager=MagicMock();manager.__enter__.return_value=manager
        info={'url':'https://media.googlevideo.com/audio','duration':210,'format_id':'251'}
        def create(options):
            settings.update(options)
            return manager
        def extract(url,download):
            self.assertTrue(download)
            path=Path(settings['outtmpl'].replace('%(ext)s','webm'));paths.append(path)
            path.write_bytes(bytes.fromhex('1a45dfa3')+b'fixture')
            return info
        manager.extract_info.side_effect=extract
        with patch('yt_dlp.YoutubeDL',side_effect=create),patch.dict('os.environ',{'YTDLP_COOKIE_FILE':''}):
            self.assertTrue(availability._remote(dict(SC,url='https://www.youtube.com/watch?v=abcdefghijk')))
        self.assertTrue(settings['test'])
        self.assertNotIn('skip_download',settings)
        self.assertFalse(paths[0].parent.exists())
        with self.assertRaisesRegex(ValueError,'Probe size'):
            settings['progress_hooks'][0]({'downloaded_bytes':65537})
        self.assertIsNotNone(settings['match_filter'](dict(info,has_drm=True)))
