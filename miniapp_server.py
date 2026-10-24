"""Optional Mini App, sharing the bot's live library and per-user lock.

Local preview: python miniapp_server.py --demo (no token or private data).
Production identity is exclusively verified Telegram initData, never client IDs.
"""
import argparse
import asyncio
from functools import lru_cache
import hashlib
import hmac
import io
import json
import math
import os
from pathlib import Path
import secrets
import struct
import time
from urllib.parse import parse_qsl, urlsplit
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
    return {'id': str(song['id']), 'title': str(song.get('title') or 'Audio')[:180],
            'artist': str(song.get('artist') or '')[:120],
            'duration': song.get('duration') if isinstance(song.get('duration'), (int, float)) else None,
            'kind': 'upload' if song.get('kind') == 'upload' else 'track', 'playable': playable}


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
    def __init__(self, application, store, favorites, saved_sessions, owner_ids):
        self.application, self.store, self.favorites = application, store, favorites
        self.saved_sessions, self.owner_ids = saved_sessions, owner_ids
        self.searches = {}
        self.search_times = {}
        self.send_times = {}
        self.search_slots = asyncio.Semaphore(2)

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
        return all_saved(uid, self.favorites, await self.folders(uid))

    def audio_path(self, uid, song):
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
        active = self.data(uid).get('downloaded_song')
        return {'tracks': [public_song(song, bool(self.audio_path(uid, song))) for song in songs],
                'recent': [public_song(active, bool(self.audio_path(uid, active)))] if active else [],
                'favorites': [str(song['id']) for song in self.favorites.get(uid, [])],
                'playlists': [{'id': key, 'name': value['name'], 'tracks': [str(s['id']) for s in value['songs']]}
                              for key, value in (await self.folders(uid)).items()],
                'language': self.data(uid).get('language', 'ru'),
                'bot': self.application.bot.username}

    async def find(self, uid, identifier):
        sources = await self.songs(uid)
        active = self.data(uid).get('downloaded_song')
        if active:
            sources.append(active)
        sources.extend(self.searches.get(uid, []))
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

    async def change(self, uid, payload):
        from library_ui import clean_name, MAX_TRACKS
        folders = await self.folders(uid)
        action = payload.get('action')
        if action == 'language':
            if payload.get('language') not in ('ru', 'en'):
                raise web.HTTPBadRequest()
            self.data(uid)['language'] = payload['language']
            # Merge rather than replacing the bot's durable session.
            sessions = await asyncio.to_thread(self.store.load_named, 'sessions')
            session = dict(sessions.get(uid, {}), language=payload['language'])
            await asyncio.to_thread(self.store.save_named, 'sessions', uid, session)
        elif action == 'create':
            name = clean_name(str(payload.get('name', '')))
            if not name or len(folders) >= 20:
                raise web.HTTPBadRequest()
            folders[secrets.token_hex(4)] = {'name': name, 'songs': []}
        elif action in ('favorite', 'playlist', 'remove'):
            song = await self.find(uid, str(payload.get('track', '')))
            favorites = self.favorites.setdefault(uid, [])
            if action == 'favorite':
                present = any(s['id'] == song['id'] for s in favorites)
                if payload.get('value') is True and not present:
                    if len(favorites) >= MAX_TRACKS:
                        raise web.HTTPConflict()
                    favorites.append(dict(song))
                elif payload.get('value') is False:
                    self.favorites[uid] = [s for s in favorites if s['id'] != song['id']]
            elif action == 'playlist':
                folder = folders.get(str(payload.get('playlist')))
                if folder is None:
                    raise web.HTTPNotFound()
                if len(folder['songs']) >= MAX_TRACKS:
                    raise web.HTTPConflict()
                if not any(s['id'] == song['id'] for s in folder['songs']):
                    folder['songs'].append(dict(song))
            else:
                self.favorites[uid] = [s for s in favorites if s['id'] != song['id']]
                for folder in folders.values():
                    folder['songs'] = [s for s in folder['songs'] if s['id'] != song['id']]
        else:
            raise web.HTTPBadRequest()
        await asyncio.to_thread(self.store.save_library, uid, self.favorites.get(uid, []), folders)
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
                await send_music(self.application.bot, uid, path, song['title'], song.get('artist'))
        else:
            # Use existing download/retry/card handlers; never accept a URL from the browser.
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            token = secrets.token_hex(5)
            data = self.data(uid)
            requests = data.setdefault('version_requests', {})
            if song.get('url', '').startswith('https://www.youtube.com/watch?v='):
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
                                 'Content-Security-Policy': "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'"})
        return response

    app = web.Application(middlewares=[boundary], client_max_size=16*1024)
    async def asset(request):
        name = request.match_info.get('name', 'index.html')
        if name not in ('index.html', 'app.css', 'app.js', 'audio.js'):
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
        if not path or path.stat().st_size > 49*1024**2:
            raise web.HTTPNotFound()
        return web.FileResponse(path)
    async def send(request):
        payload = await request.json()
        if not isinstance(payload, dict):
            raise web.HTTPBadRequest()
        return web.json_response(await bridge.send(request['user']['id'], str(payload.get('track', ''))))
    app.add_routes([web.get('/', asset), web.get('/assets/{name}', asset),
                    web.get('/demo/{number:\\d}.wav', demo), web.get('/api/library', library),
                    web.post('/api/library', mutate), web.get('/api/search', search),
                    web.get('/api/audio/{track:-?\\d{1,20}}', audio), web.post('/api/send', send)])
    return app


def public_url():
    value = os.getenv('MINIAPP_URL', '').strip()
    parsed = urlsplit(value)
    return value if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password and not parsed.fragment else None


async def start_for_bot(application, store, favorites, sessions, owner_ids):
    if os.getenv('MINIAPP_ENABLED', '').lower() not in ('1', 'true'):
        return
    bridge = BotLibrary(application, store, favorites, sessions, owner_ids)
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
