"""App-only, bounded FFmpeg studio and local speech transcription."""
import asyncio
import json
import math
import os
import signal
import shutil
from pathlib import Path
import sys
import tempfile

from aiohttp import web

from app_limits import MEDIA_BYTES,MEDIA_SECONDS,STUDIO_OUTPUT_BYTES
MAX_INPUT = MEDIA_BYTES
MAX_OUTPUT = STUDIO_OUTPUT_BYTES
EFFECTS = {
    "none": None, "reverb": "aecho=0.8:0.8:80|140:0.25|0.15",
    "echo": "aecho=0.8:0.8:250:0.3",
    "lofi": "aresample=8000,lowpass=f=3000,highpass=f=150,aresample=44100",
    "normalize": "loudnorm=I=-16:TP=-1.5:LRA=11",
    "compressor": "acompressor=threshold=0.05:ratio=4",
    "delay": "aecho=0.8:0.8:180|360|540:0.4|0.25|0.15",
    "equalizer": "equalizer=f=1000:width_type=o:width=2:g=5",
    "mastering": "afftdn,loudnorm=I=-16:TP=-1.5:LRA=11",
    "pro_reverb": "aecho=0.8:0.9:1000:0.3",
    "highpass": "highpass=f=3000", "lowpass": "lowpass=f=300",
    "reverse": "areverse", "tremolo":"tremolo", "distortion":"asoftclip", "stereo":"pan",
}

async def process(args, timeout=240):
    child = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,start_new_session=(os.name!='nt'))
    try:
        stdout, _ = await asyncio.wait_for(child.communicate(), timeout)
        if child.returncode:
            raise ValueError("Media processing failed")
        return stdout
    finally:
        if child.returncode is None:
            if os.name!='nt':
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            else:child.kill()
            await child.wait()

async def probe(path, allow_unknown=False):
    raw = await process(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','mp3,wav,ogg,flac,mov,matroska,webm',
                         '-select_streams','a:0','-show_entries','stream=codec_name:format=duration,format_name',
                         '-of','json',str(path)], 15)
    data = json.loads(raw)
    if not data.get('format',{}).get('duration') and not allow_unknown and data.get('streams'):
        # MediaRecorder WebM has no duration header. Read bounded packet timestamps,
        # rather than trusting a client-supplied recording length.
        packets = await process(['ffprobe','-v','error','-protocol_whitelist','file,pipe',
            '-format_whitelist','mp3,wav,ogg,flac,mov,matroska,webm','-select_streams','a:0',
            '-read_intervals',f'%+{MEDIA_SECONDS+1}','-show_entries','packet=pts_time,duration_time',
            '-of','csv=p=0',str(path)],60)
        ends=[]
        for line in packets.decode().splitlines():
            try:
                fields=line.split(',');ends.append(float(fields[0])+float(fields[1]))
            except (ValueError,IndexError):continue
        if ends:data['format']['duration']=max(ends)
    duration = float(data['format'].get('duration') or (0 if allow_unknown else 'nan'))
    container = data['format']['format_name'].split(',')[0]
    if not data.get('streams') or container not in ('mp3','wav','ogg','flac','mov','mp4','matroska','webm') or not math.isfinite(duration) or duration < 0 or (not duration and not allow_unknown):
        raise ValueError('Invalid audio')
    return duration

def number(settings, key, default, low, high):
    value = settings.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Invalid setting')
    return value

def plan(settings, duration):
    if not isinstance(settings, dict) or duration > MEDIA_SECONDS:
        raise ValueError('Invalid audio settings')
    format = settings.get('format','mp3')
    effects = settings.get('effects', [settings.get('effect','none')])
    if not isinstance(effects,list) or len(effects)>8 or any(not isinstance(effect,str) or effect not in EFFECTS for effect in effects):
        raise ValueError('Invalid effect chain')
    effects=list(dict.fromkeys(effects))
    if format not in ('mp3','wav'):
        raise ValueError('Invalid format or effect')
    start=number(settings,'start',0,0,MEDIA_SECONDS)
    end=number(settings,'end',0,0,MEDIA_SECONDS) or duration
    speed=number(settings,'speed',1,.5,2)
    if settings.get('preview') is True:end=min(end,start+15*speed)
    pitch=number(settings,'pitch',0,-12,12)
    linked=settings.get('linked',False)
    if type(linked) is not bool:raise ValueError('Invalid link mode')
    from app_dsp import parameters,effect_filter
    params=parameters(settings)
    bass=number(settings,'bass',0,-6,9)
    treble=number(settings,'treble',0,-6,6)
    fade=number(settings,'fade',0,0,10)
    ambience=number(settings,'ambience',100,0,100)/100
    if end <= start or end > duration+.1:
        raise ValueError('Invalid trim')
    length=(min(end,duration)-start)/speed
    if length > MEDIA_SECONDS:
        raise ValueError('Output too long')
    if format=='wav' and length*44100*4+44 > MAX_OUTPUT:
        raise OverflowError('WAV too large; select MP3')
    # Pitch and tempo are independently controlled. All expressions use validated numbers.
    ratio=speed if linked else 2**(pitch/12)
    filters=[f'volume={-max(0,bass)-max(0,treble)}dB',f'bass=g={bass}:f=100',f'treble=g={treble}:f=3000',
             f'aresample=44100',f'asetrate={44100*ratio}']
    tempo=speed/ratio
    while tempo < .5:
        filters.append('atempo=0.5');tempo/=.5
    while tempo > 2:
        filters.append('atempo=2');tempo/=2
    filters += [f'atempo={tempo}', 'aresample=44100']
    for effect in effects:
        expression=effect_filter(effect,params,ambience) or EFFECTS[effect]
        if expression: filters.append(expression)
    if fade:
        fade=min(fade,length/2)
        filters += [f'afade=t=in:d={fade}',f'afade=t=out:st={length-fade}:d={fade}']
    filters.append('alimiter=limit=0.95:level=false:latency=1')
    return format,start,min(end,duration)-start,length,','.join(filters)

async def render(source, output_dir, settings):
    duration=await probe(source)
    format,start,span,length,filters=plan(settings,duration)
    target=Path(output_dir)/('mix.'+format)
    args=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-threads','2',
          '-protocol_whitelist','file,pipe','-format_whitelist','mp3,wav,ogg,flac,mov,matroska,webm','-ss',str(start),'-t',str(span),'-i',str(source),
          '-vn','-map_metadata','-1','-af',filters,'-ar','44100','-ac','2','-threads','2']
    args += ['-c:a','libmp3lame','-b:a','192k'] if format=='mp3' else ['-c:a','pcm_s16le']
    await process(args+['-fs',str(MAX_OUTPUT+4096),str(target)],900)
    if not 0 < target.stat().st_size <= MAX_OUTPUT:
        raise OverflowError('Output too large')
    return target

async def read_upload(request, target, limit, settings=False):
    reader=await request.multipart()
    part=await reader.next()
    options={}
    if settings:
        if not part or part.name!='settings': raise ValueError('Missing settings')
        raw=await part.read_chunk(4096)
        if len(raw)>=4096: raise ValueError('Settings too large')
        options=json.loads(raw)
        if not isinstance(options,dict):raise ValueError('Invalid settings')
        part=await reader.next()
    if not part or part.name!='file': raise ValueError('Missing audio')
    total=0
    with Path(target).open('wb') as stream:
        while chunk:=await part.read_chunk(65536):
            total+=len(chunk)
            if total>limit: raise OverflowError('Input too large')
            stream.write(chunk)
    if not total: raise ValueError('Empty audio')
    return options

class Studio:
    def __init__(self):
        self.slots=asyncio.Semaphore(1)
        from dispatch import WorkQueue
        self.uploads=WorkQueue(workers=2,capacity=24,timeout=600)
        self.voices=WorkQueue(workers=1,capacity=12,timeout=600)
        from app_exports import ExportFiles
        from app_render_jobs import RenderJobs
        self.exports=ExportFiles()
        self.jobs=RenderJobs(self.exports,self.slots,render)

    async def handle(self, request, voice=False):
        uid=request['user']['id'];bridge=request.app['studio_bridge']
        bridge.allowed(uid,'voice' if voice else 'studio');bridge.allowed(uid,'search' if voice else 'downloads')
        from dispatch import QueueFull
        try:
            async with (self.voices if voice else self.uploads).enter(uid):
                return await self.handle_admitted(request,uid,bridge,voice)
        except QueueFull:raise web.HTTPTooManyRequests() from None
        except asyncio.TimeoutError:raise web.HTTPGatewayTimeout() from None

    async def handle_admitted(self,request,uid,bridge,voice):
        from scratch import scratch_root
        temporary=tempfile.TemporaryDirectory(dir=scratch_root(),prefix='app-studio-')
        folder=temporary.name;source=Path(folder)/'source.audio';handed=False
        try:
            if not voice and request.content_type=='application/json':
                settings=await request.json()
                if not isinstance(settings,dict):raise ValueError('Invalid settings')
                if settings.get('source_ticket'):
                    item=self.exports.get(str(settings['source_ticket']))
                    if not item or item['uid']!=uid or item['path'].suffix not in ('.mp3','.wav','.mp4'):raise web.HTTPGone()
                    shutil.copyfile(item['path'],source)
                elif settings.get('source_track'):
                    from dispatch import user_lock
                    async with user_lock(uid):
                        song=await bridge.find(uid,str(settings['source_track']))
                        path=bridge.audio_path(uid,song)
                        if not path:raise web.HTTPGone()
                        shutil.copyfile(path,source)
                else:raise ValueError('Missing owned source')
                if source.stat().st_size>MAX_INPUT:raise OverflowError()
            else:settings=await read_upload(request,source,8*1024**2 if voice else MAX_INPUT,not voice)
            if voice:
                duration=await probe(source,allow_unknown=True)
                if duration>30:raise ValueError('Voice too long')
                clip=Path(folder)/'voice.wav'
                await process(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','mp3,wav,ogg,flac,mov,matroska,webm','-i',str(source),'-t','31','-vn','-ar','16000','-ac','1',str(clip)],30)
                if not .3<=await probe(clip)<=30:raise ValueError('Invalid voice duration')
                raw=await process([sys.executable,str(Path(__file__).resolve()),'transcribe',str(clip)],240)
                return web.json_response({'text':str(json.loads(raw).get('text',''))[:120]})
            from miniapp_server import public_url
            if settings.get('delivery')=='ticket' or settings.get('background'):
                if not public_url():raise web.HTTPConflict()
            if settings.get('background') is True:
                try:job=self.jobs.start(uid,source,folder,settings,temporary.cleanup)
                except ValueError:raise web.HTTPTooManyRequests() from None
                handed=True
                return web.json_response(self.jobs.payload(job,public_url()))
            async with self.slots:
                target=await render(source,folder,settings)
            if settings.get('delivery')=='ticket':
                token,item=self.exports.retain(uid,target,settings.get('title','SwiDJ mix'))
                return web.json_response({'url':public_url().rstrip('/')+'/studio-file/'+token,'filename':item['filename'],'expires_in':self.exports.ttl})
            response=web.StreamResponse(headers={'Content-Type':'audio/mpeg' if target.suffix=='.mp3' else 'audio/wav',
                'Content-Length':str(target.stat().st_size),'Content-Disposition':'attachment; filename="SwiDJ-mix'+target.suffix+'"',
                'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'})
            await response.prepare(request)
            async def transfer():
                with target.open('rb') as stream:
                    while chunk:=stream.read(65536):await response.write(chunk)
                await response.write_eof()
            await asyncio.wait_for(transfer(),180)
            return response
        except OverflowError:raise web.HTTPRequestEntityTooLarge(max_size=MAX_INPUT,actual_size=MAX_INPUT+1) from None
        except (ValueError,KeyError,TypeError):raise web.HTTPBadRequest() from None
        except asyncio.TimeoutError:raise web.HTTPGatewayTimeout() from None
        finally:
            if not handed:temporary.cleanup()


def register(app,bridge):
    studio=Studio()
    app['studio_bridge']=bridge
    app['studio_worker']=studio
    async def sweeper():
        while True:
            await asyncio.sleep(60)
            studio.exports.prune()
    async def start_cleanup(_):
        studio.exports.prune()
        studio.sweeper=asyncio.create_task(sweeper())
    async def stop_cleanup(_):
        await studio.jobs.close()
        studio.sweeper.cancel()
        await asyncio.gather(studio.sweeper,return_exceptions=True)
    app.on_startup.append(start_cleanup)
    app.on_cleanup.append(stop_cleanup)
    async def export(request): return await studio.handle(request)
    async def voice(request): return await studio.handle(request,True)
    async def file(request):
        from urllib.parse import quote
        item=studio.exports.get(request.match_info['ticket'])
        if not item:raise web.HTTPNotFound()
        bridge.allowed(item['uid'],'downloads');bridge.allowed(item['uid'],item.get('feature','studio'))
        return web.FileResponse(item['path'],headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(item['filename'],safe='')})
    app.router.add_get('/studio-file/{ticket:[A-Za-z0-9_-]{32}}',file)
    async def job_status(request):
        uid=request['user']['id'];bridge.allowed(uid,'studio');bridge.allowed(uid,'downloads')
        job=studio.jobs.get(uid,request.match_info['job'])
        if not job:raise web.HTTPNotFound()
        if request.method=='POST':studio.jobs.cancel(uid,job.token)
        from miniapp_server import public_url
        return web.json_response(studio.jobs.payload(job,public_url() or ''))
    async def save_file(request):
        from copy import deepcopy
        from app_uploads import retain,StorageFull
        uid=request['user']['id'];bridge.allowed(uid,'studio');bridge.allowed(uid,'downloads')
        payload=await request.json()
        if not isinstance(payload,dict):raise web.HTTPBadRequest()
        item=studio.exports.get(str(payload.get('ticket','')))
        if not item or item['uid']!=uid or item['path'].suffix not in ('.mp3','.wav'):raise web.HTTPNotFound()
        try:song=await asyncio.to_thread(retain,item['path'],uid,item['filename'])
        except StorageFull:raise web.HTTPInsufficientStorage() from None
        except ValueError:raise web.HTTPRequestEntityTooLarge(max_size=MAX_INPUT,actual_size=item['path'].stat().st_size) from None
        favorites=deepcopy(bridge.favorites.get(uid,[]));tracks=deepcopy(await bridge.app_library(uid));folders=await bridge.folders(uid)
        if not any(s['id']==song['id'] for s in tracks):
            if len(tracks)>=200:raise web.HTTPConflict()
            tracks.append(song)
        if not any(s['id']==song['id'] for s in favorites):
            if len(favorites)>=60:raise web.HTTPConflict()
            favorites.append(song)
        await asyncio.to_thread(bridge.store.save_library,uid,favorites,folders,tracks)
        bridge.favorites[uid]=favorites;bridge.data(uid)['miniapp_library']=tracks
        from miniapp_server import public_song
        return web.json_response({'track':public_song(song,True),'library':await bridge.snapshot(uid)})
    app.router.add_get('/api/studio/jobs/{job:[a-f0-9]{24}}',job_status)
    app.router.add_post('/api/studio/jobs/{job:[a-f0-9]{24}}/cancel',job_status)
    app.router.add_post('/api/studio/save',save_file)
    app.router.add_post('/api/studio',export)
    app.router.add_post('/api/voice',voice)

if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='transcribe': raise SystemExit(2)
    import torch
    import whisper
    torch.set_num_threads(2)
    # Preinstalled official multilingual weights. Never calls paid services.
    model_path=Path.home()/'.cache/whisper/base.pt'
    if not model_path.is_file(): raise SystemExit(3)
    model=whisper.load_model(str(model_path),device='cpu')
    result=model.transcribe(sys.argv[2],fp16=False,verbose=None,condition_on_previous_text=False)
    print(json.dumps({'text':result.get('text','').strip()},ensure_ascii=True))
