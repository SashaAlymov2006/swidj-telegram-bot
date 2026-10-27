"""Opt-in external YouTube VIDEO reserve; no browser cookies or audio substitution."""
from contextlib import closing
import ipaddress
import json
import math
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import time
from urllib.parse import urlsplit, urljoin
import requests
from operations import checkpoint, run_process

API='https://api.jaky.dev/v1/download/youtube'
MEDIA_HOSTS={'dl1.ezsrv.net','dl2.ezsrv.net'}
USER_AGENT='SwiDJ-video-reserve/1.0'


class VideoPath(str):
    quality_limit=720


def output_path(path,metadata):
    return VideoPath(path) if metadata.get('video_quality_limit')==720 else str(path)


def enabled():
    return os.getenv('YOUTUBE_VIDEO_RESERVE_ENABLED','false').lower()=='true' and bool(os.getenv('JAKY_API_KEY','').strip())


def _database():
    path=Path(os.getenv('STATE_DB_PATH','data/state.sqlite3')).parent/'video_reserve.sqlite3'
    path.parent.mkdir(parents=True,exist_ok=True)
    return sqlite3.connect(path,timeout=5)


def _claim():
    """One shared in-flight request and at most 90 calls/day across worker processes."""
    now=time.time();day=time.strftime('%Y-%m-%d',time.gmtime(now+7*3600));token=secrets.token_hex(12)
    with closing(_database()) as db,db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS quota (id INTEGER PRIMARY KEY, day TEXT, used INTEGER, lease TEXT, until REAL, blocked REAL)')
        db.execute('INSERT OR IGNORE INTO quota VALUES (1,?,0,"",0,0)',(day,))
        old,used,lease,until,blocked=db.execute('SELECT day,used,lease,until,blocked FROM quota WHERE id=1').fetchone()
        used=used if old==day else 0
        if used>=90 or now<blocked or now<until:raise ValueError('Video reserve temporarily unavailable')
        db.execute('UPDATE quota SET day=?,used=?,lease=?,until=? WHERE id=1',(day,used+1,token,now+180))
    return token


def _finish(token,cooldown):
    with closing(_database()) as db,db:
        db.execute('UPDATE quota SET lease="",until=0,blocked=? WHERE id=1 AND lease=?',(time.time()+cooldown,token))


def _json(response):
    if response.status_code!=200:raise ValueError('Video reserve request failed')
    data=bytearray()
    for block in response.iter_content(16384):
        checkpoint();data.extend(block)
        if len(data)>256*1024:raise ValueError('Video reserve response too large')
    result=json.loads(data)
    if not isinstance(result,dict) or result.get('status') is not True or not isinstance(result.get('result'),dict):
        raise ValueError('Video reserve has no result')
    return result['result']


def _media_url(url):
    p=urlsplit(str(url))
    if p.scheme!='https' or p.hostname not in MEDIA_HOSTS or p.username or p.password or p.port not in (None,443):
        raise ValueError('Unexpected video reserve media host')
    addresses=socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('Non-public video reserve media host')
    return str(url)


def download(url,height,directory,max_bytes):
    """Only called AFTER primary extraction fails; 1080p falls back to a marked 720p."""
    from download_cache import source_key
    source=source_key(url)
    if not enabled() or not source or not source.startswith('youtube:') or height not in (0,144,240,360,480,720,1080):
        raise ValueError('Video reserve unavailable')
    height=min(height or 720,720)
    canonical='https://www.youtube.com/watch?v='+source.split(':',1)[1]
    token=_claim();cooldown=60;folder=Path(directory);folder.mkdir(parents=True,exist_ok=True)
    partial=folder/'reserve.mp4.part';target=folder/'reserve.mp4';started=time.monotonic()
    try:
        checkpoint()
        with requests.get(API,params={'url':canonical,'format':'mp4','quality':height or 720},
                          headers={'x-jaky-key':os.environ['JAKY_API_KEY'],'User-Agent':USER_AGENT},
                          timeout=(5,45),stream=True,allow_redirects=False) as response:
            if response.status_code==429:cooldown=3600
            metadata=_json(response)
        if metadata.get('format')!='mp4':raise ValueError('Unexpected reserve format')
        link=_media_url(metadata.get('downloadUrl'));count=0
        for hop in range(4):
            checkpoint()
            with requests.get(link,headers={'User-Agent':USER_AGENT},timeout=(5,15),stream=True,allow_redirects=False) as response:
                if response.status_code in (301,302,303,307,308):
                    link=_media_url(urljoin(link,response.headers.get('Location','')));continue
                if response.status_code!=200:raise ValueError('Video reserve file unavailable')
                length=response.headers.get('Content-Length')
                if length and int(length)>max_bytes:raise ValueError('Video reserve file too large')
                with partial.open('wb') as output:
                    for block in response.iter_content(65536):
                        checkpoint();count+=len(block)
                        if count>max_bytes or time.monotonic()-started>140:raise ValueError('Video reserve download budget exceeded')
                        output.write(block)
                break
        else:raise ValueError('Too many video reserve redirects')
        if count==0:raise ValueError('Empty video reserve file')
        result=run_process(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','mov',
                            '-show_entries','format=duration:stream=codec_type,codec_name,width,height','-of','json',str(partial)],timeout=10,check=True)
        info=json.loads(result.stdout);streams=info.get('streams',[]);duration=float(info.get('format',{}).get('duration',0))
        videos=[s for s in streams if s.get('codec_type')=='video'];audios=[s for s in streams if s.get('codec_type')=='audio']
        if not videos or not audios or not math.isfinite(duration) or duration<=0:raise ValueError('Incomplete video reserve file')
        if videos[0].get('codec_name')!='h264' or audios[0].get('codec_name')!='aac':raise ValueError('Unsupported reserve codecs')
        if not 0<min(videos[0].get('width',0),videos[0].get('height',0))<=(height or 720):raise ValueError('Unexpected reserve resolution')
        partial.replace(target);cooldown=0
        return {'path':str(target),'kind':'video','title':str(metadata.get('title') or 'YouTube')[:180],
                'artist':'','duration':duration,'source_url':canonical,'_video_reserve':'jaky','_public_source':False,'video_quality_limit':720}
    finally:
        partial.unlink(missing_ok=True)
        _finish(token,cooldown)
