"""Conservative, optional timed lyrics. Never uploads audio or Telegram identity."""
import asyncio,json,math,re,time,unicodedata
import aiohttp

def source_metadata(value):
    if not isinstance(value,dict):return None
    if value.get('disabled') is True:return {'disabled':True}
    title=value.get('title');artist=value.get('artist');duration=value.get('duration');speed=value.get('speed',1);start=value.get('start',0)
    if not all(isinstance(v,str) and 0<len(v.strip())<=limit and not any(ord(c)<32 for c in v) for v,limit in ((title,180),(artist,120))):return None
    if not all(type(v) in (int,float) and math.isfinite(v) and low<=v<=high for v,low,high in ((duration,1,86400),(speed,.5,2),(start,0,86400))):return None
    end=value.get('end',duration)
    if type(end) not in (int,float) or not math.isfinite(end) or not start<end<=duration:return None
    title=re.sub(r'\((?:official(?: music)? (?:video|audio)|lyrics?|lyric video)\)|\[(?:official(?: music)? (?:video|audio)|lyrics?|lyric video)\]','',title,flags=re.I).strip()
    artist=re.sub(r'\s*-\s*Topic$','',artist,flags=re.I).strip()
    for delimiter in re.finditer(r'\s*[-–—]\s*',title):
        if norm(title[:delimiter.start()])==norm(artist):title=title[delimiter.end():];break
    return {'title':title,'artist':artist,'duration':duration,'speed':speed,'start':start,'end':end}

def norm(text):return ''.join(c for c in unicodedata.normalize('NFKC',str(text)).casefold() if c.isalnum())

def parse_lrc(value,duration):
    if not isinstance(value,str) or len(value)>64000:return []
    # Nonzero offsets have inconsistent producer semantics; don't silently guess.
    offsets=re.findall(r'\[offset:([+-]?\d+)\]',value,re.I)
    if any(int(v)!=0 for v in offsets):return []
    rows={};raw_lines=value.splitlines()
    if len(raw_lines)>1000:return []
    for line in raw_lines:
        stamps=list(re.finditer(r'\[(\d{1,3}):([0-5]\d)(?:[.:](\d{1,3}))?\]',line))
        if not stamps:continue
        text=line[stamps[-1].end():].strip();text=re.sub(r'<\d+:\d+(?:\.\d+)?>','',text)
        text=' '.join(re.sub(r'[\x00-\x1f]','',text).split()).encode('utf-8',errors='replace').decode('utf-8')[:240]
        for stamp in stamps:
            at=int(stamp[1])*60+int(stamp[2])+int(stamp[3] or '0')/(10**len(stamp[3] or '0'))
            if 0<=at<=duration+3:rows.setdefault(round(at,3),text)
            if len(rows)>600:return []
    items=[{'at':at,'text':text} for at,text in sorted(rows.items())]
    return items if sum(bool(item['text']) for item in items)>=2 else []

def recording(record,source):
    if not isinstance(record,dict) or record.get('instrumental') is True:return None
    duration=record.get('duration')
    if norm(record.get('trackName'))!=norm(source['title']) or norm(record.get('artistName'))!=norm(source['artist']):return None
    if type(duration) not in (int,float) or not math.isfinite(duration) or abs(duration-source['duration'])>3:return None
    lines=parse_lrc(record.get('syncedLyrics'),duration)
    if not lines:return None
    identifier=record.get('id');url='https://lrclib.net/api/get/'+str(identifier) if type(identifier) is int and identifier>0 else 'https://lrclib.net/'
    return {'lines':lines,'title':source['title'],'artist':source['artist'],'source':'LRCLIB','source_url':url}

class TimedLyrics:
    def __init__(self):self.cache={};self.lock=asyncio.Lock()
    async def lookup(self,source):
        if not source or source.get('disabled'):return None
        key=(source['title'],source['artist'],round(source['duration']))
        found=self.cache.get(key)
        if found and found[0]>time.monotonic():return found[1]
        async with self.lock:
            found=self.cache.get(key)
            if found and found[0]>time.monotonic():return found[1]
            result=None
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=7),headers={'User-Agent':'SwiDJ/1.0 (https://github.com/SashaAlymov2006/swidj-telegram-bot)'}) as client:
                for path,params in [('get',{'track_name':source['title'],'artist_name':source['artist'],'duration':round(source['duration'])}),('search',{'track_name':source['title'],'artist_name':source['artist']})]:
                    try:
                        async with client.get('https://lrclib.net/api/'+path,params=params,allow_redirects=False) as response:
                            if response.status==429:break
                            if response.status!=200:continue
                            body=bytearray()
                            async for block in response.content.iter_chunked(65536):
                                body.extend(block)
                                if len(body)>1024**2:raise ValueError('Lyrics response too large')
                            data=json.loads(body)
                        records=data[:30] if isinstance(data,list) else [data]
                        result=next((value for item in records if (value:=recording(item,source))),None)
                        if result:break
                    except (aiohttp.ClientError,TimeoutError,ValueError):continue
            while len(self.cache)>=64:self.cache.pop(next(iter(self.cache)))
            self.cache[key]=(time.monotonic()+(3600 if result else 120),result)
            return result

def mapped(record,source):
    return dict(record,lines=[dict(line,at=round((line['at']-source['start'])/source['speed'],3)) for line in record['lines']])
