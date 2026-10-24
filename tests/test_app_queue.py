import asyncio
from pathlib import Path
import tempfile
import threading
import unittest
from miniapp_jobs import AudioJobs

class QueueDeadlineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    async def test_full_queue_has_deadline_and_does_not_start_download(self):
        calls=[]
        jobs=AudioJobs(lambda url:calls.append(url),Path(self.tmp.name),queue_timeout=.02)
        jobs.slots=asyncio.Semaphore(0)
        job=jobs.start(77,{'id':1,'url':'offline'})
        await asyncio.wait_for(job.task,.5)
        self.assertEqual((job.state,job.error),('failed','queueTimeout'))
        self.assertEqual(calls,[])

    async def test_queued_cancel_finishes_without_waiting_for_running_downloads(self):
        jobs=AudioJobs(lambda _:None,Path(self.tmp.name))
        jobs.slots=asyncio.Semaphore(0)
        job=jobs.start(77,{'id':1,'url':'offline'})
        await asyncio.sleep(.01)
        jobs.cancel(77,job.token)
        await asyncio.wait_for(job.task,.5)
        self.assertEqual(job.state,'cancelled')
        self.assertIsNone(jobs.get(78,job.token))

    async def test_timeout_is_visible_while_worker_keeps_capacity_until_cleanup(self):
        release=threading.Event()
        source=Path(self.tmp.name)/'audio.mp3';source.write_bytes(b'audio')
        def download(_):
            release.wait(2)
            return source,{}
        jobs=AudioJobs(download,Path(self.tmp.name)/'cache',download_timeout=.02)
        jobs.slots=asyncio.Semaphore(1)
        job=jobs.start(77,{'id':1,'url':'offline'})
        try:
            for _ in range(100):
                if job.state=='failed':break
                await asyncio.sleep(.005)
            self.assertEqual((job.state,job.error),('failed','downloadTimeout'))
            self.assertFalse(job.task.done())
            self.assertTrue(jobs.slots.locked())
            with self.assertRaises(ValueError):jobs.start(77,{'id':2,'url':'offline'})
        finally:
            release.set()
            await asyncio.wait_for(job.task,1)
        self.assertFalse(jobs.slots.locked())
        self.assertIsNone(jobs.path(77,1))
