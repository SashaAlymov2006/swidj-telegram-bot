import unittest
from unittest.mock import patch,AsyncMock
from pathlib import Path
from types import SimpleNamespace as NS
import artist_catalog as artists
from tests import test_miniapp as fixtures
from tests.test_miniapp import signed

def recordings(name='Artist',source='sc',count=25):
    return [{'title':f'Song {i} Remix','artist':name,'url':f'https://soundcloud.com/artist/song-{i}','duration':180,'source':'SoundCloud'} for i in range(count)]

class CatalogTests(unittest.TestCase):
    def setUp(self):artists._cache.clear();self.addCleanup(artists._cache.clear)
    def test_remix_tab_hides_empty_sources_without_replacing_artist_tracks(self):
        def search(name,source,song):
            return recordings(count=2) if source=='sc' else [dict(recordings(count=1)[0],title='Original',url='https://www.youtube.com/watch?v=jNQXAC9IVRw')] if source=='yt' else []
        with patch('artist_catalog._search',side_effect=search):
            remix=artists.browse({'artist':'Artist'},remixes=True)
            normal=artists.browse({'artist':'Artist'})
        self.assertEqual(remix['available_sources'],['sc']);self.assertEqual(len(remix['tracks']),2)
        self.assertEqual(len(normal['tracks']),3)
    def test_artist_pages_keep_different_works_and_remixes_not_just_versions(self):
        with patch('artist_catalog._search',side_effect=lambda name,source,song:recordings() if source=='sc' else []) as search:
            first=artists.browse({'artist':'Artist'},'all',0)
            second=artists.browse({'artist':'Artist'},'all',10)
            last=artists.browse({'artist':'Artist'},'all',20)
        self.assertEqual([len(p['tracks']) for p in (first,second,last)],[10,10,5])
        self.assertEqual(search.call_count,4);self.assertIsNone(last['next_offset'])
        self.assertFalse({r['id'] for r in first['tracks']}&{r['id'] for r in second['tracks']})
        self.assertTrue(all('Remix' in r['title'] for r in first['tracks']))
    def test_artist_identity_and_provider_values_are_not_arbitrary_urls(self):
        self.assertEqual(artists.normalized('Topic'),'topic')
        self.assertTrue(artists.matches('Artist',{'artist':'Artist - Topic'}))
        self.assertFalse(artists.matches('Artist',{'artist':'Somebody else'}))
        with self.assertRaises(ValueError):artists.browse({'artist':'Artist'},'http://127.0.0.1',0)
        with self.assertRaises(ValueError):artists.browse({'artist':'Artist'},'all',-10)
        with self.assertRaises(ValueError):artists.browse({'artist':'Artist'},'all',1)
    def test_searching_artist_keeps_their_own_remixes_instead_of_song_version_filter(self):
        from versions import source_search,_source_metadata,_source_checks
        _source_metadata.clear();_source_checks.clear()
        with patch('soundcloud_source.search',return_value=recordings()),patch('recording_availability.available',return_value=True):
            found=source_search({'_search_query':'Artist','_availability_limit':5},'sc')
        self.assertEqual(len(found),5);self.assertTrue(all('Remix' in row['title'] for row in found))
        _source_metadata.clear();_source_checks.clear()
    def test_details_have_known_source_not_a_claim_of_official_original(self):
        details=artists.details({'title':'Song','artist':'Artist','url':'https://youtu.be/jNQXAC9IVRw?list=ignored'})
        self.assertEqual(details['url'],'https://www.youtube.com/watch?v=jNQXAC9IVRw')
        self.assertNotIn('official',details);self.assertNotIn('album',details)
    def test_profile_browse_only_uses_account_when_name_matches_uploader(self):
        song={'artist':'Artist','creator_name':'Artist','url':'https://soundcloud.com/artist/song'}
        with patch('soundcloud_source.artist_tracks',return_value=recordings()) as profile,patch('soundcloud_source.search',return_value=recordings()) as search:
            self.assertEqual(len(artists._search('Artist','sc',song)),25);profile.assert_called_once();search.assert_called_once()
        with patch('soundcloud_source.artist_tracks') as profile,patch('soundcloud_source.search',return_value=recordings()) as search:
            artists._search('Artist','sc',dict(song,creator_name='Fan account'));profile.assert_not_called();search.assert_called_once()

class ArtistApi(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.MiniApiTests.asyncSetUp
    async def test_pages_are_owner_scoped_and_playable_without_modifying_library(self):
        self.bridge.favorites[77]=[{'id':1,'title':'Seed','artist':'Artist','url':'https://soundcloud.com/artist/seed'}]
        artists._cache.clear();self.addCleanup(artists._cache.clear)
        with patch('artist_catalog._search',side_effect=lambda name,source,song:recordings() if source=='sc' else []):
            response=await self.client.get('/api/artist?track=1',headers=self.headers)
            self.assertEqual(response.status,200);data=await response.json();self.assertEqual(len(data['tracks']),10)
            self.assertEqual(data['next_offset'],10)
            row=await self.bridge.find(77,data['tracks'][0]['id']);self.assertEqual(row['title'],'Song 0 Remix')
            other=await self.client.get('/api/artist?track=1',headers={'X-Telegram-Init-Data':signed(78)})
            self.assertEqual(other.status,404)
            next_page=await(await self.client.get('/api/artist?track=1&offset=10',headers=self.headers)).json()
            self.assertEqual(len(next_page['tracks']),10)
        self.assertEqual(len(self.bridge.favorites[77]),1);self.bridge.application.bot.send_message.assert_not_awaited()

class ArtistChat(unittest.IsolatedAsyncioTestCase):
    async def test_track_info_and_browse_page_work_in_both_languages(self):
        from artist_ui import info,callback
        for language in ('ru','en'):
            message=NS(reply_text=AsyncMock(),edit_text=AsyncMock());query=NS(answer=AsyncMock(),message=message,data='')
            update=NS(effective_message=message,callback_query=query);context=NS(user_data={'language':language})
            song={'id':1,'title':'Seed','artist':'Artist','url':'https://soundcloud.com/artist/seed'}
            await info(update,context,song)
            button=message.reply_text.call_args.kwargs['reply_markup'].inline_keyboard[0][0];query.data=button.callback_data
            page={'name':'Artist','tracks':recordings(count=10),'offset':0,'next_offset':10,'available_sources':['sc']}
            with patch('artist_ui.browse',return_value=page):await callback(update,context)
            rows=message.edit_text.call_args.kwargs['reply_markup'].inline_keyboard
            self.assertEqual(sum(b.callback_data.startswith('arp:') for row in rows for b in row if b.callback_data),10)
