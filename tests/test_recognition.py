import asyncio
import unittest
from unittest.mock import AsyncMock
from recognition_flow import identify


class RecognitionTests(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_after_service_failure(self):
        first = AsyncMock(side_effect=OSError('fixture failure'))
        second = AsyncMock(return_value={'title': 'Track', 'artist': 'Artist'})
        result, attempts = await identify('fixture.wav', [('first', first), ('second', second)])
        self.assertEqual(result['title'], 'Track')
        self.assertEqual(attempts, [('first', 'unavailable'), ('second', 'matched')])

    async def test_timeout_and_incomplete_result_do_not_stop_fallback(self):
        async def slow(_):
            await asyncio.sleep(1)
        result, attempts = await identify('fixture.wav', [('slow', slow),
            ('invalid', AsyncMock(return_value={'title': 'incomplete'})),
            ('none', AsyncMock(return_value=None))], timeout=0.01)
        self.assertIsNone(result)
        self.assertEqual(attempts, [('slow', 'unavailable'), ('invalid', 'no_match'), ('none', 'no_match')])

    async def test_success_skips_remaining_providers(self):
        other = AsyncMock()
        result, _ = await identify('fixture.wav', [
            ('first', AsyncMock(return_value={'title': 'Track', 'artist': 'Artist'})), ('other', other)])
        self.assertIsNotNone(result)
        other.assert_not_awaited()
