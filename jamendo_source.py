"""Read-only, optional Jamendo reserve. Download only permitted derivative-friendly tracks."""
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
import requests
from operations import checkpoint

API='https://api.jamendo.com/v3.0/tracks/'


def identifier(url):
    match=re.fullmatch(r'https://www\.jamendo\.com/track/(\d{1,12})(?:/[^?#]*)?',str(url))
    return match[1] if match else None


def license_url(value):
    match=re.fullmatch(r'https?://creativecommons\.org/(licenses/by/(?:3\.0|4\.0)|publicdomain/zero/1\.0)/?',str(value))
    return 'https://creativecommons.org/'+match[1]+'/' if match else None


def rows(params):
    client=os.getenv('JAMENDO_CLIENT_ID','').strip()
    if not client:return []
    parameters={'client_id':client,'format':'json','limit':10,'type':'single albumtrack','audioformat':'mp32','ccnd':'false','ccsa':'false','ccnc':'false',**params}
    if 'id' in params:
        for key in ('type','ccnd','ccsa','ccnc'):parameters.pop(key,None)
    checkpoint()
    with requests.get(API,params=parameters,stream=True,timeout=(5,15)) as response:
        response.raise_for_status();raw=bytearray()
        for chunk in response.iter_content(65536):
            checkpoint();raw.extend(chunk)
            if len(raw)>1024**2:raise ValueError('Catalog response too large')
    data=json.loads(raw)
    if data.get('headers',{}).get('status')!='success':raise ValueError('Catalog unavailable')
    return data.get('results',[]) if isinstance(data.get('results'),list) else []


def track(row):
    if not isinstance(row,dict):return None
    tid=str(row.get('id',''));license=license_url(row.get('license_ccurl'))
    if not tid.isdecimal() or len(tid)>12 or row.get('audiodownload_allowed') is not True or not license:return None
    title=str(row.get('name') or '').strip()[:180];artist=str(row.get('artist_name') or '').strip()[:120]
    duration=row.get('duration')
    if not title or not artist or type(duration) not in (int,float) or not 0<duration<=7200:return None
    return {'title':title,'artist':artist,'duration':round(duration),'url':'https://www.jamendo.com/track/'+tid,
            'source':'Jamendo','source_url':'https://www.jamendo.com/track/'+tid,'license_url':license,'cover':None}


def search(query,limit=5):
    try:
        result=[]
        for item in rows({'search':str(query)[:240],'limit':min(10,limit*2)}):
            value=track(item)
            if value:result.append(value)
            if len(result)>=limit:break
        return result
    except Exception:return []


def matching_track(hint):
    from recording_match import identity,matches
    title,artist=identity(hint)
    if not title or not artist or type(hint.get('duration')) not in (int,float):return None
    found=[item for item in search(artist+' '+title) if matches(hint,item)]
    return found[0] if len(found)==1 else None



def download(url,directory,max_bytes=49*1024**2):
    tid=identifier(url)
    if not tid:raise ValueError('Invalid catalog track')
    row=None
    for attempt in range(3):
        matches=rows({'id':tid})
        row=next((item for item in matches if str(item.get('id',''))==tid),None)
        if row:break
        if attempt<2:time.sleep(.4)
    info=track(row)
    if not info:raise ValueError('Track download is not permitted')
    remote=urlsplit(str(row.get('audiodownload') or ''))
    if remote.scheme!='https' or not (remote.hostname or '').endswith('.storage.jamendo.com') or remote.username or remote.password or remote.port not in (None,443):raise ValueError('Invalid catalog media')
    if not re.fullmatch(r'/download/track/'+tid+r'/[^/]+/?',remote.path):raise ValueError('Invalid catalog recording')
    from app_limits import link_budget
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    limit=min(max_bytes,link_budget(directory));target=directory/'jamendo.mp3';pending=directory/'jamendo.part'
    try:
        deadline=time.monotonic()+120;size=0
        with requests.get(remote.geturl(),stream=True,allow_redirects=False,timeout=(5,20)) as response:
            response.raise_for_status()
            if response.is_redirect:raise ValueError('Unexpected media redirect')
            with pending.open('wb') as out:
                for chunk in response.iter_content(65536):
                    checkpoint();size+=len(chunk)
                    if size>=limit or time.monotonic()>deadline:raise ValueError('Catalog media budget')
                    out.write(chunk)
        if not size:raise ValueError('Empty catalog file')
        os.replace(pending,target)
        return str(target),info
    finally:pending.unlink(missing_ok=True)
