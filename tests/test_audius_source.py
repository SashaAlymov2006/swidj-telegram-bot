import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch
import audius_source as aud

URL='https://audius.co/artist/song'
ROW={'id':'D7KyD','title':'Song','user':{'name':'Artist'},'permalink':'/artist/song',
     'duration':210,'is_downloadable':True,'access':{'download':True}}


def response(body=b'ID3audio',status=200,headers=None):
    r=MagicMock();r.__enter__.return_value=r;r.status_code=status
    r.headers=headers or {};r.iter_content.side_effect=lambda size:iter([body])
    return r


class AudiusTests(unittest.TestCase):
    def setUp(self):
        env=patch.dict(os.environ,{'AUDIUS_API_KEY':'public-fixture-key','AUDIUS_BEARER_TOKEN':'private-fixture-token','AUDIUS_ENABLED':'true'})
        env.start();self.addCleanup(env.stop)
        pace=patch('audius_source._pace');pace.start();self.addCleanup(pace.stop)

    def test_only_public_downloadable_ungated_full_tracks_are_accepted(self):
        self.assertEqual(aud.track(ROW)['url'],URL)
        for change in ({'is_downloadable':False},{'is_unlisted':True},{'download_conditions':{'follow_user_id':1}},
                       {'is_stream_gated':True},{'is_scheduled_release':True},{'duration':float('nan')},
                       {'access':{'download':False}},{'allowed_api_keys':['another-app']},{'permalink':'/settings/keys'}):
            self.assertIsNone(aud.track(dict(ROW,**change)))
        for url in ('http://audius.co/artist/song','https://audius.co.evil.test/artist/song',
                    URL+'?token=private',URL+'#private','https://user:secret@audius.co/artist/song',
                    'https://audius.co:8080/artist/song'):
            self.assertIsNone(aud.canonical(url))

    def test_disabled_source_makes_no_network_requests(self):
        with patch.dict(os.environ,AUDIUS_ENABLED='false'),patch('audius_source.requests.get') as get:
            self.assertEqual(aud.search('Artist Song'),[]);get.assert_not_called()

    def test_metadata_is_authenticated_bounded_and_does_not_follow_redirects(self):
        body=json.dumps({'data':[ROW]}).encode()
        with patch('audius_source.requests.get',return_value=response(body)) as get:
            self.assertEqual(len(aud.search('Artist Song')),1)
        args=get.call_args.kwargs
        self.assertFalse(args['allow_redirects'])
        self.assertEqual(args['headers']['Authorization'],'Bearer private-fixture-token')
        self.assertEqual(args['params']['only_downloadable'],'true')
        with patch('audius_source.requests.get',return_value=response(status=403)):
            self.assertEqual(aud.search('Artist Song'),[])

    def test_media_redirect_never_forwards_credentials_to_storage(self):
        redirect=response(status=302,headers={'Location':'https://storage.audius.co/content.mp3'})
        with patch('audius_source.requests.get',side_effect=[redirect,response()]) as get,patch('audius_source._public_media_url',return_value=True):
            with aud._media('D7KyD',sample=True) as media:
                self.assertEqual(next(media.iter_content(8192)),b'ID3audio')
        first,second=get.call_args_list
        self.assertIn('Authorization',first.kwargs['headers'])
        self.assertNotIn('Authorization',second.kwargs['headers'])
        self.assertIsNone(second.kwargs['params'])
        self.assertEqual(second.kwargs['headers']['Range'],'bytes=0-8191')

    def test_private_media_addresses_and_unexpected_metadata_redirect_are_rejected(self):
        addresses=[(2,1,6,'',('127.0.0.1',443))]
        with patch('audius_source.socket.getaddrinfo',return_value=addresses):
            self.assertFalse(aud._public_media_url('https://storage.example.test/audio'))
        with patch('audius_source.requests.get',return_value=response(status=302,headers={'Location':'https://127.0.0.1/private'})) as get,patch('audius_source._public_media_url',return_value=False):
            with self.assertRaisesRegex(ValueError,'media host'):
                with aud._media('D7KyD'):pass
            self.assertEqual(get.call_count,1)

    def test_preflight_reads_real_bytes_and_checks_duration(self):
        item=aud.track(ROW)
        with patch('audius_source._metadata',return_value=item),patch('audius_source._media',return_value=response()):
            self.assertTrue(aud.available(item))
            self.assertFalse(aud.available(dict(item,duration=30)))
        with patch('audius_source._metadata',return_value=item),patch('audius_source._media',return_value=response(b'<html>denied</html>')):
            self.assertFalse(aud.available(item))

    def test_complete_download_is_validated_and_partial_failures_are_cleaned(self):
        item=aud.track(ROW)
        probe=MagicMock(stdout=json.dumps({'format':{'duration':210},'streams':[{'codec_name':'mp3'}]}))
        with tempfile.TemporaryDirectory() as folder,patch('audius_source._metadata',return_value=item),patch('audius_source._media',side_effect=lambda *args,**kwargs:response()),patch('audius_source.run_process',return_value=probe):
            path,info=aud.download(URL,folder)
            self.assertTrue(Path(path).is_file());self.assertTrue(info['_public_source'])
            self.assertEqual(info['source'],'Audius')
            with self.assertRaisesRegex(ValueError,'budget'):aud.download(URL,folder,max_bytes=2)
            self.assertFalse((Path(folder)/'audius.part').exists())
            probe.stdout=json.dumps({'format':{'duration':30},'streams':[{'codec_name':'mp3'}]})
            with self.assertRaisesRegex(ValueError,'Incomplete'):aud.download(URL,folder)
            self.assertFalse((Path(folder)/'audius.part').exists())

    def test_audius_cache_key_and_app_link_are_separate_from_youtube(self):
        from download_cache import source_key,shareable
        from app_media import validate
        from catalog_links import classify
        self.assertTrue(source_key(URL).startswith('audius:'))
        self.assertTrue(shareable(URL));self.assertEqual(classify(URL),'audius')
        self.assertEqual(validate({'url':URL,'mode':'audio'})[3],'audius')
        with self.assertRaises(ValueError):validate({'url':URL,'mode':'video'})

    def test_exact_reserve_rejects_other_artist_and_ambiguous_versions(self):
        item=aud.track(ROW);hint={'title':'Song','artist':'Artist','duration':210}
        with patch('audius_source.search',return_value=[dict(item,artist='Other artist')]):
            self.assertIsNone(aud.matching_track(hint))
        with patch('audius_source.search',return_value=[item,item]):
            self.assertIsNone(aud.matching_track(hint))
        with patch('audius_source.search',return_value=[item]):
            self.assertEqual(aud.matching_track(hint),item)

    def test_public_dotted_slug_and_app_fetch_use_audius_directly(self):
        from app_media import fetch
        dotted='https://audius.co/artist/song-feat.-singer'
        self.assertEqual(aud.canonical(dotted),dotted)
        with patch('audius_source.download',return_value=('/fixture.mp3',aud.track(ROW))) as download,patch('app_media.yt_dlp',create=True):
            result=fetch({'url':URL,'mode':'audio'},'/tmp')
        self.assertEqual(result['path'],'/fixture.mp3');self.assertEqual(result['source'],'Audius')
        download.assert_called_once()


class AudiusInventoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_audius_button_requires_checked_results(self):
        from versions import source_inventory,source_rows,_source_checks,_source_metadata
        _source_checks.clear();_source_metadata.clear()
        try:
            with patch.dict(os.environ,AUDIUS_API_KEY='public-fixture-key',AUDIUS_ENABLED='true'),patch('audius_source.search',return_value=[aud.track(ROW)]),patch('recording_availability.available',return_value=True):
                found=await source_inventory({'title':'Song','artist':'Artist'},77,{'yt':[],'sc':[],'jam':[]})
            buttons=source_rows('token',{'available_sources':[key for key,rows in found.items() if rows]})
            self.assertEqual([r[0].callback_data for r in buttons],['ver:source:token:aud'])
        finally:_source_checks.clear();_source_metadata.clear()
