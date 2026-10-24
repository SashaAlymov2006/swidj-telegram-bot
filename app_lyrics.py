"""Read-only, bounded public lyrics lookup. No audio or Telegram identity is sent."""
import asyncio
import math
import re
import time
import aiohttp
from aiohttp import web

class Lyrics:
    def __init__(self):
        self.cache={};self.slots=asyncio.Semaphore(1);self.blocked_until=0

    async def lookup(self,title,artist):
        title=re.sub(r'\([^)]*(?:official|video|audio|lyrics)[^)]*\)|\[[^]]*(?:official|video|audio|lyrics)[^]]*\]','',title,flags=re.I).strip()[:180]
        artist=re.sub(r'\s*-\s*Topic$','',artist,flags=re.I).strip()[:120]
        key=(title,artist)
        if key in self.cache and self.cache[key][0]>time.monotonic():return self.cache[key][1]
        if self.blocked_until>time.monotonic() or self.slots.locked():raise web.HTTPTooManyRequests()
        async with self.slots:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12),headers={'User-Agent':'SwiDJ/1.0 (https://github.com/SashaAlymov2006/swidj-telegram-bot)'}) as client:
                async with client.get('https://lrclib.net/api/search',params={'q':(title if ' - ' in title else title+' '+artist)[:240]}) as response:
                    if response.status==429:
                        try:delay=float(response.headers.get('Retry-After','60'))
                        except ValueError:delay=60
                        self.blocked_until=time.monotonic()+(delay if math.isfinite(delay) and delay>0 else 60)
                        raise web.HTTPTooManyRequests()
                    if response.status!=200:raise web.HTTPServiceUnavailable()
                    chunks=[];size=0
                    async for chunk in response.content.iter_chunked(65536):
                        size+=len(chunk)
                        if size>1024*1024:raise web.HTTPServiceUnavailable()
                        chunks.append(chunk)
                    raw=b''.join(chunks)
                    import json
                    data=json.loads(raw)
            matches=[]
            if isinstance(data,list):
                for item in data[:20]:
                    if not isinstance(item,dict):continue
                    text=item.get('plainLyrics')
                    if not isinstance(text,str) or not text.strip():continue
                    matches.append({'title':str(item.get('trackName',''))[:180],
                                    'artist':str(item.get('artistName',''))[:120],
                                    'text':text[:64000],'source':'LRCLIB'})
                    if len(matches)>=5:break
            result={'matches':matches,'source':'LRCLIB'}
            while len(self.cache)>=128:self.cache.pop(next(iter(self.cache)))
            self.cache[key]=(time.monotonic()+3600,result)
            return result

def register(app,bridge):
    service=Lyrics()
    app['lyrics_service']=service
    async def lyrics(request):
        uid=request['user']['id'];bridge.allowed(uid,'search')
        song=await bridge.find(uid,request.query.get('track',''))
        return web.json_response(await service.lookup(str(song.get('title','')),str(song.get('artist',''))))
    app.router.add_get('/api/lyrics',lyrics)
