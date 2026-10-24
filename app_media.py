"""App-only public link import with bounded subprocesses and phone-compatible media."""
import asyncio
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit,urlunsplit,parse_qs,urlencode
from aiohttp import web
from miniapp_studio import process,probe

MAX_BYTES=49*1024**2
DIRECT={'youtube','soundcloud','tiktok','instagram'}

def validate(payload):
    from catalog_links import classify
    if not isinstance(payload,dict):raise ValueError('Invalid link')
    url=payload.get('url','');mode=payload.get('mode','audio');height=payload.get('height',360)
    if not isinstance(url,str) or not 1<len(url)<=2048 or mode not in ('audio','video') or type(height) is not int or height not in (360,720):raise ValueError('Invalid options')
    platform=classify(url)
    if platform not in DIRECT|{'apple','yandex','spotify'}:raise ValueError('Unsupported link')
    if mode=='video' and platform not in {'youtube','tiktok','instagram'}:raise ValueError('No video on this platform')
    parts=urlsplit(url)
    if platform=='youtube' and parts.path=='/watch':
        identifier=parse_qs(parts.query).get('v',[''])[0]
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}',identifier):raise ValueError('Invalid video')
        url='https://www.youtube.com/watch?'+urlencode({'v':identifier})
    return url,mode,height,platform

async def normalize(source,target,mode):
    if mode=='video':
        raw=await process(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','mov,matroska,webm',
                           '-select_streams','v:0','-show_entries','stream=codec_name:format=duration','-of','json',str(source)],15)
        info=json.loads(raw)
        if not info.get('streams'):raise ValueError('No video')
        duration=float(info['format']['duration'])
        if not math.isfinite(duration) or duration<=0:raise ValueError('Invalid video')
    else:duration=await probe(source)
    if duration>1800:raise ValueError('Media too long')
    command=['ffmpeg','-nostdin','-v','error','-y','-threads','2','-protocol_whitelist','file,pipe',
             '-format_whitelist','mp3,wav,ogg,flac,mov,matroska,webm','-i',str(source),'-map_metadata','-1']
    if mode=='audio':command+=['-vn','-c:a','libmp3lame','-b:a','192k']
    else:command+=['-vf','scale=w=min(1280\,iw):h=min(720\,ih):force_original_aspect_ratio=decrease:force_divisible_by=2',
                  '-c:v','libx264','-preset','veryfast','-crf','25','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart']
    await process(command+['-threads','2','-fs',str(MAX_BYTES+1024*1024),str(target)],180)
    if not 0<target.stat().st_size<=MAX_BYTES:raise ValueError('Media too large')
    return duration

def register(app,bridge):
    slots=asyncio.Semaphore(1)
    running={}
    async def import_link(request):
        uid=request['user']['id'];bridge.allowed(uid,'downloads')
        try:payload=await request.json();url,mode,height,platform=validate(payload)
        except (ValueError,TypeError):raise web.HTTPBadRequest() from None
        if slots.locked():raise web.HTTPTooManyRequests()
        from miniapp_server import public_url
        if not public_url():raise web.HTTPConflict()
        async with slots:
            running[uid]=asyncio.current_task()
            from scratch import scratch_root
            with tempfile.TemporaryDirectory(dir=scratch_root(),prefix='app-link-') as directory:
                try:
                    raw=await process([sys.executable,str(Path(__file__).resolve()),'fetch',json.dumps({'url':url,'mode':mode,'height':height,'platform':platform}),directory],180)
                    result=json.loads(raw)
                    if result.get('kind')=='search':return web.json_response(result)
                    source=Path(result['path'])
                    if source.is_symlink() or source.resolve().parent!=Path(directory).resolve() or not 0<source.stat().st_size<=MAX_BYTES:raise ValueError('Invalid output')
                    target=Path(directory)/('ready.mp4' if mode=='video' else 'ready.mp3')
                    duration=await normalize(source,target,mode)
                    token,item=app['studio_worker'].exports.retain(uid,target,result.get('title','SwiDJ'),feature='downloads')
                    poster=None;has_audio=True
                    if mode=='video':
                        streams=json.loads(await process(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=codec_name','-of','json',str(target)],15))
                        has_audio=bool(streams.get('streams'))
                        try:
                            image=Path(directory)/'poster.jpg'
                            await process(['ffmpeg','-nostdin','-v','error','-i',str(target),'-frames:v','1','-vf','scale=360:-2','-q:v','4',str(image)],20)
                            image_token,_=app['studio_worker'].exports.retain(uid,image,'preview',feature='downloads')
                            poster=public_url().rstrip('/')+'/studio-file/'+image_token
                        except (ValueError,OSError):pass
                    return web.json_response({'kind':mode,'url':public_url().rstrip('/')+'/studio-file/'+token,
                                              'filename':item['filename'],'title':result.get('title','SwiDJ'),
                                              'artist':result.get('artist',''),'duration':duration,'expires_in':600,'poster':poster,'has_audio':has_audio})
                except asyncio.TimeoutError:raise web.HTTPGatewayTimeout() from None
                except (ValueError,KeyError,TypeError,OSError):raise web.HTTPBadGateway() from None
                finally:running.pop(uid,None)
    async def cancel(request):
        task=running.get(request['user']['id'])
        if task:task.cancel()
        return web.json_response({'ok':True})
    async def extract_audio(request):
        uid=request['user']['id'];bridge.allowed(uid,'downloads')
        payload=await request.json()
        if not isinstance(payload,dict):raise web.HTTPBadRequest()
        item=app['studio_worker'].exports.get(str(payload.get('ticket','')))
        if not item or item['uid']!=uid or item['path'].suffix!='.mp4':raise web.HTTPNotFound()
        if slots.locked():raise web.HTTPTooManyRequests()
        from miniapp_server import public_url
        if not public_url():raise web.HTTPConflict()
        async with slots:
            from scratch import scratch_root
            with tempfile.TemporaryDirectory(dir=scratch_root(),prefix='app-video-audio-') as directory:
                try:
                    target=Path(directory)/'audio.mp3'
                    duration=await normalize(item['path'],target,'audio')
                    title=item['filename'].rsplit('.',1)[0]
                    token,result=app['studio_worker'].exports.retain(uid,target,title,feature='downloads')
                    return web.json_response({'kind':'audio','title':title,'artist':'','filename':result['filename'],
                                              'url':public_url().rstrip('/')+'/studio-file/'+token,'duration':duration,'expires_in':600})
                except (ValueError,KeyError,OSError):raise web.HTTPBadGateway() from None
    app.router.add_post('/api/link/audio',extract_audio)
    app.router.add_post('/api/link/cancel',cancel)
    app.router.add_post('/api/link',import_link)

def fetch(payload,directory):
    url,mode,height,platform=validate(payload)
    if platform in ('apple','yandex'):
        from catalog_links import catalog_metadata
        metadata=catalog_metadata(platform,url)
        return {'kind':'search','query':metadata['query'][:120]}
    if platform=='spotify':
        import requests
        response=requests.get('https://open.spotify.com/oembed',params={'url':url},timeout=12)
        response.raise_for_status();metadata=response.json()
        return {'kind':'search','query':str(metadata['title'])[:120]}
    import yt_dlp
    class Quiet:
        def debug(self,*args):pass
        def warning(self,*args):pass
        def error(self,*args):pass
    def progress(info):
        if info.get('downloaded_bytes',0)>MAX_BYTES:raise ValueError('File too large')
    def match(info,**kwargs):
        duration=info.get('duration')
        if info.get('is_live') or isinstance(duration,(int,float)) and (not math.isfinite(duration) or duration>1800):return 'Unsupported duration'
    options={'outtmpl':str(Path(directory)/'source.%(ext)s'),'noplaylist':True,'playlist_items':'1',
             'socket_timeout':12,'retries':1,'fragment_retries':1,'extractor_retries':1,
             'quiet':True,'no_warnings':True,'logger':Quiet(),'max_filesize':MAX_BYTES,
             'progress_hooks':[progress],'match_filter':match,'restrictfilenames':True,
             'format':'bestaudio/best' if mode=='audio' else f'bv*[height<={height}]+ba/b[height<={height}]',
             'merge_output_format':'mp4','allowed_extractors':['youtube.*','soundcloud.*','tiktok.*','instagram.*'],
             'cookiefile':os.getenv('YTDLP_COOKIE_FILE') if platform=='youtube' else None}
    with yt_dlp.YoutubeDL(options) as downloader:info=downloader.extract_info(url,download=True)
    if isinstance(info,dict) and 'entries' in info:info=next((item for item in info['entries'] if item),None)
    if not isinstance(info,dict):raise ValueError('No media')
    files=[p for p in Path(directory).glob('source.*') if p.is_file() and p.suffix not in ('.part','.ytdl','.json')]
    if len(files)!=1:raise ValueError('No complete media')
    return {'path':str(files[0]),'title':str(info.get('track') or info.get('title') or 'SwiDJ')[:180],
            'artist':str(info.get('artist') or info.get('uploader') or '')[:120]}

if __name__=='__main__':
    try:
        if len(sys.argv)!=4 or sys.argv[1]!='fetch':raise ValueError()
        print(json.dumps(fetch(json.loads(sys.argv[2]),sys.argv[3]),ensure_ascii=True))
    except Exception:raise SystemExit(2)
