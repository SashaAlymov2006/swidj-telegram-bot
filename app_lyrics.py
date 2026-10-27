"""Read-only, bounded public lyrics lookup. No audio or Telegram identity is sent."""
import asyncio
import math
import re
import time
import aiohttp
from aiohttp import web
from urllib.parse import quote
from difflib import SequenceMatcher


def search_labels(title,artist):
    title=re.sub(r'\([^)]*(?:official|video|audio|lyrics|slowed|reverb|sped up|visualizer|remaster)[^)]*\)|\[[^]]*(?:official|video|audio|lyrics|slowed|reverb|sped up|visualizer|remaster)[^]]*\]','',title,flags=re.I).strip()[:180]
    artist=re.sub(r'\s*-\s*Topic$','',artist,flags=re.I).strip()[:120]
    parts=re.split(r'\s+[-–—]\s+',title,maxsplit=1)
    normalize=lambda value:re.sub(r'\W','',value.casefold()).removesuffix('vevo')
    if len(parts)==2 and all(parts) and normalize(parts[0])==normalize(artist):
        artist,title=parts
    return title.strip(),artist.strip()


def lyric_matches(data,limit=5):
    matches=[];seen=set()
    if not isinstance(data,list):return matches
    for item in data[:100]:
        if not isinstance(item,dict):continue
        text=item.get('plainLyrics')
        if not isinstance(text,str) or not text.strip():
            synced=item.get('syncedLyrics')
            text=re.sub(r'\[\d+:\d+(?:\.\d+)?\]','',synced).strip() if isinstance(synced,str) else ''
        if not text:continue
        title=str(item.get('trackName',''))[:180];artist=str(item.get('artistName',''))[:120]
        key=(title.casefold(),artist.casefold(),text.strip())
        if key in seen:continue
        identifier=item.get('id')
        source_url='https://lrclib.net/api/get/'+str(identifier) if type(identifier) is int and identifier>0 else 'https://lrclib.net/'
        seen.add(key);matches.append({'title':title,'artist':artist,'text':text[:64000],'source':'LRCLIB','source_url':source_url})
        if len(matches)>=limit:break
    return matches

class Lyrics:
    def __init__(self):
        self.cache={};self.slots=asyncio.Semaphore(1);self.blocked_until=0

    async def _request(self,client,url,params=None):
        async with client.get(url,params=params,allow_redirects=False) as response:
            if response.status==429:
                try:delay=float(response.headers.get('Retry-After','60'))
                except ValueError:delay=60
                self.blocked_until=time.monotonic()+min(3600,max(1,delay if math.isfinite(delay) else 60))
                raise web.HTTPTooManyRequests()
            if response.status==404:return None
            if response.status!=200:raise web.HTTPServiceUnavailable()
            chunks=[];size=0
            async for chunk in response.content.iter_chunked(65536):
                size+=len(chunk)
                if size>1024*1024:raise web.HTTPServiceUnavailable()
                chunks.append(chunk)
            import json
            return json.loads(b''.join(chunks))

    async def lookup(self,title,artist,duration=None):
        title,artist=search_labels(title,artist)
        key=(title,artist)
        if key in self.cache and self.cache[key][0]>time.monotonic():return self.cache[key][1]
        if self.blocked_until>time.monotonic() or self.slots.locked():raise web.HTTPTooManyRequests()
        async with self.slots:
            matches=[]
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8),headers={'User-Agent':'SwiDJ/1.1 (https://github.com/SashaAlymov2006/swidj-telegram-bot)'}) as client:
                params={'track_name':title,'artist_name':artist}
                if type(duration) in (int,float) and math.isfinite(duration) and 1<=duration<=3600:params['duration']=round(duration)
                try:
                    record=await self._request(client,'https://lrclib.net/api/get',params)
                    matches=ranked_matches(lyric_matches([record]),title,artist) if record else []
                    if not matches:
                        await asyncio.sleep(.25)
                        records=await self._request(client,'https://lrclib.net/api/search',{'track_name':title,'artist_name':artist})
                        matches=ranked_matches(lyric_matches(records,20),title,artist)
                except (aiohttp.ClientError,asyncio.TimeoutError,ValueError,web.HTTPException):pass
                if not matches:
                    endpoint='https://api.lyrics.ovh/v1/'+quote(artist,safe='')+'/'+quote(title,safe='')
                    try:
                        record=await self._request(client,endpoint)
                        text=record.get('lyrics') if isinstance(record,dict) else None
                        if isinstance(text,str) and text.strip():
                            matches=[{'title':title,'artist':artist,'text':text.strip()[:64000],'source':'lyrics.ovh','source_url':endpoint}]
                    except (aiohttp.ClientError,asyncio.TimeoutError,ValueError,web.HTTPException):pass
            result={'matches':matches,'source':matches[0]['source'] if matches else 'LRCLIB'}
            while len(self.cache)>=128:self.cache.pop(next(iter(self.cache)))
            self.cache[key]=(time.monotonic()+(3600 if matches else 120),result)
            return result


def ranked_matches(matches,title,artist):
    normalize=lambda text:re.sub(r'[^\w]','',text.casefold())
    def score(item):
        a=SequenceMatcher(None,normalize(title),normalize(item['title'])).ratio()
        b=SequenceMatcher(None,normalize(artist),normalize(item['artist'])).ratio() if artist else 1
        return a+b if a>=.65 and b>=.6 else 0
    return sorted((item for item in matches if score(item)),key=score,reverse=True)[:5]


shared=Lyrics()

def register(app,bridge):
    service=shared
    app['lyrics_service']=service
    async def lyrics(request):
        uid=request['user']['id'];bridge.allowed(uid,'search')
        song=await bridge.find(uid,request.query.get('track',''))
        song=song.get('_catalog_song') or song
        return web.json_response(await service.lookup(str(song.get('title','')),str(song.get('artist','')),song.get('duration')))
    app.router.add_get('/api/lyrics',lyrics)
