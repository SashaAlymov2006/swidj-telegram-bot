"""Public country charts, independent from app searches and personal listening data."""
import asyncio
import time
import hashlib
import re
import unicodedata
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
    def __init__(self):self.cache={};self.lock=asyncio.Lock();self.recordings={};self.resolve_lock=asyncio.Lock()
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
            if entry and time.monotonic()-entry[0]<TTL:return dict(entry[1],stale=False)
            try:
                value=await self.fetch(country)
                self.cache[country]=(time.monotonic(),value)
                return dict(value,stale=False)
            except (aiohttp.ClientError,asyncio.TimeoutError,ValueError,TypeError,KeyError):
                if entry and time.monotonic()-entry[0]<7*86400:return dict(entry[1],stale=True)
                raise web.HTTPServiceUnavailable() from None

    async def resolve(self,country,identifier,bridge):
        chart=await self.get(country)
        item=next((row for row in chart['tracks'] if row['id']==identifier),None)
        if not item:raise web.HTTPNotFound()
        key=(country,identifier)
        async with self.resolve_lock:
            cached=self.recordings.get(key)
            if cached and time.monotonic()-cached[0]<300:return item,cached[1]
            from versions import find_versions
            async with bridge.search_slots:
                result=await asyncio.to_thread(find_versions,item['query'],limit=10)
                if not matching_versions(item,result):
                    title=re.sub(r'[\(\[]\s*(?:feat|ft|with)\.?[^\)\]]*[\)\]]','',item['title'],flags=re.I)
                    artist=re.split(r'\s+(?:&|x|and|feat\.?|ft\.?|with)\s+|,\s*',item['artist'],flags=re.I)[0]
                    extra=await asyncio.to_thread(find_versions,(artist+' '+title+' official audio')[:240],limit=10)
                    seen={row['url'] for row in result};result+= [row for row in extra if row['url'] not in seen]
            for song in result:song['id']=10**15+int.from_bytes(hashlib.sha256(song['url'].encode()).digest()[:6],'big')
            if result:
                self.recordings[key]=(time.monotonic(),result)
                while len(self.recordings)>300:self.recordings.pop(next(iter(self.recordings)))
            return item,result


def register(app,bridge):
    service=Charts();app['charts_worker']=service
    async def chart(request):
        bridge.allowed(request['user']['id'],'search')
        return web.json_response(await service.get(request.query.get('country','de').lower()))
    async def resolve(request):
        uid=request['user']['id'];bridge.allowed(uid,'search')
        value=await request.json()
        if not isinstance(value,dict):raise web.HTTPBadRequest()
        country=value.get('country','de');identifier=str(value.get('track',''))
        if country not in COUNTRIES or not identifier.isdigit() or len(identifier)>20:raise web.HTTPBadRequest()
        item,recordings=await service.resolve(country,identifier,bridge)
        from dispatch import user_lock
        async with user_lock(uid):
            current=bridge.chart_recordings.get(uid,[])
            bridge.chart_recordings.pop(uid,None)
            bridge.chart_recordings[uid]=list({row['id']:row for row in recordings+current}.values())[:100]
            while len(bridge.chart_recordings)>1000:bridge.chart_recordings.pop(next(iter(bridge.chart_recordings)))
        from miniapp_server import public_song
        return web.json_response({'tracks':[public_song(row) for row in matching_versions(item,recordings)],
                                  'alternatives':[public_song(row) for row in recordings]})
    app.router.add_get('/api/charts',chart)
    app.router.add_post('/api/charts/resolve',resolve)
