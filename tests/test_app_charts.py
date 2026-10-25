import asyncio
import time
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch
from aiohttp.test_utils import TestClient,TestServer
from app_charts import Charts,clean_feed,TTL
from miniapp_server import BotLibrary,create_app
from state_store import StateStore
from tests.test_miniapp import signed,TOKEN


def fixture():
    return {'feed':{'updated':'2026-10-25T00:00:00Z','results':[
        {'id':'101','name':'Song','artistName':'Artist','artworkUrl100':'https://is1-ssl.mzstatic.com/image.jpg'},
        {'id':'101','name':'Duplicate','artistName':'Artist'},
        {'id':'102','name':'Other song','artistName':'Other artist','artworkUrl100':'https://evil.test/image.jpg'}]}}


class ChartDataTests(unittest.IsolatedAsyncioTestCase):
    def test_provider_order_is_preserved_and_artwork_is_validated(self):
        value=clean_feed(fixture(),'de')
        self.assertEqual([item['rank'] for item in value['tracks']],[1,3])
        self.assertTrue(value['tracks'][0]['artwork']);self.assertEqual(value['tracks'][1]['artwork'],'')
        self.assertEqual(value['tracks'][0]['query'],'Artist Song')

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
            app=SimpleNamespace(user_data={77:{}},bot_data={},bot=SimpleNamespace(username='fixture',send_message=AsyncMock()))
            bridge=BotLibrary(app,StateStore(Path(folder)/'state.db'),{},{},frozenset(),cache_root=Path(folder)/'cache')
            client=TestClient(TestServer(create_app(token=TOKEN,bridge=bridge)));await client.start_server()
            try:
                self.assertEqual((await client.get('/api/charts?country=de')).status,401)
                service=client.server.app['charts_worker']
                with patch.object(service,'fetch',new_callable=AsyncMock,return_value=clean_feed(fixture(),'de')):
                    a=await(await client.get('/api/charts?country=de',headers={'X-Telegram-Init-Data':signed()})).json()
                    bridge.searches[77]=[{'title':'Unrelated search'}]
                    b=await(await client.get('/api/charts?country=de',headers={'X-Telegram-Init-Data':signed()})).json()
                    self.assertEqual(a,b)
                self.assertEqual((await client.get('/api/charts?country=invalid',headers={'X-Telegram-Init-Data':signed()})).status,400)
            finally:await client.close()
