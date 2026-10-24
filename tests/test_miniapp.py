import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

from aiohttp.test_utils import TestClient, TestServer
from miniapp_server import BotLibrary, create_app, verify_init_data, public_song, public_url
from state_store import StateStore

TOKEN = '123456:offline-miniapp-fixture'


def signed(uid=77, **overrides):
    data = {'auth_date': str(int(time.time())), 'user': json.dumps({'id': uid, 'first_name': 'Test'})}
    data.update(overrides)
    secret = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    check = '\n'.join(f'{key}={value}' for key, value in sorted(data.items()))
    data['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


class MiniAuthTests(unittest.TestCase):
    def test_signed_identity_expiry_tampering_and_duplicate_fields(self):
        self.assertEqual(verify_init_data(signed(), TOKEN)['id'], 77)
        for value in [signed()+'&user=%7B%22id%22%3A78%7D', signed().replace('Test', 'Other'),
                      signed(auth_date=str(int(time.time())-4000)),
                      signed(auth_date=str(int(time.time())+300)), signed(uid=True), signed(uid=-1), '']:
            with self.subTest(value=value[:20]), self.assertRaises((ValueError, KeyError)):
                verify_init_data(value, TOKEN)

    def test_public_payload_never_contains_private_file_fields_or_unsafe_numbers(self):
        song = {'id': -10099999999999999, 'title': '<script>', 'artist': 'A', 'file_id': 'private',
                '_library_audio': '/private/77/file', 'url': 'https://private.example'}
        payload = public_song(song)
        self.assertEqual(payload['id'], str(song['id']))
        self.assertEqual(set(payload), {'id', 'title', 'artist', 'duration', 'kind', 'playable'})
        with patch.dict(os.environ, {'MINIAPP_URL': 'http://localhost:8765'}):
            self.assertIsNone(public_url())


class MiniApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = StateStore(Path(self.tmp.name)/'state.db')
        self.song = {'id': 1, 'title': 'User 77 song', 'artist': 'Artist'}
        self.favorites = {77: [dict(self.song)], 78: [{'id': 2, 'title': 'Private 78', 'artist': 'Private'}]}
        application = SimpleNamespace(user_data={77:{},78:{}}, bot_data={},
                                      bot=SimpleNamespace(username='offline_bot', send_message=AsyncMock()))
        self.bridge = BotLibrary(application, self.store, self.favorites, {}, frozenset())
        self.client = TestClient(TestServer(create_app(token=TOKEN, bridge=self.bridge)))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)
        self.headers = {'X-Telegram-Init-Data': signed()}

    async def test_static_assets_and_demo_do_not_expose_authenticated_library(self):
        for path in ['/', '/assets/app.css', '/assets/app.js', '/assets/audio.js', '/demo/0.wav']:
            response = await self.client.get(path)
            self.assertEqual(response.status, 200, path)
        response = await self.client.get('/api/library')
        self.assertEqual(response.status, 401)
        for path in ['/assets/bot.py','/assets/.env','/demo/9.wav']:
            self.assertEqual((await self.client.get(path)).status, 404)

    async def test_library_isolation_and_persistent_playlist_changes(self):
        payload = await (await self.client.get('/api/library', headers=self.headers)).json()
        self.assertEqual([s['title'] for s in payload['tracks']], ['User 77 song'])
        self.assertNotIn('Private 78', json.dumps(payload))
        response = await self.client.post('/api/library', headers=self.headers, json={'action':'create','name':'Night'})
        folder = (await response.json())['playlists'][0]['id']
        await self.client.post('/api/library', headers=self.headers, json={'action':'playlist','playlist':folder,'track':'1'})
        self.assertEqual(self.store.load_named('music_collections')[77][folder]['songs'][0]['id'], 1)
        self.assertEqual((await self.client.post('/api/library',headers=self.headers,json={'action':'favorite','track':'2','value':True})).status,404)
        self.assertEqual((await self.client.get('/api/audio/2', headers=self.headers)).status,404)
        self.assertEqual(self.favorites[78][0]['id'],2)
        await self.client.post('/api/library',headers=self.headers,json={'action':'remove','track':'1'})
        self.assertEqual(self.store.load()[1][77], [])
        self.assertEqual(self.store.load_named('music_collections')[77][folder]['songs'], [])

    async def test_maintenance_and_disabled_search_apply_to_miniapp(self):
        controls=SimpleNamespace(settings={'blocked':[], 'maintenance':True},enabled=lambda _:False)
        self.bridge.application.bot_data['controls']=controls
        self.assertEqual((await self.client.get('/api/library',headers=self.headers)).status,503)
        controls.settings['maintenance']=False
        with patch('versions.find_versions') as find:
            response=await self.client.get('/api/search?q=test',headers=self.headers)
            self.assertEqual(response.status,503)
            find.assert_not_called()

    async def test_search_uses_server_results_and_rate_limit(self):
        with patch('versions.find_versions',return_value=[{'url':'https://www.youtube.com/watch?v=abcdefghijk','title':'Found','artist':'A'}]):
            response=await self.client.get('/api/search?q=test',headers=self.headers)
            self.assertEqual(response.status,200)
            self.assertEqual((await response.json())['tracks'][0]['title'],'Found')
            self.assertEqual((await self.client.get('/api/search?q=again',headers=self.headers)).status,429)
        response=await self.client.post('/api/library',headers=self.headers,json={'action':'favorite','track':str(self.bridge.searches[77][0]['id']),'value':True,'url':'http://127.0.0.1/private'})
        self.assertEqual(response.status,200)
        self.assertTrue(self.favorites[77][-1]['url'].startswith('https://www.youtube.com/'))

    async def test_bot_and_miniapp_share_per_user_lock(self):
        from dispatch import user_lock
        lock=user_lock(77)
        async with lock:
            task=asyncio.create_task(self.client.get('/api/library',headers=self.headers))
            await asyncio.sleep(.03)
            self.assertFalse(task.done())
        self.assertEqual((await task).status,200)

    async def test_send_choices_use_authenticated_destination_and_existing_bot_handlers(self):
        self.bridge.application.bot.send_message.return_value=SimpleNamespace(message_id=10)
        with patch('versions.find_versions',return_value=[{'url':'https://www.youtube.com/watch?v=abcdefghijk','title':'Found','artist':'A'}]):
            response=await self.client.post('/api/send',headers=self.headers,json={'track':'1','user_id':78})
        self.assertEqual(response.status,200)
        self.assertEqual(self.bridge.application.bot.send_message.await_args.args[0],77)
        session=self.store.load_named('sessions')[77]
        request=next(iter(session['version_requests'].values()))
        self.assertEqual(request['mode'],'listen')
        self.assertEqual(request['candidates'][0]['url'],'https://www.youtube.com/watch?v=abcdefghijk')
        self.assertEqual((await self.client.post('/api/send',headers=self.headers,json={'track':'1'})).status,429)

    async def test_invalid_json_and_auth_have_no_side_effects_or_secret_echo(self):
        response=await self.client.post('/api/library',headers=self.headers,data='{')
        self.assertEqual(response.status,400)
        response=await self.client.post('/api/library',json={'action':'remove','track':'1','user_id':77})
        self.assertEqual(response.status,401)
        self.assertEqual(self.favorites[77][0]['id'],1)
        self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
        self.assertNotIn(TOKEN,await response.text())

    async def test_playlist_rename_remove_and_delete_keep_recordings(self):
        self.bridge.data(77)['music_collections']={'night':{'name':'Night','songs':[dict(self.song)]}}
        self.favorites[77]=[]
        response=await self.client.post('/api/library',headers=self.headers,json={'action':'rename','playlist':'night','name':'New name'})
        self.assertEqual((await response.json())['playlists'][0]['name'],'New name')
        response=await self.client.post('/api/library',headers=self.headers,json={'action':'playlist_remove','playlist':'night','track':'1'})
        payload=await response.json()
        self.assertEqual(payload['playlists'][0]['tracks'],[])
        self.assertEqual(payload['tracks'][0]['id'],'1')
        await self.client.post('/api/library',headers=self.headers,json={'action':'playlist','playlist':'night','track':'1'})
        response=await self.client.post('/api/library',headers=self.headers,json={'action':'delete_playlist','playlist':'night'})
        payload=await response.json()
        self.assertEqual(payload['playlists'],[])
        self.assertEqual(payload['tracks'][0]['id'],'1')
        self.assertEqual(self.store.load()[1][77][0]['id'],1)
        self.assertEqual((await self.client.post('/api/library',headers=self.headers,json={'action':'delete_playlist','playlist':'someone-else'})).status,404)

    async def test_failed_commit_preserves_live_library(self):
        self.bridge.data(77)['music_collections']={'night':{'name':'Night','songs':[dict(self.song)]}}
        with patch.object(self.store,'save_library',side_effect=OSError('private filesystem detail')):
            response=await self.client.post('/api/library',headers=self.headers,json={'action':'remove','track':'1'})
        self.assertEqual(response.status,500)
        self.assertNotIn('filesystem',await response.text())
        self.assertEqual(self.favorites[77][0]['id'],1)
        self.assertEqual(self.bridge.data(77)['music_collections']['night']['songs'][0]['id'],1)
