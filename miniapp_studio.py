"""App-only, bounded FFmpeg studio and local speech transcription."""
import asyncio
import json
import math
import os
from pathlib import Path
import sys
import tempfile

from aiohttp import web

MAX_INPUT = 49*1024**2
MAX_OUTPUT = 96*1024**2
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
    "reverse": "areverse",
}

async def process(args, timeout=240):
    child = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        stdout, _ = await asyncio.wait_for(child.communicate(), timeout)
        if child.returncode:
            raise ValueError("Media processing failed")
        return stdout
    finally:
        if child.returncode is None:
            child.kill()
            await child.wait()

async def probe(path, allow_unknown=False):
    raw = await process(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','mp3,wav,ogg,flac,mov,matroska,webm',
                         '-select_streams','a:0','-show_entries','stream=codec_name:format=duration,format_name',
                         '-of','json',str(path)], 15)
    data = json.loads(raw)
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
    if not isinstance(settings, dict) or duration > 1800:
        raise ValueError('Invalid audio settings')
    format = settings.get('format','mp3')
    effects = settings.get('effects', [settings.get('effect','none')])
    if not isinstance(effects,list) or len(effects)>8 or any(not isinstance(effect,str) or effect not in EFFECTS for effect in effects):
        raise ValueError('Invalid effect chain')
    effects=list(dict.fromkeys(effects))
    if format not in ('mp3','wav'):
        raise ValueError('Invalid format or effect')
    start=number(settings,'start',0,0,1800)
    end=number(settings,'end',0,0,1800) or duration
    speed=number(settings,'speed',1,.5,2)
    pitch=number(settings,'pitch',0,-6,6)
    bass=number(settings,'bass',0,-6,9)
    treble=number(settings,'treble',0,-6,6)
    fade=number(settings,'fade',0,0,10)
    if end <= start or end > duration+.1:
        raise ValueError('Invalid trim')
    length=(min(end,duration)-start)/speed
    if length > 1800:
        raise ValueError('Output too long')
    if format=='wav' and length*44100*4+44 > MAX_OUTPUT:
        raise OverflowError('WAV too large; select MP3')
    # Pitch and tempo are independently controlled. All expressions use validated numbers.
    ratio=2**(pitch/12)
    filters=[f'volume={-max(0,bass)-max(0,treble)}dB',f'bass=g={bass}:f=100',f'treble=g={treble}:f=3000',
             f'aresample=44100',f'asetrate={44100*ratio}']
    tempo=speed/ratio
    while tempo < .5:
        filters.append('atempo=0.5');tempo/=.5
    while tempo > 2:
        filters.append('atempo=2');tempo/=2
    filters += [f'atempo={tempo}', 'aresample=44100']
    for effect in effects:
        if EFFECTS[effect]: filters.append(EFFECTS[effect])
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
    await process(args+['-fs',str(MAX_OUTPUT+4096),str(target)])
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

    async def handle(self, request, voice=False):
        uid=request['user']['id']
        bridge=request.app['studio_bridge']
        bridge.allowed(uid,'voice' if voice else 'studio')
        bridge.allowed(uid,'search' if voice else 'downloads')
        if self.slots.locked(): raise web.HTTPTooManyRequests()
        async with self.slots:
            from scratch import scratch_root
            with tempfile.TemporaryDirectory(dir=scratch_root(),prefix='app-studio-') as folder:
                source=Path(folder)/'source.audio'
                try:
                    settings=await read_upload(request,source,8*1024**2 if voice else MAX_INPUT,not voice)
                    if voice:
                        duration=await probe(source,allow_unknown=True)
                        if duration > 30: raise ValueError('Voice too long')
                        clip=Path(folder)/'voice.wav'
                        await process(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','mp3,wav,ogg,flac,mov,matroska,webm','-i',str(source),'-t','31','-vn','-ar','16000','-ac','1',str(clip)],30)
                        if not .3 <= await probe(clip) <= 30: raise ValueError('Invalid voice duration')
                        raw=await process([sys.executable,str(Path(__file__).resolve()),'transcribe',str(clip)],240)
                        result=json.loads(raw)
                        return web.json_response({'text':str(result.get('text',''))[:120]})
                    target=await render(source,folder,settings)
                    response=web.StreamResponse(headers={
                        'Content-Type':'audio/mpeg' if target.suffix=='.mp3' else 'audio/wav',
                        'Content-Length':str(target.stat().st_size),
                        'Content-Disposition':'attachment; filename="SwiDJ-mix'+target.suffix+'"',
                        'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'})
                    await response.prepare(request)
                    async def transfer():
                        with target.open('rb') as stream:
                            while chunk:=stream.read(65536):
                                await response.write(chunk)
                        await response.write_eof()
                    await asyncio.wait_for(transfer(),90)
                    return response
                except OverflowError:
                    raise web.HTTPRequestEntityTooLarge(max_size=MAX_INPUT,actual_size=MAX_INPUT+1) from None
                except (ValueError,KeyError,TypeError,json.JSONDecodeError):
                    raise web.HTTPBadRequest() from None
                except asyncio.TimeoutError:
                    raise web.HTTPGatewayTimeout() from None

def register(app,bridge):
    studio=Studio()
    app['studio_bridge']=bridge
    async def export(request): return await studio.handle(request)
    async def voice(request): return await studio.handle(request,True)
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
