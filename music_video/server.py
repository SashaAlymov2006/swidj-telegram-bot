"""Standalone isolated service. Development mode binds to loopback only.

No polling, bot messages, library writes or deployment side effects.
"""
import argparse
import asyncio
from collections import deque
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
from urllib.parse import parse_qsl,urlsplit,quote
import numpy as np
import aiohttp
from aiohttp import web
from .model import validate,DEFAULTS,PRESETS
from .lyrics import TimedLyrics,source_metadata,mapped

STATIC=Path(__file__).parent/'web'
FILES={'audio':'preview.mp3','background-image':'background.png','background-video':'background-preview.mp4',
       'background-poster':'background-poster.png','logo':'logo.png','result':'result.mp4','settings':'settings.json'}

def telegram_user(raw,token):
    pairs=parse_qsl(raw,keep_blank_values=True)
    if len(pairs)!=len(dict(pairs)):raise ValueError('Duplicate fields')
    data=dict(pairs);given=data.pop('hash','')
    secret=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
    digest=hmac.new(secret,'\n'.join(k+'='+v for k,v in sorted(data.items())).encode(),hashlib.sha256).hexdigest()
    if not token or not hmac.compare_digest(given,digest) or not -30<=time.time()-int(data['auth_date'])<=3600:raise ValueError('Expired auth')
    uid=json.loads(data['user'])['id']
    if type(uid) is not int or uid<=0:raise ValueError('Invalid user')
    return uid

class Jobs:
    def __init__(self,root):
        self.root=Path(root)
        if self.root.is_symlink():raise ValueError('Workspace cannot be a symlink')
        self.root=self.root.resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.items={};self.queue=deque();self.event=asyncio.Event();self.process=None;self.active=None;self.task=None
        self.ttl=int(os.getenv('MUSIC_VIDEO_TTL','10800'));self.upload_bytes=int(os.getenv('MUSIC_VIDEO_UPLOAD_BYTES',str(512*1024**2)))
        self.budget=int(os.getenv('MUSIC_VIDEO_MAX_WORKSPACE_BYTES',str(12*1024**3)))
        for folder in self.root.iterdir():
            if not folder.is_dir() or folder.is_symlink() or not re.fullmatch('[0-9a-f]{32}',folder.name):continue
            try:
                job=json.loads((folder/'job.json').read_text())
                if job['state'] in ('queued','analysis','render'):job['state']='interrupted';self.save(job)
                self.items[job['id']]=job
            except (ValueError,OSError,KeyError):continue

    def folder(self,job):return self.root/job['id']
    def workspace_size(self):
        size=0;seen=set()
        for folder in self.root.iterdir():
            if not folder.is_dir() or folder.is_symlink() or not re.fullmatch('[0-9a-f]{32}',folder.name):continue
            for path in folder.iterdir():
                if path.is_symlink() or not path.is_file():continue
                try:stat=path.stat()
                except FileNotFoundError:continue
                key=(stat.st_dev,stat.st_ino) if stat.st_ino else str(path)
                if key not in seen:seen.add(key);size+=stat.st_size
        return size
    def save(self,job):
        folder=self.folder(job);folder.mkdir(parents=True,exist_ok=True)
        pending=folder/'job.pending';pending.write_text(json.dumps(job,ensure_ascii=False),encoding='utf-8');os.replace(pending,folder/'job.json')
    def prune(self):
        for identifier,job in list(self.items.items()):
            if time.time()>job['expires'] and job['id']!=self.active and job['state'] not in ('queued','analysis','render'):
                folder=self.folder(job)
                if folder.parent==self.root and folder.name==identifier and not folder.is_symlink():
                    try:shutil.rmtree(folder)
                    except OSError:continue
                self.items.pop(identifier,None)
    def create(self,uid,kind):
        self.prune()
        if len(self.items)>=64:raise web.HTTPTooManyRequests(reason='Video queue is full')
        if sum(j['uid']==uid and j['state'] in ('queued','analysis','render','upload') for j in self.items.values())>=2:raise web.HTTPTooManyRequests(reason='Wait for your current task')
        if shutil.disk_usage(self.root).free<1024**3 or self.workspace_size()>=self.budget:raise web.HTTPInsufficientStorage()
        job=dict(id=secrets.token_hex(16),capability=secrets.token_urlsafe(32),uid=uid,kind=kind,state='upload',created=time.time(),expires=time.time()+self.ttl)
        self.items[job['id']]=job;self.save(job);return job
    def get(self,uid,identifier):
        self.prune();job=self.items.get(identifier)
        if not job or job['uid']!=uid:raise web.HTTPNotFound()
        return job
    def submit(self,job):
        job['state']='queued';self.save(job);self.queue.append(job['id']);self.event.set()
    def payload(self,job):
        folder=self.folder(job);out={k:job[k] for k in ('id','kind','state','expires')}
        if job['state']=='queued':out['position']=list(self.queue).index(job['id'])+1 if job['id'] in self.queue else 1
        try:out.update(json.loads((folder/'progress.json').read_text()))
        except (OSError,ValueError):pass
        # State is authoritative, including cancellation/interruption.
        out['state']=job['state']
        if job['state'] in ('ready','complete'):
            try:out.update(json.loads((folder/'analysis.json').read_text()))
            except (OSError,ValueError):pass
            out['files']={key:f"files/{job['id']}/{job['capability']}/{key}" for key,name in FILES.items() if (folder/name).is_file()}
        if job.get('scene'):out['scene']=job['scene']
        return out
    async def stop_process(self):
        process=self.process
        if not process or process.returncode is not None:return
        if os.name=='nt':
            killer=await asyncio.create_subprocess_exec('taskkill','/PID',str(process.pid),'/T','/F',stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            await killer.wait()
        else:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        try:await asyncio.wait_for(process.wait(),10)
        except asyncio.TimeoutError:
            if os.name!='nt':
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            else:process.kill()
            await process.wait()
    async def worker(self):
        while True:
            if not self.queue:self.event.clear();await self.event.wait()
            while self.queue:
                identifier=self.queue.popleft();job=self.items.get(identifier)
                if not job or job['state']!='queued':continue
                self.active=identifier;job['state']='analysis' if job['kind']=='draft' else 'render';self.save(job)
                options={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
                try:
                    log=(self.folder(job)/'worker.log').open('wb')
                    try:
                        action=job.get('action','analyse') if job['kind']=='draft' else 'render'
                        self.process=await asyncio.create_subprocess_exec(sys.executable,'-m','music_video.render',action,str(self.folder(job)),cwd=Path(__file__).parent.parent,stdout=log,stderr=log,**options)
                        waiter=asyncio.create_task(self.process.wait())
                        while not waiter.done():
                            await asyncio.wait([waiter],timeout=1)
                            if not waiter.done() and (shutil.disk_usage(self.root).free<512*1024**2 or self.workspace_size()>self.budget):
                                await self.stop_process();job['state']='failed';job['error']='workspace'
                        await waiter
                    finally:log.close()
                    if job['state'] not in ('cancelled','failed'):job['state']=('ready' if job['kind']=='draft' else 'complete') if self.process.returncode==0 else 'failed'
                except asyncio.CancelledError:
                    await self.stop_process();job['state']='interrupted';self.save(job);raise
                except Exception:
                    await self.stop_process();job['state']='failed'
                finally:self.process=None;self.active=None;job['expires']=time.time()+self.ttl;self.save(job)

def create_app(root,*,dev=False,token=''):
    jobs=Jobs(root)
    timed_lyrics=TimedLyrics()
    main_url=os.getenv('MUSIC_VIDEO_LIBRARY_URL','')
    if main_url:
        parsed=urlsplit(main_url)
        if parsed.scheme!='http' or parsed.hostname not in ('bot','localhost','127.0.0.1') or parsed.path!='/api/library' or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Invalid library gate')
    gate={};gate_session=None
    @web.middleware
    async def boundary(request,handler):
        try:
            if '/api/' in request.path:
                if dev:
                    if request.headers.get('X-SwiDJ-Local')!='1':raise web.HTTPForbidden()
                    if request.headers.get('Sec-Fetch-Site')=='cross-site':raise web.HTTPForbidden()
                    origin=request.headers.get('Origin')
                    if origin and urlsplit(origin).netloc!=request.host:raise web.HTTPForbidden()
                    request['uid']=1
                else:
                    try:request['uid']=telegram_user(request.headers.get('X-Telegram-Init-Data',''),token)
                    except (ValueError,KeyError,TypeError):raise web.HTTPUnauthorized() from None
                    if main_url:
                        known=gate.get(request['uid'])
                        if not known or known[0]<time.monotonic():
                            try:
                                async with gate_session.get(main_url,headers={'X-Telegram-Init-Data':request.headers['X-Telegram-Init-Data']},allow_redirects=False) as response:status=response.status
                            except (aiohttp.ClientError,TimeoutError):raise web.HTTPServiceUnavailable() from None
                            gate[request['uid']]=(time.monotonic()+5,status)
                            while len(gate)>1000:gate.pop(next(iter(gate)))
                        else:status=known[1]
                        if status!=200:raise web.HTTPForbidden()
            response=await handler(request)
        except web.HTTPException as error:response=web.json_response({'error':error.status},status=error.status)
        except Exception:response=web.json_response({'error':500},status=500)
        response.headers.update({'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'"})
        return response
    app=web.Application(middlewares=[boundary],client_max_size=32*1024);app['jobs']=jobs
    async def lifecycle(_):
        nonlocal gate_session
        gate_session=aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
        jobs.task=asyncio.create_task(jobs.worker())
        async def cleanup():
            while True:
                await asyncio.sleep(60);jobs.prune()
        janitor=asyncio.create_task(cleanup())
        try:yield
        finally:
            jobs.task.cancel();janitor.cancel()
            await asyncio.gather(jobs.task,janitor,return_exceptions=True)
            await gate_session.close()
    app.cleanup_ctx.append(lifecycle)
    async def index(_):return web.FileResponse(STATIC/'index.html')
    async def asset(request):
        if request.match_info['name']=='bridge.js':return web.FileResponse(Path(__file__).parent.parent/'miniapp'/'visualizer-bridge.js')
        if request.match_info['name'] not in ('editor.js','scene.js','state.js','timing.js','editor.css','bridge.css'):raise web.HTTPNotFound()
        return web.FileResponse(STATIC/request.match_info['name'])
    async def config(request):return web.json_response({'dev':dev,'profile':str(request['uid']),'defaults':DEFAULTS,'presets':PRESETS})
    async def upload(request):
        job=jobs.create(request['uid'],'draft');folder=jobs.folder(job);seen=set();total=0
        try:
            reader=await request.multipart()
            async for part in reader:
                if part.name not in ('audio','background','logo','lyric_source') or part.name in seen:raise web.HTTPBadRequest()
                seen.add(part.name)
                if part.name=='lyric_source':
                    raw=await part.read_chunk(65536)
                    if len(raw)>2048:raise web.HTTPBadRequest()
                    try:metadata=source_metadata(json.loads(raw))
                    except (ValueError,TypeError):metadata=None
                    if metadata:(folder/'lyric_source.json').write_text(json.dumps(metadata),encoding='utf-8')
                    continue
                with (folder/(part.name+'.input')).open('wb') as output:
                    while chunk:=await part.read_chunk(65536):
                        total+=len(chunk)
                        if total>jobs.upload_bytes:raise web.HTTPRequestEntityTooLarge(max_size=jobs.upload_bytes,actual_size=total)
                        if shutil.disk_usage(jobs.root).free<512*1024**2:raise web.HTTPInsufficientStorage()
                        output.write(chunk)
            if 'audio' not in seen:raise web.HTTPBadRequest()
            if jobs.workspace_size()>jobs.budget:raise web.HTTPInsufficientStorage()
            jobs.submit(job);return web.json_response(jobs.payload(job))
        except BaseException:
            job['state']='failed';jobs.save(job);raise
    async def status(request):return web.json_response(jobs.payload(jobs.get(request['uid'],request.match_info['id'])))
    async def lyrics(request):
        draft=jobs.get(request['uid'],request.match_info['id']);folder=jobs.folder(draft)
        if draft['kind']!='draft' or draft['state']!='ready':raise web.HTTPConflict()
        if (folder/'lyrics.json').is_file():return web.json_response(dict(available=True,**json.loads((folder/'lyrics.json').read_text(encoding='utf-8'))))
        try:source=source_metadata(json.loads((folder/'lyric_source.json').read_text(encoding='utf-8')))
        except (OSError,ValueError,TypeError):source=None
        if not source or source.get('disabled'):return web.json_response({'available':False})
        metadata=json.loads((folder/'analysis.json').read_text())
        if abs((source['end']-source['start'])/source['speed']-metadata['duration'])>3:return web.json_response({'available':False})
        result=await timed_lyrics.lookup(source)
        if not result:return web.json_response({'available':False})
        result=mapped(result,source);pending=folder/'lyrics.pending';pending.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');os.replace(pending,folder/'lyrics.json')
        return web.json_response(dict(available=True,**result))
    async def style_file(request):
        try:scene=validate(await request.json())
        except (ValueError,TypeError):raise web.HTTPBadRequest() from None
        job=jobs.create(request['uid'],'settings')
        (jobs.folder(job)/'settings.json').write_text(json.dumps({'type':'swidj-visual-style','version':1,'scene':scene},ensure_ascii=False,indent=2),encoding='utf-8')
        job['state']='complete';jobs.save(job);return web.json_response(jobs.payload(job))
    async def update_assets(request):
        if request.content_type!='multipart/form-data':raise web.HTTPBadRequest()
        draft=jobs.get(request['uid'],request.match_info['id'])
        if draft['kind']!='draft' or draft['state']!='ready':raise web.HTTPConflict()
        job=jobs.create(request['uid'],'draft');job['action']='assets';folder=jobs.folder(job)
        try:
            for name in ('audio.input','preview.mp3','features.npy','background.input','logo.input','background.png','background-poster.png','background-preview.mp4','logo.png','lyric_source.json','lyrics.json'):
                source=jobs.folder(draft)/name
                if source.is_file():
                    try:os.link(source,folder/name)
                    except OSError:await asyncio.to_thread(shutil.copyfile,source,folder/name)
            shutil.copyfile(jobs.folder(draft)/'analysis.json',folder/'analysis.json')
            reader=await request.multipart();seen=set();total=0
            async for part in reader:
                if part.name not in ('background','logo','remove_background','remove_logo') or part.name in seen:raise web.HTTPBadRequest()
                seen.add(part.name)
                if part.name.startswith('remove_'):
                    if await part.read_chunk(65536)!=b'1':raise web.HTTPBadRequest()
                    (folder/(part.name.removeprefix('remove_')+'.input')).unlink(missing_ok=True)
                    continue
                target=folder/(part.name+'.input');target.unlink(missing_ok=True)
                with target.open('wb') as output:
                    while chunk:=await part.read_chunk(65536):
                        total+=len(chunk)
                        if total>jobs.upload_bytes:raise web.HTTPRequestEntityTooLarge(max_size=jobs.upload_bytes,actual_size=total)
                        if shutil.disk_usage(jobs.root).free<512*1024**2:raise web.HTTPInsufficientStorage()
                        output.write(chunk)
            if any(name in seen and 'remove_'+name in seen for name in ('background','logo')) or not seen:raise web.HTTPBadRequest()
            (folder/'assets_changed.json').write_text(json.dumps(sorted({name.removeprefix('remove_') for name in seen})))
            if jobs.workspace_size()>jobs.budget:raise web.HTTPInsufficientStorage()
            jobs.submit(job);return web.json_response(jobs.payload(job))
        except BaseException:job['state']='failed';jobs.save(job);raise
    async def history(request):
        jobs.prune();items=[job for job in jobs.items.values() if job['uid']==request['uid'] and job['kind']=='video']
        return web.json_response({'jobs':[jobs.payload(job) for job in sorted(items,key=lambda job:job['created'],reverse=True)[:15]]})
    async def features(request):
        job=jobs.get(request['uid'],request.match_info['id'])
        if job['state'] not in ('ready','complete'):raise web.HTTPConflict()
        try:start=float(request.query.get('start','0'))
        except ValueError:raise web.HTTPBadRequest() from None
        if not np.isfinite(start) or start<0:raise web.HTTPBadRequest()
        values=np.load(jobs.folder(job)/'features.npy',mmap_mode='r');offset=min(len(values),int(start*30));rows=values[offset:offset+1800]
        return web.json_response({'offset':offset,'rate':30,'values':np.round(rows,3).tolist()})
    async def render_job(request):
        draft=jobs.get(request['uid'],request.match_info['id'])
        if draft['kind']!='draft' or draft['state']!='ready':raise web.HTTPConflict()
        try:scene=validate(await request.json())
        except (ValueError,TypeError):raise web.HTTPBadRequest() from None
        metadata=json.loads((jobs.folder(draft)/'analysis.json').read_text())
        if scene['start']>=metadata['duration'] or scene['backgroundKind'] not in ('color',metadata['backgroundKind']):raise web.HTTPBadRequest()
        if scene['lyricsOn'] and not (jobs.folder(draft)/'lyrics.json').is_file():raise web.HTTPBadRequest()
        job=jobs.create(request['uid'],'video');job['scene']=scene;folder=jobs.folder(job)
        try:
            for name in ('audio.input','features.npy','analysis.json','background.input','background.png','background-poster.png','background-preview.mp4','logo.png','preview.mp3'):
                source=jobs.folder(draft)/name
                if source.is_file():
                    try:os.link(source,folder/name)
                    except OSError:await asyncio.to_thread(shutil.copyfile,source,folder/name)
            if scene['lyricsOn']:shutil.copyfile(jobs.folder(draft)/'lyrics.json',folder/'lyrics.json')
            (folder/'scene.json').write_text(json.dumps(scene,ensure_ascii=False),encoding='utf-8');jobs.submit(job)
            return web.json_response(jobs.payload(job))
        except BaseException:job['state']='failed';jobs.save(job);raise
    async def cancel(request):
        job=jobs.get(request['uid'],request.match_info['id'])
        if job['state'] in ('queued','analysis','render'):
            job['state']='cancelled';jobs.save(job)
            if jobs.active==job['id']:await jobs.stop_process()
        return web.json_response(jobs.payload(job))
    async def media(request):
        jobs.prune();job=jobs.items.get(request.match_info['id']);kind=request.match_info['kind']
        if not job or not secrets.compare_digest(job['capability'],request.match_info['cap']) or kind not in FILES:raise web.HTTPNotFound()
        path=jobs.folder(job)/FILES[kind]
        if path.is_symlink() or not path.is_file():raise web.HTTPNotFound()
        headers={}
        if kind=='result':headers['Content-Disposition']="attachment; filename*=UTF-8''"+quote((job.get('scene',{}).get('title') or 'SwiDJ visualizer')+'.mp4',safe='')
        if kind=='settings':headers['Content-Disposition']='attachment; filename="SwiDJ-style.json"'
        return web.FileResponse(path,headers=headers)
    app.add_routes([web.get('/',index),web.get('/static/{name}',asset),web.get('/api/config',config),web.get('/api/history',history),web.post('/api/drafts',upload),web.post('/api/settings',style_file),
        web.get('/api/jobs/{id:[0-9a-f]{32}}',status),web.post('/api/lyrics/{id:[0-9a-f]{32}}',lyrics),web.post('/api/assets/{id:[0-9a-f]{32}}',update_assets),web.get('/api/features/{id:[0-9a-f]{32}}',features),web.post('/api/render/{id:[0-9a-f]{32}}',render_job),
        web.post('/api/cancel/{id:[0-9a-f]{32}}',cancel),web.get('/files/{id:[0-9a-f]{32}}/{cap}/{kind}',media)])
    return app

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dev',action='store_true');parser.add_argument('--port',type=int,default=8792);parser.add_argument('--root',type=Path,default=Path(os.getenv('LOCALAPPDATA','/tmp'))/'SwiDJ-video-lab'/'data');args=parser.parse_args()
    if not args.dev and not os.getenv('TELEGRAM_TOKEN'):parser.error('Production requires Telegram authentication')
    web.run_app(create_app(args.root,dev=args.dev,token=os.getenv('TELEGRAM_TOKEN','')),host='127.0.0.1' if args.dev else '0.0.0.0',port=args.port,access_log=None)
