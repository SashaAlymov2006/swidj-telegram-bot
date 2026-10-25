"""App-only public link import with bounded subprocesses and phone-compatible media."""
import asyncio
import json
import math
import os
import re
import shutil
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import urlsplit,urlunsplit,parse_qs,urlencode
from aiohttp import web
from miniapp_studio import process,probe

from app_limits import LINK_MAX_BYTES,LINK_MAX_SECONDS,LINK_QUALITIES,link_budget
MAX_BYTES=LINK_MAX_BYTES
DIRECT={'youtube','soundcloud','tiktok','instagram','vimeo','bandcamp'}

def validate(payload):
    from catalog_links import classify
    if not isinstance(payload,dict):raise ValueError('Invalid link')
    text=payload.get('url','');mode=payload.get('mode','audio');height=payload.get('height',360)
    if not isinstance(text,str) or not 1<len(text)<=4096 or mode not in ('audio','video') or type(height) is not int or height not in LINK_QUALITIES:raise ValueError('Invalid options')
    matches=re.findall(r'https?://[^\s<>]*?(?=https?://|\s|$)',text.strip(),flags=re.I)
    if not matches:raise ValueError('Invalid link')
    url=matches[0].rstrip('.,;!?)"')
    parts=urlsplit(url);host=(parts.hostname or '').lower()
    if parts.username or parts.password or parts.port not in (None,80,443):raise ValueError('Invalid URL')
    if host in ('youtu.be','youtube.com','www.youtube.com','m.youtube.com','music.youtube.com'):
        identifier=parts.path.strip('/') if host=='youtu.be' else parse_qs(parts.query).get('v',[''])[0] if parts.path=='/watch' else parts.path.strip('/').split('/')[-1]
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}',identifier):raise ValueError('Invalid video')
        url='https://www.youtube.com/watch?'+urlencode({'v':identifier})
    platform=classify(url)
    if host in ('vimeo.com','www.vimeo.com') and re.fullmatch(r'/(?:\d+|channels/[A-Za-z0-9_-]+/\d+)/?',parts.path):platform='vimeo'
    if host.endswith('.bandcamp.com') and re.fullmatch(r'/track/[^/]+/?',parts.path):platform='bandcamp'
    if platform not in DIRECT|{'apple','yandex','spotify'}:raise ValueError('Unsupported link')
    if mode=='video' and platform not in {'youtube','tiktok','instagram','vimeo'}:raise ValueError('No video on this platform')
    return url,mode,height,platform

async def normalize(source,target,mode,height=0):
    budget=link_budget(Path(target).parent)
    if mode=='video':
        raw=await process(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','mov,matroska,webm',
                           '-select_streams','v:0','-show_entries','stream=codec_name,pix_fmt,width,height:format=duration','-of','json',str(source)],15)
        info=json.loads(raw)
        if not info.get('streams'):raise ValueError('No video')
        duration=float(info['format']['duration'])
        if not math.isfinite(duration) or duration<=0:raise ValueError('Invalid video')
    else:duration=await probe(source)
    if LINK_MAX_SECONDS and duration>LINK_MAX_SECONDS:raise ValueError('Media too long')
    command=['ffmpeg','-nostdin','-v','error','-y','-threads','2','-protocol_whitelist','file,pipe',
             '-format_whitelist','mp3,wav,ogg,flac,mov,matroska,webm','-i',str(source),'-map_metadata','-1']
    if mode=='audio':command+=['-vn','-c:a','libmp3lame','-b:a','192k']
    elif info['streams'][0].get('codec_name')=='h264' and info['streams'][0].get('pix_fmt')=='yuv420p' and (not height or max(info['streams'][0].get('width',0),info['streams'][0].get('height',0))<=height*16/9):
        streams=json.loads(await process(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=codec_name','-of','json',str(source)],15))
        command+=['-c:v','copy','-c:a','copy' if not streams.get('streams') or streams['streams'][0].get('codec_name')=='aac' else 'aac','-movflags','+faststart']
    else:
        bound=round(height*16/9) if height else 100000
        command+=['-vf',fr'scale=w=min({bound}\,iw):h=min({bound}\,ih):force_original_aspect_ratio=decrease:force_divisible_by=2',
                  '-c:v','libx264','-preset','veryfast','-crf','25','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart']
    await process(command+['-threads','2','-fs',str(budget),str(target)],600)
    if not 0<target.stat().st_size<budget:raise OSError('Not enough disk space')
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
                    raw=await process([sys.executable,str(Path(__file__).resolve()),'fetch',json.dumps({'url':url,'mode':mode,'height':height,'platform':platform}),directory],600)
                    result=json.loads(raw)
                    if result.get('kind')=='search':return web.json_response(result)
                    if result.get('error'):return web.json_response({'reason':result['error']},status=502)
                    source=Path(result['path'])
                    if source.is_symlink() or source.resolve().parent!=Path(directory).resolve() or not source.stat().st_size>0:raise ValueError('Invalid output')
                    target=Path(directory)/('ready.mp4' if mode=='video' else 'ready.mp3')
                    duration=await normalize(source,target,mode,height)
                    token,item=app['studio_worker'].exports.retain(uid,target,result.get('title','SwiDJ'),feature='downloads',ttl=max(3600,duration+600))
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
                                              'artist':result.get('artist',''),'duration':duration,'expires_in':int(item['expires']-time.time()),'poster':poster,'has_audio':has_audio})
                except asyncio.TimeoutError:raise web.HTTPGatewayTimeout() from None
                except (ValueError,KeyError,TypeError,OSError) as error:
                    message=str(error).lower()
                    reason='diskSpace' if 'disk space' in message else 'mediaTooLong' if 'too long' in message else 'mediaTooLarge' if 'too large' in message else 'sourceUnavailable'
                    return web.json_response({'reason':reason},status=502)
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
                    token,result=app['studio_worker'].exports.retain(uid,target,title,feature='downloads',ttl=max(3600,duration+600))
                    return web.json_response({'kind':'audio','title':title,'artist':'','filename':result['filename'],
                                              'url':public_url().rstrip('/')+'/studio-file/'+token,'duration':duration,'expires_in':int(result['expires']-time.time())})
                except (ValueError,KeyError,OSError):raise web.HTTPBadGateway() from None
    app.router.add_post('/api/link/audio',extract_audio)
    app.router.add_post('/api/link/cancel',cancel)
    app.router.add_post('/api/link',import_link)

def fetch(payload,directory):
    url,mode,height,platform=validate(payload)
    if platform == 'youtube' and mode == 'audio' and os.getenv('SEARCH_RECORDING_SOURCE') == 'soundcloud':
        from catalog_links import youtube_metadata
        metadata = youtube_metadata(url)
        return {'kind':'search', 'query':metadata['query'][:120]}
    if platform in ('apple','yandex'):
        from catalog_links import catalog_metadata
        metadata=catalog_metadata(platform,url)
        return {'kind':'search','query':metadata['query'][:120]}
    if platform=='spotify':
        import requests
        response=requests.get('https://open.spotify.com/oembed',params={'url':url},timeout=12)
        response.raise_for_status();metadata=response.json()
        return {'kind':'search','query':(str(metadata['title'])+' '+str(metadata.get('author_name') or ''))[:120]}
    budget=link_budget(directory)
    import yt_dlp
    class Quiet:
        def debug(self,*args):pass
        def warning(self,*args):pass
        def error(self,*args):pass
    def progress(info):
        from operations import checkpoint
        checkpoint()
        if info.get('downloaded_bytes',0)>budget:raise OSError('Not enough disk space')
    def match(info,**kwargs):
        duration=info.get('duration')
        if info.get('is_live'):raise ValueError('Live broadcast')
        if isinstance(duration,(int,float)) and (not math.isfinite(duration) or LINK_MAX_SECONDS and duration>LINK_MAX_SECONDS):raise ValueError('Media too long')
    options={'outtmpl':str(Path(directory)/'source.%(ext)s'),'noplaylist':True,'playlist_items':'1',
             'socket_timeout':12,'retries':1,'fragment_retries':1,'extractor_retries':1,
             'quiet':True,'no_warnings':True,'logger':Quiet(),'max_filesize':budget,
             'progress_hooks':[progress],'match_filter':match,'restrictfilenames':True,
             'format':'bestaudio/best' if mode=='audio' else f'bv*[height<={height}][vcodec^=avc]+ba[acodec^=mp4a]/b[height<={height}][ext=mp4]/bv*[height<={height}]+ba/b[height<={height}]',
             'merge_output_format':'mp4','allowed_extractors':['youtube.*','soundcloud.*','tiktok.*',r'vm\.tiktok','instagram.*','vimeo.*','bandcamp.*'],
             'cookiefile':(os.getenv('YTDLP_COOKIE_FILE') or None) if platform=='youtube' else None}
    if mode=='video' and not height:options['format']='bv*[vcodec^=avc]+ba[acodec^=mp4a]/b[ext=mp4]/bv*+ba/b'
    elif mode=='video':options['format']+='/b[ext=mp4]/b'
    if platform in ('tiktok','instagram'):
        # Social clips commonly expose one combined MP4 above the selected YouTube height.
        # Match the working chat downloader; normalize handles phone-compatible output.
        options['format']='b[ext=mp4]/b' if mode=='video' else 'bestaudio/best'
        options['user_agent']=('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                               'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
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
    except Exception as error:
        message=str(error).lower()
        reason='sourceUnavailable'
        if 'disk space' in message:reason='diskSpace'
        elif 'too large' in message or 'max-filesize' in message:reason='mediaTooLarge'
        elif 'live broadcast' in message:reason='sourceLive'
        elif 'duration' in message or 'too long' in message:reason='mediaTooLong'
        elif 'sign in' in message or 'login' in message or 'not a bot' in message:reason='sourceLogin'
        elif '429' in message:reason='sourceRateLimit'
        elif 'unsupported' in message or 'suitable extractor' in message:reason='unsupportedLink'
        print(json.dumps({'error':reason}))


def download_app_audio(url):
    """App search uses app limits; normal chat downloader remains unchanged."""
    from scratch import scratch_root
    from operations import checkpoint
    directory=tempfile.mkdtemp(dir=scratch_root(),prefix='yt_audio_app_')
    try:
        checkpoint()
        result=fetch({'url':url,'mode':'audio','height':360},directory)
        target=Path(directory)/'ready.mp3'
        asyncio.run(normalize(Path(result['path']),target,'audio'))
        checkpoint()
        return str(target),result
    except BaseException:
        owned=Path(directory).resolve()
        if not owned.is_symlink() and owned.parent==scratch_root().resolve() and owned.name.startswith('yt_audio_app_'):
            shutil.rmtree(owned,ignore_errors=True)
        raise
