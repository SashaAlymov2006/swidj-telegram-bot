"""Optional no-main-restart Caddy rollout; run on the VPS, not on Windows.

Stage service first, run visual_studio_smoke.py, then enable the frontend.
Rollback only restores this overlay's prior Caddy configuration.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['service','frontend','rollback']);parser.add_argument('--root',type=Path,default=Path('/opt/swidj'));parser.add_argument('--web',default='swidj-vps-web-1');args=parser.parse_args()
    root=args.root;config=root/'Caddyfile.vps';release=root/'visual-studio-release';backup=root/'deployment'/'Caddyfile.before-visual-studio'
    def docker(*parts):return subprocess.run(['docker',*parts],check=True,capture_output=True,text=True).stdout
    current=config.read_text();host=current.split('{',1)[0].strip()
    if not host or any(c.isspace() for c in host):raise ValueError('Expected one existing hostname')
    if args.phase=='rollback':candidate=backup.read_text()
    else:
        if not backup.exists():
            expected=host+' {\n    reverse_proxy bot:8765\n}\n'
            if ''.join(current.split())!=''.join(expected.split()):raise ValueError('Unexpected proxy config; inspect before changing')
            backup.write_text(current)
        fragment=''
        if args.phase=='frontend':
            docker('exec',args.web,'mkdir','-p','/config/swidj-visualizer/assets')
            docker('cp',str(release/'miniapp'/'app.js'),args.web+':/config/swidj-visualizer/assets/app.js')
            fragment='''    @visualStudioAsset {
        path /assets/app.js
        file {
            root /config/swidj-visualizer
        }
    }
    handle @visualStudioAsset {
        root * /config/swidj-visualizer
        header Cache-Control "no-store"
        file_server
    }
'''
        candidate=host+''' {
    handle_path /music-video/* {
        reverse_proxy music-video:8792
    }
'''+fragment+'''    handle {
        reverse_proxy bot:8765
    }
}
'''
    pending=root/'deployment'/'Caddyfile.visual-studio.pending';pending.write_text(candidate)
    docker('cp',str(pending),args.web+':/config/Caddyfile.visual-studio.pending')
    docker('exec',args.web,'caddy','validate','--config','/config/Caddyfile.visual-studio.pending','--adapter','caddyfile')
    try:
        # Write in place: preserve the existing read-only bind mount's inode.
        config.write_text(candidate)
        docker('exec',args.web,'caddy','reload','--config','/etc/caddy/Caddyfile','--adapter','caddyfile')
    except BaseException:
        config.write_text(current)
        docker('exec',args.web,'caddy','reload','--config','/etc/caddy/Caddyfile','--adapter','caddyfile')
        raise
    print(json.dumps({'phase':args.phase,'config_sha256':hashlib.sha256(candidate.encode()).hexdigest(),'main_bot_restarted':False}))

if __name__=='__main__':main()
