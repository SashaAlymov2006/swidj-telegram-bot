"""Private VPS YouTube checks and owner-only notifications. Never logs credentials."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROBE_URL = 'https://www.youtube.com/watch?v=liRLUgaUwh4'


def probe():
    cookie = Path(os.getenv('YTDLP_COOKIE_FILE', '/nonexistent'))
    if not cookie.is_file():
        return 'auth_required'
    import http.cookiejar
    try:
        jar = http.cookiejar.MozillaCookieJar(str(cookie))
        jar.load(ignore_discard=True, ignore_expires=True)
        relevant = [c for c in jar if c.domain.lstrip('.') == 'youtube.com'
                    or c.domain.lstrip('.').endswith('.youtube.com')]
        if not relevant or not any(not c.expires or c.expires > time.time() for c in relevant):
            return 'auth_required'
    except (OSError, ValueError, http.cookiejar.LoadError):
        return 'auth_required'

    class Quiet:
        def debug(self, *args): pass
        def warning(self, *args): pass
        def error(self, *args): pass

    import yt_dlp
    try:
        # The check must not rewrite the live cookie jar used by downloads.
        with tempfile.TemporaryDirectory(prefix='youtube-health-') as folder:
            copied = Path(folder)/'cookies.txt'
            shutil.copyfile(cookie, copied)
            copied.chmod(0o600)
            options = {'cookiefile':str(copied), 'skip_download':True, 'quiet':True,
                       'logger':Quiet(), 'socket_timeout':8, 'retries':0,
                       'extractor_retries':0, 'noplaylist':True, 'format':'bestaudio/best'}
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(PROBE_URL, download=False)
            return 'ok' if info and info.get('formats') else 'temporary_error'
    except Exception as error:
        message = str(error).lower()
        print(json.dumps({'probe_error_type':type(error).__name__,
                          'http_error':'http error' in message,
                          'format_error':'format' in message,
                          'timeout':'timed out' in message or 'timeout' in message}),file=sys.stderr)
        if any(part in message for part in ('sign in', 'not a bot', 'cookies have expired',
                                             'cookies are no longer valid', 'login required')):
            return 'auth_required'
        return 'temporary_error'


def transition(previous, status, now):
    """Require repeated failures; one alert and one recovery per incident."""
    state = dict(previous)
    state.update(last_checked=now, status=status)
    if status == 'ok':
        notice = 'recovered' if state.get('incident') else None
        state.update(failures=0, incident=False)
        return state, notice
    count = previous.get('failures', 0)+1 if previous.get('status') == status else 1
    state['failures'] = count
    threshold = 2 if status == 'auth_required' else 3
    notice = status if count >= threshold and not state.get('incident') else None
    if notice:
        state['incident'] = True
    return state, notice


MESSAGES = {
    'auth_required': '⚠️ SwiDJ: две проверки подряд подтвердили ограничение авторизации YouTube. Возможно, потребуется обновить cookies. Не присылай cookies в чат — сохрани приватный файл на компьютере. Остальные функции бота проверяются отдельно.',
    'temporary_error': '⚠️ SwiDJ: три проверки подряд не смогли подтвердить доступ к YouTube. Это может быть временный сбой сети или платформы; истечение cookies пока не подтверждено.',
    'recovered': '✅ SwiDJ: контрольный запрос к YouTube снова проходит успешно.',
}


def notify(token, owners, notice):
    delivered = 0
    for owner in sorted(set(owners)):
        try:
            payload = urlencode({'chat_id':owner, 'text':MESSAGES[notice]}).encode()
            request = Request('https://api.telegram.org/bot'+token+'/sendMessage', data=payload)
            with urlopen(request, timeout=15) as response:
                delivered += bool(json.load(response).get('ok'))
        except Exception:
            # Provider errors can contain the token in a URL; never print them.
            pass
    return delivered


def run(root):
    config = {}
    for line in (root/'.env').read_text(encoding='utf-8-sig').splitlines():
        key, sep, value = line.partition('=')
        if sep and key.strip() in ('TELEGRAM_TOKEN', 'OWNER_USER_IDS'):
            config[key.strip()] = value.strip().strip('"\'')
    owners = [int(value) for value in config.get('OWNER_USER_IDS', '').split(',') if value.strip().isdigit()]
    if not owners or not config.get('TELEGRAM_TOKEN'):
        print(json.dumps({'configured':False}));return
    folder = root.parent/'swidj-private'/'youtube-monitor'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_path = folder/'state.json'
    try:
        previous = json.loads(state_path.read_text())
    except (OSError, ValueError):
        previous = {}
    try:
        result = subprocess.run(['docker', 'exec', '-i', 'swidj-vps-bot-1', 'python', '-', 'probe'],
                                input=Path(__file__).read_text(encoding='utf-8'),
                                capture_output=True, text=True, timeout=50)
        data = json.loads(result.stdout) if result.returncode == 0 else {}
        status = data.get('status', 'temporary_error') if isinstance(data, dict) else 'temporary_error'
        if status not in ('ok', 'auth_required', 'temporary_error'):
            status = 'temporary_error'
    except (OSError, ValueError, subprocess.TimeoutExpired):
        status = 'temporary_error'
    current, notice = transition(previous, status, time.time())
    if notice:
        delivered = notify(config['TELEGRAM_TOKEN'], owners, notice)
        if not delivered:
            # Retry delivery on the next timer tick, not in a tight loop.
            current['incident'] = previous.get('incident', False)
    pending = folder/'state.tmp'
    pending.write_text(json.dumps(current), encoding='utf-8')
    pending.chmod(0o600)
    os.replace(pending, state_path)
    print(json.dumps({'status':status, 'confirmed_failures':current.get('failures', 0),
                      'notice_attempted':bool(notice)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('probe', 'run'))
    parser.add_argument('--root', type=Path, default=Path('/opt/swidj'))
    args = parser.parse_args()
    if args.mode == 'probe':
        print(json.dumps({'status':probe()}))
    else:
        run(args.root)
