import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from jamendo_source import track,identifier,matching_track,download
from media_recovery import download_with_reserve


def fixture():
    return {'id':'123','name':'Exact Song','artist_name':'Artist','duration':218,'audiodownload_allowed':True,
            'license_ccurl':'http://creativecommons.org/licenses/by/3.0/',
            'audiodownload':'https://prod-1.storage.jamendo.com/download/track/123/mp32/'}


class JamendoReserveTests(unittest.TestCase):
    def test_public_credit_contains_only_validated_catalog_links(self):
        from miniapp_server import public_song
        song=dict(track(fixture()),id=123,private_token='never-public')
        public=public_song(song)
        self.assertEqual(public['source'],'Jamendo')
        self.assertNotIn('private_token',public)
        self.assertNotIn('source_url',public_song(dict(song,url='https://example.com/private')))
    def test_download_permission_and_derivative_license_are_required(self):
        self.assertIsNotNone(track(fixture()))
        for changes in ({'audiodownload_allowed':False},{'license_ccurl':'https://creativecommons.org/licenses/by-nd/4.0/'},{'license_ccurl':'https://creativecommons.org/licenses/by-nc/4.0/'}):
            self.assertIsNone(track(dict(fixture(),**changes)))
    def test_only_exact_artist_title_version_duration_can_match(self):
        song=track(fixture());hint={'title':'Artist - Exact Song (Official Audio)','artist':'Artist','duration':219}
        with patch('jamendo_source.search',return_value=[song]):
            self.assertEqual(matching_track(hint),song)
            for change in ({'artist':'Other'},{'title':'Exact Song Remix'},{'duration':250},{'duration':None}):
                self.assertIsNone(matching_track(dict(hint,**change)))
        with patch('jamendo_source.search',return_value=[song,dict(song)]):self.assertIsNone(matching_track(hint))
    def test_normal_download_does_not_contact_reserve(self):
        with patch('jamendo_source.matching_track') as search:
            self.assertEqual(download_with_reserve(lambda url:('file',{}),'url',{}),('file',{}))
            search.assert_not_called()
    def test_exact_reserve_is_used_after_primary_source_error(self):
        song=track(fixture())
        def unavailable(url):raise RuntimeError('Primary source unavailable')
        with patch.dict(os.environ,JAMENDO_CLIENT_ID='fixture'),patch('jamendo_source.matching_track',return_value=song),patch('jamendo_source.download',return_value=('fixture.mp3',song)) as reserve:
            result=download_with_reserve(unavailable,'https://www.youtube.com/watch?v=liRLUgaUwh4',song)
            self.assertEqual(result[1]['source'],'Jamendo')
            self.assertEqual(reserve.call_args.args[0],song['url'])
        with patch.dict(os.environ,JAMENDO_CLIENT_ID='fixture'),patch('jamendo_source.matching_track',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'Primary source unavailable'):download_with_reserve(unavailable,'url',song)
    def test_product_limits_do_not_trigger_alternative_download(self):
        with patch.dict(os.environ,JAMENDO_CLIENT_ID='fixture'),patch('jamendo_source.matching_track') as search:
            def primary(url):raise ValueError('File too large')
            with self.assertRaises(ValueError):download_with_reserve(primary,'url',{})
            search.assert_not_called()
    def test_selected_permitted_catalog_file_download_is_bounded(self):
        response=MagicMock();response.__enter__.return_value=response
        response.is_redirect=False;response.iter_content.return_value=[b'fixture-file']
        with tempfile.TemporaryDirectory() as directory,patch('jamendo_source.rows',return_value=[fixture()]),patch('jamendo_source.requests.get',return_value=response):
            path,info=download('https://www.jamendo.com/track/123',directory)
            self.assertEqual(Path(path).read_bytes(),b'fixture-file')
            self.assertEqual(info['source'],'Jamendo')
    def test_media_url_and_track_identity_are_validated(self):
        with tempfile.TemporaryDirectory() as directory,patch('jamendo_source.rows',return_value=[dict(fixture(),audiodownload='https://127.0.0.1/private')]),patch('jamendo_source.requests.get') as network:
            with self.assertRaises(ValueError):download('https://www.jamendo.com/track/123',directory)
            network.assert_not_called()
        self.assertIsNone(identifier('https://www.jamendo.com.evil.test/track/123'))
