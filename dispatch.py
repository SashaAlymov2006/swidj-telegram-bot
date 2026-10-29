"""Serialize one user's updates while allowing other users to progress."""
import asyncio
import functools
from weakref import WeakValueDictionary
from contextlib import asynccontextmanager

_locks = WeakValueDictionary()


class QueueFull(ValueError):
    pass


class WorkQueue:
    """Bounded admission with cancellable FIFO waiting and one request per user."""
    def __init__(self, workers=1, capacity=24, timeout=600):
        self.slots=asyncio.Semaphore(workers);self.capacity=capacity;self.timeout=timeout;self.entries={}

    def status(self,uid):
        if uid not in self.entries:return {'status':'idle','position':0}
        entry=self.entries[uid]
        waiting=[key for key,value in self.entries.items() if value=='queued']
        return {'status':entry,'position':waiting.index(uid)+1 if entry=='queued' else 0}

    @asynccontextmanager
    async def enter(self,uid):
        if uid in self.entries or len(self.entries)>=self.capacity:raise QueueFull('Queue capacity reached')
        self.entries[uid]='queued';acquired=False
        try:
            await asyncio.wait_for(self.slots.acquire(),self.timeout);acquired=True;self.entries[uid]='processing'
            yield
        finally:
            if acquired:self.slots.release()
            self.entries.pop(uid,None)


def user_lock(user_id):
    """Shared by Telegram updates and authenticated Mini App operations."""
    lock = _locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[user_id] = lock
    return lock


def serialize_user(handler):
    @functools.wraps(handler)
    async def wrapped(update, context):
        user = getattr(update, 'effective_user', None)
        if user is None:
            return await handler(update, context)
        lock = user_lock(user.id)
        async with lock:
            application = getattr(context, 'application', None)
            hooks = getattr(application, 'bot_data', {})
            if hooks.get('before_update'):
                await hooks['before_update'](update, context)
            from i18n_ui import locale, action
            language = getattr(context, "user_data", {}).get("language", "ru")
            marker = locale.set(language)
            tag = action.set(getattr(getattr(update, "callback_query", None), "data", None) or handler.__name__)
            try:
                controls = hooks.get("controls")
                if controls and not await controls.admit(handler, update, context):
                    return
                try:
                    from operations import run_handler
                    return await run_handler(handler, update, context)
                finally:
                    if hooks.get('after_update'):
                        await hooks['after_update'](update, context)
            finally:
                action.reset(tag)
                locale.reset(marker)
    return wrapped
