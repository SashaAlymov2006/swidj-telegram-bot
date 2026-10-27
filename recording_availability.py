"""Bounded preflight of public audio choices. No full remote file or credential logs."""
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from urllib.parse import urlsplit,urljoin
import requests
from operations import checkpoint,run_process

_slots=threading.BoundedSemaphore(2)
_lock=threading.Lock()
_cache={}


def _allowed(url,source):
    try:
        p=urlsplit(str(url));host=(p.hostname or '').lower()
        if p.scheme!='https' or p.username or p.password or p.port not in (None,443):return False
        domains={'youtube':('googlevideo.com',),'soundcloud':('sndcdn.com','soundcloud.com','media-streaming.soundcloud.cloud'),
            'jamendo':('storage.jamendo.com',)}[source]
        return any(host==domain or host.endswith('.'+domain) for domain in domains)
    except (ValueError,KeyError):return False


def _sample(url,source,headers=None):
    """Probe actual media bytes, following at most two public HLS levels."""
    headers={k:v for k,v in (headers or {}).items() if k.lower() in ('user-agent','referer','origin') and isinstance(v,str)}
    headers['Range']='bytes=0-8191'
    for _ in range(3):
        checkpoint()
        if not _allowed(url,source):return False
        with requests.get(url,headers=headers,stream=True,allow_redirects=False,timeout=(3,4)) as response:
            if response.status_code not in (200,206):return False
            body=next(response.iter_content(8192),b'')
        checkpoint()
        if body.lstrip().startswith(b'#EXTM3U'):
            text=body.decode('utf-8','replace')
            if '#EXT-X-KEY:' in text:return False
            line=next((s.strip() for s in text.splitlines() if s.strip() and not s.startswith('#')),None)
            if not line:return False
            url=urljoin(url,line);continue
        return _media_bytes(body)
    return False


def _media_bytes(body):
    return (body.startswith((b'ID3',b'OggS',b'fLaC',b'RIFF',bytes.fromhex('1a45dfa3')))
            or len(body)>2 and body[0]==255 and body[1]&224==224
            or len(body)>8 and body[4:8] in (b'ftyp',b'styp',b'moof'))


def _youtube_sample(item):
    """Exercise the real downloader's test mode (about 10 KiB), not a raw URL."""
    import yt_dlp
    from soundcloud_source import Quiet
    from youtube_session import cookie_snapshot
    from scratch import scratch_root
    def progress(info):
        checkpoint()
        if (info.get('downloaded_bytes') or 0)>65536:raise ValueError('Probe size exceeded')
    def match(info,**kwargs):
        checkpoint()
        if info.get('has_drm') or info.get('is_live') or not _duration_ok(item.get('duration'),info.get('duration')):
            return 'Unavailable full recording'
        if info.get('availability') in ('private','premium_only','subscriber_only','needs_auth'):
            return 'Recording requires access'
    with tempfile.TemporaryDirectory(dir=scratch_root(),prefix='availability-yt-') as folder:
        settings={'quiet':True,'no_warnings':True,'logger':Quiet(),'noplaylist':True,
                  'socket_timeout':4,'retries':0,'extractor_retries':0,'test':True,
                  'format':'bestaudio[protocol=https][format_id!*=preview]/best[protocol=https][format_id!*=preview]',
                  'outtmpl':str(Path(folder)/'probe.%(ext)s'),'allowed_extractors':['youtube.*'],
                  'progress_hooks':[progress],'match_filter':match}
        with cookie_snapshot(os.getenv('YTDLP_COOKIE_FILE')) as jar:
            settings['cookiefile']=jar
            with yt_dlp.YoutubeDL(settings) as ydl:info=ydl.extract_info(item['url'],download=True)
        checkpoint()
        if not isinstance(info,dict) or match(info) or not _allowed(info.get('url'),'youtube'):return False
        files=[p for p in Path(folder).glob('probe.*') if p.is_file() and not p.is_symlink() and p.suffix not in ('.part','.ytdl','.json')]
        if len(files)!=1 or not 0<files[0].stat().st_size<=65536:return False
        return _media_bytes(files[0].read_bytes())


def _duration_ok(expected,actual):
    return (type(actual) in (int,float) and math.isfinite(actual) and actual>0
            and (type(expected) not in (int,float) or abs(expected-actual)<=3))


def _cached(item,uid):
    from download_cache import restore
    from scratch import scratch_root
    with tempfile.TemporaryDirectory(dir=scratch_root(),prefix='availability-') as folder:
        result=restore(item['url'],'audio-mp3-192',folder,uid)
        if not result:return False
        probe=run_process(['ffprobe','-v','error','-show_entries','format=duration','-of','json',result[0]],timeout=5,check=True)
        duration=float(json.loads(probe.stdout)['format']['duration'])
        return _duration_ok(item.get('duration'),duration)


def _remote(item):
    from download_cache import source_key
    key=str(source_key(item['url']))
    if key.startswith('youtube:'):return _youtube_sample(item)
    if key.startswith('jamendo:'):
        from jamendo_source import rows,track,identifier
        tid=identifier(item['url']);row=None
        for _ in range(3):
            checkpoint();raw=rows({'id':tid})
            row=next((r for r in raw if str(r.get('id'))==tid),None)
            if row:break
        if not track(row):return False
        url=str(row.get('audiodownload') or '')
        import re
        if not re.fullmatch(r'/download/track/'+tid+r'/[^/]+/?',urlsplit(url).path):return False
        return _sample(url,'jamendo')
    from soundcloud_source import public_url
    source='soundcloud' if public_url(item['url']) else 'youtube' if key.startswith('youtube:') else None
    if not source:return False
    import yt_dlp
    from soundcloud_source import Quiet
    from youtube_session import cookie_snapshot
    settings={'quiet':True,'no_warnings':True,'logger':Quiet(),'noplaylist':True,
              'socket_timeout':4,'retries':0,'extractor_retries':0,'skip_download':True,
              'format':'bestaudio[format_id!*=preview]/best[format_id!*=preview]',
              'allowed_extractors':[source+'.*']}
    cookie=os.getenv('YTDLP_COOKIE_FILE') if source=='youtube' else None
    with cookie_snapshot(cookie) as jar:
        settings['cookiefile']=jar
        with yt_dlp.YoutubeDL(settings) as ydl:info=ydl.extract_info(item['url'],download=False)
    checkpoint()
    if not isinstance(info,dict) or info.get('has_drm') or info.get('is_live'):return False
    if info.get('availability') in ('private','premium_only','subscriber_only','needs_auth'):return False
    if not _duration_ok(item.get('duration'),info.get('duration')):return False
    if 'preview' in str(info.get('format_id','')).lower():return False
    return _sample(info.get('url'),source,info.get('http_headers'))


def available(item,uid=None):
    checkpoint()
    from download_cache import operation_uid
    uid=uid or operation_uid()
    key=(item.get('url'),item.get('duration'),uid)
    now=time.monotonic()
    with _lock:
        known=_cache.get(key)
        if known and known[0]>now:return known[1]
    deadline=now+8
    while not _slots.acquire(timeout=.2):
        checkpoint()
        if time.monotonic()>deadline:return False
    try:
        try:cached=_cached(item,uid)
        except Exception:cached=False
        try:result=cached or _remote(item)
        except Exception:result=False
        checkpoint()
        with _lock:
            _cache[key]=(time.monotonic()+(180 if result else 20),bool(result))
            while len(_cache)>1000:_cache.pop(next(iter(_cache)))
        return bool(result)
    finally:_slots.release()


def verified_choices(items,query,uid=None,limit=3):
    from search_quality import recording_choices
    if type(limit) is not int or not 1<=limit<=3:raise ValueError('Invalid choice limit')
    choices=[];deadline=time.monotonic()+18
    ranked=recording_choices(items,query,limit=6)
    if limit==1:
        for item in ranked:
            checkpoint()
            if time.monotonic()>deadline:break
            if available(item,uid):return [item]
        return []
    # Two candidates at a time; the global semaphore still caps remote work.
    # Preserve ranking, operation cancellation and user isolation in workers.
    with ThreadPoolExecutor(max_workers=2,thread_name_prefix='recording-check') as pool:
        for offset in range(0,len(ranked),2):
            checkpoint()
            if time.monotonic()>deadline:break
            batch=ranked[offset:offset+2]
            pending=[pool.submit(copy_context().run,available,item,uid) for item in batch]
            for item,result in zip(batch,pending):
                if result.result() and len(choices)<limit:choices.append(item)
            if len(choices)>=limit:break
    checkpoint()
    return choices
