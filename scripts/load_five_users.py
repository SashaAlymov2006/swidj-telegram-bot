"""Bounded five-session live load test. No polling/sends or real library writes.

Run inside bot container, PYTHONPATH=/app. Synthetic HMAC identities exercise
normal public access checks; no owner bypass or ACL changes. Temporary exports
expire normally. Raw credentials, identities and file tickets are never saved.
"""
import asyncio,hashlib,hmac,io,json,math,os,secrets,tempfile,time,wave
from array import array
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch
import aiohttp

BASE=os.environ['MINIAPP_URL'].rstrip('/')
IDS=[8_000_000_000_000_000+secrets.randbelow(100_000_000)+i for i in range(5)]
PHASE=Path('/tmp/swidj-load5-phase.json');STOP=Path('/tmp/swidj-load5-stop')
RESULT=Path('/tmp/swidj-load5-results.json');rows=[];summary=[]
SC='https://soundcloud.com/forss/flickermood'

def phase(name):
    if STOP.exists():raise RuntimeError('Load test safety stop')
    PHASE.write_text(json.dumps({'phase':name,'time':time.time()}))
    print(json.dumps({'phase':name}),flush=True)

def auth(uid):
    data={'auth_date':str(int(time.time())),'user':json.dumps({'id':uid})}
    secret=hmac.new(b'WebAppData',os.environ['TELEGRAM_TOKEN'].encode(),hashlib.sha256).digest()
    data['hash']=hmac.new(secret,'\n'.join(k+'='+v for k,v in sorted(data.items())).encode(),hashlib.sha256).hexdigest()
    return {'X-Telegram-Init-Data':urlencode(data)}

def audio(seconds):
    rate=16000;pcm=array('h')
    for n in range(round(rate*seconds)):
        t=n/rate;v=.24*math.sin(t*math.tau*220)+.08*math.sin(t*math.tau*659)
        v+=.15*math.exp(-(t%.5)*35)*math.sin(t*math.tau*75)
        pcm.extend((round(v*26000),round(v*24000)))
    out=io.BytesIO()
    with wave.open(out,'wb') as w:w.setparams((2,2,rate,0,'NONE',''));w.writeframes(pcm.tobytes())
    return out.getvalue()

async def main():
    payload=audio(45);short=audio(3);urls={}
    timeout=aiohttp.ClientTimeout(total=180,connect=15)
    async with aiohttp.ClientSession(timeout=timeout,connector=aiohttp.TCPConnector(limit=15)) as client:
        async def call(uid,route,*,body=None,form=None,extra=None,label=None):
            if STOP.exists():raise RuntimeError('Load test safety stop')
            started=time.monotonic();status=0;value={};size=0
            try:
                headers={**auth(uid),**(extra or {})}
                async with client.request('POST' if body is not None or form is not None else 'GET',BASE+route,
                                          headers=headers,json=body,data=form) as response:
                    status=response.status;raw=await response.read();size=len(raw)
                    if 'json' in response.headers.get('Content-Type',''):value=json.loads(raw)
            except Exception as error:value={'error':type(error).__name__}
            record={'phase':json.loads(PHASE.read_text())['phase'],'user':IDS.index(uid)+1,'request':label or route.split('?')[0],
                    'status':status,'seconds':round(time.monotonic()-started,4),'bytes':size}
            if value.get('error'):record['error']=value['error']
            rows.append(record);return status,value,record

        phase('baseline');await asyncio.sleep(10)
        phase('setup_public_audio')
        for uid in IDS:
            for attempt in range(6):
                status,data,_=await call(uid,'/api/link',body={'url':SC,'mode':'audio'},label='setup_link')
                if status==200 and data.get('url'):urls[uid]=data['url'];break
                if status!=429:break
                await asyncio.sleep(2)
        summary.append({'phase':'setup','ready_streams':len(urls),'sessions':5})

        async def listeners(seconds):
            async def one(uid):
                until=time.monotonic()+seconds;iteration=0
                while time.monotonic()<until and not STOP.exists():
                    if uid in urls:
                        route=urls[uid].removeprefix(BASE)
                        await call(uid,route,extra={'Range':'bytes=0-32767'},label='stream_range')
                    if iteration%5==0:await call(uid,'/api/library',label='library')
                    iteration+=1;await asyncio.sleep(.5)
            await asyncio.gather(*(one(uid) for uid in IDS))

        phase('five_listeners');await listeners(20)
        phase('five_searches')
        queries=['Ed Sheeran Shape of You','Rick Astley Never Gonna Give You Up','Jeff Lorber','Daft Punk Get Lucky','Forss Flickermood']
        async def search(uid,query):
            status,data,record=await call(uid,'/api/search?'+urlencode({'q':query}),label='search')
            return {'user':IDS.index(uid)+1,'status':status,'seconds':record['seconds'],'results':len(data.get('tracks',[]))}
        summary.append({'phase':'five_searches','users':await asyncio.gather(*(search(uid,q) for uid,q in zip(IDS,queries)))})

        phase('five_simultaneous_link_imports')
        async def link(uid):
            status,data,record=await call(uid,'/api/link',body={'url':SC,'mode':'audio'},label='simultaneous_link')
            return {'user':IDS.index(uid)+1,'status':status,'seconds':record['seconds'],'file_ready':bool(data.get('url'))}
        summary.append({'phase':'five_simultaneous_link_imports','users':await asyncio.gather(*(link(uid) for uid in IDS))})

        phase('five_chat_download_workers_cold')
        from operations import Operation,_current
        from scratch import remove_owned_file
        import bot
        from soundcloud_source import Quiet
        extract=bot._extract_media
        bot._extract_media=lambda options,url,folder:extract(dict(options,logger=Quiet(),noprogress=True,no_warnings=True),url,folder)
        def chat(uid):
            token=_current.set(Operation(uid));started=time.monotonic();path=None
            try:
                path,info=bot.download_youtube_audio(SC)
                return {'user':IDS.index(uid)+1,'ok':True,'seconds':round(time.monotonic()-started,3),'bytes':Path(path).stat().st_size}
            except Exception as error:return {'user':IDS.index(uid)+1,'ok':False,'error':type(error).__name__,'seconds':round(time.monotonic()-started,3)}
            finally:
                if path:remove_owned_file(path)
                _current.reset(token)
        with tempfile.TemporaryDirectory(prefix='load5-private-cache-') as directory,patch.dict(os.environ,DOWNLOAD_CACHE_DIR=directory):
            summary.append({'phase':'five_chat_download_workers_cold','users':await asyncio.gather(*(asyncio.to_thread(chat,uid) for uid in IDS))})

        phase('five_studio_submissions')
        async def studio(uid):
            form=aiohttp.FormData();form.add_field('settings',json.dumps({'background':True,'delivery':'ticket','format':'mp3','speed':1.1,'pitch':2,'linked':False,'effects':['pro_reverb','compressor','equalizer','stereo']}));form.add_field('file',payload,filename='load-test.wav',content_type='audio/wav')
            status,data,record=await call(uid,'/api/studio',form=form,label='studio_submit');submitted=record['seconds']
            job=data.get('job');end=time.monotonic()+120
            while job and data.get('status') in ('queued','processing') and time.monotonic()<end:
                await asyncio.sleep(.5);_,data,_=await call(uid,'/api/studio/jobs/'+job,label='studio_poll')
            return {'user':IDS.index(uid)+1,'http':status,'submit_seconds':submitted,'job_state':data.get('status'),'file_ready':bool(data.get('file'))}
        # Keep five listeners active while the audio render is admitted/executed.
        work=asyncio.gather(*(studio(uid) for uid in IDS))
        await asyncio.gather(listeners(10),work);summary.append({'phase':'five_studio_submissions','users':work.result()})

        phase('video_prepare_five')
        async def video_prepare(uid):
            form=aiohttp.FormData();form.add_field('audio',short,filename='load-test.wav',content_type='audio/wav')
            status,data,_=await call(uid,'/music-video/api/drafts',form=form,label='video_prepare')
            if status!=200:return uid,None
            end=time.monotonic()+120
            while data.get('state') in ('upload','queued','analysis') and time.monotonic()<end:
                await asyncio.sleep(.5);_,data,_=await call(uid,'/music-video/api/jobs/'+data['id'],label='video_prepare_poll')
            return uid,data.get('id') if data.get('state')=='ready' else None
        drafts=await asyncio.gather(*(video_prepare(uid) for uid in IDS))
        phase('five_video_renders')
        async def video(uid,draft):
            if not draft:return {'user':IDS.index(uid)+1,'error':'draft_not_ready'}
            start=time.monotonic();status,data,record=await call(uid,'/music-video/api/render/'+draft,body={'preset':'club','shape':'hexagon','spectrum':'ripple','motion':'sway','pulseMode':'double','resolution':1080,'fps':30,'end':2},label='video_render')
            job=data.get('id');end=time.monotonic()+150
            while job and data.get('state') in ('queued','render') and time.monotonic()<end:
                await asyncio.sleep(.5);_,data,_=await call(uid,'/music-video/api/jobs/'+job,label='video_render_poll')
            return {'user':IDS.index(uid)+1,'http':status,'submit_seconds':record['seconds'],'total_seconds':round(time.monotonic()-start,3),'state':data.get('state'),'file_ready':bool(data.get('files',{}).get('result'))}
        work=asyncio.gather(*(video(uid,draft) for uid,draft in drafts));await asyncio.gather(listeners(15),work)
        summary.append({'phase':'five_video_renders','users':work.result(),'clip_seconds':2,'resolution':1080,'fps':30})
        phase('cooldown');await asyncio.sleep(5)
    phase('complete')

try:asyncio.run(main())
except Exception as error:summary.append({'aborted':True,'error':type(error).__name__})
finally:
    RESULT.write_text(json.dumps({'sessions':5,'synthetic_identities':True,'telegram_messages_sent':0,'real_library_mutations':0,
                                 'summary':summary,'requests':rows},indent=2))
    print(json.dumps({'complete':True,'summaries':summary}),flush=True)
