"""Public TikTok photo posts: images plus original soundtrack, without account access."""
import asyncio
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import urlsplit,urlunsplit,urljoin
import requests
from bs4 import BeautifulSoup
from operations import checkpoint

HOSTS={'www.tiktok.com','tiktok.com','m.tiktok.com','vm.tiktok.com','vt.tiktok.com'}
PHOTO=re.compile(r'/(@[^/]+)/photo/(\d+)/?')
CDNS=('tiktokcdn.com','tiktokcdn-eu.com','tiktokcdn-us.com','tiktokv.com','byteoversea.com','ibytedtos.com','musical.ly')


def checked_url(url,media=False):
    p=urlsplit(url);host=(p.hostname or '').lower()
    allowed=any(host==domain or host.endswith('.'+domain) for domain in CDNS) if media else host in HOSTS
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or not allowed:raise ValueError('Invalid TikTok resource')
    return p


def photo_url(url):
    for _ in range(4):
        p=checked_url(url);match=PHOTO.fullmatch(p.path)
        if match:return urlunsplit((p.scheme,p.netloc,p.path,'','')),match
        with requests.get(url,stream=True,allow_redirects=False,timeout=(5,12)) as response:
            response.raise_for_status()
            if not response.is_redirect:return None
            url=urljoin(url,response.headers.get('Location',''))
    return None


def parse_post(html,post_id):
    soup=BeautifulSoup(html,'html.parser');script=soup.find('script',id='__UNIVERSAL_DATA_FOR_REHYDRATION__')
    if not script:raise ValueError('Photo post data unavailable')
    data=json.loads(script.string or script.get_text())
    detail=data.get('__DEFAULT_SCOPE__',{}).get('webapp.video-detail',{})
    item=detail.get('itemInfo',{}).get('itemStruct',{})
    if detail.get('statusCode')!=0 or str(item.get('id'))!=str(post_id):raise ValueError('Photo post data unavailable')
    images=(item.get('imagePost') or {}).get('images',[])
    if not isinstance(images,list) or not 1<=len(images)<=35:raise ValueError('Photo post data unavailable')
    files=[]
    for image in images:
        urls=(image.get('imageURL') or image.get('displayImage') or {}).get('urlList',[])
        allowed=[]
        for url in urls:
            try:checked_url(url,True);allowed.append(url)
            except (ValueError,TypeError):pass
        if not allowed:raise ValueError('Photo resource unavailable')
        files.append(allowed[0])
    music=item.get('music') or {};audio=music.get('playUrl')
    if audio:checked_url(audio,True)
    return {'images':files,'audio':audio,'title':str(item.get('desc') or 'TikTok')[:180],
            'artist':str((item.get('author') or {}).get('nickname') or '')[:120],
            'width':images[0].get('imageWidth',720),'height':images[0].get('imageHeight',1280)}


def download_resource(url,target,limit,media=True):
    checked_url(url,media);total=0;deadline=time.monotonic()+60
    try:
        with requests.get(url,stream=True,allow_redirects=False,timeout=(5,20)) as response:
            response.raise_for_status()
            if response.is_redirect:raise ValueError('Unexpected resource redirect')
            with Path(target).open('wb') as out:
                for chunk in response.iter_content(65536):
                    checkpoint();total+=len(chunk)
                    if total>limit or time.monotonic()>deadline:raise ValueError('Photo resource too large')
                    out.write(chunk)
        if not total:raise ValueError('Empty photo resource')
        return total
    except BaseException:
        Path(target).unlink(missing_ok=True);raise


def download(url,directory,mode='video',height=720,max_bytes=256*1024**2):
    resolved=photo_url(url)
    if not resolved:return None
    canonical,match=resolved
    # The public /video/ route exposes the same post's structured photo metadata.
    page=canonical.replace('/photo/','/video/',1)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    html=directory/'post.html'
    download_resource(page,html,2*1024**2,False)
    try:post=parse_post(html.read_text(encoding='utf-8'),match[2])
    finally:html.unlink(missing_ok=True)
    from app_limits import link_budget
    from miniapp_studio import process,probe
    workspace_budget=min(1024**3,link_budget(directory))
    budget=min(max_bytes,workspace_budget);used=0
    audio=None;audio_duration=0
    if post['audio']:
        audio=directory/'soundtrack.mp3'
        used+=download_resource(post['audio'],audio,min(32*1024**2,workspace_budget))
        audio_duration=asyncio.run(probe(audio))
    if mode=='audio':
        if not audio:raise ValueError('This photo post has no soundtrack')
        target=directory/'photos.mp3'
        asyncio.run(process(['ffmpeg','-nostdin','-v','error','-y','-threads','2','-protocol_whitelist','file,pipe',
            '-i',str(audio),'-vn','-c:a','libmp3lame','-b:a','192k','-fs',str(budget),str(target)],180))
        if not 0<target.stat().st_size<budget:raise ValueError('Photo soundtrack budget reached')
        return {'path':str(target),'title':post['title'],'artist':post['artist'],'duration':audio_duration}
    w,h=post['width'],post['height']
    if type(w) not in (int,float) or type(h) not in (int,float) or not all(math.isfinite(x) and 0<x<=20000 for x in (w,h)):w,h=720,1280
    scale=min(1,round((height or 1080)*16/9)/max(w,h));w=max(2,int(w*scale)//2*2);h=max(2,int(h*scale)//2*2)
    frame_filter=f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1'
    paths=[]
    for index,url in enumerate(post['images']):
        raw=directory/f'photo-{index:02d}.image'
        used+=download_resource(url,raw,min(20*1024**2,workspace_budget-used))
        path=directory/f'slide-{index:02d}.png'
        asyncio.run(process(['ffmpeg','-nostdin','-v','error','-y','-threads','2','-protocol_whitelist','file,pipe',
            '-i',str(raw),'-frames:v','1','-vf',frame_filter,'-threads','1',str(path)],30))
        used+=path.stat().st_size
        if used>=workspace_budget:raise ValueError('Photo resource budget reached')
        paths.append(path)
    duration=max(len(paths)*3,min(audio_duration,180))
    step=duration/len(paths)
    target=directory/'photos.mp4'
    command=['ffmpeg','-nostdin','-v','error','-y','-threads','2','-protocol_whitelist','file,pipe',
             '-framerate',str(1/step),'-start_number','0','-i',str(directory/'slide-%02d.png')]
    if audio:command+=['-stream_loop','-1','-i',str(audio)]
    command+=['-map','0:v:0']
    if audio:command+=['-map','1:a:0']
    command+=['-vf',f'tpad=stop_mode=clone:stop_duration={step}',
              '-r','25','-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k',
              '-t',str(duration),'-movflags','+faststart','-threads','2','-fs',str(budget),str(target)]
    asyncio.run(process(command,600))
    if not 0<target.stat().st_size<budget:raise ValueError('Photo video budget reached')
    return {'path':str(target),'title':post['title'],'artist':post['artist'],'duration':duration}
