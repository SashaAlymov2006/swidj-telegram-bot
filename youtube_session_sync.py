"""Refresh the private YouTube export from a dedicated, owner-authenticated browser."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

MARKERS={'SID','SAPISID','LOGIN_INFO','__Secure-3PSID','__Secure-1PSID'}


def filter_youtube(jar, now=None):
    now=time.time() if now is None else now
    for cookie in list(jar):
        domain=cookie.domain.lstrip('.').lower()
        if (domain!='youtube.com' and not domain.endswith('.youtube.com')) or (cookie.expires is not None and cookie.expires<=now):
            jar.clear(cookie.domain,cookie.path,cookie.name)
    return len(list(jar)),sum(cookie.name in MARKERS for cookie in jar)


def export():
    from yt_dlp.cookies import extract_cookies_from_browser
    class Quiet:
        def debug(self,*args,**kwargs):pass
        def info(self,*args,**kwargs):pass
        def warning(self,*args,**kwargs):pass
        def error(self,*args,**kwargs):pass
    pending=None
    try:
        jar=extract_cookies_from_browser('chromium',profile='/profile/chromium/Default',logger=Quiet())
        count,auth=filter_youtube(jar)
        if not count or not auth:
            return {'synced':False,'previous_retained':True}
        with tempfile.NamedTemporaryFile(dir='/out',prefix='.session-',delete=False) as stream:
            pending=Path(stream.name)
        jar.save(str(pending),ignore_discard=True,ignore_expires=True)
        pending.chmod(0o600);os.chown(pending,10001,10001)
        os.replace(pending,'/out/cookies-server-session.txt')
        return {'synced':True,'youtube_cookies':count,'authentication_markers':auth}
    except Exception:
        return {'synced':False,'previous_retained':True}
    finally:
        if pending:
            try:pending.unlink(missing_ok=True)
            except OSError:pass


def run(root):
    private=root.parent/'swidj-private'
    try:
        image=subprocess.run(['docker','inspect','swidj-vps-bot-1','--format','{{.Config.Image}}'],
                             capture_output=True,text=True,check=True,timeout=10).stdout.strip()
        result=subprocess.run(['docker','run','--rm','--network','none','--user','0',
            '-v',str(private/'server-browser')+':/profile:ro',
            '-v',str(private/'youtube')+':/out',
            '-v',str(Path(__file__).resolve())+':/worker.py:ro',
            '--entrypoint','python',image,'/worker.py','export'],capture_output=True,text=True,timeout=45)
        data=json.loads(result.stdout) if result.returncode==0 else {}
        return data if isinstance(data,dict) and type(data.get('synced')) is bool else {'synced':False,'previous_retained':True}
    except (OSError,ValueError,subprocess.SubprocessError):
        return {'synced':False,'previous_retained':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('run','export'))
    parser.add_argument('--root',type=Path,default=Path('/opt/swidj'));args=parser.parse_args()
    print(json.dumps(export() if args.mode=='export' else run(args.root)))
