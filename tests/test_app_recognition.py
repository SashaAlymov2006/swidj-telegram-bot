import asyncio
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch
from aiohttp import web,FormData
from aiohttp.test_utils import TestClient,TestServer
from app_recognition import matches
from app_exports import ExportFiles
from miniapp_server import BotLibrary,create_app
from state_store import StateStore
from tests.test_miniapp import signed,TOKEN
from tests.test_app_studio import audio_bytes


def upload(data=None):
    form=FormData();form.add_field('file',data or audio_bytes(15),filename='music.wav',content_type='audio/wav');return form


class RecognitionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        application=SimpleNamespace(user_data={77:{},78:{}},bot_data={},bot=SimpleNamespace(username='fixture',send_message=AsyncMock()))
        self.bridge=BotLibrary(application,StateStore(self.root/'state.db'),{},{},frozenset(),cache_root=self.root/'cache')
        self.client=TestClient(TestServer(create_app(token=TOKEN,bridge=self.bridge)));await self.client.start_server();self.addAsyncCleanup(self.client.close)
        self.headers={'X-Telegram-Init-Data':signed()}
        self.client.server.app['studio_worker'].exports=ExportFiles(self.root/'exports')

    async def test_auth_key_and_media_validation(self):
        self.assertEqual((await self.client.post('/api/recognize',data=upload())).status,401)
        with patch.dict(os.environ,{'ACOUSTID_API_KEY':''}):
            self.assertEqual((await self.client.post('/api/recognize',headers=self.headers,data=upload())).status,503)
        with patch.dict(os.environ,{'ACOUSTID_API_KEY':'fixture'}):
            self.assertEqual((await self.client.post('/api/recognize',headers=self.headers,data=upload(b'bad audio'))).status,400)
            self.assertEqual((await self.client.post('/api/recognize',headers=self.headers,data=upload(audio_bytes(2)))).status,400)

    async def test_real_fingerprint_only_is_posted_and_low_scores_are_filtered(self):
        received=[]
        async def provider(request):
            received.append(dict(await request.post()))
            return web.json_response({'status':'ok','results':[{'score':.95,'recordings':[{'title':'Track','artists':[{'name':'Artist'}]}]}, {'score':.2,'recordings':[{'title':'Wrong','artists':[{'name':'Other'}]}]}]})
        app=web.Application();app.router.add_post('/lookup',provider);server=TestServer(app);await server.start_server();self.addAsyncCleanup(server.close)
        with patch.dict(os.environ,{'ACOUSTID_API_KEY':'fixture'}),patch('app_recognition.LOOKUP_URL',str(server.make_url('/lookup'))):
            response=await self.client.post('/api/recognize',headers=self.headers,data=upload())
        self.assertEqual(response.status,200)
        self.assertEqual((await response.json())['matches'],[{'title':'Track','artist':'Artist','query':'Artist Track'}])
        self.assertEqual(set(received[0]),{'client','fingerprint','duration','meta','format'})
        self.assertEqual(received[0]['duration'],'15');self.assertTrue(received[0]['fingerprint'])
        self.bridge.application.bot.send_message.assert_not_called()

    async def test_microphone_webm_without_duration_is_decoded_before_lookup(self):
        from miniapp_studio import process,probe
        raw=await process(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=21',
                           '-c:a','libopus','-f','webm','pipe:1'],20)
        source=self.root/'mic.webm';source.write_bytes(raw)
        self.assertEqual(await probe(source,allow_unknown=True),0)
        received=[]
        async def provider(request):
            received.append(dict(await request.post()))
            return web.json_response({'status':'ok','results':[]})
        app=web.Application();app.router.add_post('/lookup',provider);server=TestServer(app);await server.start_server();self.addAsyncCleanup(server.close)
        with patch.dict(os.environ,{'ACOUSTID_API_KEY':'fixture'}),patch('app_recognition.LOOKUP_URL',str(server.make_url('/lookup'))):
            response=await self.client.post('/api/recognize',headers=self.headers,data=upload(raw))
        self.assertEqual(response.status,200,await response.text())
        self.assertEqual(received[0]['duration'],'21')
        self.assertEqual((await response.json())['matches'],[])

    async def test_cached_source_owner_is_checked_before_lookup(self):
        source=self.root/'source.wav';source.write_bytes(audio_bytes(15));exports=self.client.server.app['studio_worker'].exports
        token,_=exports.retain(77,source)
        service=self.client.server.app['recognition_worker']
        with patch.dict(os.environ,{'ACOUSTID_API_KEY':'fixture'}),patch.object(service,'lookup',new_callable=AsyncMock,return_value=[]) as lookup:
            response=await self.client.post('/api/recognize',headers={'X-Telegram-Init-Data':signed(78)},json={'source_ticket':token})
            self.assertEqual(response.status,404);lookup.assert_not_awaited()
            response=await self.client.post('/api/recognize',headers=self.headers,json={'source_ticket':token})
            self.assertEqual(response.status,200);lookup.assert_awaited_once()
        self.assertTrue(exports.get(token)['path'].exists())

    async def test_recognition_does_not_lock_library_and_rejects_parallel_work(self):
        service=self.client.server.app['recognition_worker'];started=asyncio.Event();release=asyncio.Event()
        async def lookup(source):started.set();await release.wait();return []
        with patch.dict(os.environ,{'ACOUSTID_API_KEY':'fixture'}),patch.object(service,'lookup',side_effect=lookup):
            task=asyncio.create_task(self.client.post('/api/recognize',headers=self.headers,data=upload()))
            await started.wait()
            try:
                response=await asyncio.wait_for(self.client.get('/api/library',headers=self.headers),1)
                self.assertEqual(response.status,200)
                self.assertEqual((await self.client.post('/api/recognize',headers=self.headers,data=upload())).status,429)
            finally:release.set();await task

    def test_metadata_is_deduplicated_and_malformed_scores_not_trusted(self):
        item={'title':'Track','artists':[{'name':'Artist'}]}
        self.assertEqual(len(matches({'results':[{'score':.9,'recordings':[item,item]},{'score':'bad','recordings':[item]}]})),1)
