"""Public release metadata, never previews or a replacement audio downloader."""
from copy import deepcopy
import hashlib
import re
import threading
import time
from urllib.parse import urlsplit
import requests
from operations import checkpoint

_cache={}
_lock=threading.Lock()
_slots=threading.BoundedSemaphore(2)
_inflight={}
_next_call=0.0


def _request(path,params):
    global _next_call
    key=(path,tuple(sorted(params.items())))
    with _lock:
        cached=_cache.get(key)
        if cached and cached[0]>time.monotonic():return deepcopy(cached[1])
        event=_inflight.get(key)
        leader=event is None
        if leader:event=_inflight.setdefault(key,threading.Event())
    if not leader:
        for _ in range(100):
            checkpoint()
            if event.wait(.2):break
        else:raise TimeoutError('Catalog wait timeout')
        with _lock:cached=_cache.get(key)
        if cached:return deepcopy(cached[1])
        raise ValueError('Catalog unavailable')
    acquired=False
    try:
        for _ in range(100):
            checkpoint()
            if _slots.acquire(timeout=.2):acquired=True;break
        if not acquired:raise TimeoutError('Catalog busy')
        # Public Search API is rate limited. Cached pages need no new call.
        with _lock:
            at=max(time.monotonic(),_next_call);_next_call=at+3.1
        while time.monotonic()<at:
            checkpoint();time.sleep(min(.2,at-time.monotonic()) if at>time.monotonic() else 0)
        with requests.get('https://itunes.apple.com/'+path,params=dict(country='de',media='music',**params),
                          stream=True,timeout=(5,12),allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code!=200:raise ValueError('Catalog unavailable')
            raw=bytearray()
            for chunk in response.iter_content(65536):
                checkpoint();raw.extend(chunk)
                if len(raw)>3*1024**2:raise ValueError('Catalog too large')
        import json
        data=json.loads(raw);rows=data.get('results')
        if not isinstance(rows,list):raise ValueError('Invalid catalog')
        with _lock:
            while len(_cache)>=128:_cache.pop(next(iter(_cache)))
            _cache[key]=(time.monotonic()+(1800 if rows else 60),deepcopy(rows))
        return rows
    finally:
        if acquired:_slots.release()
        with _lock:_inflight.pop(key,None)
        event.set()


def _link(value,art=False):
    try:
        p=urlsplit(str(value));host=p.hostname or ''
        valid=host.endswith('.mzstatic.com') if art else host in ('music.apple.com','itunes.apple.com')
        return p.geturl() if p.scheme=='https' and valid and not p.username and not p.password and p.port in (None,443) else ''
    except ValueError:return ''


def release(row):
    if row.get('wrapperType')!='collection' or row.get('collectionType')!='Album':return None
    identifier=str(row.get('collectionId',''));artist_id=str(row.get('artistId',''))
    if not re.fullmatch(r'\d{1,16}',identifier) or not artist_id.isdecimal():return None
    title=str(row.get('collectionName') or '').strip()[:180]
    artist=str(row.get('artistName') or '').strip()[:120]
    if not title or not artist:return None
    # Use explicit release labels; a short album is not automatically an EP.
    kind='single' if re.search(r'\s[-–—]\sSingle$',title,re.I) else 'ep' if re.search(r'\s[-–—]\sEP$',title,re.I) else 'album'
    return {'id':identifier,'artist_id':artist_id,'title':title,'artist':artist,'kind':kind,
            'cover':_link(row.get('artworkUrl100'),True),'source_url':_link(row.get('collectionViewUrl')),
            'release_date':str(row.get('releaseDate') or '')[:10],'track_count':row.get('trackCount') if type(row.get('trackCount')) is int else None}


def releases(song,offset=0):
    from artist_catalog import creator,normalized
    if type(offset) is not int or offset<0 or offset>190 or offset%10:raise ValueError('Invalid release page')
    name=creator(song)
    if not name:raise ValueError('Artist unavailable')
    rows=_request('search',{'term':name,'entity':'album','attribute':'artistTerm','limit':200})
    albums=[];seen=set()
    for raw in rows:
        item=release(raw)
        if item and normalized(item['artist'])==normalized(name) and item['id'] not in seen:
            seen.add(item['id']);albums.append(item)
    albums.sort(key=lambda a:(a['release_date'],a['title']),reverse=True)
    profiles={}
    for item in albums:profiles.setdefault(item['artist_id'],{'id':item['artist_id'],'name':item['artist'],'example':item['title'],'cover':item['cover']})
    selected=str(song.get('_release_artist_id') or '')
    if selected:
        if selected not in profiles:raise ValueError('Artist profile unavailable')
        albums=[item for item in albums if item['artist_id']==selected]
    elif len(profiles)>1:albums=[]
    return {'name':name,'releases':albums[offset:offset+10],'offset':offset,
            'next_offset':offset+10 if offset+10<len(albums) else None,'source':'Apple Music',
            'profiles':list(profiles.values()) if len(profiles)>1 else [],'selected_profile':selected}


def album(song,identifier):
    from artist_catalog import creator,normalized
    if not re.fullmatch(r'\d{1,16}',str(identifier)):raise ValueError('Invalid album')
    rows=_request('lookup',{'id':str(identifier),'entity':'song','limit':200})
    header=next((release(r) for r in rows if str(r.get('collectionId'))==str(identifier) and release(r)),None)
    if not header or normalized(header['artist'])!=normalized(creator(song)):raise ValueError('Album belongs to another artist')
    if song.get('_release_artist_id') and str(song['_release_artist_id'])!=header['artist_id']:raise ValueError('Album belongs to another profile')
    tracks=[];seen=set()
    for row in rows:
        if row.get('kind')!='song' or str(row.get('collectionId'))!=str(identifier):continue
        tid=str(row.get('trackId',''));title=str(row.get('trackName') or '').strip()[:180]
        url=_link(row.get('trackViewUrl'));artist=str(row.get('artistName') or header['artist'])[:120]
        disc=row.get('discNumber');number=row.get('trackNumber')
        if not tid.isdecimal() or tid in seen or not title or not url or type(number) is not int or number<1:continue
        seen.add(tid)
        tracks.append({'id':10**15+int.from_bytes(hashlib.sha256(url.encode()).digest()[:6],'big'),
                       'title':title,'artist':artist,'url':url,'album':header['title'],
                       'release_date':header['release_date'],'disc_number':disc if type(disc) is int and disc>0 else 1,
                       'track_number':number,'duration':round(row['trackTimeMillis']/1000) if type(row.get('trackTimeMillis')) is int and row['trackTimeMillis']>0 else None,
                       '_catalog_song':{'title':title,'artist':artist}})
    tracks.sort(key=lambda t:(t['disc_number'],t['track_number']))
    return {'name':creator(song),'album':header,'tracks':tracks,'source':'Apple Music'}
