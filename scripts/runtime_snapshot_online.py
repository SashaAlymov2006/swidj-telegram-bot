"""Online recovery snapshot: consistent SQLite copies, best-effort media snapshot.

Run in a resource-limited helper container with /source mounted read-only and
/out writable. Never stops/restarts the bot. No browser profiles or env mounts.
"""
import hashlib,json,os,shutil,sqlite3,tarfile,tempfile,time
from datetime import datetime,timezone
from pathlib import Path

def main():
    source=Path('/source');out=Path('/out');stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target=out/('runtime-online-'+stamp+'.tar.gz');skipped=[];databases=[]
    def allowed(path):
        name=path.name.lower()
        return not (path.is_symlink() or name.startswith('.env') or any(word in name for word in ('cookies','credentials','id_rsa','id_ed25519')) or name.endswith(('-wal','-shm','-journal')))
    with tempfile.TemporaryDirectory(prefix='online-snapshot-',dir=out) as temp:
        staged=Path(temp)
        for path in sorted(source.rglob('*')):
            if not path.is_file() or not allowed(path):continue
            relative=path.relative_to(source);copy=staged/relative;copy.parent.mkdir(parents=True,exist_ok=True)
            try:
                if path.suffix in ('.sqlite3','.sqlite','.db'):
                    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=30) as src,sqlite3.connect(copy) as dst:
                        src.backup(dst,pages=128,sleep=.01)
                        if dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('SQLite verification failed')
                    databases.append(relative.as_posix())
                else:
                    shutil.copy2(path,copy)
            except FileNotFoundError:
                skipped.append(relative.as_posix());copy.unlink(missing_ok=True)
        note={'mode':'online','created_utc':stamp,'sqlite_consistent':databases,'skipped_disappeared_files':skipped,'media_cross_file_atomic':False,'bot_stopped':False,'credentials_included':False}
        (staged/'ONLINE_SNAPSHOT.json').write_text(json.dumps(note,indent=2))
        with tarfile.open(target,'w:gz') as archive:
            for path in sorted(staged.iterdir()):archive.add(path,arcname=path.name)
    with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    result={'path':str(target),'sha256':digest,'bytes':target.stat().st_size,**note}
    (out/'runtime-online-snapshot.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':main()
