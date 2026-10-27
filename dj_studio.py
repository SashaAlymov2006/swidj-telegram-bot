"""Cached, local DJ analysis and owner-scoped set projects. No external API."""
import asyncio
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import sys
import tempfile
import time

from aiohttp import web
from miniapp_studio import process, probe, number
from app_limits import MEDIA_SECONDS, MEDIA_BYTES

VERSION = 1

def analyse_pcm(raw, duration):
    """100 Hz energy onsets, normalized periodicity, and a full-track overview."""
    pcm=array('h');pcm.frombytes(raw)
    if sys.byteorder!='little':pcm.byteswap()
    if not pcm:raise ValueError('Empty audio')
    width=max(1,math.ceil(len(pcm)/1200))
    peaks=[round(max(abs(x) for x in pcm[i:i+width])/32768,4) for i in range(0,len(pcm),width)]
    # Analyze the strongest 90-second window in the first three minutes. An intro
    # can be silent; do not force a tempo onto speech, silence or an ambiguous grid.
    frames=[]
    for at in range(0,min(len(pcm),2000*180)-19,20):
        frames.append(sum(x*x for x in pcm[at:at+20])/20)
    window=min(len(frames),9000)
    if window<400:return dict(version=VERSION,duration=duration,peaks=peaks,bpm=0,offset=0,confidence=0)
    sums=[sum(frames[start:start+window]) for start in range(0,max(1,len(frames)-window+1),500)]
    start=max(range(len(sums)),key=sums.__getitem__)*500
    segment=frames[start:start+window]
    energy=[sum(segment[max(0,i-4):i+1])/min(5,i+1) for i in range(len(segment))]
    novel=[];average=1.;previous=0.
    for value in energy:
        average=.98*average+.02*value
        novel.append(min(8.,max(0.,value-previous)/(average+1.)))
        previous=value
    mean=sum(novel)/len(novel)
    values=[max(0.,v-mean*.6) for v in novel]
    power=sum(v*v for v in values)
    if power<.01:return dict(version=VERSION,duration=duration,peaks=peaks,bpm=0,offset=0,confidence=0)
    scores={}
    for lag in range(33,101):
        numerator=sum(values[i]*values[i-lag] for i in range(lag,len(values)))
        denom=math.sqrt(sum(v*v for v in values[lag:])*sum(v*v for v in values[:-lag]))
        scores[lag]=numerator/max(denom,1e-12)
    best=max(scores,key=lambda lag:scores[lag]+.12*scores.get(lag*2,0))
    confidence=max(0.,min(1.,scores[best]))
    # Sub-frame interpolation reduces rate drift without claiming a perfect beat grid.
    left=scores.get(best-1,scores[best]);right=scores.get(best+1,scores[best])
    denominator=left-2*scores[best]+right
    correction=max(-.5,min(.5,.5*(left-right)/denominator)) if abs(denominator)>1e-9 else 0
    period=(best+correction)/100
    buckets=[0.]*max(1,round(period*100))
    for i,v in enumerate(values):buckets[round(i%(period*100))%len(buckets)]+=v
    phase=max(range(len(buckets)),key=buckets.__getitem__)/100+start/100
    bpm=round(60/period,2) if confidence>=.18 else 0
    return dict(version=VERSION,duration=duration,peaks=peaks,bpm=bpm,offset=round(phase%period,4) if bpm else 0,confidence=round(confidence,3))

def clean_name(value):
    return ' '.join(''.join(c if c>=' ' else ' ' for c in str(value)).split())[:50]

def deck_settings(value):
    if not isinstance(value,dict):raise ValueError('Invalid deck')
    cues=value.get('cues',[None]*3)
    if not isinstance(cues,list) or len(cues)!=3:raise ValueError('Invalid cues')
    return {**{key:number(value,key,default,low,high) for key,default,low,high in (
        ('speed',1,.5,2),('pitch',0,-12,12),('volume',.85,0,1),('bass',0,-6,9),('treble',0,-6,6),
        ('bpm',0,0,300),('offset',0,0,MEDIA_SECONDS),('position',0,0,MEDIA_SECONDS),
        ('filter',0,-1,1),('bassCut',0,0,1))},
        'cues':[None if c is None else number({'v':c},'v',0,0,MEDIA_SECONDS) for c in cues]}

async def projects(store,uid):
    return (await asyncio.to_thread(store.load_named,'dj_projects')).get(uid,[])

def public_project(item):
    from miniapp_server import public_song
    return {k:v for k,v in item.items() if k!='decks'}|{'decks':{
        key:dict(deck,track=public_song(deck['track']) if deck.get('track') else None)
        for key,deck in item['decks'].items()}}

def register(app,bridge):
    slots=asyncio.Semaphore(1);pending=set()
    cache=Path(os.getenv('DJ_ANALYSIS_DIR','/app/data/dj-analysis'))
    async def analysis(request):
        uid=request['user']['id'];bridge.allowed(uid,'studio')
        identifier=request.query.get('track','')
        from dispatch import user_lock
        async with user_lock(uid):
            song=await bridge.find(uid,identifier);source=bridge.audio_path(uid,song)
            if not source:raise web.HTTPGone()
            source=Path(source);stat=source.stat()
            if stat.st_size>MEDIA_BYTES:raise web.HTTPRequestEntityTooLarge(max_size=MEDIA_BYTES,actual_size=stat.st_size)
            key=hashlib.sha256(f'{VERSION}:{source.resolve()}:{stat.st_mtime_ns}:{stat.st_size}'.encode()).hexdigest()
            target=cache/(key+'.json')
            if target.is_file():
                try:return web.json_response(json.loads(await asyncio.to_thread(target.read_text)))
                except (OSError,ValueError):pass
            if uid in pending or len(pending)>=3:raise web.HTTPTooManyRequests()
            pending.add(uid)
            temporary=tempfile.TemporaryDirectory(prefix='dj-analysis-')
            try:await asyncio.to_thread(shutil.copyfile,source,Path(temporary.name)/'source.audio')
            except BaseException:pending.discard(uid);temporary.cleanup();raise
        try:
            async with slots:
                path=Path(temporary.name)/'source.audio';duration=await probe(path)
                if not 0<duration<=MEDIA_SECONDS:raise web.HTTPBadRequest()
                raw=await process(['ffmpeg','-nostdin','-v','error','-threads','1',
                    '-protocol_whitelist','file,pipe','-format_whitelist','mp3,wav,ogg,flac,mov,matroska,webm',
                    '-i',str(path),'-t',str(MEDIA_SECONDS),'-vn','-ac','1','-ar','2000','-f','s16le','pipe:1'],180)
                result=await asyncio.to_thread(analyse_pcm,raw,duration)
                cache.mkdir(parents=True,exist_ok=True)
                await asyncio.to_thread(target.write_text,json.dumps(result))
                # Bounded derived data; never delete the source recordings.
                files=sorted(cache.glob('*.json'),key=lambda p:p.stat().st_mtime)
                for old in files[:-400]:old.unlink(missing_ok=True)
                return web.json_response(result)
        finally:pending.discard(uid);temporary.cleanup()
    async def project(request):
        uid=request['user']['id'];bridge.allowed(uid,'studio')
        items=list(await projects(bridge.store,uid))
        if request.method=='POST':
            try:
                payload=await request.json();action=payload.get('action');identifier=str(payload.get('id',''))
                if action=='remove':
                    if not any(i['id']==identifier for i in items):raise web.HTTPNotFound()
                    items=[i for i in items if i['id']!=identifier]
                elif action=='save':
                    name=clean_name(payload.get('name',''));value=payload.get('project')
                    if not name or not isinstance(value,dict):raise ValueError()
                    decks={}
                    for key in ('A','B'):
                        deck=value.get('decks',{}).get(key,{})
                        decks[key]=deck_settings(deck)
                        track=deck.get('track')
                        decks[key]['track']=dict(await bridge.find(uid,str(track))) if track is not None else None
                    item={'id':identifier or secrets.token_hex(6),'name':name,'updated':int(time.time()),
                          'cross':number(value,'cross',50,0,100),'decks':decks}
                    if identifier:
                        if not any(i['id']==identifier for i in items):raise web.HTTPNotFound()
                        items=[item if i['id']==identifier else i for i in items]
                    else:
                        if len(items)>=12:raise web.HTTPConflict()
                        items.append(item)
                else:raise ValueError()
            except (ValueError,TypeError,AttributeError):raise web.HTTPBadRequest() from None
            await asyncio.to_thread(bridge.store.save_named,'dj_projects',uid,items)
        return web.json_response({'projects':[public_project(item) for item in items]})
    app.router.add_get('/api/dj/analysis',analysis)
    app.router.add_get('/api/dj/projects',project);app.router.add_post('/api/dj/projects',project)
