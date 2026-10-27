import asyncio
import time
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch
from aiohttp.test_utils import TestClient,TestServer
from app_charts import Charts,clean_feed,matching_versions,TTL
from miniapp_server import BotLibrary,create_app
from state_store import StateStore
from tests.test_miniapp import signed,TOKEN


def fixture():
    return {'feed':{'updated':'2026-10-25T00:00:00Z','results':[
        {'id':'101','name':'Song','artistName':'Artist','artworkUrl100':'https://is1-ssl.mzstatic.com/image.jpg'},
        {'id':'101','name':'Duplicate','artistName':'Artist'},
        {'id':'102','name':'Other song','artistName':'Other artist','artworkUrl100':'https://evil.test/image.jpg'}]}}


class ChartDataTests(unittest.IsolatedAsyncioTestCase):
    async def test_background_refresh_checks_all_countries_and_stops_cleanly(self):
        from aiohttp import web
        from app_charts import register,COUNTRIES
        application=web.Application();register(application,SimpleNamespace())
        service=application['charts_worker'];completed=asyncio.Event()
        async def delay(seconds):
            if seconds==60:return
            self.assertEqual(seconds,3600);completed.set();await asyncio.Future()
        async def get(country):
            if country=='de':raise web.HTTPServiceUnavailable()
            return {}
        with patch.object(service,'get',side_effect=get) as fetch,patch('app_charts.asyncio.sleep',side_effect=delay):
            lifecycle=application.cleanup_ctx[0](application)
            await anext(lifecycle)
            await asyncio.wait_for(completed.wait(),1)
            self.assertEqual([call.args[0] for call in fetch.await_args_list],list(COUNTRIES))
            await lifecycle.aclose()

    async def test_restart_preserves_country_rank_and_stale_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            service=Charts(cache_root=folder);value=clean_feed(fixture(),'de')
            with patch.object(service,'fetch',new_callable=AsyncMock,return_value=value):
                await service.get('de')
            path=Path(folder)/'de.json';stored=json.loads(path.read_text())
            stored['fetched_at']-=TTL+10;path.write_text(json.dumps(stored))
            restarted=Charts(cache_root=folder)
            with patch.object(restarted,'fetch',side_effect=asyncio.TimeoutError()):
                result=await restarted.get('de')
            self.assertTrue(result['stale'])
            self.assertEqual([row['rank'] for row in result['tracks']],[1,3])
            self.assertEqual(result['country'],'de')
            with patch.object(restarted,'fetch',side_effect=asyncio.TimeoutError()):
                from aiohttp import web
                with self.assertRaises(web.HTTPServiceUnavailable):await restarted.get('us')

    def test_disk_cache_rejects_expired_or_corrupt_data(self):
        with tempfile.TemporaryDirectory() as folder:
            service=Charts(cache_root=folder);value=clean_feed(fixture(),'de')
            service.save_disk('de',value)
            path=Path(folder)/'de.json';stored=json.loads(path.read_text())
            stored['fetched_at']-=8*86400;path.write_text(json.dumps(stored))
            self.assertIsNone(service.load_disk('de'))
            path.write_text('{broken')
            self.assertIsNone(service.load_disk('de'))

    def test_provider_order_is_preserved_and_artwork_is_validated(self):
        value=clean_feed(fixture(),'de')
        self.assertEqual([item['rank'] for item in value['tracks']],[1,3])
        self.assertTrue(value['tracks'][0]['artwork']);self.assertEqual(value['tracks'][1]['artwork'],'')
        self.assertEqual(value['tracks'][0]['query'],'Artist Song')

    def test_artist_collaborations_accents_and_versions_are_matched_conservatively(self):
        item={'title':"Don't Stop (feat. Guest)",'artist':'Beyonc\u00e9 & Guest'}
        recordings=[{'title':'Beyonce - Dont Stop (Official Audio)','artist':'Beyonce'},
                    {'title':'Beyonce - Dont Stop cover','artist':'Other singer'},
                    {'title':'Dont Stop','artist':'Unrelated singer'},
                    {'title':'Beyonce Dont Stop Lyrics Meaning','artist':'Genius'}]
        self.assertEqual(matching_versions(item,recordings),recordings[:1])

    async def test_cache_coalesces_requests_and_returns_explicit_stale_data(self):
        service=Charts();value=clean_feed(fixture(),'de')
        with patch.object(service,'fetch',new_callable=AsyncMock,return_value=value) as fetch:
            a,b=await asyncio.gather(service.get('de'),service.get('de'))
            self.assertEqual(fetch.await_count,1);self.assertFalse(a['stale']);self.assertEqual(a,b)
        service.cache['de']=(time.monotonic()-TTL-1,value)
        with patch.object(service,'fetch',side_effect=ValueError('Unavailable')):
            self.assertTrue((await service.get('de'))['stale'])

    async def test_transient_network_timeout_is_retried_once(self):
        service=Charts();value=clean_feed(fixture(),'fr')
        with patch.object(service,'fetch_once',new_callable=AsyncMock,side_effect=[asyncio.TimeoutError(),value]) as fetch:
            self.assertEqual((await service.get('fr'))['country'],'fr')
            self.assertEqual(fetch.await_count,2)

    async def test_country_validation_does_not_fetch_arbitrary_urls(self):
        service=Charts()
        with patch.object(service,'fetch',new_callable=AsyncMock) as fetch:
            from aiohttp import web
            with self.assertRaises(web.HTTPBadRequest):await service.get('https://evil.test')
            fetch.assert_not_awaited()

    async def test_chart_api_is_authenticated_and_independent_of_search_history(self):
        with tempfile.TemporaryDirectory() as folder:
            app=SimpleNamespace(user_data={77:{},78:{}},bot_data={},bot=SimpleNamespace(username='fixture',send_message=AsyncMock()))
            bridge=BotLibrary(app,StateStore(Path(folder)/'state.db'),{},{},frozenset(),cache_root=Path(folder)/'cache')
            client=TestClient(TestServer(create_app(token=TOKEN,bridge=bridge)));await client.start_server()
            try:
                self.assertEqual((await client.get('/api/charts?country=de')).status,401)
                service=client.server.app['charts_worker']
                with patch.object(service,'fetch',new_callable=AsyncMock,return_value=clean_feed(fixture(),'de')):
                    a=await(await client.get('/api/charts?country=de',headers={'X-Telegram-Init-Data':signed()})).json()
                    bridge.searches[77]=[{'id':999,'title':'Unrelated search'}]
                    b=await(await client.get('/api/charts?country=de',headers={'X-Telegram-Init-Data':signed()})).json()
                    self.assertEqual(a,b)
                    recording={'title':'Artist - Song (Official Audio)','artist':'Artist','url':'https://www.youtube.com/watch?v=abcdefghijk','duration':180}
                    bridge.searches[77]=[{'id':999,'title':'Unrelated search'}]
                    with patch('versions.find_versions',return_value=[recording]) as search:
                        response=await client.post('/api/charts/resolve',headers={'X-Telegram-Init-Data':signed()},json={'country':'de','track':'101'})
                        self.assertEqual(response.status,200)
                        resolved=await response.json();self.assertEqual(len(resolved['tracks']),1)
                        identifier=resolved['tracks'][0]['id']
                        self.assertEqual((await bridge.find(77,identifier))['url'],recording['url'])
                        self.assertEqual(bridge.searches[77],[{'id':999,'title':'Unrelated search'}])
                        from aiohttp import web
                        with self.assertRaises(web.HTTPNotFound):await bridge.find(78,identifier)
                        self.assertEqual(search.call_args.kwargs,{'limit':10})
                    cover={'title':'Song','artist':'Singer','url':'https://soundcloud.com/singer/song-cover','source':'SoundCloud','duration':180}
                    with patch('versions.source_search',return_value=[cover]) as source_search,patch('versions.find_versions') as youtube:
                        response=await client.post('/api/charts/resolve',headers={'X-Telegram-Init-Data':signed()},json={'country':'de','track':'101','source':'sc'})
                        self.assertEqual(response.status,200)
                        selected=await response.json();self.assertEqual(selected['source'],'SoundCloud')
                        chosen=selected['tracks'][0]
                        self.assertEqual(chosen['title'],'Song')
                        actual=await bridge.find(77,chosen['id'])
                        self.assertEqual(actual['_catalog_song'],{'title':'Song','artist':'Artist'})
                        fixture_audio=Path(folder)/'cached.mp3';fixture_audio.write_bytes(b'cached recording')
                        bridge.audio_jobs.retain(77,chosen['id'],fixture_audio)
                        repeated=await(await client.post('/api/charts/resolve',headers={'X-Telegram-Init-Data':signed()},json={'country':'de','track':'101','source':'sc'})).json()
                        self.assertTrue(repeated['tracks'][0]['playable'])
                        source_search.assert_called_once();youtube.assert_not_called()
                    await bridge.remember_app_track(77,actual)
                    restored=await(await client.post('/api/charts/resolve',headers={'X-Telegram-Init-Data':signed()},json={'country':'de','track':'101'})).json()
                    self.assertEqual(restored['tracks'][0]['id'],chosen['id'])
                    self.assertTrue(restored['tracks'][0]['playable'])
                self.assertEqual((await client.get('/api/charts?country=invalid',headers={'X-Telegram-Init-Data':signed()})).status,400)
            finally:await client.close()
