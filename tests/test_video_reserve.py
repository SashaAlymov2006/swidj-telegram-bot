import json
from contextlib import closing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch
import video_reserve as reserve

URL='https://youtu.be/jNQXAC9IVRw?list=ignored'
MEDIA={'streams':[{'codec_type':'video','codec_name':'h264','width':640,'height':360},
                  {'codec_type':'audio','codec_name':'aac'}],'format':{'duration':'19.063'}}

def response(body,status=200,headers=None):
    r=MagicMock();r.__enter__.return_value=r;r.status_code=status;r.headers=headers or {}
    r.iter_content.side_effect=lambda size:iter([body]);return r


class VideoReserveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        p=patch.dict(os.environ,{'STATE_DB_PATH':str(self.root/'state.sqlite3'),'JAKY_API_KEY':'fixture-secret','YOUTUBE_VIDEO_RESERVE_ENABLED':'true'})
        p.start();self.addCleanup(p.stop)

    def fixtures(self):
        return [response(json.dumps({'status':True,'result':{'title':'Video','format':'mp4','downloadUrl':'https://dl1.ezsrv.net/file.mp4?signature=fixture'}}).encode()),response(b'complete-mp4')]

    def test_full_video_is_validated_and_credentials_never_sent_to_cdn(self):
        with patch('video_reserve.requests.get',side_effect=self.fixtures()) as get,patch('video_reserve._media_url',side_effect=lambda u:u),patch('video_reserve.run_process',return_value=MagicMock(stdout=json.dumps(MEDIA))):
            result=reserve.download(URL,360,self.root/'job',1024)
        self.assertEqual(Path(result['path']).read_bytes(),b'complete-mp4')
        self.assertEqual(result['source_url'],'https://www.youtube.com/watch?v=jNQXAC9IVRw')
        first,second=get.call_args_list
        self.assertEqual(first.kwargs['headers']['x-jaky-key'],'fixture-secret')
        self.assertNotIn('x-jaky-key',second.kwargs['headers'])
        self.assertFalse(second.kwargs['allow_redirects'])
        self.assertEqual(first.kwargs['params']['quality'],360)

    def test_disabled_other_sources_and_unsupported_quality_never_call_api(self):
        with patch('video_reserve.requests.get') as get:
            for url,height in [('https://soundcloud.com/a/b',360),(URL,2160),('https://youtube.com.evil.test/watch?v=jNQXAC9IVRw',360)]:
                with self.assertRaises(ValueError):reserve.download(url,height,self.root,1024)
            with patch.dict(os.environ,YOUTUBE_VIDEO_RESERVE_ENABLED='false'),self.assertRaises(ValueError):reserve.download(URL,360,self.root,1024)
            get.assert_not_called()

    def test_shared_quota_lease_and_daily_budget(self):
        token=reserve._claim()
        with self.assertRaises(ValueError):reserve._claim()
        reserve._finish(token,0)
        with closing(reserve._database()) as db,db:db.execute('UPDATE quota SET used=90')
        with self.assertRaises(ValueError):reserve._claim()
        with closing(reserve._database()) as db,db:db.execute('UPDATE quota SET day="2000-01-01"')
        reserve._finish(reserve._claim(),0)

    def test_api_rate_limit_sets_shared_cooldown_without_fetching_file(self):
        with patch('video_reserve.requests.get',return_value=response(b'{}',429)) as get:
            with self.assertRaises(ValueError):reserve.download(URL,360,self.root,1024)
            with self.assertRaises(ValueError):reserve.download(URL,360,self.root,1024)
            self.assertEqual(get.call_count,1)

    def test_private_or_unexpected_media_hosts_are_rejected(self):
        for url in ['http://dl1.ezsrv.net/file','https://dl1.ezsrv.net.evil.test/file','https://secret@dl1.ezsrv.net/file','https://dl1.ezsrv.net:8443/file']:
            with self.assertRaises(ValueError):reserve._media_url(url)
        with patch('video_reserve.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),self.assertRaises(ValueError):
            reserve._media_url('https://dl1.ezsrv.net/file')

    def test_oversize_and_audio_only_files_are_cleaned(self):
        for budget,media in [(2,MEDIA),(1024,{'streams':MEDIA['streams'][1:],'format':{'duration':'19'}})]:
            with self.subTest(budget=budget),tempfile.TemporaryDirectory() as folder,patch('video_reserve._claim',return_value='lease'),patch('video_reserve._finish'),patch('video_reserve.requests.get',side_effect=self.fixtures()),patch('video_reserve._media_url',side_effect=lambda u:u),patch('video_reserve.run_process',return_value=MagicMock(stdout=json.dumps(media))):
                with self.assertRaises(ValueError):reserve.download(URL,360,folder,budget)
                self.assertFalse(list(Path(folder).iterdir()))

    def test_app_uses_reserve_only_for_failed_youtube_video(self):
        import yt_dlp
        from app_media import fetch
        reserved={'path':'fixture.mp4','kind':'video'}
        with tempfile.TemporaryDirectory() as folder,patch.object(yt_dlp.YoutubeDL,'extract_info',side_effect=yt_dlp.utils.DownloadError('source failed')),patch('video_reserve.download',return_value=reserved) as fallback:
            self.assertEqual(fetch({'url':URL,'mode':'video','height':720},folder),reserved)
            fallback.assert_called_once()
        with tempfile.TemporaryDirectory() as folder,patch.object(yt_dlp.YoutubeDL,'extract_info',return_value={'title':'Primary'}),patch('video_reserve.download') as fallback:
            (Path(folder)/'source.mp4').write_bytes(b'primary')
            self.assertEqual(fetch({'url':URL,'mode':'video','height':720},folder)['title'],'Primary')
            fallback.assert_not_called()

    def test_1080_request_uses_720_and_preserves_simple_quality_notice(self):
        with patch('video_reserve.requests.get',side_effect=self.fixtures()) as get,patch('video_reserve._media_url',side_effect=lambda u:u),patch('video_reserve.run_process',return_value=MagicMock(stdout=json.dumps(MEDIA))):
            result=reserve.download(URL,1080,self.root/'job',1024)
        self.assertEqual(get.call_args_list[0].kwargs['params']['quality'],720)
        self.assertEqual(reserve.output_path(result['path'],result).quality_limit,720)
        self.assertIsInstance(reserve.output_path(result['path'],result),str)

    def test_persistent_video_cache_keeps_quality_notice_without_provider_secrets(self):
        from download_cache import DownloadCache
        cache=DownloadCache(self.root/'cache');source=self.root/'source.mp4';source.write_bytes(b'fixture')
        cache.retain(77,URL,'chat-video-1080',source,{'kind':'video','video_quality_limit':720,'_video_reserve':'jaky','key':'private'})
        restored=cache.restore(77,URL,'chat-video-1080',self.root)
        self.assertEqual(restored[1],{'kind':'video','video_quality_limit':720})
        self.assertEqual(reserve.output_path(*restored).quality_limit,720)

    def test_chat_primary_failure_recovers_and_cache_hit_avoids_network(self):
        import ast,shutil
        tree=ast.parse(Path('bot.py').read_text(encoding='utf-8'))
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='download_youtube_video')
        def primary(options,url,folder):
            shutil.rmtree(folder);raise RuntimeError('primary unavailable')
        namespace={'os':os,'tempfile':tempfile,'shutil':shutil,'scratch_root':lambda:self.root,
                   'check_ffmpeg':lambda:None,'checkpoint':lambda:None,'_extract_media':primary}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'bot.py','exec'),namespace)
        def recover(url,height,folder,budget):
            Path(folder).mkdir();path=Path(folder)/'reserve.mp4';path.write_bytes(b'complete')
            return {'path':str(path),'kind':'video'}
        with patch('download_cache.restore',return_value=None),patch('download_cache.retain') as retain,patch('video_reserve.download',side_effect=recover) as fallback:
            path=namespace['download_youtube_video'](URL,360)
            self.assertEqual(Path(path).read_bytes(),b'complete');fallback.assert_called_once();retain.assert_called_once()
        with patch('download_cache.restore',return_value=(path,{})),patch('video_reserve.download') as fallback:
            self.assertEqual(namespace['download_youtube_video'](URL,360),path);fallback.assert_not_called()
