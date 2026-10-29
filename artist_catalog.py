"""Bounded public artist discovery, separate from versions of one recording."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from copy import deepcopy
import re
import threading
import time
from urllib.parse import urlsplit
from operations import checkpoint

PROVIDERS=('yt','sc','aud','jam')
NAMES={'yt':'YouTube','sc':'SoundCloud','aud':'Audius','jam':'Jamendo'}
_cache={};_lock=threading.Lock()

def normalized(value):
    from search_quality import normalize
    value=re.sub(r'\s+-\s+Topic$','',str(value),flags=re.I)
    return re.sub(r'\s+','',normalize(value)).removesuffix('vevo')

def matches(name,item):
    prefix=re.split(r'\s+[-–—]\s+',str(item.get('title','')),maxsplit=1)
    return bool(normalized(name)) and normalized(name) in {normalized(item.get('artist','')),normalized(item.get('creator_name','')),normalized(prefix[0]) if len(prefix)==2 else ''}

def provider(song):
    from download_cache import source_key
    key=source_key(song.get('url') or song.get('source_url')) or ''
    if key.startswith('youtube:'):return 'yt'
    if key.startswith('audius:'):return 'aud'
    if key.startswith('jamendo:'):return 'jam'
    if 'soundcloud.com/' in key:return 'sc'
    return None

def creator(song):
    return str((song.get('_catalog_song') or song).get('artist') or song.get('creator_name') or '').strip()[:120]

def details(song):
    result={key:str(song[key])[:180] for key in ('title','artist','album','release_date','upload_date','creator_name') if isinstance(song.get(key),str) and song[key].strip()}
    p=provider(song)
    if p:
        result['source']=NAMES[p];result['url']=str(song.get('url') or song.get('source_url'))
        if p=='yt':
            from download_cache import source_key
            result['url']='https://www.youtube.com/watch?v='+source_key(result['url']).split(':',1)[1]
    if type(song.get('duration')) in (int,float) and song['duration']>0:result['duration']=round(song['duration'])
    return result

def _search(name,source,song):
    checkpoint()
    if source=='sc':
        from soundcloud_source import search,artist_tracks
        rows=search(name,50)
        if provider(song)=='sc' and normalized(song.get('creator_name',''))==normalized(name):
            rows=artist_tracks(song['url'],50,artist_name=name)+rows
        rows=list({row['url']:row for row in rows}.values())
    elif source=='yt':
        from versions import find_versions
        rows=find_versions(name,limit=50)
        rows=[r for r in rows if provider(r)=='yt']
    elif source=='aud':
        from audius_source import search
        rows=search(name,50)
    else:
        from jamendo_source import search
        rows=search(name,50)
    return [dict(row,source=NAMES[source]) for row in rows if matches(name,row)]

def browse(song,source='all',offset=0,*,remixes=False):
    if source not in ('all',)+PROVIDERS or type(offset) is not int or not 0<=offset<=200 or offset%10:raise ValueError('Invalid artist page')
    name=creator(song)
    if not name:raise ValueError('Artist unavailable')
    seed=song.get('url') if provider(song)=='sc' else ''
    if seed:seed='/'.join(str(seed).split('/')[:4])
    key=(name,source,seed)
    with _lock:cached=_cache.get(key)
    if cached and cached[0]>time.monotonic():groups=deepcopy(cached[1])
    else:
        sources=PROVIDERS if source=='all' else (source,)
        groups={}
        with ThreadPoolExecutor(max_workers=4,thread_name_prefix='artist-catalog') as pool:
            tasks={s:pool.submit(copy_context().run,_search,name,s,song) for s in sources}
            for s,task in tasks.items():
                try:groups[s]=task.result()
                except Exception:groups[s]=[]
        checkpoint()
        with _lock:
            while len(_cache)>=64:_cache.pop(next(iter(_cache)))
            _cache[key]=(time.monotonic()+90,deepcopy(groups))
    if remixes:groups={source:[row for row in items if re.search(r'\b(remix|bootleg|rework|mashup|edit)\b',row.get('title',''),re.I)] for source,items in groups.items()}
    rows=[];seen=set()
    for index in range(50):
        for s in PROVIDERS:
            group=groups.get(s,[])
            if index<len(group) and group[index]['url'] not in seen:
                seen.add(group[index]['url']);rows.append(group[index])
    import hashlib
    for row in rows:row['id']=10**15+int.from_bytes(hashlib.sha256(row['url'].encode()).digest()[:6],'big')
    return {'name':name,'tracks':rows[offset:offset+10],'offset':offset,'next_offset':offset+10 if offset+10<len(rows) else None,
            'available_sources':[s for s in PROVIDERS if groups.get(s)]}

def register(app,bridge):
    from aiohttp import web
    busy=set()
    async def artist(request):
        uid=request['user']['id'];bridge.allowed(uid,'search')
        song=await bridge.find(uid,request.query.get('track',''))
        name=request.query.get('name','').strip()
        if name and len(name)<=120 and matches(name,song):
            song=dict(song,artist=name);song.pop('_catalog_song',None)
        if uid in busy:raise web.HTTPTooManyRequests()
        busy.add(uid)
        try:
            offset=int(request.query.get('offset','0'));source=request.query.get('source','all')
            async with bridge.search_slots:
                if request.query.get('section','tracks') not in ('tracks','remixes'):raise ValueError('Invalid section')
                worker=asyncio.create_task(asyncio.to_thread(browse,song,source,offset,remixes=request.query.get('section')=='remixes'))
                try:result=await asyncio.shield(worker)
                except asyncio.CancelledError:
                    await asyncio.gather(worker,return_exceptions=True)
                    raise
        except ValueError:raise web.HTTPBadRequest() from None
        finally:busy.discard(uid)
        import hashlib
        from miniapp_server import public_song
        rows=result.pop('tracks')
        for row in rows:row['id']=10**15+int.from_bytes(hashlib.sha256(row['url'].encode()).digest()[:6],'big')
        # Reuse existing owner-scoped discovery storage; this never changes a library.
        from dispatch import user_lock
        async with user_lock(uid):
            previous=bridge.chart_recordings.get(uid,[])
            bridge.chart_recordings[uid]=list({r['id']:r for r in previous+rows}.values())[-200:]
        while len(bridge.chart_recordings)>1000:bridge.chart_recordings.pop(next(iter(bridge.chart_recordings)))
        result['tracks']=[public_song(row,bool(bridge.audio_path(uid,row))) for row in rows]
        return web.json_response(result)
    app.router.add_get('/api/artist',artist)
    async def release_page(request):
        from release_catalog import releases,album
        uid=request['user']['id'];bridge.allowed(uid,'search')
        song=await bridge.find(uid,request.query.get('track',''))
        if request.query.get('profile'):
            if not re.fullmatch(r'\d{1,16}',request.query['profile']):raise web.HTTPBadRequest()
            song=dict(song,_release_artist_id=request.query['profile'])
        if uid in busy:raise web.HTTPTooManyRequests()
        busy.add(uid)
        try:
            async with bridge.search_slots:
                if request.query.get('album'):
                    task=asyncio.create_task(asyncio.to_thread(album,song,request.query['album']))
                else:
                    task=asyncio.create_task(asyncio.to_thread(releases,song,int(request.query.get('offset','0'))))
                try:result=await asyncio.shield(task)
                except asyncio.CancelledError:
                    await asyncio.gather(task,return_exceptions=True);raise
            if 'tracks' in result:
                from dispatch import user_lock
                from miniapp_server import public_song
                async with user_lock(uid):
                    previous=bridge.chart_recordings.get(uid,[])
                    bridge.chart_recordings[uid]=list({r['id']:r for r in previous+result['tracks']}.values())[-200:]
                while len(bridge.chart_recordings)>1000:bridge.chart_recordings.pop(next(iter(bridge.chart_recordings)))
                result['tracks']=[dict(public_song(row,bool(bridge.audio_path(uid,row))),disc_number=row['disc_number'],track_number=row['track_number']) for row in result['tracks']]
            return web.json_response(result)
        except (ValueError,TypeError):raise web.HTTPBadRequest() from None
        except Exception as error:
            import requests
            if isinstance(error,(requests.RequestException,TimeoutError)):raise web.HTTPServiceUnavailable() from None
            raise
        finally:busy.discard(uid)
    app.router.add_get('/api/artist/releases',release_page)
