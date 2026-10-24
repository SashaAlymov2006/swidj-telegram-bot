import asyncio
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch
from aiohttp.test_utils import TestClient,TestServer
from miniapp_server import BotLibrary,create_app
from miniapp_studio import process as real_process
from app_media import validate,normalize
from app_exports import ExportFiles
from state_store import StateStore
from tests.test_miniapp import signed,TOKEN

class LinkValidationTests(unittest.TestCase):
    def test_only_supported_links_and_explicit_modes_are_accepted(self):
        for payload in [{'url':'http://127.0.0.1/private'}, {'url':'file:///etc/passwd'}, {'url':'https://youtube.com.evil.test/watch?v=abcdefghijk'}, {'url':'https://www.youtube.com/watch?v=bad'}, {'url':'https://soundcloud.com/a/b','mode':'video'}, {'url':'https://youtu.be/abcdefghijk','height':True}]:
            with self.subTest(payload=payload),self.assertRaises(ValueError):validate(payload)
        self.assertEqual(validate({'url':'https://www.youtube.com/watch?v=abcdefghijk&utm_secret=discarded'})[0],'https://www.youtube.com/watch?v=abcdefghijk')
        self.assertEqual(validate({'url':'https://www.instagram.com/reel/abcde/','mode':'video'})[3],'instagram')

class AppMediaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        store=StateStore(self.root/'state.db')
        application=SimpleNamespace(user_data={77:{},78:{}},bot_data={},bot=SimpleNamespace(username='test',send_message=AsyncMock()))
        self.bridge=BotLibrary(application,store,{}, {},frozenset(),cache_root=self.root/'audio')
        self.client=TestClient(TestServer(create_app(token=TOKEN,bridge=self.bridge)))
        await self.client.start_server();self.addAsyncCleanup(self.client.close)
        self.client.server.app['studio_worker'].exports=ExportFiles(self.root/'exports')
        self.headers={'X-Telegram-Init-Data':signed()}

    async def test_video_import_keeps_portrait_ratio_and_serves_native_range_download(self):
        fixture=self.root/'fixture.mp4'
        await real_process(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=180x320:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(fixture)],20)
        async def fetch(args,timeout=240):
            if len(args)>2 and args[2]=='fetch':
                target=Path(args[-1])/'source.mp4';shutil.copyfile(fixture,target)
                return json.dumps({'path':str(target),'title':'Portrait fixture','artist':'Fixture'}).encode()
            return await real_process(args,timeout)
        with patch('app_media.process',side_effect=fetch),patch.dict('os.environ',{'MINIAPP_URL':'https://preview.example.test'}):
            response=await self.client.post('/api/link',headers=self.headers,json={'url':'https://www.instagram.com/reel/abcde/','mode':'video'})
        self.assertEqual(response.status,200,await response.text())
        data=await response.json();self.assertEqual(data['kind'],'video');self.assertTrue(data['filename'].endswith('.mp4'))
        self.assertFalse(data['has_audio']);self.assertTrue(data['poster'])
        item=next(iter(self.client.server.app['studio_worker'].exports.items.values()))
        raw=await real_process(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,codec_name','-of','json',str(item['path'])],15)
        stream=json.loads(raw)['streams'][0]
        self.assertEqual((stream['width'],stream['height']),(180,320));self.assertEqual(stream['codec_name'],'h264')
        from urllib.parse import urlsplit
        response=await self.client.get(urlsplit(data['url']).path,headers={'Range':'bytes=0-31'})
        self.assertEqual(response.status,206);self.assertEqual(response.content_type,'video/mp4');self.assertEqual(len(await response.read()),32)
        self.assertEqual(self.bridge.favorites,{})
        self.bridge.application.bot.send_message.assert_not_called()

    async def test_extract_audio_from_cached_video_requires_ownership(self):
        import base64
        fixture=self.root/'fixture.mp4'
        fixture.write_bytes(base64.b64decode((Path(__file__).parent/'fixtures/link_video_base64.txt').read_text()))
        exports=self.client.server.app['studio_worker'].exports
        token,_=exports.retain(77,fixture,'Video',feature='downloads')
        with patch.dict('os.environ',{'MINIAPP_URL':'https://preview.example.test'}):
            response=await self.client.post('/api/link/audio',headers={'X-Telegram-Init-Data':signed(78)},json={'ticket':token})
            self.assertEqual(response.status,404)
            response=await self.client.post('/api/link/audio',headers=self.headers,json={'ticket':token})
        self.assertEqual(response.status,200)
        data=await response.json();self.assertEqual(data['kind'],'audio');self.assertTrue(data['filename'].endswith('.mp3'))
        self.bridge.application.bot.send_message.assert_not_called()

    async def test_catalog_link_returns_recording_search_without_claiming_original_download(self):
        with patch('app_media.process',new=AsyncMock(return_value=b'{"kind":"search","query":"Fixture title artist"}')),patch.dict('os.environ',{'MINIAPP_URL':'https://preview.example.test'}):
            response=await self.client.post('/api/link',headers=self.headers,json={'url':'https://music.apple.com/us/song/123','mode':'audio'})
        self.assertEqual(response.status,200);self.assertEqual((await response.json())['kind'],'search')
        self.assertEqual(self.client.server.app['studio_worker'].exports.items,{})

    async def test_link_worker_is_cancellable_and_does_not_lock_the_library(self):
        started=asyncio.Event();stopped=asyncio.Event()
        async def slow(*args,**kwargs):
            started.set()
            try:await asyncio.sleep(30)
            finally:stopped.set()
        with patch('app_media.process',side_effect=slow),patch.dict('os.environ',{'MINIAPP_URL':'https://preview.example.test'}):
            pending=asyncio.create_task(self.client.post('/api/link',headers=self.headers,json={'url':'https://youtu.be/abcdefghijk'}))
            await asyncio.wait_for(started.wait(),2)
            response=await self.client.get('/api/library',headers=self.headers)
            self.assertEqual(response.status,200)
            await self.client.post('/api/link/cancel',headers={'X-Telegram-Init-Data':signed(78)},json={})
            self.assertFalse(stopped.is_set())
            response=await self.client.post('/api/link/cancel',headers=self.headers,json={})
            self.assertEqual(response.status,200)
            await asyncio.wait_for(stopped.wait(),2)
            await asyncio.gather(pending,return_exceptions=True)

    async def test_auth_and_arbitrary_urls_are_rejected_before_network_requests(self):
        with patch('app_media.process',new=AsyncMock()) as worker:
            self.assertEqual((await self.client.post('/api/link',json={'url':'https://youtu.be/abcdefghijk'})).status,401)
            self.assertEqual((await self.client.post('/api/link',headers=self.headers,json={'url':'http://127.0.0.1/private'})).status,400)
            worker.assert_not_called()
