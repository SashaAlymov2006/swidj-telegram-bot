import unittest
from unittest.mock import patch,AsyncMock,MagicMock
from types import SimpleNamespace as NS
import release_catalog as releases
from tests import test_miniapp as fixtures
from tests.test_miniapp import signed


def header(identifier=9,name='Artist',title='Release',**extra):
    return dict(wrapperType='collection',collectionType='Album',collectionId=identifier,artistId=7,
                artistName=name,collectionName=title,collectionViewUrl='https://music.apple.com/de/album/release/9',
                artworkUrl100='https://is1-ssl.mzstatic.com/image/test.jpg',releaseDate='2026-10-20T00:00:00Z',trackCount=3,**extra)


def song(number,disc=1):
    return dict(wrapperType='track',kind='song',collectionId=9,trackId=number+disc*100,trackName='Song '+str(number),
                artistName='Artist',trackNumber=number,discNumber=disc,trackTimeMillis=240000,
                trackViewUrl=f'https://music.apple.com/de/album/release/9?i={number+disc*100}')


class ReleaseCatalogTests(unittest.TestCase):
    def setUp(self):
        releases._views.clear();self.addCleanup(releases._views.clear)
        self.enterContext(patch('release_catalog._additional',return_value=[]))
    def test_same_name_artists_are_selected_without_merging_discographies(self):
        other=header(10);other['artistId']=8
        with patch('release_catalog._request',return_value=[header(),other]):
            ambiguous=releases.releases({'artist':'Artist'})
            self.assertEqual(ambiguous['releases'],[]);self.assertEqual(len(ambiguous['profiles']),2)
            selected=releases.releases({'artist':'Artist','_release_artist_id':'7'})
            self.assertEqual([a['id'] for a in selected['releases']],['9'])
    def test_transport_uses_bounded_public_response_and_reuses_metadata_cache(self):
        import json
        releases._cache.clear();self.addCleanup(releases._cache.clear)
        response=MagicMock(status_code=200);response.__enter__.return_value=response
        response.iter_content.return_value=[json.dumps({'results':[header()]}).encode()]
        with patch('release_catalog.requests.get',return_value=response) as get,patch('release_catalog._next_call',0):
            first=releases._request('search',{'term':'Artist'});first[0]['artistName']='Changed by caller'
            second=releases._request('search',{'term':'Artist'})
        self.assertEqual(second[0]['artistName'],'Artist');get.assert_called_once()
        self.assertFalse(get.call_args.kwargs['allow_redirects']);self.assertNotIn('headers',get.call_args.kwargs)

    def test_artist_identity_release_types_paging_and_duplicates(self):
        rows=[header(i,title=f'Release {i} - EP' if i==1 else f'Release {i} - Single' if i==2 else f'Release {i}') for i in range(12)]
        rows += [header(88,name='Another Artist'),rows[0]]
        with patch('release_catalog._request',return_value=rows):
            first=releases.releases({'artist':'Artist'});last=releases.releases({'artist':'Artist'},10)
        self.assertEqual(len(first['releases']),10);self.assertEqual(len(last['releases']),2)
        self.assertEqual(first['next_offset'],10);self.assertIsNone(last['next_offset'])
        self.assertEqual({a['kind'] for a in first['releases']+last['releases']},{'album','single','ep'})
        self.assertNotIn('88',[a['id'] for a in first['releases']+last['releases']])

    def test_real_album_order_source_identity_and_no_preview_download(self):
        with patch('release_catalog._request',return_value=[header(),song(2,2),song(2),song(1),song(1)]):
            page=releases.album({'artist':'Artist'},'9')
        self.assertEqual([(t['disc_number'],t['track_number']) for t in page['tracks']],[(1,1),(1,2),(2,2)])
        self.assertTrue(all(t['_catalog_song']['artist']=='Artist' and 'preview' not in t['url'] for t in page['tracks']))
        with patch('release_catalog._request',return_value=[header(name='Other'),song(1)]):
            with self.assertRaises(ValueError):releases.album({'artist':'Artist'},'9')
        for value in ('http://127.0.0.1','9/../lookup','-1'):
            with self.assertRaises(ValueError):releases.album({'artist':'Artist'},value)
        self.assertEqual(releases._link('https://is1.mzstatic.com.evil.test/x',True),'')
        self.assertEqual(releases._link('https://user:pass@music.apple.com/x'),'')


class ReleaseApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixtures.MiniApiTests.asyncSetUp(self)
        releases._views.clear();self.addCleanup(releases._views.clear)
        self.enterContext(patch('release_catalog._additional',return_value=[]))
    async def test_album_discovery_is_owner_scoped_and_reuses_existing_version_flow(self):
        seed={'id':1,'title':'Seed','artist':'Artist','url':'https://soundcloud.com/artist/seed'}
        self.bridge.favorites[77]=[seed]
        with patch('release_catalog._request',return_value=[header(),song(2),song(1)]):
            response=await self.client.get('/api/artist/releases?track=1',headers=self.headers)
            self.assertEqual(response.status,200);self.assertEqual(len((await response.json())['releases']),1)
            response=await self.client.get('/api/artist/releases?track=1&album=9',headers=self.headers)
            data=await response.json();self.assertEqual(response.status,200);self.assertEqual(len(data['tracks']),2)
            selected=await self.bridge.find(77,data['tracks'][0]['id']);self.assertEqual(selected['track_number'],1)
            with self.assertRaises(Exception):await self.bridge.find(78,data['tracks'][0]['id'])
            response=await self.client.get('/api/artist/releases?track=1',headers={'X-Telegram-Init-Data':signed(78)})
            self.assertEqual(response.status,404)
            response=await self.client.get('/api/artist/releases?track=1&album=../bad',headers=self.headers)
            self.assertEqual(response.status,400)
        self.assertEqual(self.bridge.favorites[77],[seed]);self.bridge.application.bot.send_message.assert_not_awaited()


class ReleaseChatTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):releases._views.clear();self.addCleanup(releases._views.clear)
    async def test_both_languages_navigate_album_to_existing_track_card(self):
        from artist_ui import callback
        for language in ('ru','en'):
            message=NS(reply_text=AsyncMock(),edit_text=AsyncMock());query=NS(data='arl:0123456789:0',message=message,answer=AsyncMock())
            update=NS(callback_query=query,effective_message=message)
            context=NS(user_data={'language':language,'artist_views':{'0123456789':{'artist':'Artist'}}})
            with patch('release_catalog._request',return_value=[header(),song(1)]),patch('release_catalog._additional',return_value=[]):
                await callback(update,context)
                query.data=message.edit_text.call_args.kwargs['reply_markup'].inline_keyboard[0][0].callback_data
                self.assertEqual(query.data,'alb:0123456789:9:0');await callback(update,context)
                query.data=message.edit_text.call_args.kwargs['reply_markup'].inline_keyboard[0][0].callback_data
                with patch('track_card.show_card',new=AsyncMock()) as show:
                    await callback(update,context);self.assertEqual(show.call_args.args[2]['title'],'Song 1')
