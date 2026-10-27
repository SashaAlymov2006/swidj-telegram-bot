"""Public country charts, independent from app searches and personal listening data."""
import asyncio
import time
import hashlib
import re
import unicodedata
import os
import json
import math
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
import aiohttp
from aiohttp import web

COUNTRIES=('de','us','gb','fr','ua','ru')
TTL=1800
BASE='https://rss.marketingtools.apple.com'


def clean_feed(data,country):
    if not isinstance(data,dict):raise ValueError('Invalid chart feed')
    feed=data.get('feed',{})
    if not isinstance(feed,dict):raise ValueError('Invalid chart feed')
    rows=feed.get('results',[])
    if not isinstance(rows,list):raise ValueError('Invalid chart feed')
    tracks=[];seen=set()
    for rank,item in enumerate(rows[:50],1):
        if not isinstance(item,dict):continue
        identifier=str(item.get('id',''));title=str(item.get('name') or '').strip()[:180];artist=str(item.get('artistName') or '').strip()[:160]
        if not identifier.isdigit() or identifier in seen or not title or not artist:continue
        seen.add(identifier)
        image=str(item.get('artworkUrl100') or '')
        try:
            url=urlsplit(image)
            if url.scheme!='https' or not (url.hostname or '').endswith('.mzstatic.com') or url.username or url.password:image=''
        except ValueError:image=''
        tracks.append({'id':identifier,'rank':rank,'title':title,'artist':artist,'artwork':image,'query':(artist+' '+title)[:120]})
    if not tracks:raise ValueError('Empty chart feed')
    return {'source':'Apple Music','country':country,'updated':str(feed.get('updated') or '')[:80],
            'source_url':'https://music.apple.com/'+country+'/browse/top-charts/songs','tracks':tracks}



def words(value):
    value=unicodedata.normalize('NFKD',str(value).casefold()).replace("'",'').replace('\u2019','')
    value=''.join(c for c in value if not unicodedata.combining(c))
    return set(re.findall(r'[^\W_]+',value))

def matching_versions(item,recordings):
    title=re.sub(r'[\(\[]\s*(?:feat|ft|with)\.?[^\)\]]*[\)\]]','',item['title'],flags=re.I)
    wanted=words(title);full_artist=words(item['artist'])
    primary=words(re.split(r'\s+(?:&|x|and|feat\.?|ft\.?|with)\s+|,\s*',item['artist'],flags=re.I)[0])
    unwanted={'cover','karaoke','reaction','tutorial','interview','slowed','sped','nightcore','instrumental','remix','live','meaning','explained','review'}-(words(item['title'])|full_artist)
    result=[]
    for recording in recordings:
        found=words(recording['title']+' '+recording.get('artist',''))
        if not wanted or not wanted<=found:continue
        if not (full_artist<=found or primary and sum(map(len,primary))>=4 and primary<=found):continue
        if unwanted & words(recording['title']):continue
        result.append(recording)
    return sorted(result,key=lambda r:('official' in words(r['title']),full_artist<=words(r['title']+' '+r.get('artist',''))),reverse=True)

class Charts:
    def __init__(self, cache_root=None):
        self.cache={};self.lock=asyncio.Lock();self.recordings={};self.resolve_lock=asyncio.Lock()
        root=cache_root or os.getenv('MINIAPP_CHART_CACHE_DIR')
        self.cache_root=Path(root) if root else None

    def load_disk(self,country):
        if self.cache_root is None:return None
        try:
            path=self.cache_root/(country+'.json')
            if path.is_symlink() or path.stat().st_size>1024**2:return None
            stored=json.loads(path.read_text(encoding='utf-8'))
            age=time.time()-stored['fetched_at']
            if not math.isfinite(age) or not -30<=age<=7*86400:return None
            value=stored['chart']
            if value['country']!=country:return None
            rows=value['tracks']
            if not isinstance(rows,list) or not rows or len(rows)>50:return None
            ranks=[row['rank'] for row in rows]
            if any(type(rank) is not int or not 1<=rank<=50 for rank in ranks) or ranks!=sorted(set(ranks)):return None
            validated=clean_feed({'feed':{'updated':value['updated'],'results':[
                {'id':row['id'],'name':row['title'],'artistName':row['artist'],'artworkUrl100':row.get('artwork','')} for row in rows]}},country)
            if len(validated['tracks'])!=len(rows):return None
            for track,rank in zip(validated['tracks'],ranks):track['rank']=rank
            return time.monotonic()-max(0,age),validated
        except (OSError,ValueError,TypeError,KeyError):return None

    def save_disk(self,country,value):
        if self.cache_root is None:return
        pending=None
        try:
            self.cache_root.mkdir(parents=True,exist_ok=True)
            raw=json.dumps({'fetched_at':time.time(),'chart':value},ensure_ascii=False)
            if len(raw.encode('utf-8'))>1024**2:return
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.cache_root,prefix='.'+country+'-',delete=False) as stream:
                pending=Path(stream.name);stream.write(raw)
            os.replace(pending,self.cache_root/(country+'.json'))
        except OSError:pass
        finally:
            try:
                if pending:pending.unlink(missing_ok=True)
            except OSError:pass
    async def fetch(self,country):
        for attempt in range(2):
            try:return await self.fetch_once(country)
            except (aiohttp.ClientError,asyncio.TimeoutError):
                if attempt:raise
                await asyncio.sleep(.5)

    async def fetch_once(self,country):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15),headers={'User-Agent':'SwiDJ/1.0 chart reader'}) as client:
            async with client.get(BASE+'/api/v2/'+country+'/music/most-played/50/songs.json') as response:
                if response.status!=200:raise ValueError('Chart unavailable')
                raw=bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    raw.extend(chunk)
                    if len(raw)>1024**2:raise ValueError('Chart too large')
                import json
                return clean_feed(json.loads(raw),country)
    async def get(self,country):
        if country not in COUNTRIES:raise web.HTTPBadRequest()
        entry=self.cache.get(country)
        if entry and time.monotonic()-entry[0]<TTL:return dict(entry[1],stale=False)
        async with self.lock:
            entry=self.cache.get(country)
            if not entry:
                entry=await asyncio.to_thread(self.load_disk,country)
                if entry:self.cache[country]=entry
            if entry and time.monotonic()-entry[0]<TTL:return dict(entry[1],stale=False)
            try:
                value=await self.fetch(country)
                self.cache[country]=(time.monotonic(),value)
                await asyncio.to_thread(self.save_disk,country,value)
                return dict(value,stale=False)
            except (aiohttp.ClientError,asyncio.TimeoutError,ValueError,TypeError,KeyError):
                if entry and time.monotonic()-entry[0]<7*86400:return dict(entry[1],stale=True)
                raise web.HTTPServiceUnavailable() from None

    async def resolve(self,country,identifier,bridge,source=None):
        chart=await self.get(country)
        item=next((row for row in chart['tracks'] if row['id']==identifier),None)
        if not item:raise web.HTTPNotFound()
        key=(country,identifier,source)
        async with self.resolve_lock:
            cached=self.recordings.get(key)
            if cached and time.monotonic()-cached[0]<300:return item,cached[1]
            from versions import find_versions
            async with bridge.search_slots:
                if source:
                    from versions import source_search
                    result=await asyncio.to_thread(source_search,item,source)
                else:
                    result=await asyncio.to_thread(find_versions,item['query'],limit=10)
                if not source and not matching_versions(item,result):
                    title=re.sub(r'[\(\[]\s*(?:feat|ft|with)\.?[^\)\]]*[\)\]]','',item['title'],flags=re.I)
                    artist=re.split(r'\s+(?:&|x|and|feat\.?|ft\.?|with)\s+|,\s*',item['artist'],flags=re.I)[0]
                    extra=await asyncio.to_thread(find_versions,(artist+' '+title+' official audio')[:240],limit=10)
                    seen={row['url'] for row in result};result+= [row for row in extra if row['url'] not in seen]
            from recording_availability import verified_choices
            result=await asyncio.to_thread(verified_choices,result,item['query'],limit=5)
            for song in result:
                song['id']=10**15+int.from_bytes(hashlib.sha256(song['url'].encode()).digest()[:6],'big')
                song['_catalog_song']={k:item.get(k,'') for k in ('title','artist')}
            if result:
                self.recordings[key]=(time.monotonic(),result)
                while len(self.recordings)>300:self.recordings.pop(next(iter(self.recordings)))
            return item,result


def register(app,bridge):
    service=Charts();app['charts_worker']=service
    async def refresh_periodically():
        # Requests still use the 30-minute TTL. Keep disk feeds fresh even without visitors.
        await asyncio.sleep(60)
        while True:
            for country in COUNTRIES:
                try:await service.get(country)
                except web.HTTPException:pass
            await asyncio.sleep(3600)
    async def lifecycle(application):
        task=asyncio.create_task(refresh_periodically())
        try:yield
        finally:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
    app.cleanup_ctx.append(lifecycle)
    async def chart(request):
        bridge.allowed(request['user']['id'],'search')
        return web.json_response(await service.get(request.query.get('country','de').lower()))
    async def resolve(request):
        uid=request['user']['id'];bridge.allowed(uid,'search')
        value=await request.json()
        if not isinstance(value,dict):raise web.HTTPBadRequest()
        country=value.get('country','de');identifier=str(value.get('track',''))
        source=value.get('source')
        if source not in (None,'yt','sc','aud','jam'):raise web.HTTPBadRequest()
        if country not in COUNTRIES or not identifier.isdigit() or len(identifier)>20:raise web.HTTPBadRequest()
        item,recordings=await service.resolve(country,identifier,bridge,source)
        from versions import source_inventory
        inventory=await source_inventory(dict(item,_inventory_limit=2),uid,{source or 'yt':recordings})
        if source is None:
            merged=[];seen=set()
            for index in range(5):
                for provider in ('yt','sc','aud','jam'):
                    rows=inventory.get(provider,[])
                    if index<len(rows) and rows[index]['url'] not in seen:
                        seen.add(rows[index]['url']);merged.append(dict(rows[index]))
            recordings=merged+[row for row in recordings if row['url'] not in seen]
            for row in recordings:
                row['id']=10**15+int.from_bytes(hashlib.sha256(row['url'].encode()).digest()[:6],'big')
                row['_catalog_song']={k:item.get(k,'') for k in ('title','artist')}
        saved=[]
        if source is None:
            origin={k:item.get(k,'') for k in ('title','artist')}
            for row in await bridge.app_history(uid):
                if row.get('kind')!='upload' and row.get('_catalog_song')==origin and bridge.audio_path(uid,row):
                    saved.append(row)
            recordings=list({row['id']:row for row in recordings+saved}.values())
        from dispatch import user_lock
        async with user_lock(uid):
            current=bridge.chart_recordings.get(uid,[])
            bridge.chart_recordings.pop(uid,None)
            bridge.chart_recordings[uid]=list({row['id']:row for row in recordings+current}.values())[:100]
            while len(bridge.chart_recordings)>1000:bridge.chart_recordings.pop(next(iter(bridge.chart_recordings)))
        from miniapp_server import public_song
        choices=(recordings if source else list({row['id']:row for row in saved+matching_versions(item,recordings)}.values()))[:5]
        return web.json_response({'tracks':[public_song(row,bool(bridge.audio_path(uid,row))) for row in choices],
                                  'alternatives':[public_song(row,bool(bridge.audio_path(uid,row))) for row in recordings[:5]],
                                  'available_sources':[key for key,rows in inventory.items() if rows],
                                  'source':{'yt':'YouTube','sc':'SoundCloud','aud':'Audius','jam':'Jamendo'}.get(source,'All sources')})
    app.router.add_get('/api/charts',chart)
    app.router.add_post('/api/charts/resolve',resolve)
