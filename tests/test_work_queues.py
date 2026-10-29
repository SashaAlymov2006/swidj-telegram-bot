import asyncio,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from dispatch import WorkQueue,QueueFull
from app_render_jobs import RenderJobs
from tests import test_app_media as media_harness
from tests.test_miniapp import signed
from tests import test_app_studio as studio_harness

class WorkQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_five_users_are_admitted_with_two_workers_and_fifo_waiting(self):
        queue=WorkQueue(2,capacity=6);release=asyncio.Event();entered=[];active=0;peak=0
        async def work(uid):
            nonlocal active,peak
            async with queue.enter(uid):
                active+=1;peak=max(peak,active);entered.append(uid)
                await release.wait();await asyncio.sleep(.001);active-=1
        tasks=[asyncio.create_task(work(uid)) for uid in range(5)]
        for _ in range(30):
            if len(entered)==2:break
            await asyncio.sleep(.001)
        self.assertEqual(entered,[0,1]);self.assertEqual(queue.status(4),{'status':'queued','position':3})
        release.set();await asyncio.gather(*tasks)
        self.assertEqual(peak,2);self.assertEqual(entered,[0,1,2,3,4]);self.assertFalse(queue.entries)

    async def test_queued_cancel_timeout_and_duplicate_never_leak_capacity(self):
        queue=WorkQueue(1,capacity=2,timeout=.02)
        async with queue.enter(1):
            with self.assertRaises(QueueFull):
                async with queue.enter(1):pass
            with self.assertRaises(asyncio.TimeoutError):
                async with queue.enter(2):pass
            task=asyncio.create_task(self.wait(queue,3));await asyncio.sleep(.001);task.cancel()
            await asyncio.gather(task,return_exceptions=True);self.assertNotIn(3,queue.entries)
        async with queue.enter(4):self.assertEqual(queue.status(4)['status'],'processing')
        self.assertFalse(queue.entries)

    async def wait(self,queue,uid):
        async with queue.enter(uid):await asyncio.sleep(1)

    async def test_render_jobs_accept_five_users_and_cancel_only_the_owned_job(self):
        release=asyncio.Event();started=[];cleaned=[]
        async def render(source,directory,settings):
            started.append(settings['uid']);await release.wait();return source
        exports=SimpleNamespace(retain=lambda uid,*a,**kw:('ticket',{'filename':'sound.mp3'}))
        jobs=RenderJobs(exports,asyncio.Semaphore(1),render)
        with patch('miniapp_studio.probe',new=AsyncMock(return_value=1)):
            batch=[jobs.start(uid,'file','directory',{'uid':uid},lambda uid=uid:cleaned.append(uid)) for uid in range(5)]
            await asyncio.sleep(.01);self.assertEqual(started,[0])
            self.assertEqual(jobs.payload(batch[4],'https://example.test')['position'],4)
            self.assertIsNone(jobs.get(99,batch[1].token));self.assertFalse(jobs.cancel(99,batch[1].token))
            with self.assertRaises(ValueError):jobs.start(1,'file','directory',{},lambda:None)
            jobs.cancel(2,batch[2].token);release.set();await asyncio.gather(*(j.task for j in batch))
            self.assertEqual([j.state for j in batch],['ready','ready','cancelled','ready','ready'])
            self.assertCountEqual(cleaned,range(5));self.assertEqual(len(cleaned),5)

class LinkQueueApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=media_harness.AppMediaTests.asyncSetUp
    async def test_five_imports_are_processed_automatically_and_expose_only_owned_status(self):
        release=asyncio.Event();started=0;active=0;peak=0
        async def process(*args,**kwargs):
            nonlocal started,active,peak
            started+=1;active+=1;peak=max(active,peak)
            try:await release.wait();await asyncio.sleep(.001);return b'{"kind":"search","query":"Fixture"}'
            finally:active-=1
        with patch('app_media.process',side_effect=process),patch('app_media.audio_worker',new=AsyncMock(return_value=None)),patch('download_cache.restore',return_value=None),patch.dict('os.environ',MINIAPP_URL='https://preview.example.test'):
            pending=[asyncio.create_task(self.client.post('/api/link',headers={'X-Telegram-Init-Data':signed(uid)},json={'url':'https://music.apple.com/us/song/123','mode':'audio'})) for uid in range(77,82)]
            for _ in range(100):
                if started==2:break
                await asyncio.sleep(.005)
            response=await self.client.get('/api/link/status',headers={'X-Telegram-Init-Data':signed(81)})
            self.assertEqual((await response.json())['status'],'queued')
            response=await self.client.get('/api/link/status',headers={'X-Telegram-Init-Data':signed(99)})
            self.assertEqual(await response.json(),{'status':'idle','position':0})
            release.set();responses=await asyncio.gather(*pending)
            self.assertEqual([r.status for r in responses],[200]*5);self.assertEqual(peak,2)

class StudioQueueApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=studio_harness.AppStudioTests.asyncSetUp
    async def test_five_background_uploads_all_finish_as_real_playable_files(self):
        from urllib.parse import urlsplit
        with patch.dict('os.environ',MINIAPP_URL='https://preview.example.test'):
            responses=await asyncio.gather(*(self.client.post('/api/studio',headers={'X-Telegram-Init-Data':signed(uid)},
                data=studio_harness.form(data=studio_harness.audio_bytes(.5),settings={'background':True,'delivery':'ticket','format':'mp3'})) for uid in range(77,82)))
            self.assertEqual([r.status for r in responses],[200]*5)
            jobs=[await r.json() for r in responses];self.assertEqual(len({j['job'] for j in jobs}),5)
            for uid,job in zip(range(77,82),jobs):
                for _ in range(100):
                    response=await self.client.get('/api/studio/jobs/'+job['job'],headers={'X-Telegram-Init-Data':signed(uid)})
                    data=await response.json()
                    if data['status'] not in ('queued','processing'):break
                    await asyncio.sleep(.05)
                self.assertEqual(data['status'],'ready')
                response=await self.client.get(urlsplit(data['file']['url']).path,headers={'Range':'bytes=0-31'})
                self.assertEqual(response.status,206);self.assertEqual(len(await response.read()),32)
        self.bridge.application.bot.send_message.assert_not_called()
