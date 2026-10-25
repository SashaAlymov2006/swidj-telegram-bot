"""Public country charts, independent from app searches and personal listening data."""
import asyncio
import time
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


class Charts:
    def __init__(self):self.cache={};self.lock=asyncio.Lock()
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


def register(app,bridge):
    service=Charts();app['charts_worker']=service
    async def chart(request):
        bridge.allowed(request['user']['id'],'search')
        return web.json_response(await service.get(request.query.get('country','de').lower()))
    app.router.add_get('/api/charts',chart)
