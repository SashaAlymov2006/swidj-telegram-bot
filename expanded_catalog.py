"""Independent public release catalogs. No audio previews or account mutations."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from copy import deepcopy
import hashlib
import json
import os
import re
import threading
import time
import requests
from operations import checkpoint

UUID=r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
_cache={};_lock=threading.Lock();_mb_lock=threading.Lock();_mb_at=0.0
_known={}
_pending={}


def cached(key,fn):
    with _lock:
        known=_cache.get(key)
        if known and known[0]>time.monotonic():return deepcopy(known[1])
        event=_pending.get(key);leader=event is None
        if leader:event=_pending.setdefault(key,threading.Event())
    if not leader:
        for _ in range(300):
            checkpoint()
            if event.wait(.2):break
        else:raise TimeoutError('Catalog wait')
        with _lock:known=_cache.get(key)
        if known:return deepcopy(known[1])
        raise ValueError('Catalog unavailable')
    try:
        value=fn()
        with _lock:
            while len(_cache)>=256:_cache.pop(next(iter(_cache)))
            _cache[key]=(time.monotonic()+1800,deepcopy(value))
        return value
    finally:
        with _lock:_pending.pop(key,None)
        event.set()


def mb(path,**params):
    def fetch():
        global _mb_at
        with _mb_lock:
            for attempt in range(2):
                while time.monotonic()<_mb_at:checkpoint();time.sleep(.1)
                _mb_at=time.monotonic()+1.1
                try:return get_json('https://musicbrainz.org/ws/2/'+path,dict(fmt='json',**params),
                                    {'User-Agent':'SwiDJ/1.0 (https://github.com/SashaAlymov2006/swidj-telegram-bot)'})
                except requests.HTTPError as error:
                    if attempt or error.response is None or error.response.status_code not in (429,503):raise
                    _mb_at=time.monotonic()+2.2
    return cached(('mb',path,tuple(sorted(params.items()))),fetch)


def get_json(url,params,headers=None):
    with requests.get(url,params=params,headers=headers or {},timeout=(4,10),stream=True,allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code!=200:raise ValueError('Catalog redirect')
        body=bytearray()
        for part in response.iter_content(65536):
            checkpoint();body.extend(part)
            if len(body)>3*1024**2:raise ValueError('Catalog size')
    return json.loads(body)


def identity(name):
    from artist_catalog import normalized
    def find():
        escaped=re.sub(r'([\\"+!():{}\[\]^~*?])',r'\\\1',name[:120])
        rows=mb('artist',query='artist:"'+escaped+'" OR alias:"'+escaped+'"',limit=12).get('artists',[])
        exact=[r for r in rows if normalized(r.get('name'))==normalized(name)]
        candidates=exact+[r for r in rows if any(normalized(a.get('name'))==normalized(name) for a in (r.get('aliases') or []))]
        unique={r.get('id'):r for r in candidates if re.fullmatch(UUID,str(r.get('id','')))}
        if len(unique)!=1:return None
        item=next(iter(unique.values()))
        detail=mb('artist/'+item['id'],inc='aliases')
        names=[name,item['name']]+[a.get('name','') for a in (detail.get('aliases') or []) if a.get('locale') in ('en',None) and a.get('type') in ('Artist name','Legal name')]
        seen=set();aliases=[]
        for value in names:
            key=normalized(value)
            if key and key not in seen and 1<len(value)<=120:seen.add(key);aliases.append(value)
        return {'id':item['id'],'name':item['name'],'aliases':aliases[:8]}
    item=cached(('identity',name),find)
    if item:
        with _lock:
            for alias in item['aliases']:
                key=normalized(alias);old=_known.get(key)
                if old and old['id']!=item['id']:_known[key]=None
                elif key not in _known or old is not None:_known[key]=item
            while len(_known)>512:_known.pop(next(iter(_known)))
    return item


def known_names(name):
    from artist_catalog import normalized
    with _lock:item=_known.get(normalized(name))
    return list(item['aliases']) if item else [name]


def browse_names(song):
    from artist_catalog import creator,normalized
    name=creator(song);aliases=song.get('_artist_aliases') or known_names(name)
    others=[a for a in aliases if isinstance(a,str) and 1<len(a)<=120 and normalized(a)!=normalized(name)]
    return [name]+list(dict.fromkeys(others))[:1]


def names(name):
    try:item=identity(name)
    except Exception:return [name]
    return item['aliases'] if item else [name]


def credit_matches(name,credit):
    from artist_catalog import normalized
    if normalized(name)==normalized(credit):return True
    allowed={normalized(n) for n in names(name)}
    parts=[credit]+re.split(r'\s*(?:,|&|\bfeat\.?|\bwith\b|\band\b)\s*',str(credit),flags=re.I)
    return any(normalized(p) in allowed for p in parts)


def _mb_releases(song):
    from artist_catalog import creator
    item={'id':song['_mb_artist_id'],'name':creator(song)} if re.fullmatch(UUID,str(song.get('_mb_artist_id',''))) else identity(creator(song))
    if not item:return []
    rows=[]
    for offset in (0,100):
        data=mb('release-group',artist=item['id'],limit=100,offset=offset,inc='artist-credits',**{'release-group-status':'website-default'})
        rows.extend(data.get('release-groups',[]))
        if offset+100>=data.get('release-group-count',0):break
    result=[]
    for row in rows:
        rid=row.get('id','');kind=str(row.get('primary-type','')).lower()
        if not re.fullmatch(UUID,rid) or kind not in ('album','single','ep'):continue
        result.append({'id':'mb-'+rid,'artist_id':'mb-'+item['id'],'artist':item['name'],'title':str(row.get('title',''))[:180],
                       'kind':kind,'cover':'','source':'MusicBrainz','source_url':'https://musicbrainz.org/release-group/'+rid,
                       'release_date':str(row.get('first-release-date',''))[:10],'track_count':None})
    return result


def jam(path,**params):
    key=os.getenv('JAMENDO_CLIENT_ID','').strip()
    if not key:return []
    def fetch():
        data=get_json('https://api.jamendo.com/v3.0/'+path+'/',dict(client_id=key,format='json',**params))
        if data.get('headers',{}).get('status')!='success':raise ValueError('Jamendo catalog unavailable')
        return data.get('results',[])
    return cached(('jam',path,tuple(sorted(params.items()))),fetch)


def _jam_releases(song):
    from artist_catalog import creator,normalized
    name=creator(song);params={'artist_id':song['_jam_artist_id']} if song.get('_jam_artist_id') else {'artist_name':name}
    rows=jam('albums',limit=100,type='album single',**params);result=[]
    for row in rows:
        rid=str(row.get('id',''))
        if not rid.isdecimal() or normalized(row.get('artist_name'))!=normalized(name):continue
        result.append({'id':'jam-'+rid,'artist_id':'jam-'+str(row.get('artist_id')),'artist':row['artist_name'],
                       'title':str(row.get('name',''))[:180],'kind':'album','cover':'','source':'Jamendo',
                       'source_url':'https://www.jamendo.com/list/a'+rid,'release_date':str(row.get('releasedate',''))[:10],'track_count':None})
    if len({r['artist_id'] for r in result})>1:return []
    return result


def _aud_releases(song):
    from artist_catalog import creator,normalized
    from audius_source import enabled,api
    if not enabled():return []
    name=creator(song)
    def find():
        def user_albums(uid,user):
            result=[]
            for offset in range(0,100,20):
                rows=api('/users/'+uid+'/albums',{'limit':20,'offset':offset}) or []
                result.extend(dict(row,user=row.get('user') or user) for row in rows)
                if len(rows)<20:break
            return result
        if song.get('_audius_user_id'):
            return user_albums(song['_audius_user_id'],{'id':song['_audius_user_id'],'name':name})
        rows=[]
        users=api('/users/search',{'query':name,'limit':10}) or []
        matched=[u for u in users if normalized(u.get('name'))==normalized(name)]
        if len(matched)>1:
            verified=[u for u in matched if u.get('is_verified')]
            if len(verified)!=1:return []
            matched=verified
        for user in matched:
            uid=str(user.get('id',''))
            if normalized(user.get('name'))==normalized(name) and re.fullmatch(r'[A-Za-z0-9]{1,20}',uid):
                rows.extend(user_albums(uid,user))
        if not matched:rows=list(api('/playlists/search',{'query':name,'limit':10}) or [])
        return list({row['id']:row for row in rows if row.get('id')}.values())
    rows=cached(('aud-albums',name,song.get('_audius_user_id')),find)
    result=[]
    for row in rows:
        user=row.get('user') or {};rid=str(row.get('id',''))
        if row.get('is_album') is not True or row.get('is_private') or row.get('is_delete') or row.get('is_stream_gated') or normalized(user.get('name'))!=normalized(name) or not re.fullmatch(r'[A-Za-z0-9]{1,20}',rid):continue
        path=str(row.get('permalink',''))
        if not path.startswith('/') or '?' in path:continue
        result.append({'id':'aud-'+rid,'artist_id':'aud-'+str(user.get('id')),'artist':user['name'],
                       'title':str(row.get('playlist_name',''))[:180],'kind':'album','cover':'','source':'Audius',
                       'source_url':'https://audius.co'+path,'release_date':str(row.get('release_date') or row.get('created_at') or '')[:10],
                       'track_count':row.get('track_count')})
    if len({r['artist_id'] for r in result})>1:return []
    return result


def collect(song):
    result=[]
    sources={'mb':_mb_releases,'jam':_jam_releases,'aud':_aud_releases}
    providers=(sources[song['_catalog_scope']],) if song.get('_catalog_scope') in sources else tuple(sources.values())
    with ThreadPoolExecutor(max_workers=3,thread_name_prefix='release-catalog') as pool:
        tasks=[pool.submit(copy_context().run,fn,song) for fn in providers]
        for task in tasks:
            try:result.extend(task.result())
            except Exception:checkpoint()
    return result


def _track(title,artist,url,album_title,number,duration=None,disc=1,**extra):
    return dict(id=10**15+int.from_bytes(hashlib.sha256(url.encode()).digest()[:6],'big'),title=title[:180],artist=artist[:120],url=url,
                album=album_title,track_number=number,disc_number=disc,duration=duration,_catalog_song={'title':title,'artist':artist},**extra)


def album(song,identifier):
    from artist_catalog import creator
    tracks=[]
    if re.fullmatch('mb-'+UUID,identifier):
        group=mb('release-group/'+identifier[3:],inc='releases+artists')
        credits=[c.get('artist',{}).get('name','') for c in group.get('artist-credit',[]) if isinstance(c,dict)]
        ids=[c.get('artist',{}).get('id','') for c in group.get('artist-credit',[]) if isinstance(c,dict)]
        if song.get('_mb_artist_id'):
            if song['_mb_artist_id'] not in ids:raise ValueError('Foreign release artist')
        elif not any(credit_matches(creator(song),c) for c in credits):raise ValueError('Foreign release artist')
        choices=sorted(group.get('releases',[]),key=lambda r:(r.get('status')!='Official',r.get('country') not in ('DE','US','GB'),r.get('date','')))
        for candidate in choices[:3]:
            rid=candidate.get('id','')
            if not re.fullmatch(UUID,rid):continue
            release=mb('release/'+rid,inc='recordings+artist-credits')
            for medium in release.get('media',[]):
                for row in medium.get('tracks',[]):
                    record=row.get('recording') or {};tid=record.get('id','')
                    if not re.fullmatch(UUID,tid):continue
                    artist=''.join(c.get('name','')+c.get('joinphrase','') for c in row.get('artist-credit',release.get('artist-credit',[])) if isinstance(c,dict)) or creator(song)
                    tracks.append(_track(str(row.get('title') or record.get('title') or ''),artist,'https://musicbrainz.org/recording/'+tid,
                                         group['title'],int(row.get('position') or 1),round(row['length']/1000) if type(row.get('length')) is int else None,int(medium.get('position') or 1)))
            if tracks:break
        header={'id':identifier,'title':group['title'],'artist':creator(song),'source':'MusicBrainz','source_url':'https://musicbrainz.org/release-group/'+identifier[3:],'cover':''}
    elif re.fullmatch(r'jam-\d{1,12}',identifier):
        data=jam('albums/tracks',id=identifier[4:],limit=1)
        if not data or not credit_matches(creator(song),data[0].get('artist_name','')):raise ValueError('Foreign release artist')
        row=data[0];header={'id':identifier,'title':row['name'],'artist':row['artist_name'],'source':'Jamendo','source_url':'https://www.jamendo.com/list/a'+identifier[4:],'cover':''}
        from jamendo_source import track
        for index,raw in enumerate(row.get('tracks',[]),1):
            value=track(dict(raw,artist_name=row['artist_name'],album_name=row['name']))
            if value:tracks.append(dict(value,id=10**15+int.from_bytes(hashlib.sha256(value['url'].encode()).digest()[:6],'big'),track_number=int(raw.get('position') or index),disc_number=1))
            elif str(raw.get('id','')).isdecimal() and raw.get('name'):
                tracks.append(_track(str(raw['name']),row['artist_name'],'https://www.jamendo.com/track/'+str(raw['id']),row['name'],int(raw.get('position') or index),raw.get('duration')))
    elif re.fullmatch(r'aud-[A-Za-z0-9]{1,20}',identifier):
        from audius_source import api,track
        rows=cached(('aud-album',identifier),lambda:api('/playlists/'+identifier[4:]) or [])
        row=rows[0] if isinstance(rows,list) and rows else rows
        if not row or row.get('is_album') is not True or row.get('is_private') or row.get('is_delete') or row.get('is_stream_gated') or not credit_matches(creator(song),row.get('user',{}).get('name','')):raise ValueError('Foreign release artist')
        header={'id':identifier,'title':row['playlist_name'],'artist':row['user']['name'],'source':'Audius','source_url':'https://audius.co'+row['permalink'],'cover':''}
        def read_tracks():
            result=[]
            for offset in range(0,200,20):
                rows=api('/playlists/'+identifier[4:]+'/tracks',{'limit':20,'offset':offset}) or []
                result.extend(rows)
                if len(rows)<20:break
            return result
        raw=cached(('aud-album-tracks',identifier),read_tracks)
        for index,r in enumerate(raw,1):
            value=track(r)
            if value:tracks.append(dict(value,id=10**15+int.from_bytes(hashlib.sha256(value['url'].encode()).digest()[:6],'big'),track_number=index,disc_number=1,album=header['title']))
            elif r.get('title') and not r.get('is_unlisted') and not r.get('is_delete'):
                from audius_source import canonical
                path=r.get('permalink','');url=canonical('https://audius.co'+path if path.startswith('/') else path)
                if url:tracks.append(_track(str(r['title']),str((r.get('user') or {}).get('name') or header['artist']),url,header['title'],index,r.get('duration')))
    else:raise ValueError('Invalid catalog album')
    if not tracks:raise ValueError('Album tracks unavailable')
    return {'name':creator(song),'album':header,'tracks':tracks,'source':header['source']}


def discover(query):
    """Artist entities, not guessed performers extracted from video titles."""
    from artist_catalog import normalized
    from release_catalog import _request,_link
    def apple():
        result=[]
        for row in _request('search',{'term':query,'entity':'musicArtist','limit':15}):
            name=str(row.get('artistName') or '').strip()[:120];url=_link(row.get('artistLinkUrl') or row.get('artistViewUrl'))
            if name and url:result.append({'name':name,'url':url,'source':'Apple Music','description':str(row.get('primaryGenreName') or '')[:100]})
        return result
    def brainz():
        escaped=re.sub(r'([\\"+!():{}\[\]^~*?])',r'\\\1',query[:120]);result=[]
        for row in mb('artist',query=escaped,limit=12).get('artists',[]):
            rid=row.get('id','');name=str(row.get('name') or '')[:120]
            if not re.fullmatch(UUID,rid) or not name or int(row.get('score') or 0)<70:continue
            aliases=[name]+[a.get('name','') for a in (row.get('aliases') or []) if a.get('locale') in ('en',None) and a.get('type') in ('Artist name','Legal name')]
            result.append({'name':name,'url':'https://musicbrainz.org/artist/'+rid,'source':'MusicBrainz',
                           'description':str(row.get('disambiguation') or row.get('country') or '')[:120],
                           '_mb_artist_id':rid,'_artist_aliases':list(dict.fromkeys(aliases))[:8]})
        return result
    def audius():
        from audius_source import enabled,api
        if not enabled():return []
        result=[]
        for user in cached(('aud-users',query),lambda:api('/users/search',{'query':query,'limit':10}) or []):
            uid=str(user.get('id',''));handle=str(user.get('handle',''));name=str(user.get('name',''))[:120]
            if not re.fullmatch(r'[A-Za-z0-9]{1,20}',uid) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',handle) or not name or user.get('is_deactivated'):continue
            result.append({'name':name,'url':'https://audius.co/'+handle,'source':'Audius','description':'@'+handle,
                           '_audius_user_id':uid,'_catalog_scope':'aud'})
        return result
    def jamendo():
        result=[]
        for row in jam('artists',namesearch=query,limit=10):
            aid=str(row.get('id',''));name=str(row.get('name',''))[:120]
            if aid.isdecimal() and name:result.append({'name':name,'url':'https://www.jamendo.com/artist/'+aid,'source':'Jamendo','description':'Jamendo',
                                                       '_jam_artist_id':aid,'_catalog_scope':'jam'})
        return result
    candidates=[]
    with ThreadPoolExecutor(max_workers=4,thread_name_prefix='artist-discovery') as pool:
        tasks=[pool.submit(copy_context().run,fn) for fn in (brainz,apple,audius,jamendo)]
        for task in tasks:
            try:candidates.extend(task.result())
            except Exception:checkpoint()
    # Only collapse a name when MusicBrainz has a single matching entity.
    brainz_rows=[r for r in candidates if r['source']=='MusicBrainz'];result=[]
    for item in candidates:
        if item['source']=='Apple Music':
            matching=[r for r in brainz_rows if normalized(item['name']) in {normalized(a) for a in r['_artist_aliases']}]
            if len(matching)==1:continue
        item=dict(item,id=10**15+int.from_bytes(hashlib.sha256(item['url'].encode()).digest()[:6],'big'),
                  title=item['name'],artist=item['name'],kind='artist')
        result.append(item)
    result.sort(key=lambda r:normalized(query) not in {normalized(a) for a in [r['name']]+r.get('_artist_aliases',[])})
    return result[:12]


def search_albums(query):
    from release_catalog import _request,release
    result=[]
    def apple():
        return [dict(item,source='Apple Music') for row in _request('search',{'term':query,'entity':'album','limit':30}) if (item:=release(row))]
    def brainz():
        escaped=re.sub(r'([\\"+!():{}\[\]^~*?])',r'\\\1',query[:120]);items=[]
        for row in mb('release-group',query=escaped,limit=20).get('release-groups',[]):
            rid=row.get('id','');kind=str(row.get('primary-type','')).lower()
            credit=next((c.get('artist',{}) for c in row.get('artist-credit',[]) if isinstance(c,dict)),{})
            aid=credit.get('id','');name=credit.get('name','')
            if kind not in ('album','single','ep') or not re.fullmatch(UUID,rid) or not re.fullmatch(UUID,aid) or not name:continue
            items.append({'id':'mb-'+rid,'title':str(row.get('title',''))[:180],'artist':name,'artist_id':'mb-'+aid,
                          'kind':kind,'cover':'','source':'MusicBrainz','source_url':'https://musicbrainz.org/release-group/'+rid,
                          'release_date':str(row.get('first-release-date',''))[:10],'_mb_artist_id':aid})
        return items
    with ThreadPoolExecutor(max_workers=2,thread_name_prefix='album-discovery') as pool:
        tasks=[pool.submit(copy_context().run,fn) for fn in (apple,brainz)]
        for task in tasks:
            try:result.extend(task.result())
            except Exception:checkpoint()
    from artist_catalog import normalized
    seen=set();rows=[]
    for item in result:
        key=(normalized(item['artist']),normalized(item['title']),item['kind'])
        if key in seen:continue
        seen.add(key)
        origin_url='https://musicbrainz.org/artist/'+item['_mb_artist_id'] if item.get('_mb_artist_id') else item['source_url']
        item['origin']={'id':10**15+int.from_bytes(hashlib.sha256(origin_url.encode()).digest()[:6],'big'),
                        'title':item['artist'],'artist':item['artist'],'url':origin_url,'kind':'artist'}
        if item.get('_mb_artist_id'):item['origin']['_mb_artist_id']=item['_mb_artist_id']
        rows.append(item)
    return rows[:12]
