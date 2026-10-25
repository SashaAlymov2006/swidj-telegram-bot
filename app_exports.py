"""Private short-lived studio files for Telegram's native mobile downloader."""
from pathlib import Path
import os
import re
import secrets
import shutil
import time
from media_store import MediaStore
from app_limits import STUDIO_OUTPUT_BYTES,TEMP_CACHE_BYTES,DISK_RESERVE_BYTES

FILE_NAME=re.compile(r'[A-Za-z0-9_-]{32}\.(?:mp3|wav|mp4|jpg)')

class ExportFiles:
    def __init__(self,root=None,ttl=3600,budget=TEMP_CACHE_BYTES):
        self.root=Path(root or Path(os.getenv('AUDIO_CACHE_DIR','/app/data/audio')).parent/'miniapp-exports')
        self.store=MediaStore(self.root)
        self.ttl,self.budget=ttl,budget
        self.items={}

    def prune(self,incoming=0,large=False):
        if self.root.is_symlink():raise ValueError('Invalid export storage')
        now=time.time();files=[]
        deadlines={value['path']:value['expires'] for value in self.items.values()}
        if self.root.exists():
            for folder in self.root.iterdir():
                if folder.is_symlink() or not folder.is_dir() or not folder.name.isdecimal():continue
                for path in folder.iterdir():
                    if path.is_symlink() or not path.is_file() or not FILE_NAME.fullmatch(path.name):continue
                    stat=path.stat()
                    if now>deadlines.get(path,stat.st_mtime+self.ttl):path.unlink(missing_ok=True)
                    else:files.append((stat.st_mtime,stat.st_size,path))
        budget=max(self.budget,incoming) if large else max(self.budget,max((x[1] for x in files),default=0)) if not incoming else self.budget
        total=sum(x[1] for x in files)
        for _,size,path in sorted(files):
            if total+incoming<=budget:break
            path.unlink(missing_ok=True);total-=size
        self.items={k:v for k,v in self.items.items() if v['expires']>now and v['path'].is_file()}
        if incoming>budget:raise ValueError('Export too large')

    def retain(self,uid,source,title='SwiDJ mix',feature='studio',ttl=None):
        source=Path(source)
        if source.suffix not in ('.mp3','.wav','.mp4','.jpg') or source.is_symlink() or not (source.stat().st_size>0 and (feature=='downloads' or source.stat().st_size<=STUDIO_OUTPUT_BYTES)):
            raise ValueError('Invalid export')
        self.prune(source.stat().st_size,large=feature=='downloads')
        self.root.mkdir(parents=True,exist_ok=True)
        if feature=='downloads' and shutil.disk_usage(self.root).free<source.stat().st_size+DISK_RESERVE_BYTES:raise OSError('Not enough disk space')
        while len(self.items)>=128:
            oldest=next(iter(self.items));self.items.pop(oldest)['path'].unlink(missing_ok=True)
        token=secrets.token_urlsafe(24)
        path=self.store.user_directory(uid)/(token+source.suffix)
        shutil.copyfile(source,path)
        title=re.sub(r'[\\/:*?"<>|\x00-\x1f]','',str(title)).strip()[:80] or 'SwiDJ mix'
        self.items[token]={'uid':uid,'feature':feature,'path':path,'filename':title+source.suffix,'expires':time.time()+(ttl or self.ttl)}
        return token,self.items[token]

    def get(self,token):
        self.prune()
        item=self.items.get(token)
        if not item or item['path'].is_symlink():return None
        return item
