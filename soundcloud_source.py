"""Independent public SoundCloud search/download; no YouTube cookies or account."""
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import yt_dlp
from operations import checkpoint,run_process
from recording_match import matches

def public_url(value):
    try:
        p=urlsplit(str(value))
        return p.scheme=='https' and p.hostname in ('soundcloud.com','www.soundcloud.com') and not p.username and not p.password and p.port in (None,443) and not p.query and not p.fragment and bool(re.fullmatch(r'/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/?',p.path)) and not p.path.rstrip('/').split('/')[-1].startswith('s-')
    except ValueError:return False

class Quiet:
    def debug(self,*args):pass
    def warning(self,*args):pass
    def error(self,*args):pass

def options():
    return {'quiet':True,'no_warnings':True,'logger':Quiet(),'noplaylist':True,
            'socket_timeout':10,'retries':0,'extractor_retries':0,
            'allowed_extractors':['soundcloud.*'],'cookiefile':None,
            'progress_hooks':[lambda _:checkpoint()],'postprocessor_hooks':[lambda _:checkpoint()]}

def row(info):
    if not isinstance(info,dict):return None
    url=info.get('webpage_url') or info.get('url')
    if not public_url(url) or info.get('is_live') or info.get('availability') in ('private','premium_only','subscriber_only','needs_auth'):return None
    artists=info.get('artists')
    artist=info.get('artist') or (artists[0] if isinstance(artists,list) and len(artists)==1 else None) or info.get('uploader')
    duration=info.get('duration')
    if not artist or type(duration) not in (int,float) or not 0<duration<=7200:return None
    return {'url':url,'source_url':url,'source':'SoundCloud','title':str(info.get('track') or info.get('title') or '')[:180],
            'artist':str(artist)[:120],'duration':duration,'cover':None}

def search(query,limit=5):
    checkpoint()
    try:
        settings=dict(options(),skip_download=True,extract_flat='in_playlist')
        with yt_dlp.YoutubeDL(settings) as ydl:info=ydl.extract_info('scsearch'+str(min(10,limit))+':'+str(query)[:240],download=False)
        result=[];seen=set()
        for entry in (info or {}).get('entries') or []:
            checkpoint();item=row(entry)
            if item and item['url'] not in seen:seen.add(item['url']);result.append(item)
        return result[:limit]
    except Exception:return []

def matching_track(hint):
    from recording_match import identity
    title,artist=identity(hint)
    if not title or not artist or type(hint.get('duration')) not in (int,float):return None
    found=[item for item in search(artist+' '+title,8) if matches(hint,item)]
    if len(found)==1:return found[0]
    if len(found)>1:
        found.sort(key=lambda item:abs(item['duration']-hint['duration']))
        first=abs(found[0]['duration']-hint['duration']);second=abs(found[1]['duration']-hint['duration'])
        if first<=1 and second-first>.25:return found[0]
    return None

def download(item,directory,max_bytes=49*1024**2):
    url=item['url']
    if not public_url(url):raise ValueError('Invalid public recording')
    from app_limits import link_budget
    budget=min(max_bytes or link_budget(directory),link_budget(directory))
    settings=dict(options(),format='bestaudio[format_id!*=preview]/best[format_id!*=preview]',
        outtmpl=str(Path(directory)/'soundcloud.%(ext)s'),max_filesize=budget,
        postprocessors=[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}])
    with yt_dlp.YoutubeDL(settings) as ydl:info=ydl.extract_info(url,download=True)
    checkpoint();actual=row(info)
    if not actual or not matches(item,actual):raise ValueError('Recording identity changed')
    files=list(Path(directory).glob('soundcloud*.mp3'))
    if len(files)!=1 or files[0].is_symlink() or not 0<files[0].stat().st_size<=budget:raise ValueError('Invalid complete recording')
    probe=run_process(['ffprobe','-v','error','-select_streams','a:0','-show_entries','format=duration','-of','json',str(files[0])],timeout=15,check=True)
    duration=float(json.loads(probe.stdout)['format']['duration'])
    if not matches(item,dict(actual,duration=duration)):raise ValueError('Incomplete recording')
    return str(files[0]),dict(actual,duration=duration,_public_source=True)
