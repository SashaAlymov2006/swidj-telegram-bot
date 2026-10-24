"""Temporary HTTPS preview; no Cloudflare account or desktop installation.

Uses the official cloudflared container, publishes only the Mini App, and keeps
the changing URL in private .env. Never prints bot credentials or user data.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.request import urlopen

from run_local import docker_cli, start_engine

ROOT = Path(__file__).resolve().parent
PATTERN = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com\b')


def replace_url(text, value):
    lines = [line for line in text.splitlines()
             if not re.match(r'^\s*MINIAPP_URL\s*=', line)]
    return '\n'.join(lines).rstrip() + '\nMINIAPP_URL=' + value + '\n'


def save_url(url):
    if url and not PATTERN.fullmatch(url):
        raise ValueError('Unexpected tunnel URL')
    path = ROOT / '.env'
    if not path.is_file():
        raise RuntimeError('Configure the bot .env first; never publish this file.')
    text = replace_url(path.read_text(encoding='utf-8-sig'), url)
    # Write in place: the credential file retains its Windows access permissions.
    path.write_text(text, encoding='utf-8')


def command(cli, *args):
    return [cli, 'compose', '-p', 'swidj-local', '-f', str(ROOT/'compose.local.yaml'),
            '-f', str(ROOT/'compose.tunnel.yaml'), *args]


def run(cli, *args):
    result = subprocess.run(command(cli, *args), cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError('Docker operation failed. Check Docker Desktop and the local bot.')
    return result.stdout + result.stderr


def tunnel_info(cli):
    log = run(cli, 'logs', '--no-color', '--tail', '150', 'tunnel')
    urls = PATTERN.findall(log)
    return urls[-1] if urls else None


def healthy(url):
    try:
        with urlopen(url, timeout=10) as response:
            return response.status == 200 and b'SwiDJ' in response.read(16000)
    except (OSError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('start', 'stop', 'status'), nargs='?', default='start')
    args = parser.parse_args()
    cli = docker_cli()
    start_engine(cli)
    if args.action == 'stop':
        run(cli, 'stop', 'tunnel')
        save_url('')
        run(cli, 'up', '-d', '--no-build', '--no-deps', 'bot')
        print('HTTPS preview stopped. The normal Telegram bot remains available.')
        return
    if args.action == 'status':
        url = tunnel_info(cli)
        print(json.dumps({'url': url, 'reachable': bool(url and healthy(url))}))
        return
    run(cli, 'up', '-d', '--no-build', 'bot', 'tunnel')
    url = None
    for _ in range(20):
        url = tunnel_info(cli)
        if url and healthy(url):
            break
        time.sleep(2)
    else:
        raise RuntimeError('HTTPS preview did not become ready. Do not use an old URL; retry start.')
    save_url(url)
    run(cli, 'up', '-d', '--no-build', '--no-deps', 'bot')
    print(json.dumps({'url': url, 'telegram': 'Open the bot and use /app or its separate Open app button. The normal command menu is preserved.',
                      'temporary': True, 'requires_laptop_online': True}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
