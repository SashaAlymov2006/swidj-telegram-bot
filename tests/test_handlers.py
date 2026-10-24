"""Exercise actual handler bodies offline; SDK integration is a separate check."""
import ast
import asyncio
import os
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from access import AccessPolicy


def load_handler(name, namespace):
    from operations import checkpoint, stage
    namespace.setdefault('checkpoint', checkpoint)
    namespace.setdefault('stage', stage)
    path = Path(__file__).resolve().parents[1] / 'bot.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef)) and n.name == name)
    node.returns = None
    for arg in node.args.args:
        arg.annotation = None
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_forged_admin_callback_cannot_create_broadcast(self):
        state = {}
        namespace = {'re': re, 'access_policy': AccessPolicy(frozenset({123})), 'broadcast_state': state}
        handler = load_handler('handle_callback', namespace)
        message = SimpleNamespace(reply_text=AsyncMock())
        query = SimpleNamespace(data='admin_send', from_user=SimpleNamespace(id=789),
                                answer=AsyncMock(), message=message)
        update = SimpleNamespace(callback_query=query, effective_user=query.from_user)
        await handler(update, SimpleNamespace(user_data={}))
        self.assertEqual(state, {})
        message.reply_text.assert_awaited_once()

    async def test_download_opens_picker_without_sending_unselected_audio(self):
        from unittest.mock import patch
        song = {'id': 7, 'title': 'Track', 'artist': 'Artist'}
        namespace = {'re': re, 'user_search_results': {789: [song]}}
        namespace['request_library_download'] = load_handler('request_library_download', namespace)
        handler = load_handler('handle_callback', namespace)
        query = SimpleNamespace(data='download_7', from_user=SimpleNamespace(id=789),
                                answer=AsyncMock(), message=SimpleNamespace(reply_text=AsyncMock()))
        update = SimpleNamespace(callback_query=query, effective_user=query.from_user)
        context = SimpleNamespace(user_data={}, bot=SimpleNamespace(send_audio=AsyncMock()))
        with patch('versions.request_versions', new_callable=AsyncMock) as picker:
            await handler(update, context)
            picker.assert_awaited_once_with(update, context, song)
        context.bot.send_audio.assert_not_awaited()

    async def test_effect_failure_preserves_source_and_does_not_send_partial_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'original.mp3';source.write_bytes(b'fixture')
            sender = AsyncMock()
            namespace = {'re': re, 'os': os, 'tempfile': tempfile, 'scratch_root': lambda: directory,
                         'apply_audio_effect': AsyncMock(return_value=False)}
            handler = load_handler('handle_callback', namespace)
            query = SimpleNamespace(data='apply_effects', from_user=SimpleNamespace(id=1), answer=AsyncMock(),
                message=SimpleNamespace(reply_text=AsyncMock(), reply_audio=sender))
            await handler(SimpleNamespace(callback_query=query), SimpleNamespace(user_data={
                'last_audio_path': str(source), 'pending_effects': ['reverb', 'echo']}))
            self.assertTrue(source.exists())
            sender.assert_not_awaited()
            self.assertEqual(namespace['apply_audio_effect'].await_count, 1)

    async def test_old_download_menu_keeps_its_original_url(self):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / 'result.mp3';audio.write_bytes(b'fixture')
            seen = []
            def download(url):
                seen.append(url)
                return str(audio), {}
            async def send(**kwargs):
                self.assertEqual(kwargs['audio'].input_file_content, b'fixture')
            namespace = {'os': os, 'asyncio': asyncio, 'download_youtube_audio': download,
                         'extract_youtube_metadata': lambda _: ('Track', 'Artist'),
                         'retain_download': AsyncMock()}
            load_handler('download_song', namespace)
            handler = load_handler('download_callback', namespace)
            message = SimpleNamespace(chat_id=1, reply_text=AsyncMock())
            query = SimpleNamespace(data='dl_audio|oldtoken', message=message, answer=AsyncMock())
            context = SimpleNamespace(user_data={'dl_platform': 'youtube', 'dl_url': 'new-url',
                'dl_requests': {'oldtoken': {'platform': 'youtube', 'url': 'old-url'}}},
                bot=SimpleNamespace(send_audio=AsyncMock(side_effect=send)))
            await handler(SimpleNamespace(callback_query=query), context)
            self.assertEqual(seen, ['old-url'])
