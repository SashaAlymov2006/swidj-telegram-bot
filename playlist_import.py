"""Public playlist metadata import. Never downloads audio or modifies remote accounts."""
import asyncio
from copy import deepcopy
import hashlib
import json
import os
import re
import secrets
import time
from urllib.parse import urlsplit, parse_qs, unquote

import requests

MAX_ITEMS = 500
SUPPORTED = ('YouTube / YouTube Music', 'SoundCloud', 'Spotify', 'Apple Music',
             'Яндекс Музыка', 'Deezer', 'Bandcamp', 'Audius', 'Jamendo')


def classify(url):
    try:
        p = urlsplit(url)
        if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
            return None
        host = (p.hostname or '').lower()
        if host in ('jamendo.com','www.jamendo.com') and re.fullmatch(r'/(?:[a-z]{2}/)?(?:list|playlist)/\d+(?:/[^/]+)?/?', p.path):
            return 'jamendo'
        if host in ('audius.co','www.audius.co') and re.fullmatch(r'/[A-Za-z0-9_.-]+/(?:playlist|album)/[A-Za-z0-9_.-]+/?', p.path):
            return 'audius'
        if host in ('youtube.com', 'www.youtube.com', 'music.youtube.com', 'm.youtube.com'):
            return 'youtube' if p.path.rstrip('/') == '/playlist' and re.fullmatch(r'[A-Za-z0-9_-]{10,100}', parse_qs(p.query).get('list', [''])[0]) else None
        if host in ('soundcloud.com', 'www.soundcloud.com') and re.fullmatch(r'/[^/]+/sets/[^/]+/?', p.path):
            return 'soundcloud'
        if host == 'open.spotify.com' and re.fullmatch(r'/(?:intl-[a-z]+/)?(?:playlist|album)/[A-Za-z0-9]{22}/?', p.path):
            return 'spotify'
        if host == 'music.apple.com' and re.fullmatch(r'/[a-z]{2}/(?:playlist|album)/[^/]+/[^/]+/?', p.path) and not parse_qs(p.query).get('i'):
            return 'apple'
        if host in ('music.yandex.ru', 'music.yandex.com', 'music.yandex.kz', 'music.yandex.by') and re.fullmatch(r'/(?:users/[^/]+/playlists/\d+|playlists/[A-Za-z0-9.-]+|album/\d+)/?', p.path):
            return 'yandex'
        if host in ('deezer.com', 'www.deezer.com') and re.fullmatch(r'/(?:[a-z]{2}/)?(?:playlist|album)/\d+/?', p.path):
            return 'deezer'
        if host and re.fullmatch(r'[a-z0-9-]+\.bandcamp\.com', host) and re.fullmatch(r'/album/[^/]+/?', p.path):
            return 'bandcamp'
    except (ValueError, TypeError):
        pass
    return None


def get_json(url, **kwargs):
    # Only adapter-constructed destinations, no user-controlled arbitrary hosts.
    response = requests.get(url, timeout=(5, 15), allow_redirects=False, **kwargs)
    response.raise_for_status()
    if response.status_code != 200 or len(response.content) > 8 * 1024 * 1024:
        raise ValueError('playlist_unavailable')
    return response.json()


def make_song(title, artist='', url='', duration=None):
    title, artist = str(title or '').strip()[:180], str(artist or '').strip()[:120]
    if not title:
        return None
    key = json.dumps([title.casefold(), artist.casefold(), url], ensure_ascii=False)
    return {'id': -(2 * 10**15 + int.from_bytes(hashlib.sha256(key.encode()).digest()[:6], 'big')),
            'title': title, 'artist': artist, 'url': url, 'duration': duration,
            '_catalog_metadata': True, '_playlist_import': True}


def normalize(name, source, rows, expected=None):
    expected = int(expected) if expected else None
    if expected and expected > MAX_ITEMS:
        raise ValueError('playlist_too_large')
    songs, seen = [], set()
    valid = 0
    for row in rows:
        if not row:
            continue
        key = row['id']
        valid += 1
        if key not in seen:
            seen.add(key)
            songs.append(row)
    if len(songs) > MAX_ITEMS:
        raise ValueError('playlist_too_large')
    if not songs:
        raise ValueError('playlist_unavailable')
    # Missing/unavailable entries are made explicit; never call a preview a full import.
    return {'name': str(name or 'Playlist')[:40], 'source': source, 'songs': songs,
            'count': len(songs), 'total': expected or len(rows),
            'partial': bool(expected and expected > valid)}


def extractor(url, source):
    import yt_dlp
    # Metadata only. Keep input restricted to explicit supported collections.
    opts = {'quiet': True, 'no_warnings': True, 'skip_download': True,
            'extract_flat': 'in_playlist', 'playlistend': MAX_ITEMS + 1,
            'socket_timeout': 12, 'retries': 1, 'extractor_retries': 1,
            'ignoreerrors': True, 'noplaylist': False}
    with yt_dlp.YoutubeDL(opts) as ydl:
        if source == 'soundcloud':
            ie = ydl.get_info_extractor('SoundcloudSet')
            ie.initialize()
            data = ie._call_api(ie._resolv_url(url.split('?')[0]), 'playlist', headers=ie._HEADERS)
            entries = data.get('tracks') or []
            if len(entries) > MAX_ITEMS:
                raise ValueError('playlist_too_large')
            missing = [str(row['id']) for row in entries if row.get('id') and not row.get('title')]
            details = {}
            for offset in range(0, len(missing), 50):
                extra = ie._call_api(ie._API_V2_BASE+'tracks', 'playlist', query={'ids':','.join(missing[offset:offset+50])}, headers=ie._HEADERS)
                details.update({str(row['id']):row for row in extra})
            entries = [details.get(str(row.get('id')), row) for row in entries]
            return normalize(data.get('title'), source,
                             [make_song(row.get('title'), (row.get('user') or {}).get('username'), row.get('permalink_url') or '',
                                        (row.get('duration') or 0)/1000) for row in entries], data.get('track_count'))
        data = ydl.extract_info(url, download=False)
        if not isinstance(data, dict):
            raise ValueError('playlist_unavailable')
        entries = list(data.get('entries') or [])
    rows = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        title = entry.get('track') or entry.get('title')
        if title in ('[Deleted video]', '[Private video]'):
            continue
        rows.append(make_song(title, entry.get('artist') or entry.get('uploader') or entry.get('channel'),
                              entry.get('webpage_url') or entry.get('url') or '', entry.get('duration')))
    return normalize(data.get('title'), source, rows, data.get('playlist_count'))


def read(url):
    source = classify(url)
    if not source:
        raise ValueError('playlist_unsupported')
    p = urlsplit(url)
    if source == 'audius':
        from audius_source import api, _auth
        headers, params = _auth()
        response = requests.get('https://api.audius.co/v1/resolve',params=dict(params,url=url),headers=headers,timeout=(5,15),allow_redirects=False)
        if response.status_code in (301,302,303,307,308):
            location = response.headers.get('Location','')
            match = re.fullmatch(r'/v1/playlists/([A-Za-z0-9]{3,32}|by_permalink/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)',urlsplit(location).path)
            if not match:raise ValueError('playlist_unavailable')
            data = api('/playlists/'+match[1])
        else:
            response.raise_for_status()
            data = response.json().get('data')
        data = data[0] if isinstance(data, list) and data else data
        if not isinstance(data, dict) or not re.fullmatch(r'[A-Za-z0-9]{3,32}', str(data.get('id',''))):
            raise ValueError('playlist_unavailable')
        total = data.get('track_count')
        rows = []
        for offset in range(0, MAX_ITEMS + 1, 100):
            block = api('/playlists/'+data['id']+'/tracks', {'limit':100, 'offset':offset}) or []
            rows.extend(block)
            if len(block)<100:break
        return normalize(data.get('playlist_name'), source, [make_song(r.get('title'), (r.get('user') or {}).get('name'),
                         'https://audius.co'+str(r.get('permalink') or ''), r.get('duration')) for r in rows], total)
    if source == 'jamendo':
        key = os.getenv('JAMENDO_CLIENT_ID','')
        if not key:raise ValueError('playlist_unavailable')
        identifier = re.search(r'/(?:list|playlist)/(\d+)', p.path)[1]
        data = get_json('https://api.jamendo.com/v3.0/playlists/tracks/', params={'client_id':key,'format':'json','id':identifier,'limit':1,'track_type':'single albumtrack'})
        if data.get('headers',{}).get('status')!='success':raise ValueError('playlist_unavailable')
        items = data.get('results') or []
        item = items[0] if items else {}
        rows = item.get('tracks') or []
        return normalize(item.get('name'),source,[make_song(r.get('name'),r.get('artist_name'),
                         'https://www.jamendo.com/track/'+str(r.get('id')),r.get('duration')) for r in rows],item.get('tracks_count'))
    if source in ('youtube', 'soundcloud', 'bandcamp'):
        return extractor(url, source)
    if source == 'deezer':
        kind, identifier = p.path.rstrip('/').split('/')[-2:]
        data = get_json(f'https://api.deezer.com/{kind}/{identifier}')
        block = data.get('tracks') or {}
        rows = list(block.get('data') or [])
        total = data.get('nb_tracks') or block.get('total') or len(rows)
        if total > MAX_ITEMS:
            raise ValueError('playlist_too_large')
        while len(rows) < total:
            page = get_json(f'https://api.deezer.com/{kind}/{identifier}/tracks', params={'index': len(rows), 'limit': 100})
            extra = page.get('data') or []
            if not extra:
                break
            rows.extend(extra)
        return normalize(data.get('title'), source, [make_song(r.get('title'), (r.get('artist') or {}).get('name'),
                         r.get('link') or '', r.get('duration')) for r in rows], total)
    if source == 'yandex' and '/users/' in p.path:
        parts = p.path.strip('/').split('/')
        data = get_json('https://api.music.yandex.net/users/'+parts[1]+'/playlists/'+parts[3]).get('result') or {}
        rows = []
        for entry in data.get('tracks') or []:
            r = entry.get('track') or {}
            rows.append(make_song(r.get('title'), ', '.join(a.get('name', '') for a in r.get('artists', [])),
                                  'https://music.yandex.ru/track/'+str(r.get('id')), (r.get('durationMs') or 0)/1000))
        return normalize(data.get('title'), source, rows, data.get('trackCount'))
    if source == 'apple' and '/album/' in p.path:
        identifier = p.path.rstrip('/').split('/')[-1]
        data = get_json('https://itunes.apple.com/lookup', params={'id': identifier, 'entity': 'song', 'country': p.path.split('/')[1], 'limit': 500})
        items = data.get('results') or []
        album = next((r for r in items if r.get('wrapperType') == 'collection'), {})
        return normalize(album.get('collectionName'), source, [make_song(r.get('trackName'), r.get('artistName'), r.get('trackViewUrl') or '',
                          (r.get('trackTimeMillis') or 0)/1000) for r in items if r.get('kind') == 'song'], album.get('trackCount'))
    # Public embed / structured page metadata; no hidden login/session extraction.
    target = url
    if source == 'spotify':
        target = 'https://open.spotify.com/embed/'+ '/'.join(p.path.strip('/').split('/')[-2:])
    response = requests.get(target, timeout=(5, 15), allow_redirects=False)
    response.raise_for_status()
    if response.status_code != 200 or len(response.content) > 8 * 1024 * 1024:
        raise ValueError('playlist_unavailable')
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    if source == 'spotify':
        node = soup.find('script', id='__NEXT_DATA__')
        data = json.loads(node.string or node.get_text()) if node else {}
        entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
        tracks = entity.get('trackList') or []
        return normalize(entity.get('name') or entity.get('title'), source,
                         [make_song(r.get('title'), r.get('subtitle'), 'https://open.spotify.com/track/'+str(r.get('uri', '')).split(':')[-1],
                                    (r.get('duration') or 0)/1000) for r in tracks], entity.get('trackCount') or entity.get('totalTracks'))
    rows, name, total = [], '', None
    for node in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(node.string or node.get_text())
        except (ValueError, TypeError):
            continue
        pending = data if isinstance(data, list) else [data]
        while pending:
            item = pending.pop()
            if not isinstance(item, dict):
                continue
            types = item.get('@type', [])
            types = types if isinstance(types, list) else [types]
            if any(t in types for t in ('MusicPlaylist', 'MusicAlbum')):
                name = item.get('name') or name
                total = item.get('numTracks') or total
            if 'MusicRecording' in types:
                artists = item.get('byArtist') or []
                artists = [artists] if isinstance(artists, (str, dict)) else artists
                rows.append(make_song(item.get('name'), ', '.join(a if isinstance(a, str) else a.get('name', '') for a in artists), item.get('url') or ''))
            for value in item.values():
                if isinstance(value, dict): pending.append(value)
                elif isinstance(value, list): pending.extend(value)
    return normalize(name, source, rows, int(total) if total else None)


def read_text(value, name='Playlist'):
    """Portable plain-text export from any catalog; one artist — title per line."""
    if not isinstance(value, str) or len(value) > 50000:
        raise ValueError('playlist_too_large')
    rows = []
    for line in value.splitlines():
        line = re.sub(r'^\s*\d+[.)]\s*', '', line).strip()
        if not line:
            continue
        if 'http://' in line or 'https://' in line:
            raise ValueError('playlist_unavailable')
        parts = re.split(r'\s+[—–-]\s+', line, maxsplit=1)
        artist, title = parts if len(parts) == 2 else ('', line)
        rows.append(make_song(title, artist))
    return normalize(name, 'text', rows)


def add_collection(folders, collection):
    result = deepcopy(folders)
    # Repeating an import is idempotent and never overwrites an edited collection.
    signature = hashlib.sha256(json.dumps([collection['source'], collection['name'], [s['id'] for s in collection['songs']]]).encode()).hexdigest()
    existing = next((key for key, value in result.items() if value.get('import_signature') == signature), None)
    if existing:
        return result, existing
    if len(result) >= 30:
        raise ValueError('playlist_capacity')
    key = secrets.token_hex(4)
    result[key] = {'name': collection['name'], 'songs': deepcopy(collection['songs']), 'import_signature': signature}
    return result, key


def text(language, key):
    return {
        'title': ('Импорт плейлиста', 'Import playlist'),
        'prompt': ('Пришли ссылку на публичный плейлист или альбом. Или /import и список песен: исполнитель — название, по одной в строке.', 'Send a public playlist or album link. Or /import followed by a track list: artist — title, one per line.'),
        'reading': ('Читаю список треков…', 'Reading the track list…'),
        'confirm': ('Добавить плейлист', 'Add playlist'),
        'done': ('Плейлист добавлен. Открой «Мою музыку».', 'Playlist added. Open My music.'),
        'error': ('Не удалось прочитать полный список. Проверь, что плейлист публичный, или попробуй другой.', 'Could not read the full list. Check that the playlist is public, or try another one.'),
        'playlist_too_large': ('За один импорт — до 500 треков.', 'Up to 500 tracks per import.'),
        'playlist_capacity': ('Уже 30 плейлистов. Освободи место для нового.', 'You already have 30 playlists. Make room for a new one.'),
    }.get(key, ('Не удалось импортировать плейлист.', 'Could not import the playlist.'))[language == 'en']


async def bot_import(update, context, store, favorites):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    language = context.user_data.get('language', 'ru')
    if getattr(update, 'callback_query', None):
        await update.callback_query.answer()
        return await update.effective_message.reply_text(text(language, 'prompt'))
    raw = update.effective_message.text or ''
    from catalog_links import link_candidates
    urls = [url for url in link_candidates(raw) if classify(url)]
    pasted = re.sub(r'^/import(?:@\w+)?\s*', '', raw).strip()
    if (not urls or not classify(urls[0])) and (not raw.startswith('/import') or not pasted):
        return await update.effective_message.reply_text(text(language, 'prompt'))
    status = await update.effective_message.reply_text(text(language, 'reading'))
    try:
        result = await asyncio.to_thread(read, urls[0]) if urls else read_text(pasted)
        token = secrets.token_hex(6)
        context.user_data['_playlist_preview'] = {'token': token, 'created': time.monotonic(), 'collection': result}
        label = f"{result['name']} · {result['count']}" + (f" / {result['total']}" if result['partial'] else '')
        return await status.edit_text(label, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text(language, 'confirm'), callback_data='pimport:'+token)]]))
    except Exception as exc:
        return await status.edit_text(text(language, str(exc) if str(exc) in ('playlist_too_large', 'playlist_capacity') else 'error'))


async def bot_confirm(update, context, store, favorites):
    language = context.user_data.get('language', 'ru')
    preview = context.user_data.get('_playlist_preview') or {}
    if preview.get('token') != update.callback_query.data.split(':')[-1] or time.monotonic()-preview.get('created', 0) > 1800:
        return await update.callback_query.answer(text(language, 'prompt'), show_alert=True)
    from library_ui import collections, commit
    try:
        folders, key = add_collection(await collections(context, update.effective_user.id, store), preview['collection'])
        await commit(context, update.effective_user.id, store, favorites, folders)
        context.user_data['music_collections'] = folders
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text(language, 'done'))
    except ValueError as exc:
        await update.callback_query.answer(text(language, str(exc)), show_alert=True)
