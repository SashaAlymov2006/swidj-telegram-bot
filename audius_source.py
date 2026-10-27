"""Optional free Audius API adapter. Only public, ungated, downloadable tracks."""
from contextlib import contextmanager
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import socket
import threading
import time
from urllib.parse import urlsplit, urljoin
import requests
from operations import checkpoint, run_process

API = 'https://api.audius.co/v1'
_lock = threading.Lock()
_blocked_until = 0
_next_request = 0


def enabled():
    return os.getenv('AUDIUS_ENABLED', 'true').lower() not in ('0','false','no') and bool(
        os.getenv('AUDIUS_BEARER_TOKEN','').strip() or os.getenv('AUDIUS_API_KEY','').strip())


def canonical(url):
    try:
        p=urlsplit(str(url))
        if p.scheme!='https' or p.hostname not in ('audius.co','www.audius.co') or p.username or p.password or p.port not in (None,443):return None
        if p.query or p.fragment or not re.fullmatch(r'/[A-Za-z0-9_-][A-Za-z0-9_.-]*/[A-Za-z0-9_-][A-Za-z0-9_.-]*/?',p.path):return None
        if p.path.strip('/').split('/')[0] in ('playlists','albums','users','settings','explore','search'):return None
        return 'https://audius.co'+p.path.rstrip('/')
    except ValueError:return None


def track(row):
    if not isinstance(row,dict) or row.get('is_downloadable') is not True:return None
    if any(row.get(key) for key in ('is_unlisted','is_delete','is_stream_gated','is_download_gated',
                                   'is_scheduled_release','download_conditions','stream_conditions')):return None
    access=row.get('access')
    if isinstance(access,dict) and access.get('download') is False:return None
    keys=row.get('allowed_api_keys')
    if keys and (not isinstance(keys,list) or os.getenv('AUDIUS_API_KEY','') not in keys):return None
    tid=str(row.get('id',''))
    if not re.fullmatch(r'[A-Za-z0-9]{3,32}',tid):return None
    permalink=row.get('permalink')
    url=canonical('https://audius.co'+permalink if isinstance(permalink,str) and permalink.startswith('/') else permalink)
    duration=row.get('duration');user=row.get('user')
    if not url or type(duration) not in (int,float) or not math.isfinite(duration) or not 0<duration<=7200 or not isinstance(user,dict):return None
    title=str(row.get('title') or '').strip()[:180];artist=str(user.get('name') or '').strip()[:120]
    if not title or not artist:return None
    return {'title':title,'artist':artist,'duration':duration,'url':url,'source_url':url,
            'source':'Audius','cover':None,'_audius_id':tid,
            'release_date':str(row.get('release_date') or '')[:40],'creator_name':artist}


def _pace():
    global _next_request
    while True:
        checkpoint()
        with _lock:
            now=time.monotonic()
            if now<_blocked_until:raise ValueError('Audius temporarily unavailable')
            delay=_next_request-now
            if delay<=0:
                _next_request=now+.25
                return
        time.sleep(min(.1,delay))


def _auth():
    if not enabled():raise ValueError('Audius is not configured')
    token=os.getenv('AUDIUS_BEARER_TOKEN','').strip()
    headers={'User-Agent':'SwiDJ/1.0','Accept':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    params={'app_name':'SwiDJ'}
    key=os.getenv('AUDIUS_API_KEY','').strip()
    if key:params['api_key']=key
    return headers,params


def _check_status(response):
    global _blocked_until
    if response.status_code==429:
        try:delay=float(response.headers.get('Retry-After','60'))
        except ValueError:delay=60
        with _lock:_blocked_until=time.monotonic()+min(900,max(1,delay if math.isfinite(delay) else 60))
    if response.status_code not in (200,206,301,302,303,307,308):
        raise ValueError('Audius request unavailable')


def api(path,params=None):
    headers,defaults=_auth();_pace()
    with requests.get(API+path,params=dict(defaults,**(params or {})),headers=headers,
                      allow_redirects=False,stream=True,timeout=(4,8)) as response:
        _check_status(response)
        if response.status_code!=200:raise ValueError('Unexpected Audius redirect')
        data=bytearray()
        for chunk in response.iter_content(65536):
            checkpoint();data.extend(chunk)
            if len(data)>1024**2:raise ValueError('Audius response budget')
    obj=json.loads(data)
    return obj.get('data') if isinstance(obj,dict) else None


def search(query,limit=5):
    if not enabled():return []
    try:
        rows=api('/tracks/search',{'query':str(query)[:240],'limit':min(100,max(1,limit*2)),
                                 'only_downloadable':'true','has_downloads':'true','sort_method':'relevant'})
        return [item for row in (rows or []) if (item:=track(row))][:limit]
    except Exception:
        checkpoint()
        return []


def _metadata(url):
    url=canonical(url)
    if not url:raise ValueError('Invalid Audius track')
    rows=api('/tracks',{'permalink':urlsplit(url).path})
    item=next((item for row in (rows or []) if (item:=track(row)) and item['url']==url),None)
    if not item:raise ValueError('Audius track download is not permitted')
    return item


def _public_media_url(url):
    try:
        p=urlsplit(url);host=p.hostname or ''
        if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or '.' not in host:return False
        addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (ValueError,OSError):return False


@contextmanager
def _media(tid, sample=False):
    if not re.fullmatch(r'[A-Za-z0-9]{3,32}',str(tid)):raise ValueError('Invalid Audius ID')
    # Only called after metadata grants public downloads. The stream endpoint
    # supplies the documented full MP3; /download may return a huge original WAV.
    headers,params=_auth();url=API+'/tracks/'+tid+'/stream'
    for hop in range(4):
        checkpoint()
        if hop and not _public_media_url(url):raise ValueError('Invalid Audius media host')
        _pace()
        # Never forward our bearer token or API key to a content node.
        h=headers if hop==0 else {'User-Agent':'SwiDJ/1.0'}
        if sample:h=dict(h,Range='bytes=0-8191')
        with requests.get(url,params=params if hop==0 else None,headers=h,allow_redirects=False,
                          stream=True,timeout=(4,12)) as response:
            _check_status(response)
            if response.status_code in (200,206):
                yield response
                return
            target=urljoin(url,response.headers.get('Location',''))
            if not target or target==url:raise ValueError('Invalid Audius media redirect')
            url=target
    raise ValueError('Too many Audius redirects')


def available(item):
    fresh=_metadata(item['url'])
    from recording_availability import _duration_ok, _media_bytes
    if not _duration_ok(item.get('duration'),fresh['duration']):return False
    with _media(fresh['_audius_id'],sample=True) as response:
        return _media_bytes(next(response.iter_content(8192),b''))


def download(url,directory,max_bytes=49*1024**2):
    item=_metadata(url)
    from app_limits import link_budget
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    budget=min(max_bytes or link_budget(directory),link_budget(directory))
    pending=directory/'audius.part';target=directory/'audius.mp3'
    try:
        total=0;deadline=time.monotonic()+180
        with _media(item['_audius_id']) as response, pending.open('wb') as stream:
            for chunk in response.iter_content(65536):
                checkpoint();total+=len(chunk)
                if total>budget or time.monotonic()>deadline:raise ValueError('Audius file budget')
                stream.write(chunk)
        if not total:raise ValueError('Empty Audius recording')
        probe=run_process(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=codec_name:format=duration','-of','json',str(pending)],timeout=15,check=True)
        data=json.loads(probe.stdout);duration=float(data['format']['duration'])
        from recording_availability import _duration_ok
        if not data.get('streams') or data['streams'][0].get('codec_name')!='mp3' or not _duration_ok(item['duration'],duration):raise ValueError('Incomplete Audius MP3')
        os.replace(pending,target)
        return str(target),dict(item,duration=duration,_public_source=True)
    except requests.RequestException:
        raise ValueError('Audius recording unavailable') from None
    finally:pending.unlink(missing_ok=True)


def matching_track(hint):
    from recording_match import identity,matches
    title,artist=identity(hint)
    if not title or not artist or type(hint.get('duration')) not in (int,float):return None
    rows=[row for row in search(artist+' '+title,8) if matches(hint,row)]
    return rows[0] if len(rows)==1 else None
