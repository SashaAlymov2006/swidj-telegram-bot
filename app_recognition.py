"""Free non-commercial AcoustID lookup; fingerprint only, no uploaded audio leaves host."""
import asyncio
import math
import os
from pathlib import Path
import shutil
import tempfile
import time

import aiohttp
from aiohttp import web
from miniapp_studio import process,probe,read_upload

MAX_UPLOAD=32*1024**2
LOOKUP_URL='https://api.acoustid.org/v2/lookup'


def matches(payload):
    found=[];seen=set()
    rows=payload.get('results',[]) if isinstance(payload,dict) else []
    if not isinstance(rows,list):return found
    def score_of(row):
        try:return float(row.get('score',0))
        except (TypeError,ValueError):return 0
    for row in sorted((r for r in rows if isinstance(r,dict)),key=score_of,reverse=True):
        score=score_of(row)
        if not math.isfinite(score) or not .9<=score<=1:continue
        for recording in row.get('recordings',[]):
            if not isinstance(recording,dict):continue
            title=str(recording.get('title') or '').strip()[:180]
            artist=', '.join(str(a.get('name') or '') for a in recording.get('artists',[]) if isinstance(a,dict))[:160]
            key=(title.casefold(),artist.casefold())
            if not title or not artist or key in seen:continue
            seen.add(key);found.append({'title':title,'artist':artist,'query':(artist+' '+title)[:120]})
            if len(found)==3:return found
    return found


class Recognition:
    def __init__(self):
        self.slot=asyncio.Lock();self.last_request=0

    async def lookup(self,source):
        key=os.getenv('ACOUSTID_API_KEY','').strip()
        if not key:raise web.HTTPServiceUnavailable()
        duration=await probe(source)
        if not 12<=duration<=21600:raise ValueError('Use a recording of at least12 seconds')
        raw=await process(['ffmpeg','-nostdin','-v','error','-threads','2','-protocol_whitelist','file,pipe',
                           '-format_whitelist','mp3,wav,ogg,flac,mov,matroska,webm','-i',str(source),
                           '-t','120','-vn','-ac','1','-ar','11025','-f','chromaprint','-fp_format','base64','pipe:1'],60)
        fingerprint=raw.decode('ascii').strip()
        if not fingerprint or len(fingerprint)>65536:raise ValueError('Invalid fingerprint')
        # One service-wide active operation; at most2.5 external requests/second.
        await asyncio.sleep(max(0,.4-(time.monotonic()-self.last_request)))
        self.last_request=time.monotonic()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),headers={'User-Agent':'SwiDJ/1.0 (non-commercial music identification)'}) as client:
            async with client.post(LOOKUP_URL,data={'client':key,'duration':str(round(duration)),
                                  'fingerprint':fingerprint,'meta':'recordings','format':'json'}) as response:
                if response.status==429:raise web.HTTPTooManyRequests()
                if response.status!=200:raise web.HTTPServiceUnavailable()
                raw=bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    raw.extend(chunk)
                    if len(raw)>512*1024:raise web.HTTPBadGateway()
                import json
                data=json.loads(raw)
        if data.get('status')!='ok':raise web.HTTPServiceUnavailable()
        return matches(data)

    async def handle(self,request):
        uid=request['user']['id'];bridge=request.app['studio_bridge']
        bridge.allowed(uid,'voice');bridge.allowed(uid,'search')
        if not os.getenv('ACOUSTID_API_KEY','').strip():raise web.HTTPServiceUnavailable()
        if self.slot.locked():raise web.HTTPTooManyRequests()
        async with self.slot:
            from scratch import scratch_root
            with tempfile.TemporaryDirectory(dir=scratch_root(),prefix='app-recognition-') as folder:
                source=Path(folder)/'source.audio'
                try:
                    if request.content_type=='application/json':
                        value=await request.json()
                        if not isinstance(value,dict):raise ValueError()
                        if value.get('source_ticket'):
                            item=request.app['studio_worker'].exports.get(str(value['source_ticket']))
                            if not item or item['uid']!=uid or item['path'].suffix not in ('.mp3','.wav','.mp4'):raise web.HTTPNotFound()
                            original=item['path']
                        elif value.get('source_track'):
                            from dispatch import user_lock
                            async with user_lock(uid):
                                song=await bridge.find(uid,str(value['source_track']))
                                original=bridge.audio_path(uid,song)
                            if not original:raise web.HTTPGone()
                        else:raise ValueError()
                        # Cached sources need no duplicate copy or phone re-upload.
                        source=Path(original)
                    else:await read_upload(request,source,MAX_UPLOAD)
                    return web.json_response({'matches':await self.lookup(source),'provider':'AcoustID'})
                except OverflowError:raise web.HTTPRequestEntityTooLarge(max_size=MAX_UPLOAD,actual_size=MAX_UPLOAD+1) from None
                except (ValueError,KeyError,TypeError):raise web.HTTPBadRequest() from None
                except asyncio.TimeoutError:raise web.HTTPGatewayTimeout() from None
                except aiohttp.ClientError:raise web.HTTPServiceUnavailable() from None


def register(app):
    service=Recognition();app['recognition_worker']=service
    app.router.add_post('/api/recognize',service.handle)
