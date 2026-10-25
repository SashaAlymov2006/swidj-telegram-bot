"""Full application + real Telegram SDK against an in-process HTTP transport.

No credentials, remote requests, messages to real users, or paid APIs.
"""
import asyncio
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, AsyncMock
from telegram import Update
from telegram.request import BaseRequest
from state_store import StateStore


class OfflineRequest(BaseRequest):
    def __init__(self):
        self.calls = []
        self.media = b''
        self.media_files = {}
        self.uploads = []

    @property
    def read_timeout(self):
        return 5

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    async def do_request(self, url, method, request_data=None, **kwargs):
        operation = url.rsplit('/', 1)[-1]
        params = request_data.parameters if request_data else {}
        self.calls.append((operation, params))
        if request_data:
            self.uploads.extend(request_data.multipart_data.values())
        if method == 'GET':
            return 200, self.media_files.get(url.rsplit('/', 1)[-1], self.media)
        if operation == 'getFile':
            result = {'file_id': 'fixture', 'file_unique_id': 'fixture', 'file_size': len(self.media), 'file_path': str(params.get('file_id', 'fixture')) + '.audio'}
        elif operation == 'getMe':
            result = {'id': 123456, 'is_bot': True, 'first_name': 'Offline', 'username': 'offline_test_bot'}
        elif operation in ('sendMessage', 'sendPhoto', 'sendAudio', 'sendVideo', 'sendDocument', 'sendVoice', 'editMessageText', 'editMessageCaption', 'editMessageMedia', 'editMessageReplyMarkup'):
            result = {'message_id': len(self.calls), 'date': 1,
                      'chat': {'id': int(params['chat_id']), 'type': 'private'},
                      'text': params.get('text', '')}
        elif operation in ('answerCallbackQuery', 'deleteMessage', 'setMyCommands', 'setChatMenuButton'):
            result = True
        else:
            raise AssertionError('Unexpected offline API operation: ' + operation)
        return 200, json.dumps({'ok': True, 'result': result}).encode()


class SDKTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = tempfile.TemporaryDirectory()
        cls.root = Path(cls.files.name)
        # Import actual bot with all installed runtime dependencies, no .env reads.
        with patch.dict(os.environ, {
            'PYTHON_DOTENV_DISABLED': '1', 'TELEGRAM_TOKEN': '123456:offline-test-token',
            'OWNER_USER_IDS': '', 'STATE_DB_PATH': str(cls.root / 'state.sqlite3'),
            'USERS_DB_PATH': str(cls.root / 'users.sqlite3'),
            'EXTERNAL_PAID_API_ENABLED': 'false',
        }):
            cls.bot = importlib.import_module('bot')

    @classmethod
    def tearDownClass(cls):
        cls.files.cleanup()

    async def asyncSetUp(self):
        self.local_files = tempfile.TemporaryDirectory()
        self.addCleanup(self.local_files.cleanup)
        local = Path(self.local_files.name)
        import scratch
        self.patches = [patch.dict(os.environ, {'AUDIO_CACHE_DIR': str(local / 'audio')}),
            patch.object(scratch, 'TEMP_ROOT', local / 'scratch'),
            patch.object(self.bot, 'state_store', StateStore(local / 'state.sqlite3')),
            patch.object(self.bot, 'USERS_DB_PATH', str(local / 'users.sqlite3'))]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.versions_patch = patch("versions.find_versions", return_value=[
            {"url": "https://www.youtube.com/watch?v=abcdefghijk", "title": "Fixture recording", "artist": "Artist", "duration": 180, "cover": None},
            {"url": "https://www.youtube.com/watch?v=lmnopqrstuv", "title": "Fixture live", "artist": "Artist", "duration": 210, "cover": None}])
        self.versions_patch.start()
        self.addCleanup(self.versions_patch.stop)
        self.cover_patch = patch("audio_presentation.fetch_cover", return_value=None)
        self.cover_patch.start()
        self.addCleanup(self.cover_patch.stop)
        self.card_cover_patch = patch("track_card.fetch_cover", return_value=None)
        self.card_cover_patch.start()
        self.addCleanup(self.card_cover_patch.stop)
        self.catalog_patch = patch("catalog_links.catalog_metadata", return_value={"title":"Catalog song","artist":"Artist","query":"Catalog song Artist"})
        self.catalog_patch.start()
        self.addCleanup(self.catalog_patch.stop)
        self.bot.broadcast_state.clear()
        self.request = OfflineRequest()
        self.app = self.bot.build_application(request=self.request, updates_request=OfflineRequest())
        self.bot.saved_sessions.clear()
        self.bot.user_search_history.clear()
        self.bot.user_favorites.clear()
        self.bot.user_search_results.clear()
        # Tests never touch or migrate a checkout's real users.db.
        with patch('state_store.migrate_users', return_value=False):
            await self.app.initialize()
            await self.bot.initialize_app(self.app)
        await self.app.start()

    async def asyncTearDown(self):
        await self.app.stop()
        await self.app.shutdown()

    def message(self, text=None, uid=77, voice=False):
        message = {'message_id': 10, 'date': 1,
            'chat': {'id': uid, 'type': 'private'},
            'from': {'id': uid, 'is_bot': False, 'first_name': 'Fixture'}}
        if text is not None:
            message['text'] = text
            if text.startswith('/'):
                message['entities'] = [{'type': 'bot_command', 'offset': 0, 'length': len(text.split()[0])}]
        if voice:
            message['voice'] = {'file_id': 'voice-fixture', 'file_unique_id': 'unique', 'duration': 5}
        return Update.de_json({'update_id': 10, 'message': message}, self.app.bot)

    def callback(self, data, uid=77):
        return Update.de_json({'update_id': 11, 'callback_query': {
            'id': 'fixture', 'chat_instance': 'fixture', 'data': data,
            'from': {'id': uid, 'is_bot': False, 'first_name': 'Fixture'},
            'message': {'message_id': 10, 'date': 1, 'chat': {'id': uid, 'type': 'private'},
                        'text': 'menu'}}}, self.app.bot)

    async def choose_latest_version(self, index=0):
        token = next(reversed(self.app.user_data[77]["version_requests"]))
        await self.app.process_update(self.callback(f"ver:pick:{token}:{index}"))

    async def test_https_miniapp_does_not_replace_native_bot_menu(self):
        with patch.dict(os.environ, {'MINIAPP_URL':'https://preview.example.test'}), \
             patch('state_store.migrate_users',return_value=False):
            await self.bot.initialize_app(self.app)
            menus=[data['menu_button'] for op,data in self.request.calls if op=='setChatMenuButton']
            menu=json.loads(menus[-1]) if isinstance(menus[-1],str) else menus[-1]
            self.assertEqual(menu['type'],'commands')
            await self.app.process_update(self.message('/app'))
            messages=[data for op,data in self.request.calls if op=='sendMessage']
            markup=messages[-1]['reply_markup']
            if isinstance(markup,str):markup=json.loads(markup)
            self.assertEqual(markup['inline_keyboard'][0][0]['web_app']['url'],'https://preview.example.test')

    def texts(self):
        return [params.get('text', '') for op, params in self.request.calls if op in ('sendMessage', 'editMessageText')]

    async def test_native_command_menu_and_search_navigation(self):
        calls=[(op,data) for op,data in self.request.calls if op in ("setMyCommands","setChatMenuButton")]
        self.assertEqual(sum(op=="setMyCommands" for op,_ in calls),3)
        public=next(data for op,data in calls if op=="setMyCommands" and "language_code" not in data)
        commands=public["commands"]
        if isinstance(commands,str):
            commands=json.loads(commands)
        self.assertEqual([item["command"] for item in commands],
                         ["menu","search","favorites","studio","help","cancel","start","language"])
        menu=next(data["menu_button"] for op,data in calls if op=="setChatMenuButton")
        if isinstance(menu,str):
            menu=json.loads(menu)
        self.assertEqual(menu["type"],"commands")
        self.app.user_data[77]["awaiting_ringtone"]="old"
        self.app.user_data[77]["awaiting_collection_name"]=True
        with patch.object(self.bot,"search_songs",new_callable=AsyncMock) as search:
            await self.app.process_update(self.message("/search"))
            search.assert_not_awaited()
        self.assertNotIn("awaiting_ringtone",self.app.user_data[77])
        self.assertNotIn("awaiting_collection_name",self.app.user_data[77])
        self.assertTrue(any("Как ищем?" in text for text in self.texts()))
        await self.app.process_update(self.message("/favorites"))
        self.assertTrue(any("Моя музыка" in text for text in self.texts()))

    async def test_full_startup_commands_and_restart_state(self):
        self.assertIsNone(self.bot.whisper_model)
        await self.app.process_update(self.message('/start'))
        self.assertTrue(any('Твой микс' in text for text in self.texts()))
        self.bot.user_search_history[77] = ['persisted track']
        self.bot.user_favorites[77] = [{'id': 7, 'title': '<Track>', 'artist': 'A&B'}]
        await self.bot.persist_user_state(77)
        await self.app.process_update(self.message('/history'))
        await self.app.process_update(self.message('/favorites'))
        await self.app.process_update(self.callback('lib:page:0'))
        self.assertTrue(any('persisted track' in text for text in self.texts()))
        self.assertTrue(any('<Track>' in str(params.get('reply_markup', ''))
                            for op, params in self.request.calls if op in ('sendMessage', 'editMessageText')))
        # Independent process proves data did not survive merely through module globals.
        code = '''from state_store import StateStore
import sys
h,f=StateStore(sys.argv[1]).load()
assert h[77]==['persisted track']
assert f[77][0]['id']==7
assert 78 not in h
'''
        result = await asyncio.to_thread(subprocess.run,
            [sys.executable, '-c', code, str(self.bot.state_store.path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        await self.app.process_update(self.message('/clearfavorites'))
        self.assertEqual(StateStore(self.bot.state_store.path).load()[1][77], [])

    async def test_voice_menu_routes_real_callback_without_network(self):
        await self.app.process_update(self.message(voice=True))
        self.assertTrue(any('Что сделать?' in text for text in self.texts()))
        with patch.object(self.bot, 'handle_voice', new_callable=AsyncMock) as handler:
            await self.app.process_update(self.callback('voice_recognize'))
            handler.assert_awaited_once()
            self.assertEqual(handler.await_args.args[0].message.voice.file_id, 'voice-fixture')

    async def test_invalid_callback_and_unknown_command_reply(self):
        await self.app.process_update(self.callback('fav_broken'))
        await self.app.process_update(self.message('/not_a_command'))
        self.assertTrue(any('команд' in text.lower() for text in self.texts()))
        self.assertNotIn(77, self.bot.user_favorites)

    async def test_owner_denied_and_other_user_cannot_read_history(self):
        self.bot.user_search_history[77] = ['private needle']
        await self.app.process_update(self.message('/history', uid=78))
        await self.app.process_update(self.callback('admin_send', uid=78))
        self.assertFalse(any('private needle' in text for text in self.texts()))
        self.assertTrue(any('доступ' in text.lower() for text in self.texts()))

    async def test_audio_upload_effects_chain_reverse_pitch_and_loop(self):
        from pydub.generators import Sine
        import io
        encoded = io.BytesIO()
        Sine(440).to_audio_segment(duration=4000).export(encoded, format='ogg', codec='libopus')
        self.request.media = encoded.getvalue()
        update = self.message(voice=True)
        await self.app.process_update(update)
        await self.app.process_update(self.callback('voice_effects'))
        source = Path(self.app.user_data[77]['last_audio_path'])
        self.assertTrue(source.exists())
        for choice in ['toggle_echo', 'toggle_normalize', 'apply_effects',
                       'reverse_audio', 'make_loop', 'detect_chords', 'pitch_detect']:
            await self.app.process_update(self.callback(choice))
        await self.app.process_update(self.message('3'))
        self.assertTrue(source.exists())
        self.assertGreaterEqual(sum(op == 'sendAudio' for op, _ in self.request.calls), 4)
        await self.app.process_update(self.callback('effect_speed_up'))
        self.assertTrue(source.exists())
        self.assertFalse(self.app.user_data[77].get('awaiting_pitch'))

    async def test_studio_tools_work_through_registered_handlers(self):
        from pydub.generators import Sine
        from pydub import AudioSegment
        import io
        import scratch
        encoded = io.BytesIO()
        Sine(440).to_audio_segment(duration=4000).export(encoded, format="ogg", codec="libopus")
        self.request.media = encoded.getvalue()
        await self.app.process_update(self.message(voice=True))
        await self.app.process_update(self.callback("voice_effects"))
        source = Path(self.app.user_data[77]["last_audio_path"])
        original = source.read_bytes()
        before_files = set(scratch.scratch_root().iterdir())
        await self.app.process_update(self.callback("studio:group:level"))
        await self.app.process_update(self.callback("toggle_normalize"))
        self.assertEqual(self.app.user_data[77]["studio_category"], "level")
        self.assertIn("normalize", self.app.user_data[77]["pending_effects"])
        await self.app.process_update(self.callback("studio:reset"))
        self.assertEqual(self.app.user_data[77]["pending_effects"], [])
        self.app.user_data[77]["downloaded_song"].update(title="Example track", artist="Example artist")
        await self.app.process_update(self.callback("studio:formats"))
        self.assertTrue(any("без сжатия" in text for text in self.texts()))
        for action in ("studio:info", "studio:preview", "studio:mp3", "studio:wav", "studio:trim"):
            await self.app.process_update(self.callback(action))
            if action in ("studio:mp3", "studio:wav"):
                kind = action.split(":")[-1]
                filename, content = self.request.uploads[-1][:2]
                self.assertIn("Example track", filename)
                self.assertTrue(filename.endswith("." + kind))
                with io.BytesIO(content) as exported:
                    self.assertAlmostEqual(len(AudioSegment.from_file(exported, format=kind)), 4000, delta=150)
        await self.app.process_update(self.message("0:01 0:03"))
        await self.app.process_update(self.message("/studio"))
        self.assertTrue(any("Длительность:" in text for text in self.texts()))
        self.assertTrue(any(op == "sendDocument" for op, _ in self.request.calls))
        self.assertGreaterEqual(sum(op == "sendAudio" for op, _ in self.request.calls), 3)
        with io.BytesIO(self.request.uploads[-1][1]) as audio:
            self.assertAlmostEqual(len(AudioSegment.from_file(audio, format="mp3")), 2000, delta=150)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(set(scratch.scratch_root().iterdir()), before_files)

    async def test_studio_invalid_trim_and_other_user_never_receive_audio(self):
        before = len(self.request.uploads)
        await self.app.process_update(self.message("/trim nonsense 2"))
        await self.app.process_update(self.callback("studio:mp3", uid=78))
        self.assertEqual(len(self.request.uploads), before)
        self.assertTrue(any("Сначала пришли" in text for text in self.texts()))

    async def test_effect_preview_then_confirmed_full_track_preserves_source(self):
        from pydub.generators import Sine
        from pydub import AudioSegment
        import io
        encoded = io.BytesIO()
        Sine(440).to_audio_segment(duration=18000).export(encoded, format="ogg", codec="libopus")
        self.request.media = encoded.getvalue()
        await self.app.process_update(self.message(voice=True))
        await self.app.process_update(self.callback("voice_effects"))
        source = Path(self.app.user_data[77]["last_audio_path"])
        original = source.read_bytes()
        await self.app.process_update(self.callback("toggle_echo"))
        await self.app.process_update(self.callback("fx:preview"))
        token = self.app.user_data[77]["effect_preview"]["token"]
        with io.BytesIO(self.request.uploads[-1][1]) as audio:
            self.assertAlmostEqual(len(AudioSegment.from_file(audio, format="mp3")), 15000, delta=150)
        await self.app.process_update(self.callback("fx:apply:" + token))
        with io.BytesIO(self.request.uploads[-1][1]) as audio:
            self.assertGreater(len(AudioSegment.from_file(audio, format="mp3")), 17000)
        before = len(self.request.uploads)
        await self.app.process_update(self.callback("fx:apply:" + token))
        self.assertEqual(len(self.request.uploads), before)
        self.assertEqual(source.read_bytes(), original)

    async def test_favorites_collections_persist_and_do_not_leak_to_another_user(self):
        song = {"id": 1, "title": "Private track", "artist": "Artist", "url": "https://genius.com/song"}
        self.bot.user_favorites[77] = [song]
        await self.bot.persist_user_state(77)
        await self.app.process_update(self.message("/collection Workout"))
        key = next(iter(self.app.user_data[77]["music_collections"]))
        await self.app.process_update(self.callback("lib:save:" + key + ":1"))
        saved = StateStore(self.bot.state_store.path).load_named("music_collections")
        self.assertEqual(saved[77][key]["songs"][0]["id"], 1)
        self.app.user_data[77].pop("music_collections")
        await self.app.process_update(self.callback("lib:col:" + key))
        self.assertIn(key, self.app.user_data[77]["music_collections"])
        await self.app.process_update(self.callback("lib:cd:" + key + ":1"))
        self.assertEqual(len(self.bot.user_favorites[77]), 1)
        self.assertEqual(self.app.user_data[77]["music_collections"][key]["songs"], [])
        await self.app.process_update(self.callback("lib:save:" + key + ":1"))
        await self.app.process_update(self.callback("lib:delete:1"))
        self.assertEqual(len(self.bot.user_favorites[77]), 1)
        await self.app.process_update(self.callback("lib:confirmdelete:1"))
        self.assertEqual(self.bot.user_favorites[77], [])
        self.assertEqual(StateStore(self.bot.state_store.path).load_named("music_collections")[77][key]["songs"], [])
        before = len(self.request.calls)
        await self.app.process_update(self.callback("lib:col:" + key, uid=78))
        outgoing = str(self.request.calls[before:])
        self.assertNotIn("Private track", outgoing)
        self.assertNotIn("Workout", outgoing)

    async def test_cancel_button_interrupts_a_real_inflight_download_without_upload(self):
        import threading
        import time
        from operations import checkpoint, _active
        entered = threading.Event()
        finished = threading.Event()
        partial = Path(self.local_files.name) / "partial-download"
        def download(url):
            try:
                partial.write_bytes(b"partial")
                entered.set()
                while True:
                    checkpoint()
                    time.sleep(0.01)
            finally:
                partial.unlink(missing_ok=True)
                finished.set()
        self.bot.user_search_results[77] = [{"id": 1, "title": "Track", "artist": "Artist", "url": "https://genius.com/song"}]
        await self.app.process_update(self.callback("download_1"))
        token = next(iter(self.app.user_data[77]["version_requests"]))
        before = len(self.request.uploads)
        with patch.object(self.bot, "download_youtube_audio", side_effect=download):
            job = asyncio.create_task(self.app.process_update(self.callback(f"ver:pick:{token}:0")))
            self.assertTrue(await asyncio.to_thread(entered.wait, 3))
            cancel_token = _active[77].token
            await self.app.process_update(self.callback("op:cancel:" + cancel_token, uid=78))
            self.assertFalse(_active[77].stopped.is_set())
            await self.app.process_update(self.callback("op:cancel:" + cancel_token))
            await asyncio.wait_for(job, 3)
        self.assertTrue(finished.is_set())
        self.assertFalse(partial.exists())
        self.assertEqual(len(self.request.uploads), before)
        self.assertNotIn(77, _active)
        self.assertTrue(any(op == "editMessageText" and params.get("text") == "Отменено." for op, params in self.request.calls))

    async def test_compact_home_help_hide_inactive_features_and_internal_names(self):
        await self.app.process_update(self.message("/start"))
        await self.app.process_update(self.message("/help"))
        await self.app.process_update(self.message(voice=True))
        texts = "\n".join(self.texts())
        for word in ("Whisper", "Shazam", "пока", "позже", "не подключ"):
            self.assertNotIn(word, texts)
        self.assertTrue(all(len(text) < 650 for text in self.texts()))
        markups = [params.get("reply_markup", {}) for op, params in self.request.calls if op == "sendMessage"]
        serialized = str(markups)
        self.assertNotIn("voice_recognize", serialized)
        self.assertIn("voice_words", serialized)

    async def test_owner_panel_rejects_forged_buttons_and_preserves_owner_access(self):
        from access import AccessPolicy
        controls = self.app.bot_data["controls"]
        await self.app.process_update(self.callback("owner:maintenance", uid=78))
        self.assertFalse(controls.settings["maintenance"])
        with patch.object(self.bot, "access_policy", AccessPolicy(frozenset({77}))):
            await self.app.process_update(self.message("/admin"))
            await self.app.process_update(self.callback("owner:stats"))
            await self.app.process_update(self.callback("owner:maintenance"))
            self.assertTrue(controls.settings["maintenance"])
            with patch.object(self.bot, "search_songs", new_callable=AsyncMock) as search:
                await self.app.process_update(self.message("words", uid=78))
                search.assert_not_awaited()
            await self.app.process_update(self.message("/admin"))
            await self.app.process_update(self.callback("owner:maintenance"))
            await self.app.process_update(self.callback("owner:block"))
            await self.app.process_update(self.message("78"))
            self.assertIn(78, controls.settings["blocked"])
            await self.app.process_update(self.callback("owner:block"))
            await self.app.process_update(self.message("77"))
            self.assertNotIn(77, controls.settings["blocked"])
            await self.app.process_update(self.message("/cancel"))
            await self.app.process_update(self.callback("owner:unblock"))
            await self.app.process_update(self.message("78"))
            self.assertNotIn(78, controls.settings["blocked"])
            await self.app.process_update(self.callback("owner:toggle:downloads"))
            self.assertFalse(controls.enabled("downloads"))
            await self.app.process_update(self.callback("owner:toggle:downloads"))
        self.assertTrue(any("Пользователей:" in text for text in self.texts()))
        self.assertTrue(any("Владельца нельзя" in text for text in self.texts()))

    async def test_one_save_creates_playlist_rename_move_and_delete_preserve_saved_tracks(self):
        song = {"id": 42, "title": "<Bright Track>", "artist": "A & B", "url": "https://genius.com/test"}
        self.bot.user_search_results[77] = [song]
        await self.app.process_update(self.callback("fav_42"))
        self.assertEqual(len(self.bot.user_favorites[77]), 1)
        await self.app.process_update(self.callback("fav_42"))
        self.assertEqual(len(self.bot.user_favorites[77]), 1)
        self.assertTrue(any("Сохранено" in text for text in self.texts()))
        await self.app.process_update(self.callback("lib:new:42"))
        await self.app.process_update(self.message("Работа"))
        folders = self.app.user_data[77]["music_collections"]
        first = next(iter(folders))
        self.assertEqual(folders[first]["songs"][0]["id"], 42)
        await self.app.process_update(self.callback("lib:rename:" + first))
        await self.app.process_update(self.message("Для работы"))
        self.assertEqual(folders[first]["name"], "Для работы")
        await self.app.process_update(self.message("/collection Дорога"))
        second = next(key for key in folders if key != first)
        await self.app.process_update(self.callback(f"lib:mv:{first}:{second}:42"))
        self.assertEqual(folders[first]["songs"], [])
        self.assertEqual(folders[second]["songs"][0]["id"], 42)
        await self.app.process_update(self.callback("lib:drop:" + second))
        self.assertIn(second, folders)
        await self.app.process_update(self.callback("lib:confirmdrop:" + second))
        self.assertNotIn(second, folders)
        self.assertEqual(self.bot.user_favorites[77][0]["id"], 42)
        durable = StateStore(self.bot.state_store.path).load()[1][77]
        self.assertEqual(durable[0]["id"], 42)

    async def test_playlist_add_picker_toggles_tracks_without_new_menu_messages(self):
        self.bot.user_favorites[77] = [
            {"id": 1, "title": "One", "artist": "A"}, {"id": 2, "title": "Two", "artist": "B"}]
        await self.bot.persist_user_state(77)
        await self.app.process_update(self.message("/collection Mix"))
        key = next(iter(self.app.user_data[77]["music_collections"]))
        await self.app.process_update(self.callback(f"lib:add:{key}:0"))
        before = sum(op == "sendMessage" for op, _ in self.request.calls)
        await self.app.process_update(self.callback(f"lib:mark:{key}:1:0"))
        await self.app.process_update(self.callback(f"lib:mark:{key}:2:0"))
        folder = self.app.user_data[77]["music_collections"][key]
        self.assertEqual([item["id"] for item in folder["songs"]], [1, 2])
        await self.app.process_update(self.callback(f"lib:mark:{key}:1:0"))
        self.assertEqual([item["id"] for item in folder["songs"]], [2])
        self.assertEqual(sum(op == "sendMessage" for op, _ in self.request.calls), before)
        self.assertEqual(len(self.bot.user_favorites[77]), 2)

    async def test_help_lists_link_platforms_and_youtube_video_without_future_features(self):
        await self.app.process_update(self.message("/help"))
        text = self.texts()[-1]
        for word in ("Spotify", "SoundCloud", "YouTube", "Видео", "клипы", "голосовое", "эффекты"):
            self.assertIn(word, text)
        self.assertNotIn("пока", text)
        await self.app.process_update(self.message("/start"))
        await self.app.process_update(self.callback("lang:set:ru"))
        markup = next(params["reply_markup"] for op, params in reversed(self.request.calls) if params.get("reply_markup"))
        if isinstance(markup, str):
            markup = json.loads(markup)
        styles = {button.get("style") for row in markup["inline_keyboard"] for button in row}
        self.assertIn("primary", styles)
        self.assertIn("success", styles)

    async def test_playlist_move_to_new_playlist_and_rename_cancel(self):
        song = {"id": 91, "title": "Track", "artist": "A"}
        self.bot.user_favorites[77] = [song]
        await self.app.process_update(self.message("/collection First"))
        folders = self.app.user_data[77]["music_collections"]
        source = next(iter(folders))
        await self.app.process_update(self.callback(f"lib:save:{source}:91"))
        await self.app.process_update(self.callback(f"lib:movenew:{source}:91"))
        await self.app.process_update(self.message("Second"))
        target = next(key for key in folders if key != source)
        self.assertEqual(folders[source]["songs"], [])
        self.assertEqual(folders[target]["songs"][0]["id"], 91)
        await self.app.process_update(self.callback("lib:rename:" + target))
        await self.app.process_update(self.callback("lib:col:" + target))
        self.assertNotIn("awaiting_playlist_rename", self.app.user_data[77])
        before = str(folders)
        await self.app.process_update(self.callback("lib:confirmdrop:" + target, uid=78))
        self.assertEqual(str(folders), before)

    async def test_full_playlist_duplicate_is_safe_and_does_not_change_saved_state_on_failure(self):
        songs = [{"id": i, "title": str(i), "artist": "A"} for i in range(60)]
        self.bot.user_favorites[77] = list(songs)
        await self.app.process_update(self.message("/collection Full"))
        key = next(iter(self.app.user_data[77]["music_collections"]))
        self.app.user_data[77]["music_collections"][key]["songs"] = list(songs)
        await self.app.process_update(self.callback(f"lib:save:{key}:1"))
        self.assertEqual(len(self.app.user_data[77]["music_collections"][key]["songs"]), 60)
        self.bot.user_search_results[77] = [{"id": 99, "title": "Extra", "artist": "B"}]
        before = list(self.bot.user_favorites[77])
        await self.app.process_update(self.callback(f"lib:save:{key}:99"))
        self.assertEqual(self.bot.user_favorites[77], before)

    async def test_own_remix_can_be_saved_after_new_upload_and_replayed_without_search(self):
        from pydub.generators import Sine
        import io
        import versions
        def mp3(frequency):
            buffer = io.BytesIO()
            Sine(frequency).to_audio_segment(duration=4000).export(buffer, format="mp3")
            return buffer.getvalue()
        first, second = mp3(440), mp3(660)
        self.request.media_files["own-a.audio"] = first
        self.request.media_files["own-b.audio"] = second
        def upload(identifier, title):
            payload = self.message().to_dict()
            payload["message"]["audio"] = {"file_id": identifier, "file_unique_id": identifier,
                "duration": 4, "file_name": title + ".mp3", "title": title, "performer": "My artist", "mime_type": "audio/mpeg"}
            return Update.de_json(payload, self.app.bot)
        await self.app.process_update(upload("own-a", "My remix"))
        identifier = self.app.user_data[77]["downloaded_song"]["id"]
        old_source = Path(self.app.user_data[77]["last_audio_path"])
        await self.app.process_update(upload("own-b", "Other track"))
        self.assertFalse(old_source.exists())
        await self.app.process_update(self.callback(f"upload:save:{identifier}"))
        saved = next(song for song in self.bot.user_favorites[77] if song["id"] == identifier)
        permanent = Path(saved["_library_audio"])
        self.assertEqual(permanent.read_bytes(), first)
        self.assertEqual(saved["title"], "My remix")
        await self.app.process_update(self.message("/collection My remixes"))
        key = next(iter(self.app.user_data[77]["music_collections"]))
        await self.app.process_update(self.callback(f"lib:save:{key}:{identifier}"))
        with patch("versions.find_versions") as search:
            await self.app.process_update(self.callback(f"lib:download:{identifier}"))
            search.assert_not_called()
        self.assertEqual(self.request.uploads[-1][1], first)
        await self.app.process_update(self.callback(f"lib:open:{identifier}"))
        await self.app.process_update(self.callback(f"enhance_{identifier}"))
        self.assertTrue(permanent.is_file())
        self.assertEqual(permanent.read_bytes(), first)
        self.assertEqual(Path(self.app.user_data[77]["last_audio_path"]).read_bytes(), first)
        saved_on_disk = StateStore(self.bot.state_store.path).load()[1][77]
        self.assertEqual(saved_on_disk[0]["kind"], "upload")
        before = len(self.request.uploads)
        await self.app.process_update(self.callback(f"lib:download:{identifier}", uid=78))
        self.assertEqual(len(self.request.uploads), before)
        await self.app.process_update(self.callback(f"lib:delete:{identifier}"))
        self.assertTrue(permanent.exists())
        await self.app.process_update(self.callback(f"lib:confirmdelete:{identifier}"))
        self.assertFalse(permanent.exists())
        self.assertFalse(any(item["id"] == identifier for item in self.bot.user_favorites[77]))

    async def test_voice_file_has_direct_save_and_keeps_original_recording(self):
        from pydub.generators import Sine
        import io
        buffer = io.BytesIO()
        Sine(440).to_audio_segment(duration=4000).export(buffer, format="ogg", codec="libopus")
        original = buffer.getvalue()
        self.request.media = original
        await self.app.process_update(self.message(voice=True))
        identifier = next(iter(self.app.user_data[77]["upload_requests"]))
        await self.app.process_update(self.callback("upload:save:" + identifier))
        saved = self.bot.user_favorites[77][0]
        self.assertEqual(Path(saved["_library_audio"]).read_bytes(), original)
        await self.app.process_update(self.callback("lib:download:" + identifier))
        self.assertTrue(any(op == "sendVoice" for op, _ in self.request.calls))
        self.assertEqual(self.request.uploads[-1][1], original)

    async def test_loop_upload_closes_export_and_removes_temporary_file(self):
        import io
        import scratch
        from pydub import AudioSegment
        from pydub.generators import Sine
        encoded = io.BytesIO()
        Sine(440).to_audio_segment(duration=4000).export(encoded, format='ogg', codec='libopus')
        self.request.media = encoded.getvalue()
        await self.app.process_update(self.message(voice=True))
        await self.app.process_update(self.callback('voice_effects'))
        source = Path(self.app.user_data[77]['last_audio_path'])
        before_files = set(scratch.scratch_root().iterdir())
        before_uploads = sum(op == 'sendAudio' for op, _ in self.request.calls)
        await self.app.process_update(self.callback('make_loop'))
        self.assertEqual(sum(op == 'sendAudio' for op, _ in self.request.calls), before_uploads + 1)
        self.assertEqual(set(scratch.scratch_root().iterdir()), before_files)
        self.assertTrue(source.is_file())
        with io.BytesIO(self.request.uploads[-1][1]) as audio:
            self.assertGreater(len(AudioSegment.from_file(audio, format='mp3')), 1000)

    async def test_search_buttons_downloads_lyrics_and_favorites(self):
        songs = [{'id': 1, 'title': 'Needle', 'artist': 'Artist', 'url': 'https://genius.com/fixture'},
                 {'id': 2, 'title': 'Other', 'artist': 'Artist', 'url': 'https://genius.com/other'}]
        source_dir = Path(self.local_files.name)
        def download(query):
            file = source_dir / f'download-{len(self.request.calls)}.mp3'
            file.write_bytes(b'offline upload fixture')
            return str(file), {}
        with patch.object(self.bot, 'search_songs', new_callable=AsyncMock, return_value=songs), \
             patch.object(self.bot, 'search_deezer', new_callable=AsyncMock, return_value=[]), \
             patch.object(self.bot, 'get_lyrics', new_callable=AsyncMock, return_value='lyrics fixture'), \
             patch.object(self.bot, 'download_youtube_audio', side_effect=download):
            await self.app.process_update(self.message('Needle'))
            for choice in ['next_1', 'prev_0', 'lyrics_1', 'fav_1', 'fav_1', 'download_1', 'enhance_1']:
                await self.app.process_update(self.callback(choice))
                if choice.startswith(('download_', 'enhance_')):
                    await self.choose_latest_version()
            await self.app.process_update(self.message('/download 1'))
            await self.choose_latest_version()
        self.assertEqual(len(self.bot.user_favorites[77]), 1)
        self.assertTrue(any('lyrics fixture' == text for text in self.texts()))
        self.assertEqual(sum(op == 'sendAudio' for op, _ in self.request.calls), 3)
        self.assertTrue(Path(self.app.user_data[77]['last_audio_path']).exists())

    async def test_track_card_snapshot_save_listen_and_local_studio(self):
        first = {"id": 11, "title": "First <track>", "artist": "A & B", "url": "https://genius.com/first", "cover": None}
        self.bot.user_search_results[77] = [first]
        await self.bot.send_song(self.message("fixture"), self.app.context_types.context.from_update(self.message("fixture"), self.app))
        cards = self.app.user_data[77]["track_cards"]
        token = next(reversed(cards))
        self.bot.user_search_results[77] = [{"id":22,"title":"Other","artist":"Other","url":"https://genius.com/other"}]
        await self.app.process_update(self.callback("track:save:" + token))
        self.assertEqual([song["id"] for song in self.bot.user_favorites[77]], [11])
        self.assertFalse(any("Добавить в плейлист?" in text for text in self.texts()))
        await self.app.process_update(self.callback("track:save:" + token, uid=88))
        self.assertFalse(self.bot.user_favorites.get(88))
        def download(url):
            target = Path(self.local_files.name) / "card.mp3"
            target.write_bytes(b"offline card audio")
            return str(target), {"title":"First recording","uploader":"A"}
        with patch.object(self.bot, "download_youtube_audio", side_effect=download) as downloader:
            await self.app.process_update(self.callback("track:listen:" + token))
            await self.choose_latest_version()
            self.assertEqual(downloader.call_count, 1)
            self.assertFalse(any(text.startswith("🎛 Студия") for text in self.texts()))
            audio = [data for operation,data in self.request.calls if operation == "sendAudio"][-1]
            self.assertIn("track:studio:", str(audio["reply_markup"]))
            await self.app.process_update(self.callback("track:studio:" + token))
            self.assertEqual(downloader.call_count, 1)
            self.assertTrue(any(text.startswith("🎛 Студия") for text in self.texts()))
        await self.app.process_update(self.callback("track:playlist:" + token))
        self.assertTrue(any("Добавить в плейлист?" in text for text in self.texts()))

    async def test_failed_download_retry_is_exact_and_other_version_skips_failure(self):
        from versions import request_versions
        update = self.message("fixture")
        context = self.app.context_types.context.from_update(update, self.app)
        song = {"id": 51, "title":"First song","artist":"A","url":"https://genius.com/first"}
        await request_versions(update, context, song, mode="listen")
        token = next(reversed(context.user_data["version_requests"]))
        with patch.object(self.bot, "download_youtube_audio", side_effect=RuntimeError("private provider error")):
            await self.app.process_update(self.callback(f"ver:pick:{token}:0"))
        markup = str(self.request.calls)
        self.assertIn(f"ver:pick:{token}:0", markup)
        self.assertIn(f"ver:other:{token}:0", markup)
        self.assertNotIn("private provider error", str(self.texts()))
        self.bot.user_search_results[77] = [{"id":99,"title":"Other search","artist":"B"}]
        await self.app.process_update(self.callback(f"ver:other:{token}:0"))
        rows = [data for op,data in self.request.calls if op in ("sendMessage", "editMessageText")][-1]["reply_markup"]
        self.assertNotIn(f"ver:pick:{token}:0", str(rows))
        self.assertIn(f"ver:pick:{token}:1", str(rows))
        def download(url):
            target = Path(self.local_files.name) / "retry.mp3"
            target.write_bytes(b"complete download fixture")
            return str(target), {"title":"First recording","uploader":"A"}
        with patch.object(self.bot,"download_youtube_audio",side_effect=download) as downloader:
            await self.app.process_update(self.callback(f"ver:pick:{token}:0",uid=88))
            downloader.assert_not_called()
            await self.app.process_update(self.callback(f"ver:pick:{token}:0"))
            downloader.assert_called_once_with("https://www.youtube.com/watch?v=abcdefghijk")
        self.assertEqual(self.request.uploads[-1][1], b"complete download fixture")
        self.assertEqual(self.app.user_data[77]["downloaded_song"]["id"],51)

    async def test_version_search_failure_can_retry_original_query_after_new_search(self):
        from versions import request_versions
        update=self.message("fixture")
        context=self.app.context_types.context.from_update(update,self.app)
        with patch("versions.find_versions",side_effect=RuntimeError("unavailable")):
            await request_versions(update,context,{"id":1,"title":"Original","artist":"Artist"},mode="listen")
        token=next(reversed(context.user_data["version_requests"]))
        self.bot.user_search_results[77]=[{"id":99,"title":"Changed","artist":"Other"}]
        with patch("versions.find_versions",return_value=[]) as search:
            await self.app.process_update(self.callback(f"ver:refresh:{token}"))
            search.assert_called_once_with("Original Artist")
        request=context.user_data["version_requests"][next(reversed(context.user_data["version_requests"]))]
        self.assertEqual(request["mode"],"listen")
        self.assertEqual(request["song"]["id"],1)
        self.assertTrue(any("Не нашёл подходящие версии" in text for text in self.texts()))

    async def test_link_failure_retry_keeps_original_url(self):
        first="https://youtu.be/original"
        await self.app.process_update(self.message(first))
        token=next(reversed(self.app.user_data[77]["dl_requests"]))
        with patch.object(self.bot,"download_youtube_audio",side_effect=RuntimeError("unavailable")):
            await self.app.process_update(self.callback("dl_audio|" + token))
        self.assertTrue(any("Можно повторить попытку" in text for text in self.texts()))
        await self.app.process_update(self.message("https://youtu.be/different"))
        def download(url):
            path=Path(self.local_files.name)/"link-retry.mp3"
            path.write_bytes(b"original link audio")
            return str(path),{"title":"Original","uploader":"Artist"}
        with patch.object(self.bot,"download_youtube_audio",side_effect=download) as downloader:
            await self.app.process_update(self.callback("dl_audio|" + token))
            downloader.assert_called_once_with(first)
        self.assertEqual(self.request.uploads[-1][1], b"original link audio")

    async def test_quick_presets_preview_then_full_and_ringtone_formats(self):
        from pydub.generators import Sine
        from pydub import AudioSegment
        from studio_tools import audio_info
        import io
        source=Path(self.local_files.name)/"quick-source.wav"
        Sine(440).to_audio_segment(duration=40000).export(source,format="wav").close()
        await self.bot.retain_audio_source(self.app.context_types.context.from_update(self.message(),self.app),77,str(source))
        self.app.user_data[77]["downloaded_song"]={"id":71,"title":"My song","artist":"My artist"}
        original=Path(self.app.user_data[77]["last_audio_path"]).read_bytes()
        await self.app.process_update(self.callback("quick:home"))
        for key in ("speed","slow","bass"):
            await self.app.process_update(self.callback("quick:preset:"+key))
            if key == "bass":
                await self.app.process_update(self.callback("studio:bass:bass_light"))
                self.assertEqual(self.app.user_data[77]["pending_effects"], ["bass_light"])
                await self.app.process_update(self.callback("fx:preview"))
            self.assertIn("effect_preview",self.app.user_data[77])
            with io.BytesIO(self.request.uploads[-1][1]) as sample:
                self.assertLessEqual(len(AudioSegment.from_file(sample,format="mp3")),15100)
        token=self.app.user_data[77]["effect_preview"]["token"]
        await self.app.process_update(self.callback("fx:apply:"+token))
        with io.BytesIO(self.request.uploads[-1][1]) as full:
            self.assertAlmostEqual(len(AudioSegment.from_file(full,format="mp3")),40000,delta=200)
        await self.app.process_update(self.callback("quick:ringtone"))
        token=next(reversed(self.app.user_data[77]["ringtone_requests"]))
        await self.app.process_update(self.callback("quick:time:"+token))
        await self.app.process_update(self.message("0:35"))
        self.assertNotIn("awaiting_ringtone",self.app.user_data[77])
        for kind in ("mp3","m4r"):
            await self.app.process_update(self.callback(f"quick:export:{token}:{kind}"))
            filename,content=self.request.uploads[-1][:2]
            self.assertTrue(filename.endswith("."+kind))
            output=Path(self.local_files.name)/("ring."+kind)
            output.write_bytes(content)
            info=audio_info(output)
            self.assertAlmostEqual(info["duration"],5,delta=0.15)
            self.assertEqual(info["codec"],"aac" if kind=="m4r" else "mp3")
        before=len(self.request.uploads)
        await self.app.process_update(self.callback(f"quick:export:{token}:mp3",uid=88))
        self.assertEqual(len(self.request.uploads),before)
        self.assertEqual(Path(self.app.user_data[77]["last_audio_path"]).read_bytes(),original)

    async def test_ringtone_start_validation_changed_source_and_cancel(self):
        from pydub.generators import Sine
        source=Path(self.local_files.name)/"ring-source.wav"
        Sine(440).to_audio_segment(duration=4000).export(source,format="wav").close()
        context=self.app.context_types.context.from_update(self.message(),self.app)
        await self.bot.retain_audio_source(context,77,str(source))
        await self.app.process_update(self.callback("quick:ringtone"))
        token=next(reversed(context.user_data["ringtone_requests"]))
        await self.app.process_update(self.callback("quick:time:"+token))
        await self.app.process_update(self.message("9:99"))
        self.assertIn("awaiting_ringtone",context.user_data)
        await self.app.process_update(self.message("0:10"))
        self.assertIn("awaiting_ringtone",context.user_data)
        await self.app.process_update(self.callback("studio:home"))
        self.assertNotIn("awaiting_ringtone",context.user_data)
        await self.app.process_update(self.callback("quick:start:"+token))
        source=Path(self.local_files.name)/"different.wav"
        Sine(660).to_audio_segment(duration=4000).export(source,format="wav").close()
        await self.bot.retain_audio_source(context,77,str(source))
        before=len(self.request.uploads)
        await self.app.process_update(self.callback(f"quick:export:{token}:m4r"))
        self.assertEqual(len(self.request.uploads),before)
        self.assertTrue(any("Этот выбор уже недоступен" in text for text in self.texts()))

    async def test_mixed_link_queue_is_ordered_and_pauses_for_catalog_choice(self):
        import io
        await self.app.process_update(self.message(
            "https://youtu.be/first https://music.apple.com/us/album/song/123?i=456 https://soundcloud.com/artist/last"))
        token=next(reversed(self.app.user_data[77]["link_queues"]))
        def download(url):
            path=Path(self.local_files.name)/"queue.mp3";path.write_bytes(b"queue full audio")
            return str(path),{"title":"Queue song","uploader":"Artist"}
        def sc(url):
            path,_=download(url)
            return {"path":path,"title":"Last","artist":"Artist"}
        with patch.object(self.bot,"download_youtube_audio",side_effect=download) as youtube, \
             patch.object(self.bot,"download_soundcloud_audio",side_effect=sc) as soundcloud:
            await self.app.process_update(self.callback("batch:run:"+token))
            queue=self.app.user_data[77]["link_queues"][token]
            self.assertEqual(queue["index"],1)
            youtube.assert_called_once_with("https://youtu.be/first")
            soundcloud.assert_not_called()
            version_token=next(reversed(self.app.user_data[77]["version_requests"]))
            await self.app.process_update(self.callback(f"ver:pick:{version_token}:0"))
            self.assertEqual(queue["done"],3)
            self.assertTrue(queue["stopped"])
            soundcloud.assert_called_once_with("https://soundcloud.com/artist/last")
            calls=youtube.call_count
            await self.app.process_update(self.callback(f"ver:pick:{version_token}:0"))
            self.assertEqual(youtube.call_count,calls)
        self.assertTrue(any("отправлено 3 из 3" in text for text in self.texts()))

    async def test_link_queue_failure_skip_and_manual_vk_metadata(self):
        await self.app.process_update(self.message(
            "https://youtu.be/bad https://vk.com/audio-123_456 https://youtu.be/last"))
        token=next(reversed(self.app.user_data[77]["link_queues"]))
        def download(url):
            if url.endswith("/bad"): raise RuntimeError("private failure")
            path=Path(self.local_files.name)/"last.mp3";path.write_bytes(b"last track")
            return str(path),{"title":"Last","uploader":"Artist"}
        with patch.object(self.bot,"download_youtube_audio",side_effect=download), \
             patch("catalog_links.catalog_metadata",side_effect=ValueError("login needed")):
            await self.app.process_update(self.callback("batch:run:"+token))
            self.assertIn("awaiting_catalog",self.app.user_data[77])
            await self.app.process_update(self.message("Artist Song"))
            request=list(self.app.user_data[77]["version_requests"].values())[-1]
            self.assertEqual(request["song"]["title"],"Artist Song")
            await self.app.process_update(self.callback(f"batch:skip:{token}:1"))
        queue=self.app.user_data[77]["link_queues"][token]
        self.assertEqual((queue["done"],queue["failed"]),(1,2))
        self.assertTrue(queue["stopped"])
        self.assertNotIn("private failure",str(self.texts()))

    async def test_link_queue_stop_and_user_isolation(self):
        await self.app.process_update(self.message("https://youtu.be/a https://youtu.be/b"))
        token=next(reversed(self.app.user_data[77]["link_queues"]))
        with patch.object(self.bot,"download_youtube_audio") as download:
            await self.app.process_update(self.callback("batch:run:"+token,uid=88))
            download.assert_not_called()
            await self.app.process_update(self.callback("batch:stop:"+token))
            await self.app.process_update(self.callback("batch:run:"+token))
            download.assert_not_called()
        self.assertTrue(self.app.user_data[77]["link_queues"][token]["stopped"])

    async def test_cancel_running_link_queue_stops_before_next_track(self):
        import threading,time,asyncio
        from operations import checkpoint
        entered=threading.Event()
        await self.app.process_update(self.message("https://youtu.be/first https://youtu.be/second"))
        token=next(reversed(self.app.user_data[77]["link_queues"]))
        def blocked(url):
            entered.set()
            while True:
                checkpoint()
                time.sleep(0.01)
        with patch.object(self.bot,"download_youtube_audio",side_effect=blocked) as download:
            job=asyncio.create_task(self.app.process_update(self.callback("batch:run:"+token)))
            self.assertTrue(await asyncio.to_thread(entered.wait,3))
            await self.app.process_update(self.callback("batch:stop:"+token))
            await asyncio.wait_for(job,3)
            download.assert_called_once_with("https://youtu.be/first")
        self.assertTrue(self.app.user_data[77]["link_queues"][token]["stopped"])
        self.assertFalse(any(op=="sendAudio" for op,_ in self.request.calls))

    async def test_search_navigation_survives_new_search_and_download_has_no_repeat_button(self):
        self.bot.user_search_results[77]=[
            {"id":81,"title":"Same name","artist":"Artist A","url":"https://genius.com/a"},
            {"id":82,"title":"Same name","artist":"Artist B","url":"https://genius.com/b"},
            {"id":83,"title":"Third","artist":"Artist C","url":"https://genius.com/c"}]
        update=self.message("fixture")
        context=self.app.context_types.context.from_update(update,self.app)
        await self.bot.send_song(update,context)
        search_token=next(reversed(context.user_data["search_pages"]))
        track_token=next(reversed(context.user_data["track_cards"]))
        self.assertTrue(any("Вариант 1 из 3" in text for text in self.texts()))
        self.bot.user_search_results[77]=[{"id":99,"title":"New search","artist":"Other","url":"https://genius.com/other"}]
        def download(url):
            path=Path(self.local_files.name)/"once.mp3";path.write_bytes(b"whole song")
            return str(path),{"title":"Same name","uploader":"Artist A"}
        with patch.object(self.bot,"download_youtube_audio",side_effect=download) as downloader:
            await self.app.process_update(self.callback("track:listen:"+track_token))
            version_token=next(reversed(context.user_data["version_requests"]))
            await self.app.process_update(self.callback(f"ver:pick:{version_token}:0"))
            await self.app.process_update(self.callback(f"ver:pick:{version_token}:0"))
            self.assertEqual(downloader.call_count,1)
        audio=[data for operation,data in self.request.calls if operation=="sendAudio"][-1]
        self.assertNotIn("track:listen:",str(audio["reply_markup"]))
        self.assertNotIn("srch:",str(audio["reply_markup"]))
        self.assertTrue(any(operation=="deleteMessage" for operation,_ in self.request.calls))
        await self.app.process_update(self.callback(f"srch:{search_token}:1"))
        self.assertTrue(any("Вариант 2 из 3" in text and "Artist B" in text for text in self.texts()))

    async def test_direct_download_old_button_does_not_send_twice(self):
        await self.app.process_update(self.message("https://youtu.be/once"))
        token=next(reversed(self.app.user_data[77]["dl_requests"]))
        def download(url):
            path=Path(self.local_files.name)/"direct-once.mp3";path.write_bytes(b"direct song")
            return str(path),{"title":"Direct","uploader":"Artist"}
        with patch.object(self.bot,"download_youtube_audio",side_effect=download) as downloader:
            await self.app.process_update(self.callback("dl_audio|"+token))
            await self.app.process_update(self.callback("dl_audio|"+token))
            self.assertEqual(downloader.call_count,1)
        audio=[data for operation,data in self.request.calls if operation=="sendAudio"][-1]
        self.assertNotIn("track:listen:",str(audio["reply_markup"]))
        self.assertFalse(any(text.startswith("🎛 Студия") for text in self.texts()))

    async def test_switching_results_and_versions_edits_one_screen(self):
        self.bot.user_search_results[77]=[
            {"id":91,"title":"One","artist":"A","url":"https://genius.com/one"},
            {"id":92,"title":"Two","artist":"B","url":"https://genius.com/two"}]
        update=self.message("fixture")
        context=self.app.context_types.context.from_update(update,self.app)
        await self.bot.send_song(update,context)
        token=next(reversed(context.user_data["search_pages"]))
        before=sum(op=="sendMessage" for op,_ in self.request.calls)
        await self.app.process_update(self.callback(f"srch:{token}:1"))
        await self.app.process_update(self.callback(f"srch:{token}:0"))
        self.assertEqual(sum(op=="sendMessage" for op,_ in self.request.calls),before)
        self.assertTrue(any(op=="editMessageText" and "Two" in data.get("text","") for op,data in self.request.calls))
        from versions import request_versions
        await request_versions(update,context,{"id":91,"title":"One","artist":"A"},mode="listen")
        version=next(reversed(context.user_data["version_requests"]))
        before=sum(op=="sendMessage" for op,_ in self.request.calls)
        await self.app.process_update(self.callback(f"ver:other:{version}:0"))
        # Only the temporary operation status is sent; the actual selector is edited.
        new=[data.get("text","") for op,data in self.request.calls if op=="sendMessage"][before:]
        self.assertFalse(any("Выбери другую версию" in text for text in new))
        self.assertTrue(any(op=="editMessageText" and "Выбери другую версию" in data.get("text","") for op,data in self.request.calls))

    async def test_language_choice_is_persisted_and_all_main_sections_use_english(self):
        await self.app.process_update(self.message("/start"))
        self.assertIn("Choose your language",self.texts()[-1])
        await self.app.process_update(self.callback("lang:set:en"))
        self.assertEqual(self.app.user_data[77]["language"],"en")
        self.assertIn("Your music. Your mix.",self.texts()[-1])
        saved=StateStore(self.bot.state_store.path).load_named("sessions")[77]
        self.assertEqual(saved["language"],"en")
        self.app.user_data[77].pop("language")
        self.bot.saved_sessions[77]=saved
        await self.app.process_update(self.message("/help"))
        self.assertIn("SwiDJ",self.texts()[-1])
        self.assertIn("Spotify",self.texts()[-1])
        self.assertIn("Apple Music",self.texts()[-1])
        self.assertIn("Yandex Music",self.texts()[-1])
        self.assertNotIn("VK",self.texts()[-1])
        await self.app.process_update(self.message("/search"))
        self.assertIn("How would you like to search?",self.texts()[-1])
        await self.app.process_update(self.message("/favorites"))
        self.assertTrue(any("My music" in text for text in self.texts()))
        await self.app.process_update(self.message("/studio"))
        self.assertIn("Send an audio file",self.texts()[-1])
        await self.app.process_update(self.callback("lang:set:ru"))
        self.assertIn("Твоя музыка. Твой микс.",self.texts()[-1])

    async def test_two_user_languages_are_isolated(self):
        self.app.user_data[77]["language"]="en"
        self.app.user_data[88]["language"]="ru"
        await asyncio.gather(self.app.process_update(self.message("/help",uid=77)),
                             self.app.process_update(self.message("/help",uid=88)))
        by_chat={int(data["chat_id"]):data["text"] for op,data in self.request.calls if op=="sendMessage" and int(data.get("chat_id",0)) in (77,88)}
        self.assertIn("SwiDJ · your music",by_chat[77])
        self.assertIn("SwiDJ · музыка рядом",by_chat[88])

    async def test_owner_panel_draft_cancel_and_fake_broadcast(self):
        from access import AccessPolicy
        with patch.object(self.bot, 'access_policy', AccessPolicy(frozenset({77}))):
            await self.app.process_update(self.message('/whoami'))
            await self.app.process_update(self.message('/panel'))
            await self.app.process_update(self.callback('admin_text'))
            await self.app.process_update(self.message('offline broadcast fixture'))
            await self.bot.save_user(78)
            await self.app.process_update(self.callback('admin_send'))
            self.assertTrue(any('Разослано' in text for text in self.texts()))
            self.assertTrue(any(op == 'sendMessage' and params.get('chat_id') == 78
                for op, params in self.request.calls))
            await self.app.process_update(self.message('/users'))
            await self.app.process_update(self.callback('admin_cancel'))
            await self.app.process_update(self.message('/cleanup'))
        self.assertNotIn(77, self.bot.broadcast_state)
        self.assertFalse(self.app.user_data[77].get('awaiting_broadcast_text'))

    async def test_empty_query_avoids_catalog_calls(self):
        with patch.object(self.bot, 'search_songs', new_callable=AsyncMock) as search:
            await self.app.process_update(self.message('   '))
            search.assert_not_awaited()
        self.assertNotIn(77, self.bot.user_search_history)

    async def test_long_favorites_are_paginated_without_losing_rows(self):
        self.bot.user_favorites[77] = [{'id': i, 'title': 'T' * 90, 'artist': 'A' * 90} for i in range(80)]
        await self.app.process_update(self.message('/favorites'))
        await self.app.process_update(self.callback('lib:page:15'))
        self.assertTrue(any('16 / 16' in text for text in self.texts()))
        markups = [(json.loads(params['reply_markup']) if isinstance(params['reply_markup'], str) else params['reply_markup']) for op, params in self.request.calls
                   if op in ('sendMessage', 'editMessageText') and params.get('reply_markup')]
        labels = [button['text'] for markup in markups for row in markup['inline_keyboard'] for button in row]
        self.assertTrue(any(label.startswith('80.') for label in labels))
        self.assertTrue(all(len(label) <= 64 for label in labels))

    async def test_audio_recognition_prepares_real_ogg_and_labels_transcript_fallback(self):
        from pydub.generators import Sine
        import io
        encoded = io.BytesIO()
        Sine(440).to_audio_segment(duration=4000).export(encoded, format='ogg', codec='libopus')
        self.request.media = encoded.getvalue()
        await self.app.process_update(self.message(voice=True))
        with patch.object(self.bot, 'recognize_song_shazam', new_callable=AsyncMock, return_value=None), \
             patch.object(self.bot, 'recognize_song_by_audio', new_callable=AsyncMock, return_value=None), \
             patch.object(self.bot, 'recognize_by_whisper', new_callable=AsyncMock, return_value='heard words'), \
             patch.object(self.bot, 'search_songs', new_callable=AsyncMock, return_value=[]) as search, \
             patch.object(self.bot, 'search_deezer', new_callable=AsyncMock, return_value=[]), \
             patch.object(self.bot, 'recognize_by_gpt_hint', new_callable=AsyncMock, return_value=None):
            await self.app.process_update(self.callback('voice_recognize'))
            search.assert_not_awaited()
            self.assertEqual(self.app.user_data[77]['pending_transcript'], 'heard words')
            await self.app.process_update(self.callback('voice_search_words'))
            search.assert_awaited_once_with('heard words')
        self.assertTrue(any('heard words' in t for t in self.texts()))
        self.assertTrue(any('Совпадение не найдено' in t for t in self.texts()))
        self.assertFalse(any('Найдено совпадение' in t for t in self.texts()))

    async def test_home_navigation_help_and_cancel_preserve_audio(self):
        await self.app.process_update(self.message('/start'))
        self.assertTrue(any('Твой микс' in t for t in self.texts()))
        await self.app.process_update(self.callback('ui:recognize'))
        self.assertTrue(any('Пришли голосовое' in t for t in self.texts()))
        await self.app.process_update(self.callback('ui:history'))
        self.assertTrue(any('История поиска' in t for t in self.texts()))
        await self.app.process_update(self.callback('ui:favorites'))
        self.assertTrue(any('Моя музыка' in t for t in self.texts()))
        await self.app.process_update(self.callback('ui:help'))
        self.assertTrue(any('SoundCloud' in t and 'Spotify' in t and 'YouTube' in t for t in self.texts()))
        state = self.app.user_data[77]
        state['awaiting_pitch'] = True
        state['pending_transcript'] = 'old words'
        state['last_audio_path'] = 'retained-audio'
        await self.app.process_update(self.message('/cancel'))
        self.assertNotIn('awaiting_pitch', state)
        self.assertNotIn('pending_transcript', state)
        self.assertEqual(state['last_audio_path'], 'retained-audio')

    async def test_expired_transcript_does_not_start_search(self):
        with patch.object(self.bot, 'search_songs', new_callable=AsyncMock) as search:
            await self.app.process_update(self.callback('voice_search_words'))
            search.assert_not_awaited()
        self.assertTrue(any('устарела' in t for t in self.texts()))

    async def test_words_mode_skips_fingerprint_services_and_waits_for_confirmation(self):
        from pydub.generators import Sine
        import io
        encoded = io.BytesIO()
        Sine(440).to_audio_segment(duration=4000).export(encoded, format='ogg', codec='libopus')
        self.request.media = encoded.getvalue()
        await self.app.process_update(self.message(voice=True))
        with patch.object(self.bot, 'recognize_song_shazam', new_callable=AsyncMock) as shazam, \
             patch.object(self.bot, 'recognize_song_by_audio', new_callable=AsyncMock) as audd, \
             patch.object(self.bot, 'recognize_by_whisper', new_callable=AsyncMock, return_value='some lyrics'), \
             patch.object(self.bot, 'search_songs', new_callable=AsyncMock) as search:
            await self.app.process_update(self.callback('voice_words'))
            shazam.assert_not_awaited()
            audd.assert_not_awaited()
            search.assert_not_awaited()
        self.assertEqual(self.app.user_data[77]['pending_transcript'], 'some lyrics')

    async def test_recording_match_stops_transcription_and_keeps_download_action(self):
        from pydub.generators import Sine
        import io
        encoded = io.BytesIO()
        Sine(440).to_audio_segment(duration=4000).export(encoded, format='mp3')
        self.request.media = encoded.getvalue()
        await self.app.process_update(self.message(voice=True))
        result = {'title': 'Fixture track', 'artist': 'Artist', 'url': 'https://example.invalid/song'}
        with patch.object(self.bot, 'recognize_song_shazam', new_callable=AsyncMock, return_value=result), \
             patch.object(self.bot, 'recognize_by_whisper', new_callable=AsyncMock) as transcribe:
            await self.app.process_update(self.callback('voice_recognize'))
            transcribe.assert_not_awaited()
        self.assertEqual(self.app.user_data[77]['recognized_song'], result)
        self.assertTrue(any('Найдено совпадение' in t for t in self.texts()))

    async def test_link_menus_all_platforms_and_video_qualities(self):
        links = ['https://youtu.be/fixture', 'https://soundcloud.com/artist/track',
                 'https://open.spotify.com/track/fixture', 'https://music.yandex.ru/album/1/track/2']
        def download(*args):
            out = Path(self.local_files.name) / f'media-{len(self.request.calls)}.mp3'
            out.write_bytes(b'fixture')
            return str(out), {'title': 'Track', 'uploader': 'Artist'}
        def soundcloud(*args):
            path, _ = download()
            return {'path': path, 'title': 'Track', 'artist': 'Artist'}
        def video(*args):
            return download()[0]
        with patch.object(self.bot, 'download_youtube_audio', side_effect=download), \
             patch.object(self.bot, 'download_youtube_video', side_effect=video), \
             patch('video_presentation.probe_video', return_value={'width': 640, 'height': 360, 'duration': 1}), \
             patch.object(self.bot, 'download_soundcloud_audio', side_effect=soundcloud), \
             patch.object(self.bot, 'spotify_to_metadata', return_value={'title': 'Track', 'artist': 'Artist', 'query': 'Track Artist'}), \
             patch.object(self.bot, 'yandex_to_metadata', return_value={'title': 'Track', 'artist': 'Artist', 'query': 'Track Artist'}):
            for link in links:
                await self.app.process_update(self.message(link))
                if 'yandex.ru' in link:
                    await self.choose_latest_version()
                    continue
                token = list(self.app.user_data[77]['dl_requests'])[-1]
                await self.app.process_update(self.callback('dl_audio|' + token))
                if 'spotify.com' in link:
                    await self.choose_latest_version()
            for height in (360, 480, 720, 1080):
                await self.app.process_update(self.message(links[0]))
                token = list(self.app.user_data[77]['dl_requests'])[-1]
                await self.app.process_update(self.callback(f'dl_video|{height}|{token}'))
        self.assertEqual(sum(op == 'sendAudio' for op, _ in self.request.calls), 4)
        self.assertEqual(sum(op == 'sendVideo' for op, _ in self.request.calls), 4)
        for op, data in self.request.calls:
            if op == 'sendVideo':
                self.assertEqual(int(data['width']), 640)
                self.assertEqual(int(data['height']), 360)

    async def test_catalog_and_metadata_contracts_with_nullable_fields(self):
        from unittest.mock import Mock
        response = Mock(status_code=200)
        response.json.return_value = {'response': {'hits': [
            {'result': {'id': 9, 'title': 'Track', 'primary_artist': {'name': 'Artist'}, 'url': 'https://genius.com/test'}},
            {'result': {'id': None, 'title': 'invalid', 'primary_artist': None}},
        ]}}
        detail = Mock()
        detail.json.return_value = {'response': {'song': {'media': [{'provider': 'spotify', 'url': 'https://open.spotify.com/track/fixture'}]}}}
        with patch.object(self.bot.requests, 'get', side_effect=[response, detail]):
            found = await self.bot.search_songs('words')
        self.assertEqual(len(found), 1)
        self.assertIn('spotify.com', found[0]['spotify_url'])
        response.json.return_value = {'data': [
            {'id': 8, 'title': 'Track', 'artist': {'name': 'Artist'}, 'link': 'https://deezer.com/track/8', 'album': None},
            {'id': 7, 'title': None, 'artist': None}]}
        with patch.object(self.bot.requests, 'get', return_value=response):
            deezer = await self.bot.search_deezer('words')
        self.assertEqual(deezer[0]['id'], -8)
        self.assertEqual(len(self.bot.merge_catalog_results(found, deezer)), 1)
        response.json.return_value = {'title': 'Track', 'author_name': None}
        with patch.object(self.bot.requests, 'get', return_value=response):
            meta = self.bot.spotify_to_metadata('https://open.spotify.com/track/fixture')
            self.assertEqual(meta['query'], 'Track')
            self.assertNotIn('None', self.bot.spotify_to_search_query('https://open.spotify.com/track/fixture'))
        response.json.return_value = {'title': None}
        with patch.object(self.bot.requests, 'get', return_value=response), self.assertRaises(RuntimeError):
            self.bot.spotify_to_metadata('https://open.spotify.com/track/fixture')
        response.text = '<script type="application/ld+json">{"@type":"MusicRecording","name":"Track","byArtist":{"name":"Artist"}}</script>'
        with patch.object(self.bot.requests, 'get', return_value=response):
            self.assertEqual(self.bot.yandex_to_metadata('https://music.yandex.ru/album/1/track/2')['query'], 'Artist Track')
        response.text = '<div data-lyrics-container="true">first<br>second</div>'
        with patch.object(self.bot.requests, 'get', return_value=response):
            self.assertEqual(await self.bot.get_lyrics('https://genius.com/fixture'), 'first\nsecond')

    async def test_provider_boundaries_and_cost_guard(self):
        from unittest.mock import Mock
        clip = Path(self.local_files.name) / 'clip.wav'; clip.write_bytes(b'fixture')
        with patch.dict(os.environ, {'EXTERNAL_PAID_API_ENABLED': 'false'}), \
             patch.object(self.bot.requests, 'post') as post, \
             patch.object(self.bot.openai.ChatCompletion, 'create') as create:
            self.assertIsNone(await self.bot.recognize_song_shazam(clip))
            self.assertIsNone(await self.bot.recognize_song_by_audio(clip))
            self.assertIsNone(await self.bot.recognize_by_gpt_hint('words'))
            await self.bot.generate_comment('Track', 'Artist')
            post.assert_not_called(); create.assert_not_called()
        response = Mock(status_code=200)
        response.json.return_value = {'status': 'success', 'result': {
            'title': 'Track', 'artist': 'Artist', 'spotify': None, 'deezer': None, 'apple_music': None}}
        # Enable only inside fully mocked provider calls. No external traffic is possible.
        with patch.dict(os.environ, {'EXTERNAL_PAID_API_ENABLED': 'true'}), \
             patch.object(self.bot.requests, 'post', return_value=response) as post:
            result = await self.bot.recognize_song_by_audio(clip)
            self.assertEqual(result['title'], 'Track')
            self.assertEqual(post.call_args.kwargs['timeout'], 30)
            self.assertTrue(post.call_args.kwargs['files']['file'].closed)
        response.json.return_value = {'matches': [1], 'track': {'title': 'Track', 'subtitle': 'Artist'}}
        with patch.dict(os.environ, {'EXTERNAL_PAID_API_ENABLED': 'true'}), \
             patch.object(self.bot.requests, 'post', return_value=response):
            self.assertEqual((await self.bot.recognize_song_shazam(clip))['artist'], 'Artist')
        with patch.dict(os.environ, {'EXTERNAL_PAID_API_ENABLED': 'true'}), \
             patch.object(self.bot.requests, 'post', side_effect=self.bot.requests.Timeout):
            self.assertIsNone(await self.bot.recognize_song_by_audio(clip))
            self.assertIsNone(await self.bot.recognize_song_shazam(clip))

    async def test_downloader_extracts_first_match_and_cleans_failed_jobs(self):
        from unittest.mock import MagicMock
        import scratch
        def factory(options):
            manager = MagicMock()
            ydl = manager.__enter__.return_value
            def extract(query, download):
                suffix = '.mp4' if 'merge_output_format' in options else '.mp3'
                target = Path(options['outtmpl']).parent / ('fixture' + suffix)
                target.write_bytes(b'mocked extractor media')
                if suffix == '.mp4':
                    self.assertIn('height<=480', options['format'])
                return {'entries': [{'title': 'Real Track (Official Video)', 'uploader': 'Artist'}]}
            ydl.extract_info.side_effect = extract
            return manager
        with patch.object(self.bot.yt_dlp, 'YoutubeDL', side_effect=factory):
            path, info = await asyncio.to_thread(self.bot.download_youtube_audio, 'ytsearch1:Track')
            self.assertEqual(info['title'], 'Real Track (Official Video)')
            self.assertTrue(Path(path).exists())
            self.assertEqual(self.bot.extract_youtube_metadata(info), ('Real Track', 'Artist'))
            self.assertTrue(Path(await asyncio.to_thread(self.bot.download_youtube_video, 'https://youtu.be/fixture', 480)).exists())
            result = await asyncio.to_thread(self.bot.download_soundcloud_audio, 'https://soundcloud.com/fixture')
            self.assertEqual(result['title'], 'Real Track')
        before = set(scratch.scratch_root().iterdir())
        manager = MagicMock()
        manager.__enter__.return_value.extract_info.side_effect = RuntimeError('simulated outage')
        with patch.object(self.bot.yt_dlp, 'YoutubeDL', return_value=manager):
            for function, args in [(self.bot.download_youtube_audio, ('query',)),
                                   (self.bot.download_youtube_video, ('url', 480)),
                                   (self.bot.download_soundcloud_audio, ('url',))]:
                with self.assertRaises(RuntimeError):
                    await asyncio.to_thread(function, *args)
                self.assertEqual(set(scratch.scratch_root().iterdir()), before)

    async def test_pitch_frequency_duration_and_legacy_conversion(self):
        import numpy as np
        from pydub.generators import Sine
        from pydub import AudioSegment
        local = Path(self.local_files.name)
        source = local / 'input.ogg'
        exported = Sine(440).to_audio_segment(duration=4000).export(source, format='ogg', codec='libopus')
        exported.close()
        wave = local / 'input.wav'
        await asyncio.to_thread(self.bot.ogg_to_wav, str(source), str(wave))
        shifted = local / 'shifted.wav'
        await asyncio.to_thread(self.bot.pitch_shift, str(wave), str(shifted), 4)
        with open(shifted, 'rb') as handle:
            result = AudioSegment.from_file(handle)
        samples = np.array(result.get_array_of_samples(), dtype=np.float32)
        frequencies = np.fft.rfftfreq(len(samples), 1/result.frame_rate)
        peak = frequencies[np.argmax(np.abs(np.fft.rfft(samples)))]
        self.assertAlmostEqual(peak, 440 * 2 ** (4/12), delta=3)
        self.assertAlmostEqual(len(result), 4000, delta=150)
        with patch.object(self.bot, 'download_youtube_video', return_value=str(wave)):
            output = await asyncio.to_thread(self.bot.download_youtube_audio_from_video, 'fixture', '480')
        with open(output, 'rb') as handle:
            self.assertGreater(len(AudioSegment.from_file(handle)), 3000)
        self.assertFalse(wave.exists())

    async def test_provider_raw_errors_are_not_logged_or_sent(self):
        import logging
        self.assertGreaterEqual(logging.getLogger('httpx').level, logging.WARNING)
        with patch.dict(os.environ, {'EXTERNAL_PAID_API_ENABLED': 'true'}), \
             patch.object(self.bot.requests, 'post', side_effect=self.bot.requests.Timeout('secret-fixture')):
            clip = Path(self.local_files.name) / 'clip.wav'; clip.write_bytes(b'fixture')
            with self.assertLogs(self.bot.logger, level='WARNING') as captured:
                self.assertIsNone(await self.bot.recognize_song_shazam(clip))
            self.assertNotIn('secret-fixture', '\n'.join(captured.output))

    async def test_owner_photo_audio_video_drafts_and_delivery(self):
        from access import AccessPolicy
        await self.bot.save_user(78)  # Explicit fake recipient; /panel alone does not register chats.
        with patch.object(self.bot, 'access_policy', AccessPolicy(frozenset({77}))):
            for kind in ('photo', 'audio', 'video'):
                await self.app.process_update(self.message('/panel'))
                await self.app.process_update(self.callback('admin_' + kind))
                payload = self.message().to_dict()
                media = {'file_id': kind + '-fixture', 'file_unique_id': kind, 'file_size': 20}
                if kind == 'photo':
                    media.update(width=10, height=10)
                    payload['message'][kind] = [media]
                else:
                    media['duration'] = 4
                    if kind == 'video': media.update(width=10, height=10)
                    payload['message'][kind] = media
                await self.app.process_update(Update.de_json(payload, self.app.bot))
                self.assertEqual(self.bot.broadcast_state[77]['type'], kind)
                await self.app.process_update(self.callback('admin_send'))
        for op in ('sendPhoto', 'sendAudio', 'sendVideo'):
            self.assertTrue(any(name == op for name, _ in self.request.calls), op)

    async def test_url_audio_file_to_effects_favorite_and_new_process_restart(self):
        from pydub.generators import Sine
        from pydub import AudioSegment
        import io
        import shutil
        import scratch
        fixture = Path(self.local_files.name) / 'fixture.mp3'
        Sine(440).to_audio_segment(duration=4000).export(fixture, format='mp3').close()
        def download(query):
            with tempfile.NamedTemporaryFile(dir=scratch.scratch_root(), suffix='.mp3', delete=False) as output:
                shutil.copyfile(fixture, output.name)
                path = output.name
            return path, {'title': 'Fixture Track', 'artist': 'Fixture Artist'}
        def soundcloud(url):
            path, _ = download(url)
            return {'path': path, 'title': 'Fixture Track', 'artist': 'Fixture Artist'}
        urls = ['https://youtu.be/fixture', 'https://soundcloud.com/fixture/track',
                'https://open.spotify.com/track/fixture']
        metadata = {'title': 'Fixture Track', 'artist': 'Fixture Artist', 'query': 'Fixture Track Fixture Artist'}
        with patch.object(self.bot, 'download_youtube_audio', side_effect=download), \
             patch.object(self.bot, 'download_soundcloud_audio', side_effect=soundcloud), \
             patch.object(self.bot, 'spotify_to_metadata', return_value=metadata):
            for url in urls:
                await self.app.process_update(self.message(url))
                token = list(self.app.user_data[77]['dl_requests'])[-1]
                before = len(self.request.uploads)
                await self.app.process_update(self.callback('dl_audio|' + token))
                if 'spotify.com' in url:
                    await self.choose_latest_version()
                self.assertGreater(len(self.request.uploads), before)
                filename, body, mime = self.request.uploads[-1]
                self.assertTrue(filename.endswith('.mp3'))
                self.assertEqual(mime, 'audio/mpeg')
                sent = next(params for op, params in reversed(self.request.calls) if op == 'sendAudio')
                self.assertEqual(sent['title'], 'Fixture Track')
                self.assertEqual(sent['performer'], 'Fixture Artist')
                with io.BytesIO(body) as content:
                    self.assertGreater(len(AudioSegment.from_file(content, format='mp3')), 3000)
                source = Path(self.app.user_data[77]['last_audio_path'])
                self.assertTrue(source.exists())
                self.assertIn(url, self.bot.user_search_history[77])
                self.assertEqual(self.app.user_data[77]['downloaded_song']['title'], 'Fixture Track')
                for callback in ('toggle_echo', 'apply_effects', 'audio_favorite', 'audio_favorite'):
                    await self.app.process_update(self.callback(callback))
                self.assertTrue(source.exists())
                with patch.object(self.bot, 'handle_voice', new_callable=AsyncMock) as recognize:
                    await self.app.process_update(self.callback('audio_recognize'))
                    self.assertEqual(recognize.await_args.kwargs['local_path'], str(source))
        self.assertEqual(len(self.bot.user_favorites[77]), 3)
        # Reload the complete bot in a new interpreter, restore saved session via middleware,
        # then process another effect with real FFmpeg and the offline SDK transport.
        code = '''import asyncio,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from test_sdk import OfflineRequest
from telegram import Update
import bot
async def run():
 r=OfflineRequest(); app=bot.build_application(request=r, updates_request=OfflineRequest())
 await app.initialize(); await bot.initialize_app(app); await app.start()
 try:
  def event(data):
   return Update.de_json({'update_id':1,'callback_query':{'id':'fixture','chat_instance':'fixture','data':data,
    'from':{'id':77,'is_bot':False,'first_name':'Fixture'},'message':{'message_id':1,'date':1,'text':'menu',
    'chat':{'id':77,'type':'private'}}}}, app.bot)
  await app.process_update(event('toggle_normalize'))
  assert app.user_data[77]['downloaded_song']['title']=='Fixture Track'
  assert Path(app.user_data[77]['last_audio_path']).is_file()
  await app.process_update(event('apply_effects'))
  assert any(op=='sendAudio' for op,_ in r.calls)
  assert len(bot.user_favorites[77])==3
  assert len(bot.user_search_history[77])==3
 finally:
  await app.stop(); await app.shutdown()
asyncio.run(run())'''
        environment = dict(os.environ)
        environment.update(PYTHON_DOTENV_DISABLED='1', TELEGRAM_TOKEN='123456:offline-test-token',
            STATE_DB_PATH=str(self.bot.state_store.path), USERS_DB_PATH=self.bot.USERS_DB_PATH,
            OWNER_USER_IDS='', EXTERNAL_PAID_API_ENABLED='false')
        completed = await asyncio.to_thread(subprocess.run,
            [sys.executable, '-c', code, str(Path(__file__).parent)], env=environment,
            capture_output=True, text=True, timeout=45)
        self.assertEqual(completed.returncode, 0, completed.stderr)


    async def test_tiktok_video_menu_delivery_retry_and_duplicate(self):
        self.app.user_data[77]["language"]="en"
        url="https://vm.tiktok.com/ABC12/"
        await self.app.process_update(self.message(url))
        token=next(reversed(self.app.user_data[77]["dl_requests"]))
        self.assertEqual(self.app.user_data[77]["dl_requests"][token]["platform"],"tiktok")
        self.assertIn("Download video",str(self.request.calls))
        with patch.object(self.bot,"download_youtube_video",side_effect=RuntimeError("private failure")):
            await self.app.process_update(self.callback("dl_video|1080|"+token))
        self.assertIn("Could not download the video",self.texts()[-1])
        self.assertNotIn("private failure",self.texts()[-1])
        path=Path(self.local_files.name)/"tiktok.mp4";path.write_bytes(b"video")
        with patch.object(self.bot,"download_youtube_video",return_value=str(path)) as download, patch("video_presentation.probe_video",return_value={"width":1080,"height":1920,"duration":5}):
            await self.app.process_update(self.callback("dl_video|1080|"+token))
            await self.app.process_update(self.callback("dl_video|1080|"+token))
            download.assert_called_once_with(url,1080)
        self.assertFalse(path.exists())
        video=[data for op,data in self.request.calls if op=="sendVideo"][-1]
        self.assertEqual((int(video["width"]),int(video["height"])),(1080,1920))

    async def test_tiktok_queue_sends_video_and_cleans_files(self):
        await self.app.process_update(self.message("https://vm.tiktok.com/ABC12/ https://vt.tiktok.com/DEF34/"))
        token=next(reversed(self.app.user_data[77]["link_queues"]))
        paths=[]
        def download(url,height):
            path=Path(self.local_files.name)/("queue-"+str(len(paths))+".mp4");path.write_bytes(b"video");paths.append(path);return str(path)
        with patch.object(self.bot,"download_youtube_video",side_effect=download), patch("video_presentation.probe_video",return_value={"width":720,"height":1280}):
            await self.app.process_update(self.callback("batch:run:"+token))
        queue=self.app.user_data[77]["link_queues"][token]
        self.assertEqual(queue["done"],2)
        self.assertTrue(queue["stopped"])
        self.assertTrue(all(not path.exists() for path in paths))
        self.assertEqual(sum(op=="sendVideo" for op,_ in self.request.calls),2)

    async def test_tiktok_downloader_keeps_portrait_and_does_not_use_youtube_cookies(self):
        import scratch
        def extract(options,url,directory):
            self.assertEqual(options["format"],"b[ext=mp4]/b")
            self.assertIsNone(options["cookiefile"])
            self.assertTrue(options["noplaylist"])
            (Path(directory)/"clip.mp4").write_bytes(b"video")
            return {"id":"clip"}
        with patch.object(self.bot,"_extract_media",side_effect=extract), patch.dict(os.environ,{"YTDLP_COOKIE_FILE":"private-youtube-cookies"}):
            path=self.bot.download_youtube_video("https://www.tiktok.com/@a/video/123",1080)
        self.assertTrue(Path(path).exists())
        scratch.remove_owned_file(path)
        self.assertFalse(Path(path).parent.exists())

    async def test_apple_and_yandex_links_download_selected_full_recording_in_both_languages(self):
        for uid,language,url in ((77,"ru","https://music.yandex.ru/album/1/track/2"),(88,"en","https://music.apple.com/us/song/1632632842")):
            self.app.user_data[uid]["language"]=language
            await self.app.process_update(self.message(url,uid=uid))
            token=next(reversed(self.app.user_data[uid]["version_requests"]))
            request=self.app.user_data[uid]["version_requests"][token]
            self.assertEqual(request["song"]["url"],url)
            self.assertIn("Recording source: YouTube" if language=="en" else "Источник записи: YouTube",self.texts()[-1])
            path=Path(self.local_files.name)/("full-"+str(uid)+".mp3");path.write_bytes(b"full-recording-fixture")
            with patch.object(self.bot,"download_youtube_audio",return_value=(str(path),{"title":"Song","artist":"Artist"})) as download:
                await self.app.process_update(self.callback("ver:pick:"+token+":0",uid=uid))
                download.assert_called_once_with("https://www.youtube.com/watch?v=abcdefghijk")
            self.assertIn(0,request["sent_indices"])
            await self.app.process_update(self.message("/help",uid=uid))
            for platform in ("Apple Music","Yandex Music" if language=="en" else "Яндекс Музыка","Spotify","SoundCloud","YouTube","TikTok","Instagram"):
                self.assertIn(platform,self.texts()[-1])

    async def test_catalog_link_downloads_automatically_when_title_and_artist_match(self):
        url="https://music.apple.com/us/song/1632632842"
        def download(source):
            path=Path(self.local_files.name)/"automatic.mp3";path.write_bytes(b"full-recording")
            return str(path),{"title":"Catalog song","artist":"Artist"}
        with patch("versions.find_versions",return_value=[{"url":"https://www.youtube.com/watch?v=abcdefghijk","title":"Artist - Catalog song (Official Audio)","artist":"Artist","cover":None}]), patch.object(self.bot,"download_youtube_audio",side_effect=download) as get:
            await self.app.process_update(self.message(url))
            get.assert_called_once_with("https://www.youtube.com/watch?v=abcdefghijk")
        self.assertEqual(sum(op=="sendAudio" for op,_ in self.request.calls),1)
        self.assertFalse(any("Выбери версию" in text for text in self.texts()))

    async def test_instagram_video_menu_delivery_retry_and_duplicate(self):
        self.app.user_data[77]["language"]="en"
        url="https://www.instagram.com/reel/ABC12/"
        await self.app.process_update(self.message(url))
        token=next(reversed(self.app.user_data[77]["dl_requests"]))
        self.assertEqual(self.app.user_data[77]["dl_requests"][token]["platform"],"instagram")
        self.assertIn("Download video",str(self.request.calls))
        with patch.object(self.bot,"download_youtube_video",side_effect=RuntimeError("private failure")):
            await self.app.process_update(self.callback("dl_video|1080|"+token))
        self.assertIn("Could not download the Instagram video",self.texts()[-1])
        self.assertNotIn("private failure",self.texts()[-1])
        path=Path(self.local_files.name)/"instagram.mp4";path.write_bytes(b"video")
        with patch.object(self.bot,"download_youtube_video",return_value=str(path)) as download, patch("video_presentation.probe_video",return_value={"width":1080,"height":1920,"duration":5}):
            await self.app.process_update(self.callback("dl_video|1080|"+token))
            await self.app.process_update(self.callback("dl_video|1080|"+token))
            download.assert_called_once_with(url,1080)
        self.assertFalse(path.exists())
        video=[data for op,data in self.request.calls if op=="sendVideo"][-1]
        self.assertEqual((int(video["width"]),int(video["height"])),(1080,1920))

    async def test_instagram_queue_sends_video_and_cleans_files(self):
        await self.app.process_update(self.message("https://www.instagram.com/reel/ABC12/ https://instagram.com/p/DEF34/"))
        token=next(reversed(self.app.user_data[77]["link_queues"]))
        paths=[]
        def download(url,height):
            path=Path(self.local_files.name)/("queue-"+str(len(paths))+".mp4");path.write_bytes(b"video");paths.append(path);return str(path)
        with patch.object(self.bot,"download_youtube_video",side_effect=download), patch("video_presentation.probe_video",return_value={"width":720,"height":1280}):
            await self.app.process_update(self.callback("batch:run:"+token))
        queue=self.app.user_data[77]["link_queues"][token]
        self.assertEqual(queue["done"],2)
        self.assertTrue(queue["stopped"])
        self.assertTrue(all(not path.exists() for path in paths))
        self.assertEqual(sum(op=="sendVideo" for op,_ in self.request.calls),2)

    async def test_instagram_downloader_keeps_portrait_and_does_not_use_youtube_cookies(self):
        import scratch
        def extract(options,url,directory):
            self.assertEqual(options["format"],"b[ext=mp4]/b")
            self.assertIsNone(options["cookiefile"])
            self.assertTrue(options["noplaylist"])
            (Path(directory)/"clip.mp4").write_bytes(b"video")
            return {"id":"clip"}
        with patch.object(self.bot,"_extract_media",side_effect=extract), patch.dict(os.environ,{"YTDLP_COOKIE_FILE":"private-youtube-cookies"}):
            path=self.bot.download_youtube_video("https://www.instagram.com/reel/ABC12/",1080)
        self.assertTrue(Path(path).exists())
        scratch.remove_owned_file(path)
        self.assertFalse(Path(path).parent.exists())
