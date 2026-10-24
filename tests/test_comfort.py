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
