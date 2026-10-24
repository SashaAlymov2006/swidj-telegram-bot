"""Prepare Railway's root-owned volume, then run the bot as uid 10001."""
import json
import os
from pathlib import Path
import pwd
import sys
import tempfile

DATA = Path('/app/data')


def prepare_storage():
    mount = os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
    if os.getenv('RAILWAY_PROJECT_ID') and mount != str(DATA):
        raise RuntimeError('Attach the persistent Railway volume at /app/data before starting SwiDJ')
    if DATA.is_symlink():
        raise RuntimeError('Persistent data directory cannot be a symlink')
    DATA.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('STATE_DB_PATH', str(DATA / 'state.sqlite3'))
    os.environ.setdefault('USERS_DB_PATH', str(DATA / 'users.sqlite3'))
    os.environ.setdefault('AUDIO_CACHE_DIR', str(DATA / 'audio'))
    os.environ.setdefault('XDG_CACHE_HOME', str(DATA / 'models'))
    for name in ('STATE_DB_PATH', 'USERS_DB_PATH', 'AUDIO_CACHE_DIR', 'XDG_CACHE_HOME'):
        path = Path(os.environ[name])
        if not path.is_absolute() or not path.resolve().is_relative_to(DATA.resolve()):
            raise RuntimeError(name + ' must be inside the persistent /app/data volume')
    for name in ('AUDIO_CACHE_DIR', 'XDG_CACHE_HOME'):
        Path(os.environ[name]).mkdir(parents=True, exist_ok=True)
    if os.geteuid() == 0:
        account = pwd.getpwnam('bot')
        # Never follow symlinks while repairing ownership of an existing volume.
        os.chown(DATA, account.pw_uid, account.pw_gid, follow_symlinks=False)
        for directory, folders, files in os.walk(DATA, followlinks=False):
            for name in folders + files:
                path = Path(directory) / name
                if path.is_symlink():
                    continue
                stat = path.stat()
                if (stat.st_uid, stat.st_gid) != (account.pw_uid, account.pw_gid):
                    os.chown(path, account.pw_uid, account.pw_gid, follow_symlinks=False)
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
        os.environ['HOME'] = account.pw_dir
    if os.geteuid() != pwd.getpwnam('bot').pw_uid:
        raise RuntimeError('SwiDJ must run as the non-root bot user')
    with tempfile.TemporaryFile(dir=DATA) as check:
        check.write(b'SwiDJ volume ready')


def main():
    prepare_storage()
    if sys.argv[1:] == ['--check-storage']:
        print(json.dumps({'uid': os.geteuid(), 'storage_ready': True,
                          'model_cache': os.environ['XDG_CACHE_HOME']}))
        return
    if sys.argv[1:]:
        raise RuntimeError('Unexpected startup arguments')
    os.execv(sys.executable, [sys.executable, '/app/bot.py'])


if __name__ == '__main__':
    main()
