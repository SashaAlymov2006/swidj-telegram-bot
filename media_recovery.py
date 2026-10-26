"""Recover the same user's exact previously delivered audio via the official Bot API."""
import os
from pathlib import Path
import re
import time
import requests
from download_cache import configured,operation_uid,retain
from operations import checkpoint


def recover_audio(url,directory,uid=None):
    token=os.getenv('TELEGRAM_TOKEN','')
    uid=uid or operation_uid()
    pending=Path(directory)/'telegram-recovery.part'
    try:
        if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+',token) or not uid:return None
        cache=configured()
        saved=cache.telegram_info(int(token.split(':')[0]),uid,url) if cache else None
        if not saved:return None
        checkpoint()
        with requests.get('https://api.telegram.org/bot'+token+'/getFile',params={'file_id':saved['file_id']},timeout=(5,15)) as response:
            response.raise_for_status();data=response.json()
        file=data.get('result',{})
        remote=file.get('file_path','');size=file.get('file_size')
        # The standard Telegram Bot API supports file downloads up to 20 MB.
        limit=20*1024**2
        if not data.get('ok') or not re.fullmatch(r'[A-Za-z0-9_./-]+',remote) or remote.startswith('/') or '..' in remote.split('/'):return None
        if type(size) is not int or not 0<size<=limit:return None
        from app_limits import link_budget
        Path(directory).mkdir(parents=True,exist_ok=True)
        if size>=link_budget(directory):return None
        Path(directory).mkdir(parents=True,exist_ok=True)
        deadline=time.monotonic()+60;total=0
        with requests.get('https://api.telegram.org/file/bot'+token+'/'+remote,stream=True,timeout=(5,20)) as response:
            response.raise_for_status()
            if not response.headers.get('Content-Type','application/octet-stream').startswith(('audio/','application/octet-stream')):return None
            with pending.open('wb') as out:
                for chunk in response.iter_content(65536):
                    checkpoint();total+=len(chunk)
                    if total>limit or total>size or time.monotonic()>deadline:raise ValueError('Recovery budget')
                    out.write(chunk)
        if total!=size:return None
        target=Path(directory)/'recovered.mp3';os.replace(pending,target)
        metadata=saved['metadata']
        retain(url,'audio-mp3-192',target,metadata,uid)
        return str(target),metadata
    except Exception:
        # Request exceptions can contain the bot token: never propagate or log them.
        return None
    finally:pending.unlink(missing_ok=True)


def download_with_reserve(downloader,url,hint):
    try:return downloader(url)
    except Exception as original:
        # Never substitute a shorter file to get around product limits or a full disk.
        if isinstance(original,(OSError,ValueError)) or not os.getenv('JAMENDO_CLIENT_ID'):raise
        from jamendo_source import matching_track,download
        item=matching_track(hint)
        if not item:raise
        import tempfile,shutil
        from scratch import scratch_root
        directory=tempfile.mkdtemp(dir=scratch_root(),prefix='yt_audio_reserve_')
        try:return download(item['url'],directory)
        except BaseException:
            shutil.rmtree(directory,ignore_errors=True)
            import sys
            if not isinstance(sys.exception(),Exception):raise
            raise original from None
