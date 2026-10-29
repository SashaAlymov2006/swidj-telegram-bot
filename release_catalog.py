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
_views={}


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
        with requests.get('https://itunes.apple.com/'+path,params={'country':'de','media':'music',**params},
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


def _apple_releases(song,offset=0,*,all_rows=False):
    from artist_catalog import creator,normalized
    if type(offset) is not int or offset<0 or offset>190 or offset%10:raise ValueError('Invalid release page')
    name=creator(song)
    if not name:raise ValueError('Artist unavailable')
    rows=_request('search',{'term':name,'entity':'album','attribute':'artistTerm','limit':200})
    artist_ids=list(dict.fromkeys(str(r.get('artistId')) for r in rows if normalized(r.get('artistName'))==normalized(name) and str(r.get('artistId','')).isdecimal()))
    rows=list(rows)
    for aid in artist_ids[:2]:
        try:rows.extend(_request('lookup',{'id':aid,'entity':'album','limit':200}))
        except (ValueError,requests.RequestException,TimeoutError):pass
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
    return {'name':name,'releases':albums if all_rows else albums[offset:offset+10],'offset':offset,
            'next_offset':offset+10 if offset+10<len(albums) else None,'source':'Apple Music',
            'profiles':list(profiles.values()) if len(profiles)>1 else [],'selected_profile':selected}


def _apple_album(song,identifier):
    from artist_catalog import creator,normalized
    if not re.fullmatch(r'\d{1,16}',str(identifier)):raise ValueError('Invalid album')
    rows=_request('lookup',{'id':str(identifier),'entity':'song','limit':200})
    header=next((release(r) for r in rows if str(r.get('collectionId'))==str(identifier) and release(r)),None)
    from expanded_catalog import known_names
    if not header or normalized(header['artist']) not in {normalized(n) for n in (song.get('_artist_aliases') or known_names(creator(song)))}:raise ValueError('Album belongs to another artist')
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


def _additional(song):
    from expanded_catalog import collect
    return collect(song)


def _combined(song):
    from artist_catalog import creator,normalized
    from expanded_catalog import browse_names
    extra=_additional(song)
    page=None;apple=[]
    for name in ([] if song.get('_catalog_scope') in ('aud','jam') else browse_names(song)):
        origin=dict(song,artist=name);origin.pop('_catalog_song',None)
        try:
            result=_apple_releases(origin,all_rows=True)
            if song.get('_mb_artist_id') and result.get('profiles') and not result.get('selected_profile'):
                continue  # A chosen MusicBrainz entity does not need an ambiguous Apple profile.
            if page is None:page=result
            apple.extend(dict(row,source='Apple Music') for row in result['releases'])
        except (ValueError,requests.RequestException,TimeoutError):pass
    if page is None:page={'name':creator(song),'profiles':[],'selected_profile':''}
    if page.get('profiles'):
        if not page.get('selected_profile'):extra=[]
        else:extra=[]  # An unverified same-name cross-catalog identity must not be merged.
    combined={}
    for item in apple+extra:
        title=re.sub(r'\s[-–—]\s(?:Single|EP)$','',item['title'],flags=re.I)
        key=(normalized(title),item['kind'],item.get('release_date','')[:4])
        known=combined.get(key)
        if known:
            if item['id'] not in [a['id'] for a in known['alternatives']]:known['alternatives'].append({k:item.get(k,'') for k in ('id','source','source_url')})
            if not known.get('cover') and item.get('cover'):known['cover']=item['cover']
        else:
            combined[key]=dict(item,alternatives=[{k:item.get(k,'') for k in ('id','source','source_url')}])
    rows=sorted(combined.values(),key=lambda a:(a.get('release_date',''),a['title']),reverse=True)
    catalogs=list(dict.fromkeys(a['source'] for row in rows for a in row['alternatives']))
    return dict(name=creator(song),releases=rows,
                profiles=page.get('profiles',[]),selected_profile=page.get('selected_profile',''),source=' / '.join(catalogs),catalogs=catalogs,total=len(rows))


def releases(song,offset=0):
    from artist_catalog import creator
    if type(offset) is not int or not 0<=offset<=990 or offset%10:raise ValueError('Invalid release page')
    key=(creator(song),song.get('_mb_artist_id'),song.get('_release_artist_id'),tuple(song.get('_artist_aliases') or []),song.get('_catalog_scope'),song.get('_audius_user_id'),song.get('_jam_artist_id'))
    with _lock:known=_views.get(key)
    if known and known[0]>time.monotonic():view=deepcopy(known[1])
    else:
        view=_combined(song)
        with _lock:
            while len(_views)>=64:_views.pop(next(iter(_views)))
            _views[key]=(time.monotonic()+(300 if len(view['catalogs'])>1 else 60),deepcopy(view))
    rows=view.pop('releases')
    return dict(view,releases=rows[offset:offset+10],offset=offset,next_offset=offset+10 if offset+10<len(rows) else None)


def album(song,identifier):
    from expanded_catalog import album as other_album
    def open_one(value):
        result=_apple_album(song,value) if re.fullmatch(r'\d{1,16}',str(value)) else other_album(song,str(value))
        for track in result['tracks']:
            track['_catalog_metadata']=True
            track.setdefault('_catalog_song',{'title':track['title'],'artist':track['artist']})
        return result
    try:return open_one(identifier)
    except (ValueError,requests.RequestException,TimeoutError):
        from artist_catalog import creator
        with _lock:views=[deepcopy(v[1]) for key,v in _views.items() if key[0]==creator(song)]
        alternatives=[]
        for view in views:
            for item in view['releases']:
                ids=[a['id'] for a in item['alternatives']]
                if identifier in ids:alternatives.extend(value for value in ids if value!=identifier)
        for value in list(dict.fromkeys(alternatives))[:3]:
            try:return open_one(value)
            except (ValueError,requests.RequestException,TimeoutError):pass
        raise
