"""Serialize one user's updates while allowing other users to progress."""
import asyncio
import functools
from weakref import WeakValueDictionary

_locks = WeakValueDictionary()


def serialize_user(handler):
    @functools.wraps(handler)
    async def wrapped(update, context):
        user = getattr(update, 'effective_user', None)
        if user is None:
            return await handler(update, context)
        lock = _locks.get(user.id)
        if lock is None:
            lock = asyncio.Lock()
            _locks[user.id] = lock
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
