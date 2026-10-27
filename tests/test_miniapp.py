import asyncio
import hashlib
import hmac
import json
import io
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
import wave
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode, urlsplit

from aiohttp.test_utils import TestClient, TestServer
from aiohttp import FormData
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
        self.assertEqual(set(payload), {'id', 'title', 'artist', 'duration', 'kind', 'playable', 'cover', 'app_upload'})
        self.assertIsNone(public_song(dict(song,cover='https://127.0.0.1/private'))['cover'])
        cover='https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg'
        self.assertEqual(public_song(dict(song,cover=cover))['cover'],cover)
        with patch.dict(os.environ, {'MINIAPP_URL': 'http://localhost:8765'}):
            self.assertIsNone(public_url())


class MiniApiTests(unittest.IsolatedAsyncioTestCase):
    def upload_form(self, data=None):
        if data is None:
            buffer=io.BytesIO()
            with wave.open(buffer,'wb') as audio:
                audio.setparams((1,2,16000,0,'NONE','not compressed'))
                audio.writeframes(b'\x01\x00'*64000)
            data=buffer.getvalue()
        form=FormData()
        form.add_field('file',data,filename='My remix.wav',content_type='audio/wav')
        return form

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = StateStore(Path(self.tmp.name)/'state.db')
        self.song = {'id': 1, 'title': 'User 77 song', 'artist': 'Artist'}
        self.favorites = {77: [dict(self.song)], 78: [{'id': 2, 'title': 'Private 78', 'artist': 'Private'}]}
        application = SimpleNamespace(user_data={77:{},78:{}}, bot_data={},
                                      bot=SimpleNamespace(username='offline_bot', send_message=AsyncMock()))
        self.bridge = BotLibrary(application, self.store, self.favorites, {}, frozenset(), cache_root=Path(self.tmp.name)/'app-cache')
        self.client = TestClient(TestServer(create_app(token=TOKEN, bridge=self.bridge)))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)
        self.headers = {'X-Telegram-Init-Data': signed()}

    async def test_static_assets_and_demo_do_not_expose_authenticated_library(self):
        for path in ['/', '/assets/app.css', '/assets/app.js', '/assets/audio.js', '/assets/dj.js', '/assets/dj-effects.js', '/assets/dj-loop-processor.js', '/assets/dj-recorder.js', '/assets/dj-recorder-processor.js', '/assets/SoundTouchNode.js', '/assets/constants.js', '/assets/soundtouch-processor.js', '/assets/soundtouch-LICENSE.txt', '/assets/soundtouch-NOTICE.json', '/demo/0.wav']:
            response = await self.client.get(path)
            self.assertEqual(response.status, 200, path)
        response = await self.client.get('/api/library')
        self.assertEqual(response.status, 401)
        for path in ['/assets/bot.py','/assets/.env','/demo/9.wav']:
            self.assertEqual((await self.client.get(path)).status, 404)

    async def test_source_versions_use_original_chart_identity_and_remain_owner_scoped(self):
        song=dict(id=90,title='Video label',artist='Uploader',url='https://www.youtube.com/watch?v=abcdefghijk',_catalog_song={'title':'Perfect','artist':'Ed Sheeran'})
        self.bridge.chart_recordings[77]=[song]
        found=dict(title='Perfect Cover',artist='Singer',duration=261.5,url='https://soundcloud.com/singer/perfect-cover',source='SoundCloud')
        self.assertEqual((await self.client.post('/api/versions',json={'track':'90'})).status,401)
        with patch('soundcloud_source.search',return_value=[found]) as search,patch('versions.find_versions') as youtube:
            response=await self.client.post('/api/versions',headers=self.headers,json={'track':'90','source':'next'})
            self.assertEqual(response.status,200)
            payload=await response.json()
        search.assert_called_once_with('Perfect Ed Sheeran',5);youtube.assert_not_called()
        self.assertEqual(payload['source'],'SoundCloud')
        candidate=payload['tracks'][0]
        resolved=await self.bridge.find(77,candidate['id'])
        self.assertEqual(resolved['_catalog_song'],song['_catalog_song'])
        self.assertNotIn('_catalog_song',candidate)
        self.assertEqual((await self.client.post('/api/versions',headers={'X-Telegram-Init-Data':signed(uid=78)},json={'track':candidate['id'],'source':'jam'})).status,404)
        with patch('jamendo_source.search',return_value=[]) as search:
            response=await self.client.post('/api/versions',headers=self.headers,json={'track':candidate['id'],'source':'next'})
            self.assertEqual(response.status,200)
            self.assertEqual((await response.json())['source'],'Jamendo')
        search.assert_called_once_with('Perfect Ed Sheeran',5)
        self.assertEqual((await self.client.post('/api/versions',headers=self.headers,json={'track':'90','source':'unknown'})).status,400)
        self.assertFalse(self.bridge.data(77).get('_source_search_busy'))

    async def test_sound_presets_are_private_persistent_and_validated(self):
        self.assertEqual((await self.client.get('/api/presets')).status,401)
        payload={'action':'save','name':'Night sound','user_id':78,'settings':{'speed':1.25,'pitch':-2,'bass':3,'effects':['reverb','echo'],'params':{'feedback':.3}}}
        response=await self.client.post('/api/presets',headers=self.headers,json=payload)
        self.assertEqual(response.status,200)
        item=(await response.json())['presets'][0]
        self.assertEqual(item['settings']['pitch'],-2)
        self.assertEqual(self.store.load_named('studio_presets')[77][0]['name'],'Night sound')
        other={'X-Telegram-Init-Data':signed(78)}
        self.assertEqual((await(await self.client.get('/api/presets',headers=other)).json())['presets'],[])
        self.assertEqual((await self.client.post('/api/presets',headers=other,json={'action':'remove','id':item['id']})).status,404)
        bad=dict(payload,settings={'params':{'ffmpeg':'arbitrary filter'}})
        self.assertEqual((await self.client.post('/api/presets',headers=self.headers,json=bad)).status,400)
        self.assertEqual((await self.client.post('/api/presets',headers=self.headers,json=dict(payload,settings={'speed':99}))).status,400)
        response=await self.client.post('/api/presets',headers=self.headers,json={'action':'remove','id':item['id']})
        self.assertEqual((await response.json())['presets'],[])

    async def test_named_sound_does_not_store_track_paths_or_crop_other_tracks(self):
        response=await self.client.post('/api/presets',headers=self.headers,json={'action':'save','name':'Linked','settings':{'linked':True,'speed':2,'pitch':0,'start':90,'end':100,'source_track':'private','source_ticket':'secret'}})
        config=(await response.json())['presets'][0]['settings']
        self.assertEqual(config['pitch'],12)
        for key in ('start','end','source_track','source_ticket'):self.assertNotIn(key,config)

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

    async def test_all_source_search_survives_youtube_failure_and_can_switch_immediately(self):
        recording=dict(title='Original song',artist='Singer',url='https://soundcloud.com/singer/original',source='SoundCloud')
        def search(song,source):
            self.assertEqual(song['_search_query'],'original song')
            if source=='yt':raise RuntimeError('YouTube unavailable')
            return [dict(recording)] if source=='sc' else []
        with patch('versions.source_search',side_effect=search) as searcher:
            response=await self.client.get('/api/search?q=original+song',headers=self.headers)
            self.assertEqual(response.status,200)
            payload=await response.json()
            self.assertEqual([g['source'] for g in payload['groups']],['SoundCloud'])
            identifier=payload['tracks'][0]['id']
            self.assertEqual((await self.bridge.find(77,identifier))['_search_query'],'original song')
            self.assertEqual(searcher.call_count,3)
            response=await self.client.get('/api/search?q=original+song&source=sc',headers=self.headers)
            self.assertEqual(response.status,200)
            self.assertEqual((await response.json())['tracks'][0]['title'],'Original song')
            self.assertEqual((await self.client.get('/api/search?q=original+song&source=sc',headers=self.headers)).status,429)
        self.assertEqual((await self.client.get('/api/search?q=original+song&source=invalid',headers=self.headers)).status,400)

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

    async def test_send_soundcloud_choice_preserves_its_source_without_youtube_lookup(self):
        song=dict(id=90,title='Selected SC recording',artist='Singer',url='https://soundcloud.com/singer/selected',source='SoundCloud')
        self.bridge.searches[77]=[song]
        self.bridge.application.bot.send_message.return_value=SimpleNamespace(message_id=10)
        with patch('versions.find_versions') as youtube:
            response=await self.client.post('/api/send',headers=self.headers,json={'track':'90'})
        self.assertEqual(response.status,200);youtube.assert_not_called()
        request=next(iter(self.store.load_named('sessions')[77]['version_requests'].values()))
        self.assertEqual(request['candidates'],[song]);self.assertEqual(request['source'],'sc')

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
        self.assertEqual(self.store.load()[1][77],[])
        self.assertEqual(self.store.load_named('miniapp_library')[77][0]['id'],1)
        self.assertEqual((await self.client.post('/api/library',headers=self.headers,json={'action':'delete_playlist','playlist':'someone-else'})).status,404)

    async def test_failed_commit_preserves_live_library(self):
        self.bridge.data(77)['music_collections']={'night':{'name':'Night','songs':[dict(self.song)]}}
        with patch.object(self.store,'save_library',side_effect=OSError('private filesystem detail')):
            response=await self.client.post('/api/library',headers=self.headers,json={'action':'remove','track':'1'})
        self.assertEqual(response.status,500)
        self.assertNotIn('filesystem',await response.text())
        self.assertEqual(self.favorites[77][0]['id'],1)
        self.assertEqual(self.bridge.data(77)['music_collections']['night']['songs'][0]['id'],1)

    async def test_chat_and_app_share_language_unstarred_tracks_and_deletion(self):
        from library_ui import handle_library,all_saved
        data=self.bridge.data(77)
        context=SimpleNamespace(user_data=data)
        data['miniapp_library']=[dict(self.song)]
        self.favorites[77]=[]
        data['music_collections']={'abcdef12':{'name':'Shared','songs':[dict(self.song)]}}
        response=await self.client.post('/api/library',headers=self.headers,json={'action':'language','language':'en'})
        self.assertEqual(response.status,200)
        self.assertEqual(context.user_data['language'],'en')
        self.assertEqual(self.store.load_named('sessions')[77]['language'],'en')
        # A bot language change is immediately visible to the authenticated app.
        context.user_data['language']='ru'
        self.assertEqual((await(await self.client.get('/api/library',headers=self.headers)).json())['language'],'ru')
        update=SimpleNamespace(effective_user=SimpleNamespace(id=77),callback_query=SimpleNamespace(data='lib:mark:abcdef12:1:0',answer=AsyncMock()))
        with patch('library_ui.screen',new=AsyncMock()):
            await handle_library(update,context,self.favorites,AsyncMock(),self.store,{},AsyncMock(),AsyncMock())
        payload=await(await self.client.get('/api/library',headers=self.headers)).json()
        self.assertEqual(payload['favorites'],[])
        self.assertEqual(payload['playlists'][0]['tracks'],[])
        self.assertEqual(len(all_saved(77,self.favorites,data['music_collections'],data['miniapp_library'])),1)
        update.callback_query.data='lib:confirmdelete:1'
        with patch('library_ui.screen',new=AsyncMock()):
            await handle_library(update,context,self.favorites,AsyncMock(),self.store,{},AsyncMock(),AsyncMock())
        payload=await(await self.client.get('/api/library',headers=self.headers)).json()
        self.assertEqual(payload['tracks'],[])
        self.assertEqual(self.store.load_named('miniapp_library')[77],[])

    async def test_bot_card_can_open_own_track_in_app_without_saving_it(self):
        self.bridge.data(77)['track_cards']={'a'*10:{'id':999,'title':'Bot search result','artist':'Artist'}}
        response=await self.client.get('/api/track/999',headers=self.headers)
        self.assertEqual(response.status,200)
        self.assertEqual((await response.json())['track']['title'],'Bot search result')
        self.assertEqual((await self.client.get('/api/track/999',headers={'X-Telegram-Init-Data':signed(78)})).status,404)
        self.assertEqual((await self.client.get('/api/track/999')).status,401)
        self.assertEqual([song['id'] for song in self.favorites[77]],[1])

    async def test_app_saved_audio_returns_to_chat_with_shared_studio_controls(self):
        source=Path(self.tmp.name)/'mix.mp3';source.write_bytes(b'fixture audio')
        self.bridge.audio_jobs.retain(77,1,source)
        with patch('audio_presentation.send_music',new=AsyncMock()) as send:
            response=await self.client.post('/api/send',headers=self.headers,json={'track':'1'})
        self.assertEqual(response.status,200)
        markup=send.await_args.kwargs['reply_markup']
        buttons=[button for row in markup.inline_keyboard for button in row]
        self.assertTrue(any(button.callback_data and ':studio:' in button.callback_data for button in buttons))
        cards=self.store.load_named('sessions')[77]['track_cards']
        self.assertEqual(next(iter(cards.values()))['id'],1)

    async def test_app_prepares_and_plays_audio_without_chat_or_chat_session_changes(self):
        source=Path(self.tmp.name)/'download.mp3'
        source.write_bytes(b'offline full audio fixture')
        calls=[]
        def download(url):
            calls.append(url)
            return str(source), {'title':'Found'}
        self.bridge.audio_jobs.downloader=download
        self.song['url']='https://www.youtube.com/watch?v=abcdefghijk'
        self.favorites[77]=[dict(self.song)]
        self.bridge.data(77)['downloaded_song']={'id':99,'title':'Chat track'}
        self.bridge.data(77)['last_audio_path']='chat-audio-do-not-change'
        response=await self.client.post('/api/prepare',headers=self.headers,json={'track':'1','url':'http://127.0.0.1/private','user_id':78})
        info=await response.json()
        job=self.bridge.audio_jobs.get(77,info['job'])
        await job.task
        response=await self.client.get('/api/jobs/'+job.token,headers=self.headers)
        self.assertEqual((await response.json())['status'],'ready')
        response=await self.client.get('/api/audio/1',headers=self.headers)
        self.assertEqual(await response.read(),source.read_bytes())
        self.assertEqual(calls,['https://www.youtube.com/watch?v=abcdefghijk'])
        self.bridge.application.bot.send_message.assert_not_awaited()
        self.assertEqual(self.bridge.data(77)['downloaded_song']['id'],99)
        self.assertEqual(self.bridge.data(77)['last_audio_path'],'chat-audio-do-not-change')
        self.assertNotIn(77,self.store.load_named('sessions'))
        self.assertEqual(self.store.load_named('miniapp_recent')[77][0]['id'],1)
        response=await self.client.post('/api/prepare',headers=self.headers,json={'track':'1'})
        self.assertEqual((await response.json())['status'],'ready')
        self.assertEqual(len(calls),1)

    async def test_app_job_is_private_and_cancellable(self):
        from operations import checkpoint
        def download(_):
            for _ in range(100):
                time.sleep(.01)
                checkpoint()
            raise AssertionError('Cancellation did not arrive')
        self.bridge.audio_jobs.downloader=download
        self.favorites[77][0]['url']='https://www.youtube.com/watch?v=abcdefghijk'
        response=await self.client.post('/api/prepare',headers=self.headers,json={'track':'1'})
        token=(await response.json())['job']
        other={'X-Telegram-Init-Data':signed(78)}
        self.assertEqual((await self.client.get('/api/jobs/'+token,headers=other)).status,404)
        self.assertEqual((await self.client.get('/api/audio/1',headers=other)).status,404)
        await self.client.post('/api/jobs/'+token+'/cancel',headers=self.headers,json={})
        await self.bridge.audio_jobs.get(77,token).task
        response=await self.client.get('/api/jobs/'+token,headers=self.headers)
        self.assertEqual((await response.json())['status'],'cancelled')
        self.assertIsNone(self.bridge.audio_jobs.path(77,1))
        self.bridge.application.bot.send_message.assert_not_awaited()

    async def test_catalog_recording_choices_stay_inside_app(self):
        with patch('versions.find_versions',return_value=[{'url':'https://www.youtube.com/watch?v=abcdefghijk','title':'Recording','artist':'A'}]):
            response=await self.client.post('/api/prepare',headers=self.headers,json={'track':'1'})
        payload=await response.json()
        self.assertEqual(payload['status'],'choices')
        self.assertEqual(payload['tracks'][0]['title'],'Recording')
        self.bridge.application.bot.send_message.assert_not_awaited()

    async def test_failed_audio_job_does_not_expose_provider_error(self):
        def download(_):
            raise ValueError('private provider token and path')
        self.bridge.audio_jobs.downloader=download
        self.favorites[77][0]['url']='https://www.youtube.com/watch?v=abcdefghijk'
        response=await self.client.post('/api/prepare',headers=self.headers,json={'track':'1'})
        token=(await response.json())['job']
        await self.bridge.audio_jobs.get(77,token).task
        response=await self.client.get('/api/jobs/'+token,headers=self.headers)
        text=await response.text()
        self.assertEqual(json.loads(text)['status'],'failed')
        self.assertNotIn('provider token',text)
        self.assertNotIn('path',text)

    async def test_native_download_links_are_private_scoped_and_expire(self):
        source=Path(self.tmp.name)/'audio.mp3';source.write_bytes(b'private audio')
        self.bridge.audio_jobs.retain(77,1,source)
        with patch.dict(os.environ,{'MINIAPP_URL':'https://preview.example.test'}):
            response=await self.client.post('/api/download',headers=self.headers,json={'track':'1'})
        ticket=await response.json()
        path=urlsplit(ticket['url']).path
        response=await self.client.get(path)
        self.assertEqual(await response.read(),b'private audio')
        self.assertIn('attachment',response.headers['Content-Disposition'])
        other={'X-Telegram-Init-Data':signed(78)}
        with patch.dict(os.environ,{'MINIAPP_URL':'https://preview.example.test'}):
            self.assertEqual((await self.client.post('/api/download',headers=other,json={'track':'1'})).status,404)
        self.assertEqual((await self.client.get('/download/'+'x'*32)).status,404)
        self.bridge.download_tickets[path.rsplit('/',1)[-1]]['expires']=0
        self.assertEqual((await self.client.get(path)).status,404)

    async def test_stream_tickets_allow_seeking_and_preserve_privacy(self):
        source=Path(self.tmp.name)/'audio.mp3';source.write_bytes(b'private audio')
        self.bridge.audio_jobs.retain(77,1,source)
        self.assertEqual((await self.client.post('/api/stream',json={'track':'1'})).status,401)
        with patch.dict(os.environ,{'MINIAPP_URL':'https://preview.example.test'}):
            response=await self.client.post('/api/stream',headers=self.headers,json={'track':'1'})
            ticket=await response.json()
            repeated=await (await self.client.post('/api/stream',headers=self.headers,json={'track':'1'})).json()
            self.assertEqual(repeated,ticket)
            other={'X-Telegram-Init-Data':signed(78)}
            self.assertEqual((await self.client.post('/api/stream',headers=other,json={'track':'1'})).status,404)
        path=urlsplit(ticket['url']).path
        response=await self.client.get(path,headers={'Range':'bytes=2-5'})
        self.assertEqual(response.status,206)
        self.assertEqual(await response.read(),b'ivat')
        self.assertTrue(response.headers['Content-Type'].startswith('audio/'))
        self.assertIn('inline',response.headers['Content-Disposition'])
        self.assertEqual((await self.client.get(path.replace('/stream/','/download/'))).status,404)
        self.bridge.download_tickets[path.rsplit('/',1)[-1]]['expires']=0
        self.assertEqual((await self.client.get(path)).status,404)

    async def test_upload_saves_own_audio_inside_app_without_chat(self):
        with patch.dict(os.environ,{'AUDIO_CACHE_DIR':str(Path(self.tmp.name)/'audio')}):
            response=await self.client.post('/api/upload',headers=self.headers,data=self.upload_form())
            self.assertEqual(response.status,200,await response.text())
            result=await response.json();identifier=result['track']['id']
            self.assertEqual(result['track']['kind'],'upload')
            self.assertTrue(result['track']['playable'])
            self.assertIsInstance(identifier,str)
            self.assertNotIn('_library_audio',json.dumps(result))
            response=await self.client.get('/api/audio/'+identifier,headers=self.headers)
            self.assertEqual(response.status,200)
            self.assertTrue((await response.read()).startswith(b'RIFF'))
            self.assertIn('audio/',response.headers['Content-Type'])
            self.assertEqual((await self.client.get('/api/audio/'+identifier,headers={'X-Telegram-Init-Data':signed(78)})).status,404)
            await self.client.post('/api/upload',headers=self.headers,data=self.upload_form())
            self.assertEqual(len(self.favorites[77]),2)
            self.bridge.application.bot.send_message.assert_not_awaited()

    async def test_invalid_upload_is_rejected_without_library_changes(self):
        with patch.dict(os.environ,{'AUDIO_CACHE_DIR':str(Path(self.tmp.name)/'audio')}):
            response=await self.client.post('/api/upload',headers=self.headers,data=self.upload_form(b'not an audio file'))
        self.assertEqual(response.status,400)
        self.assertEqual(len(self.favorites[77]),1)
        self.bridge.application.bot.send_message.assert_not_awaited()

    async def test_upload_capacity_guard_preserves_library(self):
        with patch.dict(os.environ,{'AUDIO_CACHE_DIR':str(Path(self.tmp.name)/'audio')}),patch('app_uploads.MAX_USER_BYTES',1):
            response=await self.client.post('/api/upload',headers=self.headers,data=self.upload_form())
        self.assertEqual(response.status,507)
        self.assertEqual(len(self.favorites[77]),1)

    async def test_unfavoriting_does_not_delete_app_library_track(self):
        self.bridge.searches[77]=[{'id':100,'title':'App track','artist':'A','url':'https://www.youtube.com/watch?v=abcdefghijk'}]
        await self.client.post('/api/library',headers=self.headers,json={'action':'favorite','track':'100','value':True})
        response=await self.client.post('/api/library',headers=self.headers,json={'action':'favorite','track':'100','value':False})
        result=await response.json()
        self.assertNotIn('100',result['favorites'])
        self.assertIn('100',[s['id'] for s in result['tracks']])
        self.assertEqual(self.store.load_named('miniapp_library')[77][0]['id'],100)

    async def test_explicit_uploaded_file_deletion_reclaims_storage(self):
        with patch.dict(os.environ,{'AUDIO_CACHE_DIR':str(Path(self.tmp.name)/'audio')}):
            response=await self.client.post('/api/upload',headers=self.headers,data=self.upload_form())
            identifier=(await response.json())['track']['id']
            metadata=self.store.load_named('miniapp_library')[77][0]
            path=Path(metadata['_library_audio'])
            self.assertTrue(path.is_file())
            await self.client.post('/api/prepare',headers=self.headers,json={'track':identifier})
            await self.client.post('/api/library',headers=self.headers,json={'action':'favorite','track':identifier,'value':False})
            self.assertTrue(path.is_file())
            await self.client.post('/api/library',headers=self.headers,json={'action':'remove','track':identifier,'delete_file':True})
            self.assertFalse(path.exists())
            self.assertEqual(self.store.load_named('miniapp_library')[77],[])
            self.assertEqual(self.store.load_named('miniapp_recent')[77],[])

    async def test_missing_own_file_is_never_replaced_by_catalog_search(self):
        self.favorites[77]=[{'id':-999,'title':'My private remix','artist':'','kind':'upload'}]
        with patch('versions.find_versions') as finder:
            response=await self.client.post('/api/prepare',headers=self.headers,json={'track':'-999'})
        self.assertEqual(response.status,410)
        finder.assert_not_called()
