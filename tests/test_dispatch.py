import asyncio
import unittest
from types import SimpleNamespace
from dispatch import serialize_user


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_user_serialized_other_user_can_progress(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        events = []
        @serialize_user
        async def handler(update, context):
            events.append(('start', update.name))
            if update.name == 'first':
                entered.set()
                await release.wait()
            events.append(('end', update.name))
        def update(uid, name):
            return SimpleNamespace(effective_user=SimpleNamespace(id=uid), name=name)
        first = asyncio.create_task(handler(update(1, 'first'), None))
        await entered.wait()
        second = asyncio.create_task(handler(update(1, 'second'), None))
        await handler(update(2, 'other'), None)
        self.assertNotIn(('start', 'second'), events)
        self.assertIn(('end', 'other'), events)
        release.set()
        await asyncio.gather(first, second)
        self.assertLess(events.index(('end', 'first')), events.index(('start', 'second')))

    async def test_access_control_sees_restored_session_before_handler(self):
        from unittest.mock import AsyncMock
        seen = []
        async def restore(update, context):
            context.user_data["awaiting_pitch"] = True
        async def admit(handler, update, context):
            seen.append(context.user_data.get("awaiting_pitch"))
            return False
        context = SimpleNamespace(user_data={}, application=SimpleNamespace(bot_data={
            "before_update": restore, "controls": SimpleNamespace(admit=admit)}))
        update = SimpleNamespace(effective_user=SimpleNamespace(id=77))
        called = AsyncMock()
        @serialize_user
        async def handle_message(update, context):
            await called()
        await handle_message(update, context)
        self.assertEqual(seen, [True])
        called.assert_not_awaited()
