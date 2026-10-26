import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch
from download_cache import DownloadCache
from media_recovery import recover_audio

URL='https://www.youtube.com/watch?v=liRLUgaUwh4'


def response(data=None,body=b'fixture-audio'):
    item=MagicMock();item.__enter__.return_value=item
    item.json.return_value=data;item.headers={'Content-Type':'audio/mpeg'}
    item.iter_content.return_value=[body]
    return item


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.cache=DownloadCache(self.root/'cache')
        self.cache.telegram_set(123456,77,URL,'fixture-file',metadata={'title':'Exact recording','artist':'Artist','duration':5})
        self.env=patch.dict(os.environ,TELEGRAM_TOKEN='123456:fixture',DOWNLOAD_CACHE_DIR=str(self.cache.root));self.env.start()
        self.budget=patch('app_limits.link_budget',return_value=1024*1024);self.budget.start()
    def tearDown(self):self.budget.stop();self.env.stop();self.tmp.cleanup()
    def test_exact_private_recording_is_recovered_and_cached(self):
        first=response({'ok':True,'result':{'file_path':'music/file.mp3','file_size':13}})
        with patch('media_recovery.requests.get',side_effect=[first,response()]) as network:
            path,metadata=recover_audio(URL,self.root/'work',77)
        self.assertEqual(Path(path).read_bytes(),b'fixture-audio')
        self.assertEqual(metadata['title'],'Exact recording')
        self.assertEqual(network.call_count,2)
        out=self.root/'out';out.mkdir()
        self.assertIsNotNone(self.cache.restore(77,URL,'audio-mp3-192',out))
    def test_different_user_or_source_cannot_access_file(self):
        with patch('media_recovery.requests.get') as network:
            self.assertIsNone(recover_audio(URL,self.root/'work',78))
            self.assertIsNone(recover_audio(URL.replace('liRLUgaUwh4','7DVM7DYJX1c'),self.root/'work',77))
            network.assert_not_called()
    def test_oversize_or_unsafe_remote_path_is_not_downloaded(self):
        for remote,size in [('music/file.mp3',21*1024**2),('../private',13)]:
            with patch('media_recovery.requests.get',return_value=response({'ok':True,'result':{'file_path':remote,'file_size':size}})) as network:
                self.assertIsNone(recover_audio(URL,self.root/'work',77))
                self.assertEqual(network.call_count,1)
    def test_partial_response_is_cleaned_and_original_error_remains_private(self):
        first=response({'ok':True,'result':{'file_path':'music/file.mp3','file_size':20}})
        with patch('media_recovery.requests.get',side_effect=[first,response()]):
            self.assertIsNone(recover_audio(URL,self.root/'work',77))
        self.assertFalse((self.root/'work'/'telegram-recovery.part').exists())
        with patch('media_recovery.requests.get',side_effect=RuntimeError('private network URL')):
            self.assertIsNone(recover_audio(URL,self.root/'work',77))


class SearchRecoveryTests(unittest.TestCase):
    def test_search_cache_survives_restart_and_expires(self):
        with tempfile.TemporaryDirectory() as folder:
            cache=DownloadCache(folder)
            cache.search('Artist Song',[{'title':'Song','artist':'Artist','url':URL,'duration':5,'cookiefile':'secret'}])
            fresh=DownloadCache(folder)
            self.assertEqual(fresh.search('artist song')[0]['title'],'Song')
            self.assertNotIn('cookiefile',fresh.search('Artist Song')[0])
            self.assertEqual(fresh.search('Other Song'),[])
            with cache.db() as db:db.execute('UPDATE searches SET touched=0')
            self.assertEqual(fresh.search('Artist Song'),[])

    def test_versions_uses_same_query_cache_only_after_source_error(self):
        from versions import find_versions
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,DOWNLOAD_CACHE_DIR=folder,YTDLP_COOKIE_FILE=''):
            with patch('versions.yt_dlp.YoutubeDL') as downloader:
                extract=downloader.return_value.__enter__.return_value.extract_info
                extract.side_effect=[{'entries':[{'id':'liRLUgaUwh4','title':'Song','uploader':'Artist','duration':5}]},RuntimeError('Source down'),RuntimeError('Source down')]
                original=find_versions('Artist Song')
                self.assertEqual(find_versions('Artist Song'),original)
                with self.assertRaises(RuntimeError):find_versions('Other Song')
