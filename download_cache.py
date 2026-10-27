"""Bounded persistent downloads; opaque keys and user isolation, no provider secrets."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
from urllib.parse import urlsplit, parse_qs


def source_key(url):
    if not isinstance(url, str): return None
    try:
        p = urlsplit(url)
        if p.scheme != 'https' or p.username or p.password: return None
        host = (p.hostname or '').lower()
        if host=='www.jamendo.com':
            from jamendo_source import identifier
            track=identifier(url)
            return 'jamendo:'+track if track else None
        if host in ('youtu.be', 'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'):
            import re
            video = p.path.strip('/') if host == 'youtu.be' else parse_qs(p.query).get('v', [''])[0] if p.path == '/watch' else p.path.strip('/').split('/')[-1]
            return 'youtube:'+video if re.fullmatch(r'[A-Za-z0-9_-]{11}', video) else None
        if host in ('soundcloud.com','www.soundcloud.com','tiktok.com','www.tiktok.com','vm.tiktok.com','vt.tiktok.com','instagram.com','www.instagram.com','vimeo.com','www.vimeo.com') or host.endswith('.bandcamp.com'):
            # Preserve query parameters on non-YouTube links: they may affect access.
            return url
    except ValueError: pass
    return None


def operation_uid():
    from operations import _current
    op = _current.get()
    return op.uid if op and type(op.uid) is int and op.uid > 0 else None


class DownloadCache:
    def __init__(self, root, limit=20*1024**3, ttl=30*86400):
        self.root = Path(root)
        self.limit, self.ttl = limit, ttl
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink(): raise ValueError('Invalid cache root')

    @contextmanager
    def db(self):
        with sqlite3.connect(self.root/'index.sqlite3', timeout=30) as db:
            db.execute('CREATE TABLE IF NOT EXISTS media (key TEXT PRIMARY KEY, suffix TEXT, metadata TEXT, size INTEGER, touched REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS telegram (key TEXT PRIMARY KEY, file_id TEXT, touched REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS telegram_metadata (key TEXT PRIMARY KEY, metadata TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS searches (key TEXT PRIMARY KEY, records TEXT, touched REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS public_media (source TEXT, variant TEXT, media_key TEXT, canonical TEXT, touched REAL, PRIMARY KEY(source,variant))')
            db.execute('CREATE TABLE IF NOT EXISTS public_telegram (key TEXT PRIMARY KEY, file_id TEXT, metadata TEXT, touched REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS public_fingerprints (media_key TEXT PRIMARY KEY, digest TEXT NOT NULL)')
            yield db

    def key(self, uid, url, variant):
        source = source_key(url)
        if type(uid) is not int or uid <= 0 or not source: return None
        return hashlib.sha256(json.dumps([uid,source,variant]).encode()).hexdigest()

    def restore(self, uid, url, variant, directory):
        key = self.key(uid,url,variant)
        if not key: return None
        with self.db() as db:
            row = db.execute('SELECT suffix, metadata, touched FROM media WHERE key=?',(key,)).fetchone()
            if not row: return None
            suffix, metadata, touched = row
            if suffix not in ('.mp3','.mp4') or time.time()-touched > self.ttl: return None
            source = self.root/(key+suffix)
            if source.is_symlink() or not source.is_file(): return None
            target = Path(directory)/('cached'+suffix)
            try: shutil.copyfile(source,target)
            except FileNotFoundError: return None
            db.execute('UPDATE media SET touched=? WHERE key=?',(time.time(),key))
            return str(target),json.loads(metadata)

    def retain(self, uid, url, variant, source, metadata):
        key = self.key(uid,url,variant)
        source = Path(source)
        if not key or source.is_symlink() or source.suffix not in ('.mp3','.mp4'): return
        size = source.stat().st_size
        if not 0 < size <= self.limit: return
        safe = {k:metadata[k] for k in ('title','artist','track','uploader','duration','kind') if isinstance(metadata.get(k),(str,int,float))}
        if metadata.get('source') in ('SoundCloud','Jamendo') and shareable(metadata.get('source_url')):
            safe.update(source=metadata['source'],source_url=metadata['source_url'])
            from jamendo_source import license_url
            license=license_url(metadata.get('license_url'))
            if license:safe['license_url']=license
        pending = None
        with self.db() as db:
            # Serialize eviction/promotion across subprocesses and bot download threads.
            db.execute('BEGIN IMMEDIATE')
            if metadata.get('_public_source') is not True or not shareable(url):
                db.execute('DELETE FROM public_media WHERE media_key=?',(key,))
            rows = db.execute('SELECT key,suffix,size,touched FROM media ORDER BY touched').fetchall()
            total = sum(r[2] for r in rows if r[0] != key)
            for old,suffix,n,touched in rows:
                if old != key and (total+size > self.limit or time.time()-touched > self.ttl):
                    if suffix in ('.mp3','.mp4') and len(old)==64:
                        (self.root/(old+suffix)).unlink(missing_ok=True)
                    db.execute('DELETE FROM media WHERE key=?',(old,)); total -= n
            try:
                with tempfile.NamedTemporaryFile(dir=self.root,suffix='.pending',delete=False) as out:
                    pending = Path(out.name)
                    with source.open('rb') as inp: shutil.copyfileobj(inp,out)
                os.replace(pending,self.root/(key+source.suffix))
                db.execute('INSERT OR REPLACE INTO media VALUES (?,?,?,?,?)',(key,source.suffix,json.dumps(safe),size,time.time()))
                if variant=='audio-mp3-192' and metadata.get('_public_source') is True and shareable(url):
                    with (self.root/(key+source.suffix)).open('rb') as stream:fingerprint=hashlib.file_digest(stream,'sha256').hexdigest()
                    db.execute('INSERT OR REPLACE INTO public_fingerprints VALUES (?,?)',(key,fingerprint))
                    canonical=public_key(metadata.get('source_url')) if shareable(metadata.get('source_url')) else public_key(url)
                    db.execute('INSERT OR REPLACE INTO public_media VALUES (?,?,?,?,?)',(public_key(url),variant,key,canonical,time.time()))
                    db.execute('DELETE FROM public_media WHERE source IN (SELECT source FROM public_media ORDER BY touched DESC LIMIT -1 OFFSET 100000)')
                    db.execute('DELETE FROM public_fingerprints WHERE media_key NOT IN (SELECT media_key FROM public_media)')
            finally:
                if pending: pending.unlink(missing_ok=True)

    def telegram_get(self, bot_id, uid, url, variant='audio-mp3-192', allow_public=True):
        key = self.key(uid,url,'telegram:'+str(bot_id)+':'+variant)
        if not key: return None
        with self.db() as db:
            public=self.public_telegram_key(db,bot_id,url,variant) if allow_public else None
            shared=db.execute('SELECT file_id FROM public_telegram WHERE key=?',(public,)).fetchone() if public else None
            if shared:return shared[0]
            row=db.execute('SELECT file_id FROM telegram WHERE key=?',(key,)).fetchone()
            if row: db.execute('UPDATE telegram SET touched=? WHERE key=?',(time.time(),key))
            return row[0] if row else None

    def telegram_info(self, bot_id, uid, url):
        key=self.key(uid,url,'telegram:'+str(bot_id)+':audio-mp3-192')
        if not key:return None
        with self.db() as db:
            public=self.public_telegram_key(db,bot_id,url,'audio-mp3-192')
            shared=db.execute('SELECT file_id,metadata FROM public_telegram WHERE key=?',(public,)).fetchone() if public else None
            if shared:return {'file_id':shared[0],'metadata':json.loads(shared[1] or '{}'),'public':True}
            row=db.execute('SELECT t.file_id,m.metadata FROM telegram t LEFT JOIN telegram_metadata m ON t.key=m.key WHERE t.key=?',(key,)).fetchone()
            return {'file_id':row[0],'metadata':json.loads(row[1] or '{}'),'public':False} if row else None

    def telegram_set(self, bot_id, uid, url, file_id, variant='audio-mp3-192', metadata=None, public=False):
        key = self.key(uid,url,'telegram:'+str(bot_id)+':'+variant)
        if not key: return
        with self.db() as db:
            if file_id:
                db.execute('INSERT OR REPLACE INTO telegram VALUES (?,?,?)',(key,str(file_id),time.time()))
                if metadata is not None:
                    safe={k:v for k,v in metadata.items() if k in ('title','artist','duration') and isinstance(v,(str,int,float))}
                    if metadata.get('source') in ('SoundCloud','Jamendo') and shareable(metadata.get('source_url')):
                        safe.update(source=metadata['source'],source_url=metadata['source_url'])
                        from jamendo_source import license_url
                        license=license_url(metadata.get('license_url'))
                        if license:safe['license_url']=license
                    db.execute('INSERT OR REPLACE INTO telegram_metadata VALUES (?,?)',(key,json.dumps(safe)))
                shared=self.public_telegram_key(db,bot_id,url,variant) if public else None
                if shared and metadata is not None:
                    db.execute('INSERT OR REPLACE INTO public_telegram VALUES (?,?,?,?)',(shared,str(file_id),json.dumps(safe),time.time()))
                    db.execute('DELETE FROM public_telegram WHERE key IN (SELECT key FROM public_telegram ORDER BY touched DESC LIMIT -1 OFFSET 100000)')
                db.execute('DELETE FROM telegram WHERE key IN (SELECT key FROM telegram ORDER BY touched DESC LIMIT -1 OFFSET 100000)')
                db.execute('DELETE FROM telegram_metadata WHERE key NOT IN (SELECT key FROM telegram)')
            else:
                db.execute('DELETE FROM telegram WHERE key=?',(key,))
                db.execute('DELETE FROM telegram_metadata WHERE key=?',(key,))
                public=self.public_telegram_key(db,bot_id,url,variant)
                if public:db.execute('DELETE FROM public_telegram WHERE key=?',(public,))

    def public_telegram_key(self,db,bot_id,url,variant):
        if not shareable(url):return None
        row=db.execute('SELECT canonical FROM public_media WHERE source=? AND variant=?',(public_key(url),variant)).fetchone()
        return hashlib.sha256(json.dumps([bot_id,row[0],variant]).encode()).hexdigest() if row else None

    def alias_public(self,url,resolved):
        if not shareable(url) or not shareable(resolved):return
        with self.db() as db:
            row=db.execute('SELECT media_key,canonical FROM public_media WHERE source=? AND variant=?',(public_key(resolved),'audio-mp3-192')).fetchone()
            if row:db.execute('INSERT OR REPLACE INTO public_media VALUES (?,?,?,?,?)',(public_key(url),'audio-mp3-192',row[0],row[1],time.time()))

    def public_file(self,url,path=None):
        if not shareable(url):return False
        with self.db() as db:
            row=db.execute('SELECT p.media_key,f.digest FROM public_media p LEFT JOIN public_fingerprints f ON p.media_key=f.media_key WHERE p.source=? AND p.variant=?',(public_key(url),'audio-mp3-192')).fetchone()
        if not row:return False
        if path is None:return True
        if not row[1]:return False
        candidate=Path(path)
        if candidate.is_symlink():return False
        try:
            with candidate.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()==row[1]
        except OSError:return False

    def public_metadata(self,url):
        if not shareable(url):return {}
        with self.db() as db:
            row=db.execute('SELECT m.metadata FROM public_media p JOIN media m ON p.media_key=m.key WHERE p.source=? AND p.variant=?',(public_key(url),'audio-mp3-192')).fetchone()
            return json.loads(row[0]) if row else {}

    def restore_public(self,url,variant,directory):
        if not shareable(url) or variant!='audio-mp3-192':return None
        with self.db() as db:
            row=db.execute('SELECT m.key,m.suffix,m.metadata,m.touched,f.digest FROM public_media p JOIN media m ON p.media_key=m.key JOIN public_fingerprints f ON p.media_key=f.media_key WHERE p.source=? AND p.variant=?',(public_key(url),variant)).fetchone()
            if not row:return None
            key,suffix,metadata,touched,fingerprint=row
            if suffix!='.mp3' or time.time()-touched>self.ttl:return None
            source=self.root/(key+suffix)
            if source.is_symlink() or not source.is_file():return None
            target=Path(directory)/'cached.mp3'
            try:shutil.copyfile(source,target)
            except FileNotFoundError:return None
            with target.open('rb') as stream:valid=hashlib.file_digest(stream,'sha256').hexdigest()==fingerprint
            if not valid:target.unlink(missing_ok=True);return None
            db.execute('UPDATE media SET touched=? WHERE key=?',(time.time(),key))
            return str(target),json.loads(metadata)

    def hint(self,url):
        source=source_key(url)
        if not source:return {}
        with self.db() as db:
            for records, in db.execute('SELECT records FROM searches ORDER BY touched DESC LIMIT 300'):
                for row in json.loads(records):
                    if source_key(row.get('url'))==source:return row
        return {}

    def search(self, query, records=None):
        key=hashlib.sha256(str(query).strip().casefold()[:240].encode()).hexdigest()
        with self.db() as db:
            if records:
                safe=[]
                for row in records[:10]:
                    if not isinstance(row,dict) or not shareable(row.get('url')):continue
                    safe.append({k:v for k,v in row.items() if k in ('url','title','artist','duration','cover','source','source_url','license_url') and isinstance(v,(str,int,float,type(None)))})
                if safe:
                    db.execute('INSERT OR REPLACE INTO searches VALUES (?,?,?)',(key,json.dumps(safe),time.time()))
                    db.execute('DELETE FROM searches WHERE touched<?',(time.time()-7*86400,))
                    db.execute('DELETE FROM searches WHERE key IN (SELECT key FROM searches ORDER BY touched DESC LIMIT -1 OFFSET 300)')
                return safe
            row=db.execute('SELECT records,touched FROM searches WHERE key=?',(key,)).fetchone()
            return json.loads(row[0]) if row and time.time()-row[1]<=7*86400 else []


def configured():
    root = os.getenv('DOWNLOAD_CACHE_DIR')
    if not root: return None
    return DownloadCache(root, int(os.getenv('DOWNLOAD_CACHE_BYTES',str(20*1024**3))))

def public_key(url):return hashlib.sha256(str(source_key(url)).encode()).hexdigest()

def shareable(url):
    try:
        p=urlsplit(str(url))
        if p.scheme!='https' or p.username or p.password or p.port not in (None,443):return False
        source=source_key(url)
        if str(source).startswith(('youtube:','jamendo:')):return True
        from soundcloud_source import public_url
        return public_url(url)
    except ValueError:return False


def restore(url, variant, directory, uid=None):
    try:
        cache=configured()
        owner=uid or operation_uid()
        if not cache or not owner:return None
        return cache.restore(owner,url,variant,directory) or cache.restore_public(url,variant,directory)
    except (OSError,ValueError,sqlite3.Error): return None


def retain(url, variant, source, metadata, uid=None):
    try:
        cache=configured()
        if cache: cache.retain(uid or operation_uid(),url,variant,source,metadata)
    except (OSError,ValueError,sqlite3.Error): pass

def alias_public(url,resolved):
    try:
        cache=configured()
        if cache:cache.alias_public(url,resolved)
    except (OSError,ValueError,sqlite3.Error):pass


def search_cache(query, records=None):
    try:
        cache=configured()
        return cache.search(query,records) if cache else []
    except (OSError,ValueError,sqlite3.Error):return []
