#!/usr/bin/env python3
"""Free live retrieval -> local Telegram SDK transport -> effects/favorites.

Never polls Telegram, sends real messages, or calls recognition/payment APIs.
Use only a public URL for which downloading is authorized.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from urllib.parse import urlparse


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='Authorized public YouTube, SoundCloud or Spotify track URL')
    parser.add_argument('--rights-confirmed', action='store_true', help='Confirm permission to download this test content')
    parser.add_argument('--output', required=True, type=Path, help='New directory for retained audio, test state and report')
    args = parser.parse_args()
    parsed = urlparse(args.url)
    allowed = {'youtube.com', 'www.youtube.com', 'youtu.be', 'soundcloud.com',
               'www.soundcloud.com', 'm.soundcloud.com', 'open.spotify.com'}
    if parsed.scheme != 'https' or parsed.hostname not in allowed or parsed.username or parsed.password or parsed.port not in (None, 443):
        parser.error('Use a supported public HTTPS media URL without credentials')
    if not args.rights_confirmed:
        parser.error('--rights-confirmed is required; do not use arbitrary copyrighted test recordings')
    if args.output.exists():
        parser.error('--output must name a new directory; existing data will not be overwritten')
    return args


async def verify(args, bot, OfflineRequest, Update):
    request = OfflineRequest()
    app = bot.build_application(request=request, updates_request=OfflineRequest())
    await app.initialize()
    await bot.initialize_app(app)
    await app.start()
    try:
        user = {'id': 77, 'is_bot': False, 'first_name': 'Local verification'}
        message = {'message_id': 1, 'date': 1, 'chat': {'id': 77, 'type': 'private'}, 'from': user, 'text': args.url}
        await app.process_update(Update.de_json({'update_id': 1, 'message': message}, app.bot))
        session = app.user_data.get(77, {})
        requests = session.get('dl_requests', {})
        if not requests:
            raise RuntimeError('The URL did not produce a supported media menu')
        token = next(reversed(requests))
        async def callback(data):
            query = {'id': 'local-fixture', 'chat_instance': 'local-fixture', 'data': data,
                     'from': user, 'message': message}
            await app.process_update(Update.de_json({'update_id': 2, 'callback_query': query}, app.bot))
        await callback('dl_audio|' + token)
        source = session.get('last_audio_path')
        if not source or not Path(source).is_file():
            raise RuntimeError('Live retrieval failed: no retained audio file was produced')
        from pydub import AudioSegment
        with open(source, 'rb') as audio:
            decoded = await asyncio.to_thread(AudioSegment.from_file, audio)
        if len(decoded) <= 0:
            raise RuntimeError('Retrieved audio has no decodable duration')
        if not request.uploads or request.uploads[-1][2] != 'audio/mpeg':
            raise RuntimeError('Telegram SDK did not produce an MP3 audio upload')
        await callback('toggle_echo')
        before = sum(operation == 'sendAudio' for operation, _ in request.calls)
        await callback('apply_effects')
        if sum(operation == 'sendAudio' for operation, _ in request.calls) != before + 1:
            raise RuntimeError('Effect processing did not produce another audio upload')
        await callback('audio_favorite')
        if not bot.user_favorites.get(77):
            raise RuntimeError('Downloaded track was not saved in favorites')
        shutil.copyfile(source, args.output / 'downloaded.mp3')
        effect_bytes = request.uploads[-1][1]
        if not isinstance(effect_bytes, bytes):
            raise RuntimeError('Expected an in-memory Telegram upload payload')
        (args.output / 'echo.mp3').write_bytes(effect_bytes)
        report = {'live_retrieval': True, 'provider': urlparse(args.url).hostname,
                  'duration_ms': len(decoded), 'channels': decoded.channels,
                  'sample_rate': decoded.frame_rate, 'telegram_transport': 'local-only',
                  'mime': 'audio/mpeg', 'effect': 'echo', 'favorites': len(bot.user_favorites[77]),
                  'history_entries': len(bot.user_search_history.get(77, [])),
                  'real_messages_sent': 0, 'paid_api_calls': 0}
        (args.output / 'report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
    finally:
        await app.stop()
        await app.shutdown()


def main():
    args = arguments()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    # Isolate from all real bot credentials, data, cookies and user sessions.
    os.environ.update(PYTHON_DOTENV_DISABLED='1', TELEGRAM_TOKEN='123456:local-verification-token',
        OWNER_USER_IDS='', EXTERNAL_PAID_API_ENABLED='false', YTDLP_COOKIE_FILE='',
        STATE_DB_PATH=str(args.output / 'state.sqlite3'), USERS_DB_PATH=str(args.output / 'users.sqlite3'),
        SWIDJ_TEMP_DIR=str(args.output / 'scratch'), AUDIO_CACHE_DIR=str(args.output / 'audio'))
    with sqlite3.connect(os.environ['USERS_DB_PATH']) as db:
        db.execute('CREATE TABLE users (chat_id INTEGER PRIMARY KEY)')
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / 'tests'))
    import bot
    from telegram import Update
    from test_sdk import OfflineRequest
    try:
        asyncio.run(verify(args, bot, OfflineRequest, Update))
    except Exception as exc:
        print(json.dumps({'live_retrieval': False, 'error_type': type(exc).__name__,
                          'real_messages_sent': 0, 'paid_api_calls': 0}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
