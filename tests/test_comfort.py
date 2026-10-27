import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from operations import Operation, OperationCancelled, checkpoint, cancel, run_process, _active, _current
from dispatch import serialize_user
from lyrics_search import phrases, search_lyrics
from versions import find_versions, request_versions, choose_version
from effect_preview import accept_preview


class ComfortUnitTests(unittest.TestCase):
    def test_version_results_are_safe_deduplicated_and_keep_duration(self):
        manager = MagicMock()
        manager.__enter__.return_value.extract_info.return_value = {"entries": [
            {"id": "abcdefghijk", "title": "Track", "duration": 182},
            {"id": "abcdefghijk", "title": "Duplicate"},
            {"id": "../private", "url": "http://127.0.0.1"},
            {"id": "lmnopqrstuv", "title": "Live", "is_live": True},
        ]}
        with patch("versions.yt_dlp.YoutubeDL", return_value=manager):
            songs = find_versions("Song")
        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0]["duration"], 182)
        self.assertEqual(songs[0]["url"], "https://www.youtube.com/watch?v=abcdefghijk")

    def test_preview_confirmation_rejects_changed_source_or_effects(self):
        state = {"last_audio_path": "source", "pending_effects": ["echo"],
                 "effect_preview": {"token": "token", "source": "source", "selected": ["echo"]}}
        context = SimpleNamespace(user_data=state)
        self.assertFalse(accept_preview(context, "other"))
        state["pending_effects"] = ["normalize"]
        self.assertFalse(accept_preview(context, "token"))
        state["pending_effects"] = ["echo"]
        self.assertTrue(accept_preview(context, "token"))
        self.assertFalse(accept_preview(context, "token"))


class ComfortAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        inventory=patch('versions.source_inventory',new_callable=AsyncMock,return_value={'yt':[], 'sc':[], 'jam':[]})
        inventory.start();self.addCleanup(inventory.stop)
        preflight=patch('recording_availability.available',return_value=True)
        preflight.start();self.addCleanup(preflight.stop)
    async def test_other_versions_survive_cached_delivery_and_source_block(self):
        from versions import download_selected, show_versions
        candidates = [dict(id=i, title="Song", artist="Artist", url=f"https://example.com/{i}") for i in range(3)]
        context = SimpleNamespace(user_data={}, bot=SimpleNamespace())
        update = SimpleNamespace(effective_chat=SimpleNamespace(id=77), effective_user=SimpleNamespace(id=77))
        request = dict(song=candidates[0], candidates=candidates, mode="listen")
        with patch("audio_presentation.send_cached_music", new_callable=AsyncMock, return_value=True) as cached, patch("track_card.retire_download_menus", new_callable=AsyncMock):
            self.assertTrue(await download_selected(update, context, "0123456789", request, 0, None, None, None, None))
        markup = cached.call_args.kwargs["reply_markup"]
        self.assertIn("ver:other:0123456789:0", [b.callback_data for row in markup.inline_keyboard for b in row])
        with patch("versions.version_screen", new_callable=AsyncMock) as screen:
            await show_versions(update, context, "0123456789", request, exclude=0)
        callbacks = [b.callback_data for row in screen.call_args.args[3].inline_keyboard for b in row]
        self.assertNotIn("ver:pick:0123456789:0", callbacks)
        self.assertIn("ver:pick:0123456789:1", callbacks)
        self.assertIn("ver:pick:0123456789:2", callbacks)
        request['source'] = 'sc'
        with patch("audio_presentation.send_cached_music", new_callable=AsyncMock, return_value=False), patch("media_recovery.download_with_reserve", side_effect=RuntimeError("blocked")), patch("diagnostics.source_access_blocked", return_value=True), patch("versions.version_screen", new_callable=AsyncMock) as screen:
            self.assertFalse(await download_selected(update, context, "0123456789", request, 1, None, None, None, None))
        callbacks = [b.callback_data for row in screen.call_args.args[3].inline_keyboard for b in row]
        self.assertIn("ver:other:0123456789:1", callbacks)

    async def test_independent_provider_choices_keep_catalog_identity_and_exact_selected_url(self):
        catalog = dict(id=91, title='Perfect', artist='Ed Sheeran')
        failed = dict(title='Ed Sheeran - Perfect [Official Lyric Video]', artist='Uploader', duration=264, url='https://www.youtube.com/watch?v=abcdefghijk')
        candidate = dict(title='Perfect', artist='Another singer', duration=265.222, source='SoundCloud', url='https://soundcloud.com/singer/perfect-cover')
        context = SimpleNamespace(user_data={'version_requests': {'0123456789': dict(song=catalog,candidates=[failed],mode='listen')}}, bot=SimpleNamespace())
        update = SimpleNamespace(callback_query=SimpleNamespace(data='ver:source:0123456789:sc',answer=AsyncMock()),effective_chat=SimpleNamespace(id=77),effective_user=SimpleNamespace(id=77))
        with patch('soundcloud_source.search', return_value=[candidate]) as search, patch('versions.find_versions') as youtube, patch('versions.version_screen', new_callable=AsyncMock):
            await choose_version(update, context, None, None, None, None)
        search.assert_called_once_with('Perfect Ed Sheeran',10)
        youtube.assert_not_called()
        token = next(reversed(context.user_data['version_requests']))
        selected = context.user_data['version_requests'][token]
        self.assertEqual(selected['song'],catalog)
        self.assertEqual(selected['source'],'sc')
        self.assertEqual(selected['candidates'],[candidate])
        update.callback_query.data = f'ver:pick:{token}:0'
        with patch('audio_presentation.send_cached_music',new_callable=AsyncMock,return_value=True) as cached, patch('track_card.retire_download_menus',new_callable=AsyncMock),patch('media_recovery.download_with_reserve') as download:
            self.assertTrue(await choose_version(update,context,None,None,None,None))
        self.assertEqual(cached.call_args.args[2],candidate['url'])
        download.assert_not_called()
        update.callback_query.data = f'ver:source:{token}:jam'
        with patch('jamendo_source.search',return_value=[]) as search,patch('versions.version_screen',new_callable=AsyncMock):
            await choose_version(update,context,None,None,None,None)
        search.assert_called_once_with('Perfect Ed Sheeran',10)

    async def test_blocked_youtube_offers_new_catalog_search_after_exact_reserve_failed(self):
        from versions import download_selected
        original=dict(id=1,title='Perfect',artist='Ed Sheeran')
        request=dict(song=original,candidates=[dict(title='Video title',artist='Uploader',url='https://www.youtube.com/watch?v=abcdefghijk')],mode='listen')
        update=SimpleNamespace(effective_chat=SimpleNamespace(id=77))
        with patch('audio_presentation.send_cached_music',new_callable=AsyncMock,return_value=False),patch('media_recovery.download_with_reserve',side_effect=RuntimeError("Sign in to confirm you're not a bot")),patch('versions.request_versions',new_callable=AsyncMock) as search:
            self.assertFalse(await download_selected(update,SimpleNamespace(user_data={},bot=None),'0123456789',request,0,None,None,None,None))
        self.assertEqual(search.call_args.args[2],original)
        self.assertEqual(search.call_args.kwargs['source'],'sc')

    async def test_lyrics_search_boosts_verified_phrase_and_bounds_requests(self):
        query = "these are the words I remember"
        false = {"id": 1, "title": "Wrong", "artist": "A", "url": "https://genius.com/wrong"}
        right = {"id": 2, "title": "Right", "artist": "B", "url": "https://genius.com/right"}
        genius = AsyncMock(return_value=[false, right])
        deezer = AsyncMock(return_value=[])
        lyrics = AsyncMock(side_effect=lambda url: query if url.endswith("right") else "unrelated text")
        songs = await search_lyrics(query, genius, deezer, lyrics)
        self.assertEqual(songs[0]["id"], 2)
        self.assertTrue(songs[0]["lyrics_match"])
        self.assertFalse(songs[1]["lyrics_match"])
        self.assertLessEqual(len(phrases("word " * 100)), 2)
        self.assertEqual(genius.await_count, 1)

    async def test_lyrics_does_not_fetch_arbitrary_provider_links(self):
        songs = [{"id": 1, "title": "T", "artist": "A", "url": "http://127.0.0.1/secret"}]
        lyrics = AsyncMock()
        await search_lyrics("words", AsyncMock(return_value=songs), AsyncMock(return_value=[]), lyrics)
        lyrics.assert_not_awaited()

    async def test_version_choice_uses_original_snapshot_and_exact_url(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.mp3"
            path.write_bytes(b"fixture")
            candidates = [{"url": "https://www.youtube.com/watch?v=abcdefghijk", "title": "Original choice",
                           "artist": "A", "duration": 180, "cover": None}]
            context = SimpleNamespace(user_data={}, bot=SimpleNamespace(send_audio=AsyncMock()))
            message = SimpleNamespace(reply_text=AsyncMock())
            update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=77),
                                     effective_chat=SimpleNamespace(id=77))
            with patch("versions.find_versions", return_value=candidates):
                await request_versions(update, context, {"title": "Old", "artist": "A", "id": 1})
            token = next(iter(context.user_data["version_requests"]))
            # A different search must not mutate the original request.
            with patch("versions.find_versions", return_value=[dict(candidates[0], title="Different")]):
                await request_versions(update, context, {"title": "New", "artist": "B", "id": 2})
            update.callback_query = SimpleNamespace(data=f"ver:pick:{token}:0", answer=AsyncMock())
            downloader = MagicMock(return_value=(str(path), {}))
            with patch("versions.send_music", new_callable=AsyncMock) as sender:
                await choose_version(update, context, downloader, lambda _: (None, None), AsyncMock(), AsyncMock())
            downloader.assert_called_once_with(candidates[0]["url"])
            self.assertEqual(sender.await_args.args[3], "Original choice")
            self.assertFalse(path.exists())

    async def test_cancel_bypasses_user_lock_and_waits_for_worker_cleanup(self):
        entered, finished = threading.Event(), threading.Event()
        status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
        message = SimpleNamespace(reply_text=AsyncMock(return_value=status))
        update = SimpleNamespace(effective_user=SimpleNamespace(id=77), effective_message=message)
        context = SimpleNamespace(application=SimpleNamespace(bot_data={}))
        with tempfile.TemporaryDirectory() as directory:
            partial = Path(directory) / "partial"
            def worker():
                try:
                    partial.write_bytes(b"partial")
                    entered.set()
                    while True:
                        checkpoint()
                        time.sleep(0.01)
                finally:
                    partial.unlink(missing_ok=True)
                    finished.set()
            @serialize_user
            async def versions_callback(update, context):
                await asyncio.to_thread(worker)
                raise AssertionError("Cancelled worker must not produce an upload")
            task = asyncio.create_task(versions_callback(update, context))
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            token = _active[77].token
            self.assertFalse(cancel(78, token))
            self.assertFalse(cancel(77, "old-token"))
            self.assertTrue(cancel(77, token))
            await asyncio.wait_for(task, 3)
            self.assertTrue(finished.is_set())
            self.assertFalse(partial.exists())
            self.assertNotIn(77, _active)
            status.edit_text.assert_awaited_with("Отменено.")

    async def test_cancel_terminates_running_child_process(self):
        with tempfile.TemporaryDirectory() as directory:
            pidfile = Path(directory) / "pid"
            op = Operation(77)
            marker = _current.set(op)
            try:
                code = "import os,time; from pathlib import Path; Path(" + repr(str(pidfile)) + ").write_text(str(os.getpid())); time.sleep(60)"
                task = asyncio.create_task(asyncio.to_thread(run_process, [sys.executable, "-c", code], check=True))
                deadline = time.monotonic() + 3
                while not pidfile.exists() and time.monotonic() < deadline:
                    await asyncio.sleep(0.01)
                self.assertTrue(pidfile.exists())
                pid = int(pidfile.read_text())
                op.stopped.set()
                with self.assertRaises(OperationCancelled):
                    await asyncio.wait_for(task, 3)
                if os.name == "posix":
                    with self.assertRaises(ProcessLookupError):
                        os.kill(pid, 0)
            finally:
                _current.reset(marker)
