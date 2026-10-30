import asyncio
import json
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch
from aiohttp.test_utils import TestClient, TestServer
from playlist_import import classify, read, read_text, make_song, normalize, add_collection, bot_import, bot_confirm
from miniapp_server import BotLibrary, create_app
from state_store import StateStore
from test_miniapp import signed, TOKEN


class ImportMetadataTests(unittest.TestCase):
    def test_links_are_strict_and_single_track_behavior_is_unchanged(self):
        samples={
          'youtube':'https://music.youtube.com/playlist?list=PL1234567890',
          'soundcloud':'https://soundcloud.com/artist/sets/mix',
          'spotify':'https://open.spotify.com/playlist/3cEYpjA9oz9GiPac4AsH4n',
          'apple':'https://music.apple.com/us/playlist/test/pl.123',
          'yandex':'https://music.yandex.ru/users/artist/playlists/123',
          'deezer':'https://www.deezer.com/de/playlist/123',
          'bandcamp':'https://artist.bandcamp.com/album/test',
          'jamendo':'https://www.jamendo.com/list/123/test',
          'audius':'https://audius.co/artist/playlist/my-mix-123',
        }
        for source,url in samples.items():self.assertEqual(classify(url),source)
        for url in ['https://www.youtube.com/watch?v=abcdefghijk&list=PL1234567890',
                    'https://open.spotify.com/track/3cEYpjA9oz9GiPac4AsH4n',
                    'https://music.apple.com/us/album/test/123?i=456',
                    'https://127.0.0.1/playlist/123', 'file:///etc/passwd',
                    'https://open.spotify.com.evil.test/playlist/3cEYpjA9oz9GiPac4AsH4n',
                    'https://user:password@open.spotify.com/playlist/3cEYpjA9oz9GiPac4AsH4n',
                    'https://www.deezer.com:444/playlist/123']:
            self.assertIsNone(classify(url),url)

    def test_text_preserves_order_unicode_and_deduplicates_without_download(self):
        data=read_text('1. Исполнитель — Песня\nArtist - Song\nArtist - Song\nJust title')
        self.assertEqual([(s['artist'],s['title']) for s in data['songs']], [('Исполнитель','Песня'),('Artist','Song'),('','Just title')])
        self.assertTrue(all(s['_catalog_metadata'] for s in data['songs']))
        with self.assertRaises(ValueError):read_text('https://localhost/secret')
        with self.assertRaisesRegex(ValueError,'playlist_too_large'):read_text('\n'.join('A — '+str(i) for i in range(501)))

    def test_partial_playlist_is_explicit_and_large_list_never_silently_truncated(self):
        data=normalize('Mix','youtube',[make_song('One'),None],2)
        self.assertTrue(data['partial']);self.assertEqual(data['count'],1);self.assertEqual(data['total'],2)
        with self.assertRaisesRegex(ValueError,'playlist_too_large'):normalize('Mix','youtube',[make_song('One')],501)

    def test_import_does_not_mutate_existing_collections_and_is_idempotent(self):
        old={'old':{'name':'Keep me','songs':[{'id':1}]}}
        data=read_text('Artist — Song')
        new,key=add_collection(old,data)
        self.assertEqual(len(old),1);self.assertEqual(new['old'],old['old'])
        again,key2=add_collection(new,data)
        self.assertEqual(key,key2);self.assertEqual(len(again),2)

    def test_deezer_pagination_ignores_arbitrary_next_urls(self):
        first={'title':'Mix','nb_tracks':2,'tracks':{'data':[{'title':'One','artist':{'name':'A'}}], 'next':'http://localhost/private'}}
        with patch('playlist_import.get_json', side_effect=[first,{'data':[{'title':'Two','artist':{'name':'B'}}]}]) as get:
            result=read('https://www.deezer.com/playlist/123')
        self.assertEqual(result['count'],2);self.assertFalse(result['partial'])
        self.assertEqual(get.call_args.args[0],'https://api.deezer.com/playlist/123/tracks')

    def test_spotify_embed_and_apple_structured_rows(self):
        entity={'name':'Mix','trackCount':2,'trackList':[{'title':'One','subtitle':'Artist','uri':'spotify:track:123','duration':90000}]}
        html='<script id="__NEXT_DATA__">'+json.dumps({'props':{'pageProps':{'state':{'data':{'entity':entity}}}}})+'</script>'
        response=NS(status_code=200,content=html.encode(),text=html,raise_for_status=lambda:None)
        with patch('playlist_import.requests.get',return_value=response):
            result=read('https://open.spotify.com/playlist/3cEYpjA9oz9GiPac4AsH4n')
        self.assertTrue(result['partial']);self.assertEqual(result['songs'][0]['duration'],90)
        html='<script type="application/ld+json">'+json.dumps({'@type':'MusicPlaylist','name':'Apple Mix','numTracks':1,'track':[{'@type':'MusicRecording','name':'Song','byArtist':{'name':'Singer'}}]})+'</script>'
        response=NS(status_code=200,content=html.encode(),text=html,raise_for_status=lambda:None)
        with patch('playlist_import.requests.get',return_value=response):
            result=read('https://music.apple.com/us/playlist/test/pl.123')
        self.assertEqual(result['songs'][0]['artist'],'Singer')

    def test_audius_relative_resolution_uses_official_api_without_forwarding_credentials(self):
        response=NS(status_code=302,headers={'Location':'/v1/playlists/by_permalink/artist/my-mix-123'})
        playlist={'id':'abc12','playlist_name':'Mix','track_count':1}
        track={'title':'Song','user':{'name':'Artist'},'permalink':'/artist/song','duration':180}
        with patch('audius_source._auth',return_value=({'Authorization':'fixture'},{})),patch('playlist_import.requests.get',return_value=response) as get,patch('audius_source.api',side_effect=[[playlist],[track]]) as api:
            result=read('https://audius.co/artist/playlist/my-mix-123')
        self.assertEqual(result['count'],1)
        self.assertEqual(get.call_args.args[0],'https://api.audius.co/v1/resolve')
        self.assertEqual(api.call_args_list[0].args[0],'/playlists/by_permalink/artist/my-mix-123')

    def test_jamendo_playlist_keeps_metadata_without_downloading_audio(self):
        import os
        data={'headers':{'status':'success'},'results':[{'name':'Mix','tracks':[{'id':'123','name':'Song','artist_name':'Artist','duration':120}]}]}
        with patch.dict(os.environ,JAMENDO_CLIENT_ID='fixture'),patch('playlist_import.get_json',return_value=data):
            result=read('https://www.jamendo.com/list/10000')
        self.assertEqual(result['count'],1)
        self.assertEqual(result['songs'][0]['url'],'https://www.jamendo.com/track/123')


class ImportIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=StateStore(Path(self.tmp.name)/'state.db')
        self.old={'old':{'name':'Old collection','songs':[{'id':1,'title':'Old','artist':'A'}]}}
        self.store.save_library(77,[],self.old,[])
        self.application=NS(user_data={77:{'language':'en'},78:{}},bot_data={},bot=NS(username='offline_bot',send_message=AsyncMock()))
        self.bridge=BotLibrary(self.application,self.store,{}, {},frozenset(),cache_root=Path(self.tmp.name)/'cache')
        self.client=TestClient(TestServer(create_app(token=TOKEN,bridge=self.bridge)))
        await self.client.start_server();self.addAsyncCleanup(self.client.close)
        self.headers={'X-Telegram-Init-Data':signed()}

    async def test_preview_confirm_cross_user_rejection_persistence_and_lazy_versions(self):
        url='/api/playlists/import'
        self.assertEqual((await self.client.post(url,json={'text':'A — One'})).status,401)
        response=await self.client.post(url,json={'text':'Artist — One\nArtist — Two'},headers=self.headers)
        self.assertEqual(response.status,200);preview=await response.json()
        self.assertEqual(len(self.store.load_named('music_collections')[77]),1)
        self.assertEqual((await self.client.post(url,json={'confirm':preview['token']},headers={'X-Telegram-Init-Data':signed(78)})).status,410)
        response=await self.client.post(url,json={'confirm':preview['token']},headers=self.headers)
        self.assertEqual(response.status,200);result=await response.json()
        self.assertEqual(len(result['library']['playlists']),2)
        self.assertEqual(self.store.load_named('music_collections')[77]['old'],self.old['old'])
        collection=self.store.load_named('music_collections')[77][result['playlist']]
        self.assertEqual(len(collection['songs']),2)
        self.assertEqual((await self.client.post(url,json={'confirm':preview['token']},headers=self.headers)).status,200)
        self.assertEqual(len(self.store.load_named('music_collections')[77]),2)
        with patch('versions.catalog_choices',new_callable=AsyncMock,return_value=([],{})) as versions:
            await self.bridge.prepare(77,str(collection['songs'][0]['id']))
        versions.assert_awaited_once()
        # The bot reads the same durable folders, not an app-only copy.
        from library_ui import collections
        folders=await collections(NS(user_data={}),77,self.store)
        self.assertEqual(folders[result['playlist']],collection)

    async def test_expiry_failure_and_preview_rate_limit_preserve_library(self):
        self.bridge.playlist_previews[77]={'token':'expired','created':time.monotonic()-1801,'collection':read_text('A — Song')}
        self.assertEqual((await self.client.post('/api/playlists/import',json={'confirm':'expired'},headers=self.headers)).status,410)
        self.assertEqual((await self.client.post('/api/playlists/import',json={'url':'http://127.0.0.1/private'},headers=self.headers)).status,400)
        self.assertEqual((await self.client.post('/api/playlists/import',json={'text':'A — Song'},headers=self.headers)).status,429)
        self.assertEqual(self.store.load_named('music_collections')[77],self.old)

    async def test_multilingual_text_body_above_old_api_limit_and_clear_capacity_error(self):
        value='\n'.join('Исполнитель — '+('Песня'*18)+str(i) for i in range(200))
        self.assertGreater(len(value.encode()),16384)
        response=await self.client.post('/api/playlists/import',json={'text':value},headers=self.headers)
        self.assertEqual(response.status,200)
        self.assertEqual((await response.json())['count'],200)
        self.bridge.playlist_times.clear()
        response=await self.client.post('/api/playlists/import',json={'text':'\n'.join('A — '+str(i) for i in range(501))},headers=self.headers)
        self.assertEqual(response.status,400)
        self.assertEqual((await response.json())['message'],'Up to 500 tracks per import.')

    async def test_imported_collection_can_accept_tracks_without_changing_legacy_limit(self):
        from library_ui import track_limit, MAX_TRACKS
        data=read_text('\n'.join('Artist — '+str(i) for i in range(61)))
        folders,key=add_collection(self.old,data)
        self.assertEqual(track_limit(folders[key]),500)
        self.assertEqual(track_limit(folders['old']),MAX_TRACKS)
        await asyncio.to_thread(self.store.save_library,77,[],folders,[])
        self.application.user_data[77]['music_collections']=folders
        self.bridge.searches[77]=[{'id':999,'title':'Another','artist':'Artist'}]
        result=await self.bridge.change(77,{'action':'playlist','playlist':key,'track':'999'})
        imported=next(p for p in result['playlists'] if p['id']==key)
        self.assertEqual(len(imported['tracks']),62)

    async def test_bot_preview_and_confirmation_in_both_languages(self):
        for language in ('ru','en'):
            with self.subTest(language=language):
                context=NS(user_data={'language':language})
                status=NS(edit_text=AsyncMock())
                update=NS(effective_user=NS(id=77),effective_message=NS(text='/import Artist — Song',reply_text=AsyncMock(return_value=status)))
                await bot_import(update,context,self.store,{})
                self.assertIn('_playlist_preview',context.user_data)
                preview=context.user_data['_playlist_preview']
                update.callback_query=NS(data='pimport:'+preview['token'],answer=AsyncMock(),edit_message_text=AsyncMock())
                await bot_confirm(update,context,self.store,{})
                update.callback_query.edit_message_text.assert_awaited_once()
                from playlist_import import text
                self.assertEqual(update.callback_query.edit_message_text.call_args.args[0],text(language,'done'))


if __name__=='__main__':unittest.main()
