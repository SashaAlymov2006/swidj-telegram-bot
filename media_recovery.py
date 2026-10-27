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
        retain(url,'audio-mp3-192',target,dict(metadata,_public_source=saved.get('public') is True),uid)
        if saved.get('public') and metadata.get('source_url'):cache.alias_public(metadata['source_url'],url)
        return str(target),metadata
    except Exception:
        # Request exceptions can contain the bot token: never propagate or log them.
        return None
    finally:pending.unlink(missing_ok=True)


def download_with_reserve(downloader,url,hint,max_bytes=49*1024**2,uid=None):
    import tempfile,shutil
    from scratch import scratch_root
    from download_cache import restore,source_key
    directory=None
    def room():
        nonlocal directory
        if directory is None:directory=tempfile.mkdtemp(dir=scratch_root(),prefix='yt_audio_reserve_')
        return directory
    def checked(result):
        if max_bytes and Path(result[0]).stat().st_size>max_bytes:raise ValueError('File too large')
        return result
    try:
        checkpoint()
        cached=restore(url,'audio-mp3-192',room(),uid)
        if cached:return checked(cached)
        recovered=recover_audio(url,room(),uid)
        if recovered:return checked(recovered)
        shutil.rmtree(directory,ignore_errors=True);directory=None
    except BaseException:
        if directory:shutil.rmtree(directory,ignore_errors=True)
        raise
    try:
        result=downloader(url)
        if result[1].get('source') in ('Jamendo','Audius'):retain(url,'audio-mp3-192',result[0],dict(result[1],_public_source=True),uid)
        return result
    except Exception as original:
        # Never substitute a shorter file to get around product limits or a full disk.
        if isinstance(original,(OSError,ValueError)) or not str(source_key(url)).startswith('youtube:'):raise
        from download_cache import configured,alias_public
        try:
            cache=configured();known=cache.hint(url) if cache else {}
        except Exception:known={}
        hint=dict(known,**{k:v for k,v in hint.items() if v not in (None,'')})
        from soundcloud_source import matching_track as sc_match,download as sc_download
        from jamendo_source import matching_track as jam_match,download as jam_download
        from audius_source import matching_track as aud_match,download as aud_download
        for match,download in ((sc_match,lambda item,folder:sc_download(item,folder,max_bytes)),
                               (aud_match,lambda item,folder:aud_download(item['url'],folder,max_bytes)),
                               (jam_match,lambda item,folder:jam_download(item['url'],folder,max_bytes or 256*1024**2))):
            checkpoint()
            try:
                item=match(hint)
                if not item:continue
                result=checked(download(item,room()))
                retain(item['url'],'audio-mp3-192',result[0],dict(result[1],_public_source=True),uid)
                alias_public(url,item['url'])
                return result
            except Exception:
                if directory:shutil.rmtree(directory,ignore_errors=True);directory=None
            except BaseException:
                if directory:shutil.rmtree(directory,ignore_errors=True)
                raise
        raise original from None
