"""Validated, quota-bounded app uploads into the existing owned audio library."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import threading

from operations import run_process
from uploaded_media import library_store

MAX_FILE_BYTES = 20*1024**2
MAX_USER_BYTES = 128*1024**2
MAX_TOTAL_BYTES = 512*1024**2
_quota_lock = threading.Lock()


class StorageFull(ValueError):
    pass


def retain(source, uid, filename):
    source = Path(source)
    if source.is_symlink() or not source.is_file() or not 0 < source.stat().st_size <= MAX_FILE_BYTES:
        raise ValueError('Invalid upload size')
    result = run_process(['ffprobe','-v','error','-protocol_whitelist','file,pipe',
                          '-select_streams','a:0','-show_entries','stream=codec_name:format=duration,format_name',
                          '-of','json',str(source)], check=True, capture_output=True, timeout=15)
    data = json.loads(result.stdout)
    duration = float(data['format']['duration'])
    if not data.get('streams') or not math.isfinite(duration) or not 0 < duration <= 3600:
        raise ValueError('Invalid audio')
    format = data['format']['format_name'].split(',')[0]
    suffix = {'mp3':'.mp3','wav':'.wav','ogg':'.ogg','flac':'.flac','mov':'.m4a','mp4':'.m4a'}.get(format)
    if not suffix:
        raise ValueError('Unsupported audio container')
    digest = hashlib.sha256(str(uid).encode()+b':'+source.read_bytes()).hexdigest()
    store = library_store()
    directory = store.user_directory(uid)
    target = directory/('app-'+digest[:24]+suffix)
    if target.is_symlink():
        raise ValueError('Invalid upload target')
    with _quota_lock:
        if not target.is_file():
            total = own = 0
            for folder in store.root.iterdir():
                if folder.is_symlink() or not folder.is_dir() or not folder.name.isdecimal():
                    continue
                for path in folder.iterdir():
                    if path.is_file() and not path.is_symlink():
                        size = path.stat().st_size
                        total += size
                        if folder == directory:
                            own += size
            incoming = source.stat().st_size
            if own+incoming > MAX_USER_BYTES or total+incoming > MAX_TOTAL_BYTES:
                raise StorageFull('Library capacity reached')
            pending = directory/(secrets.token_hex(12)+'.pending')
            try:
                shutil.copyfile(source,pending)
                os.replace(pending,target)
            finally:
                pending.unlink(missing_ok=True)
    name = str(filename or 'My audio').replace(chr(92),'/').rsplit('/',1)[-1]
    title = re.sub(r'[\x00-\x1f\x7f]', '', Path(name).stem).strip()[:128] or 'My audio'
    return {'id':-(2*10**16+int(digest[:12],16)), 'title':title, 'artist':'',
            'kind':'upload','media_kind':'audio','duration':duration,'app_upload':True,
            'original_filename':title+suffix, '_library_audio':str(target)}
