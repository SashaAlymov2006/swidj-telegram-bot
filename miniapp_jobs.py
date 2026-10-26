"""Bounded app-only audio preparation. No Telegram messages or chat session writes."""
import asyncio
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import time

from media_store import MediaStore
from app_limits import MEDIA_BYTES,TEMP_CACHE_BYTES
from operations import Operation, OperationCancelled, _current, checkpoint


@dataclass
class Job:
    uid: int
    song: dict
    token: str = field(default_factory=lambda: secrets.token_hex(12))
    state: str = 'queued'
    created: float = field(default_factory=time.monotonic)
    operation: object = None
    task: object = None
    error: str = None


class AudioJobs:
    def __init__(self, downloader=None, root=None, *, max_bytes=TEMP_CACHE_BYTES, queue_timeout=30, download_timeout=900):
        active = Path(os.getenv('AUDIO_CACHE_DIR', '/app/data/audio'))
        self.root = Path(root or os.getenv('MINIAPP_CACHE_DIR') or active.parent/'miniapp-cache')
        self.store = MediaStore(self.root)
        self.downloader = downloader
        self.limit = max_bytes
        self.jobs = {}
        self.slots = asyncio.Semaphore(2)
        self.queue_timeout, self.download_timeout = queue_timeout, download_timeout

    def path(self, uid, identifier):
        directory = self.store.user_directory(uid)
        key = hashlib.sha256(str(identifier).encode()).hexdigest()[:32]
        path = directory/(key+'.mp3')
        return path if path.is_file() and not path.is_symlink() and path.stat().st_size else None

    def touch(self, uid, identifier):
        path = self.path(uid, identifier)
        if path:
            os.utime(path, None)
        return path

    def trim(self, incoming):
        files = []
        if self.root.exists():
            for directory in self.root.iterdir():
                if directory.is_symlink() or not directory.is_dir() or not directory.name.isdecimal():
                    continue
                for path in directory.glob('*.mp3'):
                    if path.is_file() and not path.is_symlink():
                        stat = path.stat()
                        files.append((stat.st_mtime, stat.st_size, path))
        total = sum(size for _, size, _ in files)
        now = time.time()
        for modified, size, path in sorted(files):
            if now-modified < 60:
                continue
            if total+incoming <= self.limit and now-modified <= 86400:
                continue
            path.unlink(missing_ok=True)
            total -= size
        if total+incoming > self.limit:
            raise ValueError('Cache budget reached')

    def retain(self, uid, identifier, source):
        source = Path(source)
        if source.is_symlink() or not source.is_file() or not 0 < source.stat().st_size <= MEDIA_BYTES:
            raise ValueError('Invalid audio output')
        directory = self.store.user_directory(uid)
        self.trim(source.stat().st_size)
        key = hashlib.sha256(str(identifier).encode()).hexdigest()[:32]
        target = directory/(key+'.mp3')
        pending = directory/(secrets.token_hex(8)+'.pending')
        try:
            shutil.copyfile(source, pending)
            os.replace(pending, target)
        finally:
            pending.unlink(missing_ok=True)
        return target

    def start(self, uid, song):
        now = time.monotonic()
        for token, job in list(self.jobs.items()):
            if (not job.task or job.task.done()) and now-job.created > 600:
                self.jobs.pop(token)
        for job in self.jobs.values():
            if job.uid == uid and job.task and not job.task.done():
                if job.song['id'] == song['id']:
                    return job
                raise ValueError('User already preparing audio')
        if not self.downloader or len(self.jobs) >= 100 or sum(bool(j.task and not j.task.done()) for j in self.jobs.values()) >= 8:
            raise ValueError('Preparation capacity reached')
        job = Job(uid, dict(song), operation=Operation(uid))
        self.jobs[job.token] = job
        job.task = asyncio.create_task(self.work(job))
        return job

    async def work(self, job):
        source = None
        worker = None
        timed_out = False
        acquired = False
        marker = _current.set(job.operation)
        try:
            try:
                await asyncio.wait_for(self.slots.acquire(), timeout=self.queue_timeout)
                acquired = True
            except asyncio.TimeoutError:
                job.state, job.error = 'failed', 'queueTimeout'
                return
            if acquired:
                checkpoint()
                job.state = 'downloading'
                from media_recovery import download_with_reserve
                worker = asyncio.create_task(asyncio.to_thread(download_with_reserve,self.downloader,job.song['url'],job.song))
                done, _ = await asyncio.wait([worker], timeout=self.download_timeout)
                if not done:
                    timed_out = True
                    job.state, job.error = 'failed', 'downloadTimeout'
                    job.operation.stopped.set()
                    # Keep the worker slot until cooperative cleanup actually finishes.
                    # Reporting the timeout must not spawn more unbounded download threads.
                source, metadata = await asyncio.shield(worker)
                checkpoint()
                if metadata.get('source')=='Jamendo':
                    job.song.update({k:metadata[k] for k in ('title','artist','duration','source','license_url')})
                    job.song['url']=metadata['source_url']
                # One event loop serializes all budget checks and atomic cache promotions.
                self.retain(job.uid, job.song['id'], source)
                job.state = 'ready'
        except OperationCancelled:
            job.state = 'failed' if timed_out else 'cancelled'
        except asyncio.CancelledError:
            job.operation.stopped.set()
            if worker:
                try:
                    source, _ = await asyncio.shield(worker)
                except (Exception, OperationCancelled):
                    pass
            job.state = 'cancelled'
        except Exception:
            job.state = 'failed'
            if not job.error: job.error = 'prepareFailed'
        finally:
            if acquired: self.slots.release()
            _current.reset(marker)
            if source:
                from scratch import remove_owned_file
                remove_owned_file(source)

    def get(self, uid, token):
        job = self.jobs.get(token)
        return job if job and job.uid == uid else None

    def cancel(self, uid, token):
        job = self.get(uid, token)
        if job and job.state in ('queued','downloading'):
            job.operation.stopped.set()
            if job.state == 'queued':
                job.state = 'cancelled'
                job.task.cancel()
            else:
                job.state = 'cancelling'
        return job

    async def close(self):
        tasks = []
        for job in self.jobs.values():
            if job.task and not job.task.done():
                job.operation.stopped.set()
                tasks.append(job.task)
        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=20)
            except asyncio.TimeoutError:
                pass
