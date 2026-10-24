"""Private short-lived studio files for Telegram's native mobile downloader."""
from pathlib import Path
import os
import re
import secrets
import shutil
import time
from media_store import MediaStore

FILE_NAME=re.compile(r'[A-Za-z0-9_-]{32}\.(?:mp3|wav|mp4|jpg)')

class ExportFiles:
    def __init__(self,root=None,ttl=600,budget=256*1024**2):
        self.root=Path(root or Path(os.getenv('AUDIO_CACHE_DIR','/app/data/audio')).parent/'miniapp-exports')
        self.store=MediaStore(self.root)
        self.ttl,self.budget=ttl,budget
        self.items={}

    def prune(self,incoming=0):
        if self.root.is_symlink():raise ValueError('Invalid export storage')
        now=time.time();files=[]
        if self.root.exists():
            for folder in self.root.iterdir():
                if folder.is_symlink() or not folder.is_dir() or not folder.name.isdecimal():continue
                for path in folder.iterdir():
                    if path.is_symlink() or not path.is_file() or not FILE_NAME.fullmatch(path.name):continue
                    stat=path.stat()
                    if now-stat.st_mtime>self.ttl:path.unlink(missing_ok=True)
                    else:files.append((stat.st_mtime,stat.st_size,path))
        total=sum(x[1] for x in files)
        for _,size,path in sorted(files):
            if total+incoming<=self.budget:break
            path.unlink(missing_ok=True);total-=size
        self.items={k:v for k,v in self.items.items() if v['expires']>now and v['path'].is_file()}
        if incoming>self.budget:raise ValueError('Export too large')

    def retain(self,uid,source,title='SwiDJ mix',feature='studio'):
        source=Path(source)
        if source.suffix not in ('.mp3','.wav','.mp4','.jpg') or source.is_symlink() or not 0<source.stat().st_size<=96*1024**2:
            raise ValueError('Invalid export')
        self.prune(source.stat().st_size)
        while len(self.items)>=128:
            oldest=next(iter(self.items));self.items.pop(oldest)['path'].unlink(missing_ok=True)
        token=secrets.token_urlsafe(24)
        path=self.store.user_directory(uid)/(token+source.suffix)
        shutil.copyfile(source,path)
        title=re.sub(r'[\\/:*?"<>|\x00-\x1f]','',str(title)).strip()[:80] or 'SwiDJ mix'
        self.items[token]={'uid':uid,'feature':feature,'path':path,'filename':title+source.suffix,'expires':time.time()+self.ttl}
        return token,self.items[token]

    def get(self,token):
        self.prune()
        item=self.items.get(token)
        if not item or item['path'].is_symlink():return None
        return item
