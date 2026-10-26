"""Optional Mini App, sharing the bot's live library and per-user lock.

Local preview: python miniapp_server.py --demo (no token or private data).
Production identity is exclusively verified Telegram initData, never client IDs.
"""
import argparse
from app_limits import MEDIA_BYTES
import asyncio
from copy import deepcopy
from functools import lru_cache
import hashlib
import hmac
import io
import json
import math
import mimetypes
import os
import re
from pathlib import Path
import secrets
import struct
import tempfile
import time
from urllib.parse import parse_qsl, urlsplit, quote
import wave

from aiohttp import web

ASSETS = Path(__file__).with_name('miniapp')


def verify_init_data(raw, token, *, now=None):
    if not token or not raw or len(raw) > 8192:
        raise ValueError('Unauthorized')
    pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=32)
    data = dict(pairs)
    if len(data) != len(pairs):
        raise ValueError('Duplicate authentication fields')
    supplied = data.pop('hash', '')
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    check = '\n'.join(f'{key}={value}' for key, value in sorted(data.items()))
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise ValueError('Unauthorized')
    age = (time.time() if now is None else now) - int(data['auth_date'])
    if not -30 <= age <= 3600:
        raise ValueError('Expired authentication')
    user = json.loads(data['user'])
    if type(user.get('id')) is not int or not 0 < user['id'] < 2**53:
        raise ValueError('Invalid identity')
    return user


def public_song(song, playable=False):
    # IDs are strings: upload identities can exceed JavaScript's integer range.
    cover = song.get('cover')
    if not isinstance(cover, str) or not re.fullmatch(r'https://i\.ytimg\.com/vi/[A-Za-z0-9_-]{11}/(?:hqdefault|mqdefault|default)\.jpg', cover):
        cover = None
    from jamendo_source import identifier,license_url
    catalog=bool(identifier(song.get('url')) and license_url(song.get('license_url')))
    return {**({'source':'Jamendo','source_url':song['url'],'license_url':license_url(song.get('license_url'))} if catalog else {}),
            'id': str(song['id']), 'title': str(song.get('title') or 'Audio')[:180],
            'artist': str(song.get('artist') or '')[:120],
            'duration': song.get('duration') if isinstance(song.get('duration'), (int, float)) else None,
            'kind': 'upload' if song.get('kind') == 'upload' else 'track', 'playable': playable, 'cover':cover,
            'app_upload':song.get('app_upload') is True}


@lru_cache(maxsize=6)
def demo_audio(number):
    """Original small synthesised loops; no third-party recordings or API calls."""
    rate, duration = 16000, 24
    roots = (110, 130.81, 146.83, 98, 123.47, 164.81)
    root = roots[number % len(roots)]
    samples = bytearray()
    for i in range(rate * duration):
        t = i / rate
        beat = t % .5
        kick = math.sin(2*math.pi*(48*beat + 9*(1-math.exp(-beat*25)))) * math.exp(-beat*18)
        chord = sum(math.sin(2*math.pi*root*ratio*t) for ratio in (1, 1.25, 1.5)) / 3
        melody = math.sin(2*math.pi*root*(2, 2.5, 3, 3.75)[int(t*2) % 4]*t)
        fade = min(1, t*3, (duration-t)*3)
        value = int(11000 * fade * (.4*chord + .35*kick + .13*melody))
        samples.extend(struct.pack('<h', value))
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        audio.writeframes(samples)
    return output.getvalue()


class BotLibrary:
    def __init__(self, application, store, favorites, saved_sessions, owner_ids, downloader=None, cache_root=None):
        self.application, self.store, self.favorites = application, store, favorites
        self.saved_sessions, self.owner_ids = saved_sessions, owner_ids
        self.searches = {}
        self.chart_recordings = {}
        self.search_times = {}
        self.send_times = {}
        self.search_slots = asyncio.Semaphore(2)
        self.upload_slots = asyncio.Semaphore(2)
        from miniapp_jobs import AudioJobs
        self.audio_jobs = AudioJobs(downloader, cache_root)
        self.download_tickets = {}

    def data(self, uid):
        data = self.application.user_data[uid]
        if uid in self.saved_sessions:
            saved = dict(self.saved_sessions.pop(uid))
            from telegram import Update
            for key in ('voice_update', 'audio_update'):
                if saved.get(key):
                    saved[key] = Update.de_json(saved[key], self.application.bot)
            data.update(saved)
        return data

    async def folders(self, uid):
        data = self.data(uid)
        if 'music_collections' not in data:
            data['music_collections'] = (await asyncio.to_thread(self.store.load_named, 'music_collections')).get(uid, {})
        return data['music_collections']

    def allowed(self, uid, feature=None):
        controls = self.application.bot_data.get('controls')
        if uid in self.owner_ids or not controls:
            return
        settings = controls.settings
        if uid in settings['blocked']:
            raise web.HTTPForbidden(text='Access restricted')
        if settings['maintenance'] or (feature and not controls.enabled(feature)):
            raise web.HTTPServiceUnavailable(text='Temporarily unavailable')

    async def songs(self, uid):
        from library_ui import all_saved
        songs = list(await self.app_library(uid)) + all_saved(uid, self.favorites, await self.folders(uid))
        return list({song['id']:song for song in songs}.values())

    async def app_library(self, uid):
        data = self.data(uid)
        if 'miniapp_library' not in data:
            data['miniapp_library'] = (await asyncio.to_thread(self.store.load_named, 'miniapp_library')).get(uid, [])
        return data['miniapp_library']

    def audio_path(self, uid, song):
        cached = self.audio_jobs.touch(uid, song['id'])
        if cached:
            return cached
        from uploaded_media import owned_path
        path = owned_path(song.get('_library_audio'), uid)
        if path:
            return path
        data = self.data(uid)
        if str(data.get('downloaded_song', {}).get('id')) == str(song['id']):
            return owned_path(data.get('last_audio_path'), uid, active=True)
        return None

    async def snapshot(self, uid):
        songs = await self.songs(uid)
        recent = await self.app_history(uid)
        return {'tracks': [public_song(song, bool(self.audio_path(uid, song))) for song in songs],
                'recent': [public_song(song, bool(self.audio_path(uid, song))) for song in recent[:8]],
                'favorites': [str(song['id']) for song in self.favorites.get(uid, [])],
                'playlists': [{'id': key, 'name': value['name'], 'tracks': [str(s['id']) for s in value['songs']]}
                              for key, value in (await self.folders(uid)).items()],
                'language': self.data(uid).get('language', 'ru'),
                'bot': self.application.bot.username}

    async def app_history(self, uid):
        data = self.data(uid)
        if 'miniapp_recent' not in data:
            data['miniapp_recent'] = (await asyncio.to_thread(self.store.load_named, 'miniapp_recent')).get(uid, [])
        return data['miniapp_recent']

    async def remember_app_track(self, uid, song):
        recent = [dict(song)] + [s for s in await self.app_history(uid) if s['id'] != song['id']]
        recent = recent[:20]
        await asyncio.to_thread(self.store.save_named, 'miniapp_recent', uid, recent)
        self.data(uid)['miniapp_recent'] = recent

    async def find(self, uid, identifier):
        sources = await self.songs(uid)
        active = self.data(uid).get('downloaded_song')
        if active:
            sources.append(active)
        sources.extend(self.searches.get(uid, []))
        sources.extend(self.chart_recordings.get(uid, []))
        sources.extend(await self.app_history(uid))
        sources.extend(job.song for job in self.audio_jobs.jobs.values() if job.uid == uid)
        song = next((s for s in sources if str(s['id']) == identifier), None)
        if not song:
            raise web.HTTPNotFound()
        return song

    async def search(self, uid, query):
        self.allowed(uid, 'search')
        if time.monotonic() - self.search_times.get(uid, 0) < 3:
            raise web.HTTPTooManyRequests()
        self.search_times[uid] = time.monotonic()
        if len(self.search_times) > 1000:
            oldest = min(self.search_times, key=self.search_times.get)
            self.search_times.pop(oldest, None)
            self.searches.pop(oldest, None)
        from versions import find_versions
        async with self.search_slots:
            result = await asyncio.to_thread(find_versions, query)
        for song in result:
            song['id'] = 10**15 + int.from_bytes(hashlib.sha256(song['url'].encode()).digest()[:6], 'big')
        self.searches[uid] = result
        return {'tracks': [public_song(s) for s in result]}

    def job_payload(self, job):
        return {'job': job.token, 'status': job.state, 'error': job.error,
                'track': public_song(job.song, job.state == 'ready')}

    async def prepare(self, uid, identifier):
        self.allowed(uid, 'downloads')
        song = await self.find(uid, identifier)
        if self.audio_path(uid, song):
            await self.remember_app_track(uid, song)
            return {'status':'ready', 'track':public_song(song, True)}
        if song.get('kind') == 'upload':
            raise web.HTTPGone()
        from jamendo_source import identifier as jamendo_id
        if not re.fullmatch(r'https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}', song.get('url', '')) and not jamendo_id(song.get('url')):
            self.allowed(uid, 'search')
            from versions import find_versions
            async with self.search_slots:
                candidates = await asyncio.to_thread(find_versions, song['title']+' '+song.get('artist', ''))
            for item in candidates:
                item['id'] = 10**15 + int.from_bytes(hashlib.sha256(item['url'].encode()).digest()[:6], 'big')
            self.searches[uid] = candidates
            return {'status':'choices', 'tracks':[public_song(item) for item in candidates]}
        try:
            return self.job_payload(self.audio_jobs.start(uid, song))
        except ValueError:
            raise web.HTTPTooManyRequests() from None

    async def download_ticket(self, uid, identifier, *, stream=False):
        self.allowed(uid, 'downloads')
        song = await self.find(uid, identifier)
        if not self.audio_path(uid, song) or not public_url():
            raise web.HTTPConflict()
        now = time.monotonic()
        self.download_tickets = {key:item for key,item in self.download_tickets.items() if item['expires'] > now}
        if stream:
            for token, item in self.download_tickets.items():
                if item.get('stream') and item['uid'] == uid and str(item['song']['id']) == str(song['id']) and item['expires'] > now+600:
                    return {'url':public_url().rstrip('/')+'/stream/'+token, 'filename':item['filename']}
        if len(self.download_tickets) >= 256:
            raise web.HTTPTooManyRequests()
        token = secrets.token_urlsafe(24)
        name = song.get('original_filename') if song.get('kind') == 'upload' else str(song.get('title') or 'SwiDJ')+'.mp3'
        name = re.sub(r'[\x00-\x1f\x7f/\\:*?"<>|]', '', name or 'SwiDJ.audio')[:150]
        self.download_tickets[token] = {'uid':uid, 'song':dict(song), 'expires':now+(10800 if stream else 120), 'filename':name, 'stream':stream}
        return {'url':public_url().rstrip('/')+('/stream/' if stream else '/download/')+token, 'filename':name}

    async def change(self, uid, payload):
        from library_ui import clean_name, MAX_TRACKS
        folders = deepcopy(await self.folders(uid))
        favorites = deepcopy(self.favorites.get(uid, []))
        app_tracks = deepcopy(await self.app_library(uid))
        removed_upload = None
        action = payload.get('action')
        if action == 'language':
            if payload.get('language') not in ('ru', 'en'):
                raise web.HTTPBadRequest()
            # Merge rather than replacing the bot's durable session.
            sessions = await asyncio.to_thread(self.store.load_named, 'sessions')
            session = dict(sessions.get(uid, {}), language=payload['language'])
            await asyncio.to_thread(self.store.save_named, 'sessions', uid, session)
            self.data(uid)['language'] = payload['language']
            return await self.snapshot(uid)
        elif action == 'create':
            name = clean_name(str(payload.get('name', '')))
            if not name or len(folders) >= 20:
                raise web.HTTPBadRequest()
            folders[secrets.token_hex(4)] = {'name': name, 'songs': []}
        elif action in ('rename', 'delete_playlist', 'playlist_remove'):
            key = str(payload.get('playlist', ''))
            folder = folders.get(key)
            if folder is None:
                raise web.HTTPNotFound()
            if action == 'rename':
                name = clean_name(str(payload.get('name', '')))
                if not name:
                    raise web.HTTPBadRequest()
                folder['name'] = name
            else:
                removed = folder['songs'] if action == 'delete_playlist' else [
                    s for s in folder['songs'] if str(s['id']) == str(payload.get('track', ''))]
                # Removing a playlist/membership keeps the recordings in the library.
                known = {s['id'] for s in favorites}
                favorites.extend(dict(s) for s in removed if s['id'] not in known)
                if action == 'delete_playlist':
                    del folders[key]
                else:
                    folder['songs'] = [s for s in folder['songs'] if str(s['id']) != str(payload.get('track', ''))]
        elif action in ('favorite', 'playlist', 'remove'):
            song = await self.find(uid, str(payload.get('track', '')))
            if action == 'playlist' or (action == 'favorite' and payload.get('value') is True):
                if not any(s['id'] == song['id'] for s in app_tracks):
                    if len(app_tracks) >= 200:
                        raise web.HTTPConflict()
                    app_tracks.append(dict(song))
            if action == 'favorite':
                present = any(s['id'] == song['id'] for s in favorites)
                if payload.get('value') is True and not present:
                    if len(favorites) >= MAX_TRACKS:
                        raise web.HTTPConflict()
                    favorites.append(dict(song))
                elif payload.get('value') is False:
                    favorites = [s for s in favorites if s['id'] != song['id']]
            elif action == 'playlist':
                folder = folders.get(str(payload.get('playlist')))
                if folder is None:
                    raise web.HTTPNotFound()
                if len(folder['songs']) >= MAX_TRACKS:
                    raise web.HTTPConflict()
                if not any(s['id'] == song['id'] for s in folder['songs']):
                    folder['songs'].append(dict(song))
            else:
                app_tracks = [s for s in app_tracks if s['id'] != song['id']]
                if payload.get('delete_file') is True and song.get('app_upload') is True:
                    removed_upload = song
                favorites = [s for s in favorites if s['id'] != song['id']]
                for folder in folders.values():
                    folder['songs'] = [s for s in folder['songs'] if s['id'] != song['id']]
        else:
            raise web.HTTPBadRequest()
        app_recent = [s for s in await self.app_history(uid) if s['id'] != removed_upload['id']] if removed_upload else None
        await asyncio.to_thread(self.store.save_library, uid, favorites, folders, app_tracks, app_recent)
        self.favorites[uid] = favorites
        self.data(uid)['music_collections'] = folders
        self.data(uid)['miniapp_library'] = app_tracks
        if app_recent is not None:
            self.data(uid)['miniapp_recent'] = app_recent
        if removed_upload:
            from uploaded_media import owned_path
            path = owned_path(removed_upload.get('_library_audio'), uid)
            if path and re.fullmatch(r'app-[a-f0-9]{24}\.(mp3|wav|ogg|flac|m4a)', path.name):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
        return await self.snapshot(uid)

    async def send(self, uid, identifier):
        self.allowed(uid, 'downloads')
        if time.monotonic() - self.send_times.get(uid, 0) < 5:
            raise web.HTTPTooManyRequests()
        self.send_times[uid] = time.monotonic()
        if len(self.send_times) > 1000:
            self.send_times.pop(min(self.send_times, key=self.send_times.get), None)
        song = await self.find(uid, identifier)
        path = self.audio_path(uid, song)
        if path:
            if song.get('kind') == 'upload':
                with path.open('rb') as source:
                    await self.application.bot.send_document(uid, document=source,
                        filename=song.get('original_filename') or 'SwiDJ.audio', caption=song['title'])
            else:
                from audio_presentation import send_music
                await send_music(self.application.bot, uid, path, song['title'], song.get('artist'), source_url=song.get('url'),license_url=song.get('license_url'))
        else:
            # Use existing download/retry/card handlers; never accept a URL from the browser.
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            token = secrets.token_hex(5)
            data = self.data(uid)
            requests = data.setdefault('version_requests', {})
            from jamendo_source import identifier as jamendo_id
            if song.get('url', '').startswith('https://www.youtube.com/watch?v=') or jamendo_id(song.get('url')):
                candidates = [dict(song)]
            else:
                from versions import find_versions
                async with self.search_slots:
                    candidates = await asyncio.to_thread(find_versions, song['title'] + ' ' + song.get('artist', ''))
            if not candidates:
                raise web.HTTPNotFound()
            requests[token] = {'song': dict(song), 'mode': 'listen', 'candidates': candidates}
            while len(requests) > 8:
                requests.pop(next(iter(requests)))
            rows = [[InlineKeyboardButton(s['title'][:60], callback_data=f'ver:pick:{token}:{i}')]
                    for i, s in enumerate(candidates)]
            message = await self.application.bot.send_message(uid, song['title'], reply_markup=InlineKeyboardMarkup(rows))
            requests[token]['menu_messages'] = [[uid, message.message_id]]
            sessions = await asyncio.to_thread(self.store.load_named, 'sessions')
            session = dict(sessions.get(uid, {}), version_requests=requests)
            await asyncio.to_thread(self.store.save_named, 'sessions', uid, session)
        return {'ok': True}


def create_app(*, token='', bridge=None):
    @web.middleware
    async def boundary(request, handler):
        try:
            if request.path.startswith('/api/'):
                if bridge is None:
                    raise web.HTTPUnauthorized()
                try:
                    user = verify_init_data(request.headers.get('X-Telegram-Init-Data', ''), token)
                except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                    raise web.HTTPUnauthorized() from None
                request['user'] = user
                uid = user['id']
                bridge.allowed(uid)
                from dispatch import user_lock
                if request.path in ('/api/studio','/api/voice','/api/link','/api/link/cancel','/api/link/audio','/api/recognize','/api/charts','/api/charts/resolve'):
                    response=await handler(request)
                else:
                    async with user_lock(uid):
                        response = await handler(request)
            else:
                response = await handler(request)
        except web.HTTPException as exc:
            response = web.json_response({'error': exc.status}, status=exc.status)
        except Exception:
            # Never return/log provider URLs, headers, tokens or local paths.
            response = web.json_response({'error': 500}, status=500)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                                 'Referrer-Policy': 'no-referrer',
                                 'Content-Security-Policy': "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; img-src 'self' https://i.ytimg.com https://*.mzstatic.com data: blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'"})
        return response

    app = web.Application(middlewares=[boundary], client_max_size=16*1024)
    async def asset(request):
        name = request.match_info.get('name', 'index.html')
        if name not in ('index.html', 'app.css', 'app.js', 'audio.js', 'live.js'):
            raise web.HTTPNotFound()
        return web.FileResponse(ASSETS / name)
    async def demo(request):
        number = int(request.match_info['number'])
        if not 0 <= number < 6:
            raise web.HTTPNotFound()
        return web.Response(body=await asyncio.to_thread(demo_audio, number), content_type='audio/wav')
    async def library(request):
        return web.json_response(await bridge.snapshot(request['user']['id']))
    async def mutate(request):
        try:
            payload = await request.json()
        except (ValueError, TypeError):
            raise web.HTTPBadRequest() from None
        if not isinstance(payload, dict):
            raise web.HTTPBadRequest()
        return web.json_response(await bridge.change(request['user']['id'], payload))
    async def search(request):
        query = request.query.get('q', '').strip()
        if not 2 <= len(query) <= 120:
            raise web.HTTPBadRequest()
        return web.json_response(await bridge.search(request['user']['id'], query))
    async def audio(request):
        uid = request['user']['id']
        bridge.allowed(uid, 'downloads')
        song = await bridge.find(uid, request.match_info['track'])
        path = bridge.audio_path(uid, song)
        if not path or path.stat().st_size > MEDIA_BYTES:
            raise web.HTTPNotFound()
        headers = {}
        if song.get('kind') == 'upload':
            headers['Content-Type'] = mimetypes.guess_type(song.get('original_filename') or '')[0] or 'audio/mpeg'
        return web.FileResponse(path, headers=headers)
    async def upload(request):
        if bridge.upload_slots.locked():
            raise web.HTTPTooManyRequests()
        async with bridge.upload_slots:
            return await upload_inner(request)
    async def upload_inner(request):
        uid = request['user']['id']
        bridge.allowed(uid, 'downloads')
        from app_uploads import retain, MAX_FILE_BYTES, StorageFull
        from scratch import scratch_root
        if request.content_length and request.content_length > MAX_FILE_BYTES+4096:
            raise web.HTTPRequestEntityTooLarge(max_size=MAX_FILE_BYTES, actual_size=request.content_length)
        reader = await request.multipart()
        part = await reader.next()
        if not part or part.name != 'file' or not part.filename:
            raise web.HTTPBadRequest()
        with tempfile.NamedTemporaryFile(dir=scratch_root(),suffix='.audio',delete=False) as stream:
            path = Path(stream.name)
            try:
                total = 0
                while chunk := await part.read_chunk(65536):
                    total += len(chunk)
                    if total > MAX_FILE_BYTES:
                        raise web.HTTPRequestEntityTooLarge(max_size=MAX_FILE_BYTES,actual_size=total)
                    stream.write(chunk)
                stream.close()
                try:
                    song = await asyncio.to_thread(retain,path,uid,part.filename)
                except StorageFull:
                    raise web.HTTPInsufficientStorage() from None
                except Exception:
                    raise web.HTTPBadRequest() from None
                favorites = deepcopy(bridge.favorites.get(uid, []))
                app_tracks = deepcopy(await bridge.app_library(uid))
                if not any(s['id'] == song['id'] for s in app_tracks):
                    if len(app_tracks) >= 200:
                        raise web.HTTPConflict()
                    app_tracks.append(song)
                if not any(s['id'] == song['id'] for s in favorites):
                    if len(favorites) >= 60:
                        raise web.HTTPConflict()
                    favorites.append(song)
                folders = await bridge.folders(uid)
                await asyncio.to_thread(bridge.store.save_library,uid,favorites,folders,app_tracks)
                bridge.favorites[uid] = favorites
                bridge.data(uid)['miniapp_library'] = app_tracks
                return web.json_response({'track':public_song(song,True),'library':await bridge.snapshot(uid)})
            finally:
                stream.close()
                path.unlink(missing_ok=True)
    async def send(request):
        payload = await request.json()
        if not isinstance(payload, dict):
            raise web.HTTPBadRequest()
        return web.json_response(await bridge.send(request['user']['id'], str(payload.get('track', ''))))
    async def prepare(request):
        payload = await request.json()
        if not isinstance(payload, dict):
            raise web.HTTPBadRequest()
        return web.json_response(await bridge.prepare(request['user']['id'], str(payload.get('track', ''))))
    async def job_status(request):
        uid = request['user']['id']
        bridge.allowed(uid, 'downloads')
        job = bridge.audio_jobs.get(uid, request.match_info['job'])
        if not job:
            raise web.HTTPNotFound()
        if request.method == 'POST':
            bridge.audio_jobs.cancel(uid, job.token)
        elif job.state == 'ready' and not getattr(job, 'remembered', False):
            await bridge.remember_app_track(uid, job.song)
            job.remembered = True
        return web.json_response(bridge.job_payload(job))
    async def download_ticket(request):
        payload = await request.json()
        if not isinstance(payload, dict):
            raise web.HTTPBadRequest()
        return web.json_response(await bridge.download_ticket(request['user']['id'], str(payload.get('track', '')), stream=request.path == '/api/stream'))
    async def download_file(request):
        item = bridge.download_tickets.get(request.match_info['ticket']) if bridge else None
        if not item or item['expires'] <= time.monotonic():
            raise web.HTTPNotFound()
        streaming = request.path.startswith('/stream/')
        if streaming != bool(item.get('stream')):
            raise web.HTTPNotFound()
        bridge.allowed(item['uid'], 'downloads')
        path = bridge.audio_path(item['uid'], item['song'])
        if not path or path.stat().st_size > MEDIA_BYTES:
            raise web.HTTPNotFound()
        headers = {'Content-Disposition':("inline" if streaming else "attachment")+"; filename*=UTF-8''"+quote(item['filename'],safe='')}
        if streaming:
            headers['Content-Type'] = mimetypes.guess_type(item['filename'])[0] or 'audio/mpeg'
        return web.FileResponse(path, headers=headers)
    async def close_jobs(_):
        if bridge:
            await bridge.audio_jobs.close()
    app.on_cleanup.append(close_jobs)
    app.add_routes([web.get('/', asset), web.get('/assets/{name}', asset),
                    web.get('/demo/{number:\\d}.wav', demo), web.get('/api/library', library),
                    web.post('/api/library', mutate), web.get('/api/search', search),
                    web.get('/api/audio/{track:-?\\d{1,20}}', audio), web.post('/api/send', send),
                    web.post('/api/prepare', prepare),
                    web.post('/api/download', download_ticket),
                    web.post('/api/stream', download_ticket),
                    web.post('/api/upload', upload),
                    web.get('/download/{ticket:[A-Za-z0-9_-]{32}}', download_file),
                    web.get('/stream/{ticket:[A-Za-z0-9_-]{32}}', download_file),
                    web.get('/api/jobs/{job:[a-f0-9]{24}}', job_status),
                    web.post('/api/jobs/{job:[a-f0-9]{24}}/cancel', job_status)])
    from miniapp_studio import register
    register(app, bridge)
    from app_recognition import register as register_recognition
    register_recognition(app)
    from app_charts import register as register_charts
    register_charts(app,bridge)
    from app_lyrics import register as register_lyrics
    register_lyrics(app, bridge)
    from app_media import register as register_media
    register_media(app, bridge)
    return app


def public_url():
    value = os.getenv('MINIAPP_URL', '').strip()
    parsed = urlsplit(value)
    return value if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password and not parsed.fragment else None


async def start_for_bot(application, store, favorites, sessions, owner_ids, downloader=None):
    if os.getenv('MINIAPP_ENABLED', '').lower() not in ('1', 'true'):
        return
    from app_media import download_app_audio
    bridge = BotLibrary(application, store, favorites, sessions, owner_ids, download_app_audio)
    runner = web.AppRunner(create_app(token=application.bot.token, bridge=bridge), access_log=None)
    await runner.setup()
    try:
        await web.TCPSite(runner, os.getenv('MINIAPP_HOST', '127.0.0.1'), int(os.getenv('MINIAPP_PORT', '8765'))).start()
    except Exception:
        await runner.cleanup()
        raise
    application.bot_data['miniapp_runner'] = runner


async def stop_for_bot(application):
    runner = application.bot_data.pop('miniapp_runner', None)
    if runner:
        await runner.cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true', required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    web.run_app(create_app(), host=args.host, port=args.port, access_log=None)
