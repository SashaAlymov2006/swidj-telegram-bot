from i18n_ui import tr
from diagnostics import classify_error
from operations import checkpoint, stage
import aiosqlite

import os
from html import escape
from urllib.parse import quote
import logging
broadcast_state = {}
from telegram import Update, BotCommand, MenuButtonCommands, InlineKeyboardButton
from ui_layout import comfortable_keyboard as InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
load_dotenv()
from access import AccessPolicy, parse_owner_ids
access_policy = AccessPolicy(parse_owner_ids(os.getenv("OWNER_USER_IDS", "")))
USERS_DB_PATH = os.getenv("USERS_DB_PATH", "data/users.sqlite3")
import requests
from bs4 import BeautifulSoup
import openai
import yt_dlp
import tempfile
from scratch import scratch_root
import subprocess
from state_store import StateStore
import asyncio
from dispatch import serialize_user
import json
import secrets
import traceback

from pydub import AudioSegment
from pydub.effects import speedup, low_pass_filter, high_pass_filter, normalize

import numpy as np
import librosa

import shutil

from pydub import AudioSegment

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# HTTP client INFO logs contain credential-bearing Telegram request URLs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

import logging

import re
# … ваши остальные import …

# Регулярное выражение для захвата YouTube-ссылок
import re

from telegram.ext import CommandHandler
import aiosqlite


async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return await update.message.reply_text("Используйте эту команду в личном чате с ботом.")
    if not access_policy.is_owner(update):
        return await update.message.reply_text("❌ У тебя нет прав использовать эту команду.")

    try:
        async with aiosqlite.connect(USERS_DB_PATH) as db:
            async with db.execute("SELECT chat_id FROM users") as cursor:
                users = [row[0] async for row in cursor]
        if not users:
            await update.message.reply_text("❌ В базе нет пользователей.")
        else:
            await reply_rows(update.message, [f"👥 В базе {len(users)} пользователей:\n"] +
                             [f"{uid}\n" for uid in users])
    except Exception as e:
        await update.message.reply_text("Не удалось прочитать список пользователей. Попробуйте ещё раз.")



USERS_FILE = "users.json"

async def save_user(chat_id: int):
    async with aiosqlite.connect(USERS_DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))
        await db.commit()

import re

def clean_filename(text: str) -> str:
    """
    Убирает мусор, запрещённые символы и лишние пробелы
    """
    text = re.sub(r'[\\/*?:"<>|]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
def clean_title(text: str) -> str:
    if not text:
        return None

    trash_patterns = [
        r"\(official.*?\)",
        r"\[official.*?\]",
        r"\(lyrics.*?\)",
        r"\[lyrics.*?\]",
        r"\(audio.*?\)",
        r"\[audio.*?\]",
        r"\(video.*?\)",
        r"\[video.*?\]",
    ]

    t = text
    for pattern in trash_patterns:
        t = re.sub(pattern, "", t, flags=re.IGNORECASE)

    return t.strip()



def check_ffmpeg():
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
    except Exception:
        raise RuntimeError("❌ ffmpeg не установлен или не доступен")



YOUTUBE_REGEX    = re.compile(
    r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[^\s]+)'
)
SOUNDCLOUD_REGEX = re.compile(
    r'(https?://(?:(?:www|m|api|on)\.)?soundcloud\.com[^\s]*)'
)
SPOTIFY_REGEX    = re.compile(
    r'(https?://open\.spotify\.com/(?:track|playlist)/[^\s]+)'
)
YANDEX_REGEX = re.compile(
    r'https?://music\.yandex\.(?:ru|com)/album/\d+/track/\d+'
)




async def broadcast_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not access_policy.is_owner(update):
        return await update.effective_message.reply_text("❌ Нет доступа.")

    broadcast_state[update.effective_user.id] = {"text": None, "media": None, "type": None}
    keyboard = [
        [InlineKeyboardButton("📝 Ввести текст", callback_data="admin_text")],
        [InlineKeyboardButton("📸 Фото", callback_data="admin_photo")],
        [InlineKeyboardButton("🎵 Аудио", callback_data="admin_audio")],
        [InlineKeyboardButton("🎥 Видео", callback_data="admin_video")],
        [InlineKeyboardButton("🎯 Разослать", callback_data="admin_send")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel")]
    ]
    await update.effective_message.reply_text("📢 Админ-панель рассылки", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not access_policy.is_owner(update):
        return await update.effective_message.reply_text("Нет доступа.")
    if update.effective_chat.type != "private":
        return await update.effective_message.reply_text("Открой панель в личном чате.")
    from owner_panel import show_panel
    await show_panel(update, context)


async def owner_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not access_policy.is_owner(update) or update.effective_chat.type != "private":
        await update.callback_query.answer("Нет доступа.", show_alert=True)
        return
    from owner_panel import handle_panel
    await handle_panel(update, context, access_policy.owner_ids, USERS_DB_PATH, broadcast_panel, cleanup_command)


def spotify_to_search_query(url: str) -> str:
    """
    Spotify работает как поисковый запрос.
    Никакого DRM, никакого скачивания Spotify.
    """
    return "ytsearch1:" + spotify_to_metadata(url)['query']


logger = logging.getLogger(__name__)

def _extract_media(options, query, directory):
    try:
        checkpoint()
        options = dict(options)
        options.setdefault("max_filesize", 49 * 1024 * 1024)
        options["progress_hooks"] = list(options.get("progress_hooks", [])) + [lambda _: checkpoint()]
        options["postprocessor_hooks"] = list(options.get("postprocessor_hooks", [])) + [lambda _: checkpoint()]
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(query, download=True)
        checkpoint()
        if isinstance(info, dict) and 'entries' in info:
            info = next((entry for entry in info.get('entries') or [] if entry), None)
        if not isinstance(info, dict) or not info:
            raise ValueError("Не найдено подходящих медиа")
        return info
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise


def download_youtube_audio(query: str):
    check_ffmpeg()
    temp_dir = tempfile.mkdtemp(dir=scratch_root(), prefix="yt_audio_")

    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "socket_timeout": 15,
        "retries": 2,
        "quiet": True,
        "cookiefile": os.getenv("YTDLP_COOKIE_FILE") or None,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    try:
        info = _extract_media(ydl_opts, query, temp_dir)

    except Exception as e:
        msg = str(e)

        # 🎯 GRACEFUL FALLBACK — ВАЖНЕЙШАЯ ЧАСТЬ
        if (
            "Sign in to confirm" in msg
            or "confirm you're not a bot" in msg
            or "cookies" in msg.lower()
        ):
            raise RuntimeError(
                "⚠️ YouTube временно ограничил доступ.\n"
                "Это не ошибка бота.\n"
                "Попробуй повторить позже или выбрать другой трек."
            )

        # все остальные ошибки — пробрасываем дальше
        raise RuntimeError(f"YouTube: ошибка загрузки ({msg})")

    # дальше код БЕЗ изменений
    if not info:
        shutil.rmtree(temp_dir)
        raise RuntimeError("YouTube: ничего не найдено")

    for f in os.listdir(temp_dir):
        if f.endswith(".mp3"):
            if os.path.getsize(os.path.join(temp_dir, f)) > 49 * 1024 * 1024:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise ValueError("Файл слишком большой. Выбери более короткий трек или меньшее качество видео.")
            return os.path.join(temp_dir, f), info

    shutil.rmtree(temp_dir)
    raise RuntimeError("YouTube: mp3 не создан")


def spotify_to_metadata(spotify_url: str) -> dict:
    r = requests.get(
        "https://open.spotify.com/oembed",
        params={"url": spotify_url},
        timeout=10
    )

    if r.status_code != 200:
        raise RuntimeError("Spotify: не удалось получить данные трека")

    data = r.json()

    title = (data.get("title") or "").strip()
    artist = (data.get("author_name") or "").strip()

    # 1️⃣ Идеальный случай
    if title and artist:
        query = f"{title} {artist}"

    # 2️⃣ Есть только title — тоже нормально
    elif title:
        query = title
        artist = None

    else:
        raise RuntimeError("Spotify не предоставил название трека; отправьте название текстом")

    return {
        "title": title,
        "artist": artist,
        "query": query,
        "cover": data.get("thumbnail_url")
    }

def yandex_to_search_query(url: str) -> str:
    return "ytsearch1:" + yandex_to_metadata(url)['query']


def yandex_to_metadata(url: str) -> dict:
    from catalog_links import classify
    if classify(url) != "yandex":
        raise ValueError("Яндекс.Музыка: нужна ссылка на отдельный трек")
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            value = json.loads(script.string or script.get_text())
        except (TypeError, ValueError):
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            if not isinstance(item, dict):
                continue
            candidates = item.get('@graph', [item])
            for track in candidates:
                if not isinstance(track, dict) or track.get('@type') != 'MusicRecording':
                    continue
                title = track.get('name')
                artists = track.get('byArtist', [])
                if isinstance(artists, dict):
                    artists = [artists]
                artist = ', '.join(a['name'] for a in artists if isinstance(a, dict) and a.get('name'))
                if title and artist:
                    return {'title': title, 'artist': artist, 'query': f'{artist} {title}'}
    raise RuntimeError("Яндекс.Музыка не предоставила название и исполнителя; отправьте их текстом")




def download_youtube_video(url: str, height: int) -> str:
    if height not in (360, 480, 720, 1080):
        raise ValueError("Unsupported video quality")
    check_ffmpeg()
    temp_dir = tempfile.mkdtemp(dir=scratch_root(), prefix="yt_video_")

    ydl_opts = {
        "format": f"bv*[height<={height}]+ba/b[height<={height}]",
        "merge_output_format": "mp4",
        "cookiefile": os.getenv("YTDLP_COOKIE_FILE") or None,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "socket_timeout": 15,
        "retries": 2,
        "quiet": True,
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4"
        }],
    }


    from catalog_links import classify
    if classify(url) in ("tiktok", "instagram"):
        ydl_opts["cookiefile"] = None
        ydl_opts["format"] = "b[ext=mp4]/b"
        ydl_opts["playlist_items"] = "1"
    _extract_media(ydl_opts, url, temp_dir)

    for f in os.listdir(temp_dir):
        if f.endswith(".mp4"):
            if os.path.getsize(os.path.join(temp_dir, f)) > 49 * 1024 * 1024:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise ValueError("Файл слишком большой. Выбери более короткий трек или меньшее качество видео.")
            return os.path.join(temp_dir, f)

    shutil.rmtree(temp_dir)
    raise RuntimeError("❌ Видео не найдено")


def extract_youtube_metadata(info: dict) -> tuple[str | None, str | None]:
    """
    Возвращает (title, artist) из yt-dlp info
    """
    if not info:
        return None, None

    title = info.get("track") or info.get("title")
    artist = info.get("artist") or info.get("uploader")

    title = clean_title(title)
    artist = clean_title(artist)

    return title, artist



def download_youtube_audio_from_video(url: str, fmt: str) -> str:
    """
    Скачивает видео через download_youtube_video, затем конвертирует его в MP3 192kbps.
    """
    video_path = download_youtube_video(url, int(fmt))
    fd, mp3_path = tempfile.mkstemp(dir=scratch_root(), suffix=".mp3")
    os.close(fd)
    from audio_tools import transcode
    try:
        transcode(video_path, mp3_path)
        return mp3_path
    finally:
        os.remove(video_path)


async def route_music_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_navigation_entry(context)
    from catalog_links import extract_links
    items = extract_links(update.effective_message.text or "")
    if not items:
        return await update.effective_message.reply_text("Пришли ссылку на отдельный музыкальный трек.")
    if len(items) > 1:
        from link_queue import create
        return await create(update, context, items)
    item = items[0]
    if item["platform"] not in ("apple", "vk", "yandex"):
        return await prompt_download_menu(update, context)
    from catalog_links import catalog_metadata
    try:
        metadata = await asyncio.to_thread(catalog_metadata, item["platform"], item["url"])
        checkpoint()
    except Exception:
        checkpoint()
        context.user_data["awaiting_catalog"] = dict(item)
        return await update.effective_message.reply_text(
            "Не удалось прочитать сведения о треке. Напиши название и исполнителя — найду доступные версии.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Меню", callback_data="ui:home")]]))
    from hashlib import sha256
    song = dict(metadata, id=-(10**15+int.from_bytes(sha256(item["url"].encode()).digest()[:6],"big")),
                url=item["url"], source=item["platform"])
    from versions import request_versions
    return await request_versions(update, context, song, mode="listen",
        automatic=(download_youtube_audio, extract_youtube_metadata, retain_audio_source, studio_command))


async def batch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    from link_queue import run, advance
    import sys
    match = re.fullmatch(r"batch:(run|skip):([0-9a-f]{10})(?::([0-9]))?", update.callback_query.data or "")
    if not match:
        return
    if match[1] == "skip" and match[3] is not None:
        return await advance(update, context, [match[2],int(match[3])], sys.modules[__name__], skipped=True)
    return await run(update, context, match[2], sys.modules[__name__])


async def batch_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from link_queue import stop
    from operations import _active
    await stop(update, context)
    if update.effective_user.id not in _active:
        await save_session(update, context)


async def prompt_download_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    from catalog_links import extract_links
    items = extract_links(text)
    if not items:
        return
    platform, url = items[0]["platform"], items[0]["url"]

    uid = update.effective_user.id
    await save_user(update.effective_chat.id)
    history = user_search_history.setdefault(uid, [])
    history.append(url)
    del history[:-MAX_HISTORY]
    await persist_user_state(uid)
    context.user_data['dl_platform'] = platform
    context.user_data['dl_url'] = url
    token = secrets.token_hex(6)
    requests_by_token = context.user_data.setdefault('dl_requests', {})
    requests_by_token[token] = {'platform': platform, 'url': url}
    if len(requests_by_token) > 20:
        requests_by_token.pop(next(iter(requests_by_token)))

    # Social video links offer video only; YouTube keeps audio and quality choices.
    if platform in ('tiktok', 'instagram'):
        buttons = [[InlineKeyboardButton("📺 Скачать видео", callback_data=f"dl_video|1080|{token}", style="primary")]]
    elif platform == 'youtube':
        buttons = [
            [InlineKeyboardButton("🎶 Аудио", callback_data=f"dl_audio|{token}")],
            [InlineKeyboardButton("📺 1080p", callback_data=f"dl_video|1080|{token}")],
            [InlineKeyboardButton("📺 720p",  callback_data=f"dl_video|720|{token}")],
            [InlineKeyboardButton("📺 480p",  callback_data=f"dl_video|480|{token}")],
            [InlineKeyboardButton("📺 360p",  callback_data=f"dl_video|360|{token}")],
        ]
    else:
        buttons = [[InlineKeyboardButton("🎶 Скачать аудио", callback_data=f"dl_audio|{token}")]]

    await update.message.reply_text(
        "Что скачать?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )




def active_media_store():
    from media_store import MediaStore
    return MediaStore(os.getenv('AUDIO_CACHE_DIR') or str(state_store.path.parent / 'audio'))


async def retain_audio_source(context, user_id, source):
    from scratch import remove_owned_file
    retained = await asyncio.to_thread(active_media_store().retain, user_id, source)
    previous = context.user_data.get('last_audio_path')
    context.user_data['last_audio_path'] = retained
    if previous and previous != retained:
        context.user_data.setdefault('_previous_audio_paths', []).append(previous)
    remove_owned_file(source)
    return retained


def download_song(platform, url, title, artist, cover=None):
    from hashlib import sha256
    return {
        "id": -(10**15 + int.from_bytes(sha256((platform + ":" + url).encode()).digest()[:6], "big")),
        "title": title or "Аудио", "artist": artist or "Исполнитель не указан",
        "url": url, "source": platform, "download_platform": platform, "cover": cover,
        "spotify_url": url if platform == "spotify" else None,
    }


async def retain_download(update, context, path, platform, url, title, artist, cover=None):
    await retain_audio_source(context, update.effective_user.id, path)
    song = download_song(platform, url, title, artist, cover)
    context.user_data["pending_effects"] = []
    context.user_data["studio_category"] = "main"
    context.user_data["downloaded_song"] = song
    user_search_results[update.effective_user.id] = [song]
    return song


async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    early_parts = query.data.split("|")
    early_action = early_parts[0] if early_parts[0] == "dl_audio" else "|".join(early_parts[:2])
    early_token = early_parts[1] if early_parts[0] == "dl_audio" and len(early_parts)>1 else (early_parts[2] if len(early_parts)>2 else None)
    previous = context.user_data.get("dl_requests",{}).get(early_token,{})
    if early_action in previous.get("delivered_actions",[]):
        return await query.answer("Этот файл уже отправлен выше.")
    await query.answer()
    platform = context.user_data.get('dl_platform')
    url      = context.user_data.get('dl_url')
    parts = query.data.split('|')
    action = parts[0] if parts[0] == 'dl_audio' else '|'.join(parts[:2])
    token = parts[1] if parts[0] == 'dl_audio' and len(parts) > 1 else (parts[2] if len(parts) > 2 else None)
    if token:
        request = context.user_data.get('dl_requests', {}).get(token)
        if not request:
            return await query.message.reply_text("Это меню устарело. Пришлите ссылку ещё раз.")
        platform, url = request['platform'], request['url']

    if not platform or not url:
        return await query.message.reply_text("❌ URL не найден.")

    if not token:
        token = secrets.token_hex(5)
        requests = context.user_data.setdefault("dl_requests", {})
        requests[token] = {"platform": platform, "url": url}
        while len(requests) > 8:
            requests.pop(next(iter(requests)))

    request = context.user_data["dl_requests"][token]

    # — АУДИО для всех платформ —
    if action == "dl_audio":
        await stage("Скачиваю…")

        title = None
        performer = None

        try:
            if platform == 'youtube':
                mp3, info = await asyncio.to_thread(download_youtube_audio, url)
                title, performer = extract_youtube_metadata(info)


            elif platform == 'soundcloud':
                data = await asyncio.to_thread(download_soundcloud_audio, url)
                mp3 = data["path"]
                title = data["title"]
                performer = data["artist"]


            elif platform == 'spotify':
                meta = await asyncio.to_thread(spotify_to_metadata, url)
                from versions import request_versions
                from hashlib import sha256
                song = dict(meta, id=-(10**15 + int.from_bytes(sha256(url.encode()).digest()[:6], "big")),
                            url=url, source="Spotify", spotify_url=url)
                return await request_versions(update, context, song)

            elif platform == 'yandex':
                meta = await asyncio.to_thread(yandex_to_metadata, url)
                from versions import request_versions
                from hashlib import sha256
                song = dict(meta, id=-(10**15 + int.from_bytes(sha256(url.encode()).digest()[:6], "big")),
                            url=url, source="Яндекс.Музыка")
                return await request_versions(update, context, song)

            else:
                raise RuntimeError("Неизвестная платформа")

            from audio_presentation import send_music
            art = None
            if platform == "youtube":
                art = info.get("thumbnail")
            elif platform == "soundcloud":
                art = data.get("cover")
            from track_card import card_keyboard, retire_download_menus
            song = download_song(platform, url, title, performer, art)
            await send_music(context.bot, query.message.chat_id, mp3, title, performer, art,
                             reply_markup=card_keyboard(context, song, delivered=True))
            request.setdefault("delivered_actions",[]).append(action)
            await retire_download_menus(update, context)
            delivered = mp3
            await retain_download(update, context, delivered, platform, url, title, performer, art)
            mp3 = None


        except Exception as e:
            if 'delivered' in locals():
                await query.message.reply_text("Аудио отправлено, но студию открыть не удалось.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎛 Открыть студию", callback_data="studio:home")]]))
            else:
                await query.message.reply_text("Не удалось скачать аудио. Можно повторить попытку.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Повторить", callback_data=f"dl_audio|{token}", style="primary")],
                        [InlineKeyboardButton("← Меню", callback_data="ui:home")]]))

        finally:
            if 'mp3' in locals() and mp3 and os.path.exists(mp3):
                from scratch import remove_owned_file
                remove_owned_file(mp3)
                if os.path.exists(mp3): os.remove(mp3)





    # — ВИДЕО только для YouTube —
    elif action.startswith("dl_video|") and platform in ("youtube", "tiktok", "instagram"):
        quality = action.split("|", 1)[1]
        if quality not in ('360', '480', '720', '1080'):
            return await query.message.reply_text("Выберите качество из меню.")
        height = int(quality)
        await stage("Скачиваю видео…" if platform in ("tiktok", "instagram") else f"Скачиваю · {height}p…")
        try:
            mp4 = await asyncio.to_thread(download_youtube_video, url, height)
            from video_presentation import probe_video
            video_metadata = await asyncio.to_thread(probe_video, mp4)
            checkpoint()
            with open(mp4, "rb") as media_file:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=media_file,
                    supports_streaming=True,
                    **video_metadata
                )
            request.setdefault("delivered_actions",[]).append(action)
            from track_card import retire_download_menus
            await retire_download_menus(update,context)
        except Exception as e:
            await query.message.reply_text(
                "Не удалось скачать видео Instagram. Проверь, что публикация открыта, и повтори." if platform == "instagram" else "Не удалось скачать видео. Повтори попытку или выбери другое качество.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Повторить", callback_data=f"dl_video|{height}|{token}", style="primary")],
                    *[[InlineKeyboardButton(f"Видео · {value}p", callback_data=f"dl_video|{value}|{token}")] for value in (360, 480, 720, 1080) if value != height and platform == "youtube"],
                    [InlineKeyboardButton("← Меню", callback_data="ui:home")]]))
        finally:
            if 'mp4' in locals() and os.path.exists(mp4):
                from scratch import remove_owned_file
                remove_owned_file(mp4)
                if os.path.exists(mp4): os.remove(mp4)

    else:
        await query.message.reply_text("❌ Неверная операция для этой платформы.")

    context.user_data.pop('dl_platform', None)
    context.user_data.pop('dl_url', None)


def download_soundcloud_audio(url: str) -> dict:
    check_ffmpeg()
    temp_dir = tempfile.mkdtemp(dir=scratch_root(), prefix="sc_audio_")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
        "socket_timeout": 15,
        "retries": 2,
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    info = _extract_media(ydl_opts, url, temp_dir)

    title = clean_title(info.get("title"))
    artist = info.get("uploader") or info.get("creator")

    # ищем mp3
    for f in os.listdir(temp_dir):
        if f.endswith(".mp3"):
            if os.path.getsize(os.path.join(temp_dir, f)) > 49 * 1024 * 1024:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise ValueError("Файл слишком большой. Выбери более короткий трек или меньшее качество видео.")
            return {
                "path": os.path.join(temp_dir, f),
                "title": title,
                "artist": artist,
                "cover": info.get("thumbnail")
            }

    shutil.rmtree(temp_dir)
    raise RuntimeError("SoundCloud: mp3 не создан")






KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
MAJOR_PROFILE = np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
MINOR_PROFILE = np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])

# Load environment variables
dotenv_path = os.getenv('DOTENV_PATH', None)
load_dotenv(dotenv_path)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GENIUS_TOKEN = os.getenv("GENIUS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AUDD_API_TOKEN = os.getenv("AUDD_API_TOKEN")
SHAZAM_API_KEY = os.getenv("SHAZAM_API_KEY")
openai.api_key = OPENAI_API_KEY

state_store = StateStore(os.getenv("STATE_DB_PATH", "data/state.sqlite3"))
user_search_results = state_store.load_named('search_results')
broadcast_state = state_store.load_named('broadcast_drafts')
saved_sessions = state_store.load_named('sessions')
user_search_history, user_favorites = state_store.load()
MAX_HISTORY = 10

# Загружаем модель Whisper один раз при старте
whisper_model = None
whisper_lock = asyncio.Lock()

async def persist_user_state(user_id):
    await asyncio.to_thread(state_store.save, user_id,
                            list(user_search_history.get(user_id, [])),
                            list(user_favorites.get(user_id, [])))

AUDIO_EFFECTS = {
    "reverb": "Псевдо-реверб",
    "speed_up": "Ускорить",
    "slow_down": "Замедлить",
    "bass_boost": "Больше баса",
    "normalize": "Нормализация",
    "pitch_up": "Повышение тона",
    "pitch_down": "Понижение тона",
    "lofi": "Lo-Fi стиль",
    "echo": "Эхо",
    "delay": "Задержка",
    "highpass": "Фильтр высоких частот",
    "lowpass": "Фильтр низких частот",
# новые «премиум»-эффекты
    "compressor":   "Компрессор",
    "equalizer":    "Эквалайзер",
    "mastering":      "🎚 Авто-мастеринг",
    "pro_reverb":  "🏢 Студийный реверб"
}

async def make_loop(update, context):
    inp = context.user_data.get('last_audio_path')
    if not inp or not os.path.exists(inp):
        return await update.callback_query.message.reply_text("❌ Нет аудио для обработки.")
    sound = await asyncio.to_thread(AudioSegment.from_file, inp)
    start = len(sound) // 2  # середина трека
    loop = sound[start:start + 10000]  # 10 секунд
    # делаем плавный заезд/съезд (фейд)
    loop = loop.fade_in(500).fade_out(500)
    tmp = tempfile.NamedTemporaryFile(dir=scratch_root(), delete=False, suffix='.mp3')
    tmp.close()
    try:
        with open(tmp.name, "wb") as output:
            await asyncio.to_thread(loop.export, output, format="mp3")
        checkpoint()
        with open(tmp.name, 'rb') as audio:
            await context.bot.send_audio(update.effective_chat.id, audio=audio, title=tr("🔂 Ваш луп"))
    finally:
        os.remove(tmp.name)

def detect_key(audio_path: str) -> str:
    y, sr = librosa.load(audio_path, sr=44100, mono=True)
    if len(y) < sr or np.max(np.abs(y)) < 1e-5:
        raise ValueError("Для анализа нужен слышимый музыкальный фрагмент длиной хотя бы секунду.")
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    dist_major = [np.corrcoef(chroma.mean(axis=1), np.roll(MAJOR_PROFILE, i))[0,1] for i in range(12)]
    dist_minor = [np.corrcoef(chroma.mean(axis=1), np.roll(MINOR_PROFILE, i))[0,1] for i in range(12)]
    maj_idx = int(np.argmax(dist_major))
    min_idx = int(np.argmax(dist_minor))
    if dist_major[maj_idx] >= dist_minor[min_idx]:
        return f"{KEYS[maj_idx]} мажор"
    else:
        return f"{KEYS[min_idx]} минор"

# Очень простая «выборка» аккордов по хроме с шагом ~0.5 с
def detect_chords(audio_path: str) -> list[str]:
    y, sr = librosa.load(audio_path, sr=44100, mono=True)
    if len(y) < sr or np.max(np.abs(y)) < 1e-5:
        raise ValueError("Для анализа нужен слышимый музыкальный фрагмент длиной хотя бы секунду.")
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    # создаём шаблоны мажорных и минорных трезвучий
    MAJ = np.array([1,0,0,0,1,0,0,1,0,0,0,0])
    MIN = np.array([1,0,0,1,0,0,0,1,0,0,0,0])
    chords = []
    hop = max(1, round(0.5 * sr / 512))  # ~0.5 сек в кадрах
    for i in range(0, chroma.shape[1], hop):
        vec = chroma[:, i]
        best = None
        best_score = -1
        for shift in range(12):
            # мажор
            tpl = np.roll(MAJ, shift)
            score = np.dot(vec, tpl)
            if score > best_score:
                best_score, best = score, f"{KEYS[shift]}maj"
            # минор
            tpl = np.roll(MIN, shift)
            score = np.dot(vec, tpl)
            if score > best_score:
                best_score, best = score, f"{KEYS[shift]}min"
        chords.append(best)
    # сжимаем повторяющиеся
    prog = [chords[0]] if chords else []
    for c in chords[1:]:
        if c != prog[-1]:
            prog.append(c)
    return prog
def reverse_audio(input_path: str, output_path: str):
    from audio_tools import transcode
    transcode(input_path, output_path, audio_filter='areverse')


def pitch_shift(input_path: str, output_path: str, semitones: int):
    from audio_tools import transcode
    if not -24 <= semitones <= 24:
        raise ValueError("Выберите сдвиг от -24 до 24 полутонов.")
    ratio = 2 ** (semitones / 12)
    tempo = 1 / ratio
    factors = []
    while tempo < 0.5:
        factors.append('atempo=0.5');tempo /= 0.5
    while tempo > 2:
        factors.append('atempo=2');tempo /= 2
    factors.append(f'atempo={tempo}')
    transcode(input_path, output_path, audio_filter=f'aresample=44100,asetrate={44100*ratio},aresample=44100,' + ','.join(factors))

# Новая функция: клавиатура мультивыбора эффектов
def build_multiselect_keyboard(selected_effects, song=None, category="main"):
    from studio_ui import keyboard
    return keyboard(AUDIO_EFFECTS, selected_effects, song, category)


async def studio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_navigation_entry(context)
    from studio_ui import show_studio
    await show_studio(update, context, AUDIO_EFFECTS)


async def studio_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from studio_ui import handle_studio
    await handle_studio(update, context, AUDIO_EFFECTS)


async def quick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from quick_studio import handle_quick
    return await handle_quick(update, context)


async def trim_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from studio_ui import trim_command as trim
    await trim(update, context)

# Новый хэндлер: приём любого аудиофайла с предложением эффектов
async def handle_user_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if access_policy.is_owner(update) and context.user_data.get('awaiting_media_type'):
        return await handle_admin_media(update, context)
    chat_id = update.effective_chat.id
    await save_user(chat_id)
    file_obj = update.message.audio or update.message.document or update.message.voice
    if not file_obj:
        await update.message.reply_text("❌ Пожалуйста, пришлите аудиофайл или голосовое сообщение.")
        return
    if getattr(file_obj, 'file_size', 0) and file_obj.file_size > 20 * 1024 * 1024:
        return await update.message.reply_text("Пришлите аудио до 20 МБ или более короткий фрагмент.")
    # Сохраняем файл локально
    file = await context.bot.get_file(file_obj.file_id)
    with tempfile.NamedTemporaryFile(dir=scratch_root(), delete=False, suffix='.mp3') as tmp:
        path = tmp.name
    try:
        await file.download_to_drive(path)
    except BaseException:
        os.remove(path)
        raise
    try:
        await retain_audio_source(context, update.effective_user.id, path)
    except BaseException:
        if os.path.exists(path):
            os.remove(path)
        raise
    from uploaded_media import register_upload
    song = register_upload(update, context, file_obj, context.user_data['last_audio_path'])
    context.user_data['downloaded_song'] = song
    context.user_data['audio_update'] = update
    context.user_data['pending_effects'] = []
    context.user_data['studio_category'] = 'main'
    if context.user_data.pop("open_studio_on_upload", False):
        return await studio_command(update, context)
    from track_card import show_card
    await show_card(update, context, song, extra_rows=[
        [InlineKeyboardButton("⭐ Моя музыка", callback_data="lib:home")]])



# Синхронная функция применения одного эффекта
def upgrade_audio(input_path: str, output_path: str, effect: str):
    from audio_tools import effect as process_effect
    process_effect(input_path, output_path, effect)

# Асинхронная-обёртка для применения
async def apply_audio_effect(effect: str, input_path: str, output_path: str) -> bool:
    try:
        await asyncio.to_thread(upgrade_audio, input_path, output_path, effect)
        return True
    except Exception as e:
        logger.error(f"Error applying effect {effect}: {e}")
        return False




NAVIGATION_COMMANDS = [
    ("menu", "🏠 Главное меню"),
    ("search", "🔎 Найти песню"),
    ("favorites", "⭐ Моя музыка"),
    ("studio", "🎛 Студия · ремикс и рингтон"),
    ("help", "❓ Как пользоваться"),
    ("cancel", "✕ Отменить действие"),
    ("start", "🎧 Начать"),
    ("language", "🌐 Язык"),
]


def clear_navigation_entry(context):
    for key in ("awaiting_catalog", "awaiting_ringtone", "awaiting_trim", "awaiting_collection_name",
                "awaiting_pitch", "awaiting_owner_action", "awaiting_playlist_rename",
                "new_collection_song", "new_playlist_move_from", "awaiting_broadcast_text", "awaiting_media_type"):
        context.user_data.pop(key, None)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_navigation_entry(context)
    await update.effective_message.reply_text("🔎 Как ищем?", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("По названию", callback_data="ui:title"),
         InlineKeyboardButton("По словам", callback_data="ui:lyrics")],
        [InlineKeyboardButton("🕘 История", callback_data="ui:history"),
         InlineKeyboardButton("← Меню", callback_data="ui:home")]]))


def home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 Найти песню", callback_data="ui:search", style="primary"),
         InlineKeyboardButton("🎙 Голосом", callback_data="ui:recognize")],
        [InlineKeyboardButton("🎛 Студия", callback_data="ui:audio"),
         InlineKeyboardButton("⭐ Моя музыка", callback_data="ui:favorites", style="success")],
        [InlineKeyboardButton("❓ Помощь", callback_data="ui:help")],
        [InlineKeyboardButton("🌐 Язык / Language", callback_data="lang:choose")],
    ])


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_navigation_entry(context)
    keyboard = home_keyboard()
    if access_policy.is_owner(update):
        keyboard = InlineKeyboardMarkup(list(keyboard.inline_keyboard) + [
            [InlineKeyboardButton("⚙ Панель владельца", callback_data="owner:home")]])
    text = "🎧 <b>SwiDJ</b>\nТвоя музыка. Твой микс."
    if update.callback_query and update.callback_query.message.text:
        return await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    return await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_navigation_entry(context)
    await update.effective_message.reply_text(
        "✨ <b>SwiDJ · музыка рядом</b>\n\n"
        "🔎 Напиши название песни или её слова.\n"
        "🎙 Отправь голосовое — попробуем найти песню.\n\n"
        "🎵 Музыка по ссылке: Spotify, Apple Music, Яндекс Музыка, YouTube и SoundCloud.\n"
        "📺 Видео по ссылке: YouTube, TikTok и Instagram, включая Reels и клипы.\n\n"
        "🎛 Пришли аудио — обрежь его или добавь эффекты.\n"
        "⭐ Сохраняй любимое в «Мою музыку» и плейлисты.",
        parse_mode="HTML", reply_markup=home_keyboard())


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    action = update.callback_query.data
    if action != "ui:help":
        for key in ("awaiting_catalog", "awaiting_ringtone", "awaiting_trim", "awaiting_collection_name", "awaiting_pitch", "awaiting_owner_action", "awaiting_playlist_rename", "new_collection_song", "new_playlist_move_from"):
            context.user_data.pop(key, None)
    if action == "ui:help":
        return await help_command(update, context)
    if action == "ui:home":
        return await menu_command(update, context)
    if action == "ui:favorites":
        return await favorites_command(update, context)
    if action == "ui:history":
        return await history_command(update, context)
    if action == "ui:audio":
        return await studio_command(update, context)
    if action == "ui:search":
        return await search_command(update, context)
    if action in ("ui:title", "ui:lyrics"):
        context.user_data["search_mode"] = "lyrics" if action == "ui:lyrics" else "title"
        prompt = "Напиши строку из песни." if action == "ui:lyrics" else "Название или исполнитель?"
    else:
        prompt = "🎙 Пришли голосовое со словами песни."
    await update.effective_message.reply_text(prompt, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("← Меню", callback_data="ui:home")]]))


async def cancel_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from operations import cancel
    if cancel(update.effective_user.id):
        return await update.effective_message.reply_text("Отменяю…")
    return await serialize_user(cancel_command)(update, context)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for key in ("awaiting_catalog", "awaiting_ringtone", "awaiting_pitch", "awaiting_broadcast_text", "awaiting_media_type",
                "pending_transcript", "dl_platform", "dl_url", "dl_requests", "awaiting_collection_name", "awaiting_trim", "awaiting_owner_action", "awaiting_playlist_rename", "new_collection_song", "new_playlist_move_from"):
        context.user_data.pop(key, None)
    await update.effective_message.reply_text("Ввод отменён.")
    await menu_command(update, context)

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:set:ru"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang:set:en")]])
    text = "🌐 Выбери язык / Choose your language"
    query = update.callback_query
    if query:
        await query.answer()
        return await query.edit_message_text(text, reply_markup=keyboard)
    return await update.effective_message.reply_text(text, reply_markup=keyboard)


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query.data == "lang:choose":
        return await language_command(update, context)
    await update.callback_query.answer()
    language = update.callback_query.data.rsplit(":", 1)[-1]
    if language not in ("ru", "en"):
        return
    context.user_data["language"] = language
    from i18n_ui import locale, english
    locale.set(language)
    # The chosen UI language also controls the native command popup in private chats.
    if update.effective_chat.type == "private":
        from telegram import BotCommandScopeChat
        from telegram.error import TelegramError
        commands = [BotCommand(command, english(description, protect=False) if language == "en" else description)
                    for command, description in NAVIGATION_COMMANDS]
        try:
            await context.bot.set_my_commands(commands, scope=BotCommandScopeChat(update.effective_chat.id))
        except TelegramError as exc:
            logger.warning("User command language setup failed (%s)", type(exc).__name__)
    return await menu_command(update, context)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(update.effective_chat.id)
    if context.user_data.get("language") not in ("ru", "en"):
        return await update.effective_message.reply_text(
            "🎧 <b>SwiDJ</b>\nТвоя музыка. Твой микс.\n\nВыбери язык / Choose your language",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:set:ru"),
                 InlineKeyboardButton("🇬🇧 English", callback_data="lang:set:en")]]))
    await menu_command(update, context)

# Функции клавы
def build_effects_keyboard():
    buttons = []
    for key, label in AUDIO_EFFECTS.items():
        buttons.append([InlineKeyboardButton(label, callback_data=f"effect_{key}")])
    return InlineKeyboardMarkup(buttons)

async def handle_audio_enhancement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await save_user(chat_id)
    query = update.callback_query
    await query.message.reply_text("Начинаю обработку, подождите…")
    path = context.user_data.get('last_audio_path')
    effect = query.data.replace("effect_", "")
    if not path or not os.path.exists(path):
        await query.message.reply_text("Нет аудио для обработки. Пришлите файл ещё раз.")
        return
    with tempfile.NamedTemporaryFile(dir=scratch_root(), delete=False, suffix='.mp3') as tmp:
        out_path = tmp.name
    try:
        if await apply_audio_effect(effect, path, out_path):
            checkpoint()
            with open(out_path, 'rb') as audio:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id, audio=audio,
                    title=f"Эффект: {AUDIO_EFFECTS.get(effect, effect)}")
        else:
            await query.message.reply_text("❌ Ошибка при применении эффекта.")
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)

# Хандлеры
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Update failed (%s; category=%s)", type(context.error).__name__, classify_error(context.error))
    if update and update.effective_message:
        await update.effective_message.reply_text("Не удалось выполнить запрос. Попробуйте ещё раз.")

async def reply_rows(message, rows, **kwargs):
    chunk = ""
    for row in rows:
        if len(chunk) + len(row) > 3500 and chunk:
            await message.reply_text(chunk, **kwargs)
            chunk = ""
        chunk += row
    if chunk:
        await message.reply_text(chunk, **kwargs)


def merge_catalog_results(*groups, query=""):
    from search_quality import merge_results
    return merge_results(groups, query)



def _search_songs_sync(query):
    headers = {"Authorization": f"Bearer {GENIUS_TOKEN}"}
    params = {"q": query}
    try:
        response = requests.get("https://api.genius.com/search", headers=headers, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        hits = data.get("response", {}).get("hits", [])
        songs = []
        for hit in hits[:10]:
            song = hit.get("result") or {}
            if (not isinstance(song.get('id'), int) or not song.get('title')
                    or not (song.get('primary_artist') or {}).get('name') or not song.get('url')):
                continue
            songs.append({
                "title": song.get("title"),
                "artist": song.get("primary_artist", {}).get("name"),
                "url": song.get("url"),
                "id": song.get("id"),
                "source": "Genius",
                "cover": song.get("song_art_image_url"),
                "spotify_url": None
            })
        # Preserve Spotify buttons while bounding detail lookup concurrency.
        from concurrent.futures import ThreadPoolExecutor
        def enrich(song):
            try:
                detail = requests.get(f"https://api.genius.com/songs/{song['id']}", headers=headers, timeout=5)
                detail.raise_for_status()
                media = detail.json()['response']['song'].get('media') or []
                song['spotify_url'] = next((m.get('url') for m in media
                                             if m.get('provider') == 'spotify'), None)
            except Exception:
                pass
            return song
        with ThreadPoolExecutor(max_workers=4) as pool:
            songs = list(pool.map(enrich, songs))
        return songs
    except Exception:
        return []



async def search_songs(query):
    return await asyncio.to_thread(_search_songs_sync, query)

def _get_lyrics_sync(song_url):
    try:
        page = requests.get(song_url, timeout=5)
        if page.status_code != 200:
            return None
        soup = BeautifulSoup(page.text, "html.parser")
        lyrics_divs = soup.select('[data-lyrics-container="true"]') or soup.find_all(
            "div", class_=lambda x: x and "Lyrics__Container" in x)
        lyrics = "\n".join(div.get_text(separator="\n") for div in lyrics_divs if div)
        return lyrics.strip() if lyrics else "Не удалось получить текст песни."
    except Exception:
        return "Ошибка при получении текста песни."



async def get_lyrics(song_url):
    return await asyncio.to_thread(_get_lyrics_sync, song_url)

def _generate_comment_sync(title, artist):
    prompt = f"Дай короткое и интересное пояснение к песне '{title}' исполнителя {artist}."
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.7,
            request_timeout=15,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Комментарий недоступен."



async def generate_comment(title, artist):
    if os.getenv("EXTERNAL_PAID_API_ENABLED", "false").lower() != "true":
        return 'Комментарий недоступен.'
    return await asyncio.to_thread(_generate_comment_sync, title, artist)

def build_keyboard(songs, index, song):
    navigation = []
    if index:
        navigation.append(InlineKeyboardButton("← Назад", callback_data=f"prev_{index - 1}"))
    if index + 1 < len(songs):
        navigation.append(InlineKeyboardButton("Следующий →", callback_data=f"next_{index + 1}"))
    rows = [navigation] if navigation else []
    rows += [
        [InlineKeyboardButton("🎧 Скачать", callback_data=f"download_{song['id']}", style="primary"),
         InlineKeyboardButton("＋ Сохранить", callback_data=f"fav_{song['id']}", style="success")],
        [InlineKeyboardButton("📄 Текст песни", callback_data=f"lyrics_{song['id']}"),
         InlineKeyboardButton("🎛 В студию", callback_data=f"enhance_{song['id']}")],
    ]
    links = []
    if song.get("spotify_url"):
        links.append(InlineKeyboardButton("Spotify", url=song["spotify_url"]))
    links.append(InlineKeyboardButton("Поделиться", url="https://t.me/share/url?url=" + quote(song["url"], safe="")))
    rows.append(links)
    rows.append([InlineKeyboardButton("🔎 Новый поиск", callback_data="ui:search"),
                 InlineKeyboardButton("← Меню", callback_data="ui:home")])
    return InlineKeyboardMarkup(rows)


async def send_song(update: Update, context: ContextTypes.DEFAULT_TYPE, index=0, search_token=None):
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        chat_id = update.callback_query.message.chat_id
    else:
        user_id = update.effective_user.id
        chat_id = update.message.chat_id

    pages = context.user_data.setdefault("search_pages", {})
    if search_token:
        songs = pages.get(search_token, [])
    else:
        songs = user_search_results.get(user_id, [])
        search_token = secrets.token_hex(5)
        pages[search_token] = [dict(song) for song in songs]
        while len(pages) > 5:
            pages.pop(next(iter(pages)))
    if not songs or index < 0 or index >= len(songs):
        if update.callback_query:
            await update.callback_query.answer("Больше вариантов нет.", show_alert=True)
        else:
            await update.message.reply_text("Больше вариантов нет.")
        return

    song = dict(songs[index], _search_page=[search_token,index])
    from track_card import show_card
    extra = [[InlineKeyboardButton("← Меню", callback_data="ui:home")]]
    from library_ui import collections, all_saved
    folders = await collections(context, user_id, state_store)
    saved = any(item["id"] == song["id"] for item in all_saved(user_id, user_favorites, folders))
    return await show_card(update, context, song, saved=saved, extra_rows=extra)


async def search_result_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    match = re.fullmatch(r"srch:([0-9a-f]{10}):([0-9]{1,2})", update.callback_query.data or "")
    if match:
        return await send_song(update, context, int(match[2]), search_token=match[1])


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    await save_user(chat_id)
    user_id = update.effective_user.id

    if context.user_data.get("awaiting_catalog"):
        request = context.user_data.pop("awaiting_catalog")
        from hashlib import sha256
        song = {"id":-(10**15+int.from_bytes(sha256(request["url"].encode()).digest()[:6],"big")),
                "title":query[:240],"artist":"","url":request["url"],"source":request["platform"]}
        reference = request.get("queue_ref")
        if reference:
            from link_queue import current
            if not current(context,*reference):
                return await update.effective_message.reply_text("Очередь уже завершена или отменена.")
        from versions import request_versions
        return await request_versions(update,context,song,mode="queue" if reference else "listen",queue_ref=reference)

    if context.user_data.get("awaiting_owner_action"):
        if not access_policy.is_owner(update):
            context.user_data.pop("awaiting_owner_action", None)
            return await update.effective_message.reply_text("Нет доступа.")
        from owner_panel import accept_owner_input
        return await accept_owner_input(update, context, access_policy.owner_ids)

    if context.user_data.get("awaiting_ringtone"):
        from quick_studio import accept_time
        return await accept_time(update, context, query)

    if context.user_data.get("awaiting_trim"):
        from studio_tools import timestamp
        from studio_ui import deliver_export
        try:
            values = query.split()
            if len(values) != 2:
                raise ValueError("Два времени, например: 0:10 0:30")
            start, end = (timestamp(value) for value in values)
            if end - start > 600:
                raise ValueError("Выбери фрагмент до 10 минут.")
            await deliver_export(update, context, start=start, end=end, label="Фрагмент")
            context.user_data.pop("awaiting_trim", None)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
        return

    if context.user_data.get("awaiting_playlist_rename"):
        from library_ui import rename_playlist
        return await rename_playlist(update, context, state_store, query)

    if context.user_data.get("awaiting_collection_name"):
        from library_ui import create_collection
        return await create_collection(update, context, state_store, query, user_favorites)

    # Если ожидается текст для рассылки
    if context.user_data.get("awaiting_broadcast_text"):
        broadcast_state[user_id]["text"] = update.message.text
        context.user_data.pop("awaiting_broadcast_text")
        await update.message.reply_text("✅ Текст сохранён.")
        return

    # Если мы ждём от пользователя число полутонов — применяем его
    if context.user_data.get('awaiting_pitch'):
        try:
            semis = int(update.message.text.strip())
        except ValueError:
            return await update.message.reply_text("❌ Введите целое число полутонов.")
        if not -24 <= semis <= 24:
            return await update.message.reply_text("Выберите сдвиг от -24 до 24 полутонов.")
        inp = context.user_data.get('last_audio_path')
        if not inp or not os.path.exists(inp):
            context.user_data.pop("awaiting_pitch", None)
            return await update.message.reply_text("❌ Ошибка: исходное аудио не найдено.")
        # создаём выходной файл
        out = tempfile.NamedTemporaryFile(dir=scratch_root(), delete=False, suffix='.mp3').name
        try:
            await asyncio.to_thread(pitch_shift, inp, out, semis)
            checkpoint()
            with open(out, 'rb') as audio:
                await update.message.reply_audio(
                    audio=audio, title=f"Тональность сдвинута на {semis} полутонов")
        finally:
            if os.path.exists(out):
                os.remove(out)
        context.user_data.pop("awaiting_pitch", None)
        return

    if not query:
        return await update.message.reply_text("Напиши название или фрагмент песни.")

    context.user_data.pop('pending_transcript', None)

    # Сохраняем в историю
    history = user_search_history.get(user_id, [])
    history.append(query)
    if len(history) > MAX_HISTORY:
        history.pop(0)
    user_search_history[user_id] = history
    await persist_user_state(user_id)

    await stage("Ищу…")

    if context.user_data.get("search_mode") == "lyrics":
        from lyrics_search import search_lyrics
        songs = await search_lyrics(query, search_songs, search_deezer, get_lyrics)
    else:
        genius, deezer = await asyncio.gather(search_songs(query), search_deezer(query))
        songs = merge_catalog_results(genius, deezer, query=query)
    checkpoint()
    if not songs:
        await update.message.reply_text("❌ Не удалось найти песню. Попробуй другой фрагмент.")
        return

    user_search_results[user_id] = songs
    await send_song(update, context, index=0)

    # Текст для рассылки
    if context.user_data.get("awaiting_broadcast_text"):
        broadcast_state[user_id]["text"] = update.message.text
        context.user_data.pop("awaiting_broadcast_text")
        await update.message.reply_text("✅ Текст сохранён.")
        return

async def handle_admin_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not access_policy.is_owner(update):
        return

    media_type = context.user_data.get("awaiting_media_type")
    if not media_type:
        return

    if media_type == "photo" and update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif media_type == "audio" and update.message.audio:
        file_id = update.message.audio.file_id
    elif media_type == "video" and update.message.video:
        file_id = update.message.video.file_id
    else:
        return await update.message.reply_text("❌ Неверный тип файла.")

    broadcast_state[user_id]["media"] = file_id
    broadcast_state[user_id]["type"] = media_type
    context.user_data.pop("awaiting_media_type")
    await update.message.reply_text(f"✅ {media_type.capitalize()} сохранён.")



def ogg_to_wav(input_path, output_path):
    command = [
        "ffmpeg",
        "-i", input_path,
        "-ar", "16000",  # Частота, подходящая для Whisper
        "-ac", "1",  # Моно звук
        "-acodec", "pcm_s16le",  # PCM 16-bit формат
        output_path,
        "-y"
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=120)

def _recognize_song_shazam_sync(file_path: str):
    """Новая функция для распознавания через Shazam"""
    try:
        with open(file_path, 'rb') as audio_file:
            headers = {
                'X-RapidAPI-Key': SHAZAM_API_KEY,
                'X-RapidAPI-Host': 'shazam.p.rapidapi.com'
            }
            response = requests.post(
                "https://shazam.p.rapidapi.com/songs/detect",
                headers=headers,
                files={'upload_file': audio_file},
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            if not data.get('matches'):
                return None

            track = data.get('track', {})
            return {
                "title": track.get("title"),
                "artist": track.get("subtitle"),
                "url": track.get("url"),
                "image": track.get("images", {}).get("coverart"),
                "audio": next((action.get("uri") for action in track.get("hub", {}).get("actions", []) if
                               action.get("type") == "uri"), None)
            }
    except Exception as e:
        logger.warning("Shazam failed (%s)", type(e).__name__)
        return None


async def recognize_song_shazam(file_path: str):
    if os.getenv("EXTERNAL_PAID_API_ENABLED", "false").lower() != "true":
        return None
    return await asyncio.to_thread(_recognize_song_shazam_sync, file_path)

def _recognize_song_by_audio_sync(wav_file_path):
    try:
        with open(wav_file_path, "rb") as f:
            files = {'file': f}
            data = {
                'api_token': AUDD_API_TOKEN,
                'return': 'timecode,apple_music,spotify,deezer',
            }

            response = requests.post(
                "https://api.audd.io/",
                data=data,
                files=files,
                timeout=30  # Увеличил таймаут
            )

            # Проверяем HTTP статус
            if response.status_code != 200:
                logger.warning("AudD HTTP error: %s", response.status_code)
                return None

            result = response.json()
            # Provider responses may contain account details; do not log raw bodies.

            # Проверяем статус ответа API
            if result.get('status') != 'success':
                error_msg = result.get('error', {}).get('error_message', 'Unknown API error')
                logger.warning("AudD rejected the request")
                return None

            # Проверяем наличие результата
            if not result.get('result'):
                print("Audd.io: No recognition result")
                return None

            song = result['result']
            title = song.get('title')
            artist = song.get('artist')

            # Безопасно извлекаем ссылки
            spotify_url = None
            apple_url = None
            deezer_url = None

            if 'spotify' in song:
                spotify_url = ((song['spotify'] or {}).get('external_urls') or {}).get('spotify')

            if 'apple_music' in song:
                apple_url = (song['apple_music'] or {}).get('url')

            if 'deezer' in song:
                deezer_url = (song['deezer'] or {}).get('link')

            return {
                'title': title,
                'artist': artist,
                'spotify_url': spotify_url,
                'apple_url': apple_url,
                'deezer_url': deezer_url,
            }

    except requests.exceptions.RequestException as e:
        logger.warning("AudD request failed (%s)", type(e).__name__)
        return None
    except Exception as e:
        logger.warning("AudD response invalid (%s)", type(e).__name__)
        return None


async def recognize_song_by_audio(wav_file_path):
    if os.getenv("EXTERNAL_PAID_API_ENABLED", "false").lower() != "true":
        return None
    return await asyncio.to_thread(_recognize_song_by_audio_sync, wav_file_path)

async def recognize_by_whisper(wav_path):
    global whisper_model
    try:
        async with whisper_lock:
            if whisper_model is None:
                import whisper
                whisper_model = await asyncio.to_thread(
                    whisper.load_model, os.getenv("WHISPER_MODEL", "medium"))
            result = await asyncio.to_thread(whisper_model.transcribe, wav_path, fp16=False)
        text = (result.get("text") or "").strip()
        return text
    except Exception as e:
        logger.warning("Transcription failed (%s)", type(e).__name__)
        return None


def _recognize_by_gpt_hint_sync(text_snippet):
    prompt = (
        f"Это фрагмент напевания или текста песни:\n\"{text_snippet}\"\n"
        "Можешь предположить, какая это песня? Ответь кратко: название и исполнитель."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.7,
            request_timeout=15,
        )
        answer = response.choices[0].message.content.strip()
        return answer
    except Exception as e:
        logger.warning("OpenAI failed (%s)", type(e).__name__)
        return None



async def recognize_by_gpt_hint(text_snippet):
    if os.getenv("EXTERNAL_PAID_API_ENABLED", "false").lower() != "true":
        return None
    return await asyncio.to_thread(_recognize_by_gpt_hint_sync, text_snippet)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE, local_path=None, words_only=False):
    from audio_tools import recognition_clip
    from recognition_flow import identify
    message = update.effective_message
    voice = None if local_path else (message.voice or message.audio or message.document)
    if not local_path and not voice:
        return await message.reply_text("Пришлите аудио или голосовое сообщение.")
    if getattr(voice, 'file_size', 0) and voice.file_size > 10 * 1024 * 1024:
        return await message.reply_text("Для распознавания пришлите фрагмент до 10 МБ, лучше 8–12 секунд.")
    await save_user(update.effective_chat.id)
    with tempfile.TemporaryDirectory(dir=scratch_root(), prefix='swidj_recognition_') as directory:
        source = local_path or os.path.join(directory, 'source.audio')
        clip = os.path.join(directory, 'clip.wav')
        try:
            await stage("Слушаю…")
            if not local_path:
                file = await context.bot.get_file(voice.file_id)
                await file.download_to_drive(source)
            await asyncio.to_thread(recognition_clip, source, clip)
            result, attempts = (None, []) if words_only else await identify(clip, [
                ('Shazam', recognize_song_shazam), ('AudD', recognize_song_by_audio)])
            if result:
                context.user_data['recognized_song'] = result
                buttons = [[InlineKeyboardButton('🎧 Найти аудио трека', callback_data='recognized_download')]]
                for key, label in [('url', 'Источник'), ('spotify_url', 'Spotify'),
                                   ('apple_url', 'Apple Music'), ('deezer_url', 'Deezer')]:
                    link = result.get(key)
                    if isinstance(link, str) and link.startswith('https://'):
                        buttons.append([InlineKeyboardButton(label, url=link)])
                return await message.reply_text(
                    f"🎵 Найдено совпадение: {result['title']} — {result['artist']}",
                    reply_markup=InlineKeyboardMarkup(buttons))
            await stage("Разбираю слова…")
            text = await recognize_by_whisper(clip)
            checkpoint()
            if not text:
                return await message.reply_text("Не разобрал слова. Пришли запись чётче или напиши текст.")
            context.user_data['pending_transcript'] = text[:1500]
            await message.reply_text(
                f"📝 {text[:1500]}\n\nИскать по этим словам?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔎 Искать", callback_data="voice_search_words"),
                     InlineKeyboardButton("Исправить", callback_data="voice_edit_words")],
                    [InlineKeyboardButton("← Главное меню", callback_data="ui:home")]]))
        except ValueError as exc:
            await message.reply_text(str(exc))
        except Exception as exc:
            logger.warning('Recognition failed (%s)', type(exc).__name__)
            await message.reply_text("Не удалось обработать запись. Попробуйте ещё раз или пришлите другой аудиофайл.")


async def voice_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['voice_update'] = update
    context.user_data.pop('pending_transcript', None)
    from uploaded_media import register_upload
    uploaded = register_upload(update, context, update.effective_message.voice)
    rows = [[InlineKeyboardButton("🔎 Найти по словам", callback_data="voice_words")],
            [InlineKeyboardButton("🎛 Эффекты", callback_data="voice_effects")]]
    if os.getenv("EXTERNAL_PAID_API_ENABLED", "false").lower() == "true":
        rows.insert(0, [InlineKeyboardButton("🎵 Узнать песню", callback_data="voice_recognize")])
    rows.append([InlineKeyboardButton("＋ Сохранить", callback_data=f"upload:save:{uploaded['id']}", style="success")])
    rows.append([InlineKeyboardButton("← Меню", callback_data="ui:home")])
    await update.message.reply_text("🎙 Что сделать?", reply_markup=InlineKeyboardMarkup(rows))


async def voice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if update.callback_query.data == "voice_edit_words":
        context.user_data["search_mode"] = "lyrics"
        context.user_data.pop("pending_transcript", None)
        return await update.effective_message.reply_text("Напиши правильные слова.")
    if update.callback_query.data == 'voice_search_words':
        text = context.user_data.pop('pending_transcript', None)
        if not text:
            return await update.effective_message.reply_text("Расшифровка устарела. Пришли новое голосовое.")
        await stage("Ищу по словам…")
        from lyrics_search import search_lyrics
        songs = await search_lyrics(text, search_songs, search_deezer, get_lyrics)
        if not songs:
            return await update.effective_message.reply_text("Совпадение не найдено. Исправь слова или пришли другой фрагмент.")
        user_search_results[update.effective_user.id] = songs
        return await send_song(update, context, 0)
    if update.callback_query.data == 'audio_recognize' and context.user_data.get('downloaded_song'):
        path = context.user_data.get('last_audio_path')
        if not path or not os.path.isfile(path):
            return await update.effective_message.reply_text("Исходник недоступен. Скачайте трек по ссылке ещё раз.")
        return await handle_voice(update, context, local_path=path, words_only=os.getenv("EXTERNAL_PAID_API_ENABLED", "false").lower() != "true")
    source = context.user_data.get('audio_update' if update.callback_query.data == 'audio_recognize' else 'voice_update')
    if source is None:
        return await update.effective_message.reply_text("Пришлите голосовое сообщение ещё раз.")
    if update.callback_query.data == "voice_effects":
        context.user_data["open_studio_on_upload"] = True
        await handle_user_audio(source, context)
    else:
        await handle_voice(source, context, words_only=update.callback_query.data == "voice_words")


async def send_audd_result(update: Update, result: dict):
    """Отправка результата от Audd.io"""
    title = result.get('title', 'Неизвестно')
    artist = result.get('artist', 'Неизвестно')

    buttons = []
    if result.get('spotify_url'):
        buttons.append([InlineKeyboardButton("Spotify 🎧", url=result['spotify_url'])])
    if result.get('apple_url'):
        buttons.append([InlineKeyboardButton("Apple Music 🍏", url=result['apple_url'])])
    if result.get('deezer_url'):
        buttons.append([InlineKeyboardButton("Deezer 🎵", url=result['deezer_url'])])

    await update.message.reply_text(
        f"✅ Распознано:\n<b>{title}</b> — {artist}",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
    )


def _search_deezer_sync(query: str):
    """Поиск через Deezer API"""
    try:
        response = requests.get(
            "https://api.deezer.com/search",
            params={'q': query, 'limit': 5},
            timeout=10
        )
        data = response.json()
        return [{
            'title': item['title'],
            'artist': item['artist']['name'],
            'url': item['link'],
            'id': -int(item['id']),
            'source': 'Deezer',
            'cover': (item.get('album') or {}).get('cover_medium'),
            'deezer_url': item['link']
        } for item in data.get('data', [])
          if isinstance(item, dict) and isinstance(item.get('id'), int)
          and item.get('title') and (item.get('artist') or {}).get('name') and item.get('link')]
    except Exception:
        return []


async def search_deezer(query: str):
    return await asyncio.to_thread(_search_deezer_sync, query)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    user_id = query.from_user.id
    if not isinstance(data, str) or len(data) > 64:
        return await query.message.reply_text('Кнопка недоступна. Повторите запрос.')
    if data.startswith(('next_', 'prev_', 'lyrics_', 'download_', 'fav_', 'enhance_')) and not re.fullmatch(r'(next|prev|lyrics|download|fav|enhance)_-?\d+', data):
        return await query.message.reply_text('Некорректная кнопка. Повторите поиск.')

    if data == "fx:preview":
        from effect_preview import preview_effects
        return await preview_effects(update, context)
    if data.startswith("fx:apply:"):
        from effect_preview import accept_preview
        if not accept_preview(context, data.rsplit(":", 1)[-1]):
            return await query.message.reply_text("Эффекты изменились. Послушай новый пример.")
        data = "apply_effects"

    if data == "audio_favorite":
        song = context.user_data.get('downloaded_song')
        if not song:
            return await query.message.reply_text("Сначала выбери трек.")
        from library_ui import save_song
        return await save_song(update, context, song, user_favorites, state_store)

    if data == "make_loop":
        await query.message.reply_text("🎚 Формирую луп…")
        await make_loop(update, context)
        return

    if data == "reverse_audio":
        inp = context.user_data.get('last_audio_path')
        if not inp or not os.path.exists(inp):
            return await query.message.reply_text("❌ Нет файла для переворота.")
        # создаём выходной файл
        out = tempfile.NamedTemporaryFile(dir=scratch_root(), delete=False, suffix=".mp3").name
        try:
            await asyncio.to_thread(reverse_audio, inp, out)
            checkpoint()
            with open(out, 'rb') as audio:
                await query.message.reply_audio(audio, title=tr("🔄 Ваш реверс"))
        finally:
            if os.path.exists(out):
                os.remove(out)
        context.user_data.pop("awaiting_pitch", None)
        return

    # Обработка сдвига тональности
    if query.data == "pitch_detect":
        inp = context.user_data.get('last_audio_path')
        if not inp or not os.path.exists(inp):
            await query.message.reply_text("❌ Аудио не найдено.")
            return
        context.user_data['awaiting_pitch'] = True
        await query.message.reply_text("Введите число полутонов (например 2 или -3):")
        return

    # Переход по результатам поиска
    if data.startswith("next_"):
        idx = int(data.split("_")[1])
        await send_song(update, context, idx)

        return

    elif data.startswith("prev_"):                 # Кнопка "назад"
        idx = int(data.split("_")[1])
        await send_song(update, context, idx)

        return

    # Показать текст песни
    if data.startswith("lyrics_"):
        song_id = int(data.split("_")[1])
        songs = user_search_results.get(user_id, [])
        song = next((s for s in songs if s['id'] == song_id), None)
        if not song:
            await query.message.reply_text("Песня не найдена в результатах.")
            return

        await query.message.reply_text("⏳ Загружаю текст песни...")
        lyrics = await get_lyrics(song['url'])
        if lyrics:
            if len(lyrics) > 4000:
                # Разбиваем длинные тексты на части
                for i in range(0, len(lyrics), 3900):
                    await query.message.reply_text(lyrics[i:i + 3900])
            else:
                await query.message.reply_text(lyrics)
        else:
            await query.message.reply_text("Не удалось получить текст песни.")
        return

    # Скачивание аудио
    if data.startswith("download_") or data == "recognized_download":

        # узнаём ID и объект song
        if data == "recognized_download":
            song = context.user_data.get('recognized_song')
        else:
            song_id = int(data.split("_")[1])
            songs = user_search_results.get(user_id, [])
            song = next((s for s in songs if s['id'] == song_id), None)
        if not song:
            return await query.message.reply_text("Песня не найдена. Повторите поиск.")

        return await request_library_download(update, context, song)


    if data.startswith("fav_"):
        song_id = int(data.split("_")[1])
        song = next((song for song in user_search_results.get(user_id, []) if song["id"] == song_id), None)
        if not song:
            return await query.message.reply_text("Открой поиск ещё раз.")
        from library_ui import save_song
        return await save_song(update, context, song, user_favorites, state_store)

    if data.startswith("enhance_"):

        # 1) Находим song по ID
        song_id = int(data.split("_")[1])
        songs = user_search_results.get(user_id, [])
        song = next((s for s in songs if s['id'] == song_id), None)
        if not song:
            return await query.message.reply_text("Песня не найдена. Повторите поиск.")

        if song.get("kind") == "upload":
            from uploaded_media import open_studio
            return await open_studio(update, context, song, retain_audio_source, studio_command)
        from versions import request_versions
        return await request_versions(update, context, song)

        # Применение выбранного эффекта через pydub
    if data.startswith("effect_"):
        await stage("Применяю эффект…")
        await handle_audio_enhancement(update, context)
        return

    # Переключение эффекта
    if data.startswith("toggle_"):
        effect = data.split("_",1)[1]
        if effect not in AUDIO_EFFECTS:
            return await query.message.reply_text("Неизвестный эффект.")
        sel = context.user_data.setdefault('pending_effects', [])
        if effect in sel:
            sel.remove(effect)
        else:
            sel.append(effect)
        # обновляем клавиатуру
        await query.edit_message_reply_markup(reply_markup=build_multiselect_keyboard(sel, context.user_data.get('downloaded_song'), context.user_data.get('studio_category', 'main')))
        return

    # Apply selected effects without destroying the source or leaking intermediates.
    if data == "apply_effects":
        source = context.user_data.get('last_audio_path')
        selected = list(context.user_data.get('pending_effects', []))
        if not source or not os.path.isfile(source):
            return await query.message.reply_text("Пришлите аудиофайл ещё раз: исходный файл недоступен.")
        if not selected:
            return await query.message.reply_text("Сначала выберите хотя бы один эффект.")
        await stage("Применяю эффекты…")
        with tempfile.TemporaryDirectory(dir=scratch_root(), prefix='swidj_effects_') as directory:
            current = source
            for index, name in enumerate(selected):
                output = os.path.join(directory, f'{index}.mp3')
                if not await apply_audio_effect(name, current, output):
                    return await query.message.reply_text("Не удалось применить эффект. Исходная запись сохранена; попробуйте другой вариант.")
                current = output
            checkpoint()
            from quick_studio import PRESETS
            label = next((value[0] for value in PRESETS.values() if list(value[1]) == selected), "Микс")
            song = context.user_data.get("downloaded_song") or {}
            from audio_presentation import send_music
            await send_music(context.bot, update.effective_chat.id, current,
                             (song.get("title") or "Мой трек") + " · " + tr(label), song.get("artist"), song.get("cover"))
        return

    if data == "detect_chords":
        inp = context.user_data.get('last_audio_path')
        if not inp or not os.path.exists(inp):
            return await query.message.reply_text("❌ Нет аудио для анализа.")
        key = await asyncio.to_thread(detect_key, inp)
        chords = await asyncio.to_thread(detect_chords, inp)
        checkpoint()
        await query.message.reply_text(
            f"🎼 Тональность: <b>{key}</b>\n" +
            "Аккорды:\n" + " — ".join(chords),
            parse_mode="HTML"
        )
        return

    if data.startswith("admin_"):
        if not access_policy.is_owner(update):
            await query.message.reply_text("❌ Нет доступа к панели владельца.")
            return
        state = broadcast_state.setdefault(user_id, {"text": None, "media": None, "type": None})

        if data == "admin_text":
            context.user_data["awaiting_broadcast_text"] = True
            return await query.message.reply_text("📝 Напиши текст рассылки:")

        if data in ["admin_photo", "admin_audio", "admin_video"]:
            context.user_data["awaiting_media_type"] = data.split("_")[1]
            return await query.message.reply_text(
                f"📤 Отправь {context.user_data['awaiting_media_type']} для рассылки:")

        if data == "admin_cancel":
            broadcast_state.pop(user_id, None)
            context.user_data.pop('awaiting_broadcast_text', None)
            context.user_data.pop('awaiting_media_type', None)
            return await query.message.reply_text("❌ Рассылка отменена.")

        if data == "admin_send":
            if not state.get('text') and not state.get('media'):
                return await query.message.reply_text("Сначала добавьте текст или медиа для рассылки.")
            try:
                async with aiosqlite.connect(USERS_DB_PATH) as db:
                    async with db.execute("SELECT chat_id FROM users") as cursor:
                        users = [row[0] async for row in cursor]

            except:
                users = []

            if not users:
                return await query.message.reply_text("❌ Нет пользователей.")

            text = state.get("text")
            media = state.get("media")
            media_type = state.get("type")
            success = 0

            for uid in users:
                try:
                    if media_type == "photo":
                        await context.bot.send_photo(uid, media, caption=text or "")
                    elif media_type == "audio":
                        await context.bot.send_audio(uid, media, caption=text or "")
                    elif media_type == "video":
                        await context.bot.send_video(uid, media, caption=text or "")
                    else:
                        await context.bot.send_message(uid, text)
                    await asyncio.sleep(0.1)
                    success += 1
                except Exception as e:
                    print(f"Ошибка отправки {uid}: {e}")

            await query.message.reply_text(f"📤 Разослано {success} пользователям.")
            broadcast_state.pop(user_id, None)
            return


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    await save_user(chat_id)
    history = user_search_history.get(user_id, [])
    if not history:
        await update.effective_message.reply_text("🕓 История поиска пуста.")
        return
    text = "🕓 История поиска:\n" + "\n".join(f"{i + 1}. {h[:1000]}" for i, h in enumerate(history))
    await reply_rows(update.effective_message, text.splitlines(keepends=True))


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_navigation_entry(context)
    from library_ui import show_library_home
    await show_library_home(update, context, user_favorites, state_store)


async def request_library_download(update, context, song):
    if song.get("kind") == "upload":
        from uploaded_media import send_upload
        return await send_upload(update, context, song)
    from versions import request_versions
    return await request_versions(update, context, song)


async def upload_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    identifier = update.callback_query.data.rsplit(":", 1)[-1]
    song = context.user_data.get("upload_requests", {}).get(identifier)
    if not song:
        return await update.effective_message.reply_text("Пришли этот файл снова.")
    if update.callback_query.data.startswith("upload:studio:"):
        from uploaded_media import open_studio
        return await open_studio(update, context, song, retain_audio_source, studio_command)
    from library_ui import save_song
    await save_song(update, context, song, user_favorites, state_store)


async def track_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    from track_card import selected_song, show_card
    from library_ui import collections, all_saved, save_song
    action, song = selected_song(context, update.callback_query.data)
    if not song:
        return await update.effective_message.reply_text("Открой трек ещё раз — эта карточка уже недоступна.")
    uid = update.effective_user.id
    folders = await collections(context, uid, state_store)
    current = next((item for item in all_saved(uid, user_favorites, folders) if item["id"] == song["id"]), None)
    if song.get("kind") == "upload" and current:
        song = current
    if action in ("save", "playlist"):
        if action == "playlist":
            return await save_song(update, context, song, user_favorites, state_store)
        await save_song(update, context, song, user_favorites, state_store, offer_playlist=False)
        return await show_card(update, context, song, saved=True, notice="Сохранено в Моей музыке",
                               extra_rows=[[InlineKeyboardButton("← Моя музыка", callback_data="lib:home")]])
    if song.get("kind") == "upload":
        from uploaded_media import send_upload, open_studio
        if action == "listen":
            return await send_upload(update, context, song)
        return await open_studio(update, context, song, retain_audio_source, studio_command)
    active = context.user_data.get("downloaded_song") or {}
    path = context.user_data.get("last_audio_path")
    if active.get("id") == song["id"] and path and os.path.isfile(path) and (
            "youtube.com/watch" not in str(song.get("url", "")) or song.get("url") == active.get("url")):
        if action == "studio":
            return await studio_command(update, context)
        from audio_presentation import send_music
        from track_card import card_keyboard
        result = await send_music(context.bot, update.effective_chat.id, path,
                                  active.get("title"), active.get("artist"), active.get("cover"),
                                  reply_markup=card_keyboard(context, active, saved=current is not None, delivered=True))
        from track_card import retire_download_menus
        await retire_download_menus(update,context)
        return result
    controls = context.application.bot_data.get("controls")
    if controls and not access_policy.is_owner(update) and not controls.enabled("downloads"):
        return await update.effective_message.reply_text("Этот раздел временно закрыт.")
    from versions import request_versions
    return await request_versions(update, context, song, mode="listen" if action == "listen" else "studio")


async def library_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from library_ui import handle_library
    from versions import request_versions
    await handle_library(update, context, user_favorites, persist_user_state, state_store,
                         user_search_results, send_song, request_library_download)


async def collection_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from library_ui import create_collection, show_folders
    if context.args:
        return await create_collection(update, context, state_store, " ".join(context.args), user_favorites)
    return await show_folders(update, context, state_store)



async def clearfavorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await save_user(chat_id)
    user_id = update.effective_user.id
    user_favorites[user_id] = []
    await persist_user_state(user_id)
    await update.message.reply_text("⭐️ Избранное очищено.")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await save_user(chat_id)
    await update.message.reply_text("❓ Неизвестная команда. Используй /start для помощи.")


async def whoami_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return await update.message.reply_text("Используйте /whoami в личном чате с ботом.")
    await update.message.reply_text(f"Ваш Telegram user ID: {update.effective_user.id}")


async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or not re.fullmatch(r'-?[0-9]{1,18}', context.args[0]):
        return await update.message.reply_text("Используйте /download <ID из результатов поиска>.")
    song_id = int(context.args[0])
    song = next((song for song in user_search_results.get(update.effective_user.id, []) if song['id'] == song_id), None)
    if not song:
        return await update.message.reply_text("Песня не найдена в ваших результатах. Сначала выполните поиск.")
    return await request_library_download(update, context, song)


async def versions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from versions import choose_version
    done = await choose_version(update, context, download_youtube_audio, extract_youtube_metadata,
                                retain_audio_source, studio_command)
    match = re.fullmatch(r"ver:pick:([0-9a-f]{10}):[0-4]", update.callback_query.data or "")
    request = context.user_data.get("version_requests", {}).get(match[1], {}) if match else {}
    if done is True and request.get("queue_ref"):
        from link_queue import advance
        import sys
        return await advance(update,context,request["queue_ref"],sys.modules[__name__])


import time


def safe_cleanup(path, older_than_sec=600, protected=()):
    from scratch import cleanup
    return cleanup(path, older_than_sec, protected)


from telegram.ext import CommandHandler


async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not access_policy.is_owner(update):
        return await update.effective_message.reply_text("❌ У тебя нет доступа к этой команде.")

    protected = [data.get('last_audio_path') for data in context.application.user_data.values()]
    removed = safe_cleanup(scratch_root(), protected=protected)
    await update.effective_message.reply_text(f"🧹 Удалено временных файлов старше 10 минут: {removed}.")



async def initialize_app(app):
    from state_store import migrate_users
    await asyncio.to_thread(migrate_users, 'users.db', USERS_DB_PATH)
    os.makedirs(os.path.dirname(USERS_DB_PATH) or '.', exist_ok=True)
    async with aiosqlite.connect(USERS_DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY)")
        await db.commit()
    from owner_panel import Controls
    controls = Controls(state_store)
    await controls.load()
    app.bot_data["controls"] = controls
    app.bot_data["is_owner"] = lambda update: access_policy.is_owner(update)
    app.bot_data['before_update'] = restore_session
    app.bot_data['after_update'] = save_session
    # Native composer menu and slash suggestions; no extra chat keyboard/messages.
    from telegram.error import TelegramError
    try:
        commands = [BotCommand(command, description) for command, description in NAVIGATION_COMMANDS]
        await app.bot.set_my_commands(commands)
        await app.bot.set_my_commands(commands, language_code="ru")
        from i18n_ui import english
        await app.bot.set_my_commands([BotCommand(command, english(description, protect=False)) for command, description in NAVIGATION_COMMANDS], language_code="en")
        await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Command menu configured")
    except TelegramError as exc:
        logger.warning("Command menu configuration failed (%s)", type(exc).__name__)


SESSION_KEYS = ('language', 'search_pages', 'link_queues', 'awaiting_catalog', 'ringtone_requests', 'awaiting_ringtone', 'version_requests', 'track_cards', 'upload_requests', 'search_mode', 'downloaded_song', 'dl_requests', 'recognized_song', 'last_audio_path', 'pending_effects', 'awaiting_pitch', 'dl_url',
                'dl_platform', 'awaiting_broadcast_text', 'awaiting_media_type')


async def restore_session(update, context):
    uid = update.effective_user.id
    if uid in saved_sessions:
        saved = saved_sessions.pop(uid)
        context.user_data.update({key: saved[key] for key in SESSION_KEYS if key in saved})
        for key in ('voice_update', 'audio_update'):
            if saved.get(key):
                context.user_data[key] = Update.de_json(saved[key], context.bot)


async def save_session(update, context):
    uid = update.effective_user.id
    session = {key: context.user_data[key] for key in SESSION_KEYS if key in context.user_data}
    for key in ('voice_update', 'audio_update'):
        if context.user_data.get(key):
            session[key] = context.user_data[key].to_dict()
    await asyncio.to_thread(state_store.save_named, 'sessions', uid, session)
    await asyncio.to_thread(state_store.save_named, 'search_results', uid, user_search_results.get(uid, []))
    await asyncio.to_thread(state_store.save_named, 'broadcast_drafts', uid, broadcast_state.get(uid, {}))
    # The durable session now references the new source. Only now may old bytes go.
    current = context.user_data.get('last_audio_path')
    if current:
        try:
            await asyncio.to_thread(active_media_store().prune, uid, current)
            from scratch import remove_owned_file
            for previous in context.user_data.pop('_previous_audio_paths', []):
                remove_owned_file(previous)
        except OSError as exc:
            logger.warning("Audio cleanup failed (%s)", type(exc).__name__)
    from operations import _active
    try:
        await asyncio.to_thread(active_media_store().trim_cache,
                                protected_users=set(_active) | {uid})
    except OSError as exc:
        logger.warning("Cache budget cleanup failed (%s)", type(exc).__name__)



def build_application(*, request=None, updates_request=None):
    """Build handlers independently of polling, including offline SDK validation."""
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Set TELEGRAM_TOKEN before starting the bot")
    from i18n_ui import LocalizedBot, localized_callback
    bot_options = {}
    if request is not None:
        bot_options["request"] = request
    if updates_request is not None:
        bot_options["get_updates_request"] = updates_request
    builder = ApplicationBuilder().bot(LocalizedBot(TELEGRAM_TOKEN, **bot_options)).concurrent_updates(8).post_init(initialize_app)
    app = builder.build()
    app.add_error_handler(localized_callback(error_handler))
    from operations import cancel_callback
    app.add_handler(CallbackQueryHandler(localized_callback(cancel_callback), pattern=r"^op:cancel:[0-9a-f]{12}$"))


    from catalog_links import extract_links
    class MusicLinkFilter(filters.MessageFilter):
        def filter(self, message):
            return bool(extract_links(message.text or ""))
    app.add_handler(MessageHandler(MusicLinkFilter() & (~filters.COMMAND), serialize_user(route_music_links)))
    app.add_handler(CallbackQueryHandler(localized_callback(batch_stop), pattern=r"^batch:stop:[0-9a-f]{10}$"))
    app.add_handler(CallbackQueryHandler(serialize_user(batch_callback), pattern=r"^batch:(run|skip):"))
    app.add_handler(
        CallbackQueryHandler(
            serialize_user(download_callback),
            pattern=r"^dl_(audio|video)\b"
        )
    )
    app.add_handler(
        MessageHandler(filters.VOICE, serialize_user(voice_menu))
    )
    app.add_handler(CallbackQueryHandler(serialize_user(voice_callback), pattern=r"^(voice_(effects|recognize|words|search_words|edit_words)|audio_recognize)$"))

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), serialize_user(handle_message)))

    app.add_handler(CommandHandler("start", serialize_user(start)))
    app.add_handler(CommandHandler("language", serialize_user(language_command)))
    app.add_handler(CallbackQueryHandler(serialize_user(language_callback), pattern=r"^lang:(choose|set:(ru|en))$"))
    app.add_handler(CommandHandler("menu", serialize_user(menu_command)))
    app.add_handler(CommandHandler("search", serialize_user(search_command)))
    app.add_handler(CommandHandler("studio", serialize_user(studio_command)))
    app.add_handler(CommandHandler("trim", serialize_user(trim_command)))
    app.add_handler(CallbackQueryHandler(serialize_user(quick_callback), pattern=r"^quick:"))
    app.add_handler(CallbackQueryHandler(serialize_user(studio_callback), pattern=r"^studio:(home|reset|help|trim|preview|mp3|wav|info|formats|more|group:(level|tone|color|space))$"))
    app.add_handler(CommandHandler("help", serialize_user(help_command)))
    app.add_handler(CommandHandler("cancel", localized_callback(cancel_entry)))
    app.add_handler(CallbackQueryHandler(serialize_user(menu_callback), pattern=r"^ui:(search|title|lyrics|recognize|audio|help|home|favorites|history)$"))
    app.add_handler(CommandHandler("download", serialize_user(download_command)))
    app.add_handler(CallbackQueryHandler(serialize_user(versions_callback), pattern=r"^ver:(pick|refresh|other):"))
    app.add_handler(CommandHandler("whoami", serialize_user(whoami_command)))
    app.add_handler(CommandHandler("history", serialize_user(history_command)))
    app.add_handler(CommandHandler("favorites", serialize_user(favorites_command)))
    app.add_handler(CommandHandler("collection", serialize_user(collection_command)))
    app.add_handler(CallbackQueryHandler(serialize_user(search_result_callback), pattern=r"^srch:"))
    app.add_handler(CallbackQueryHandler(serialize_user(track_callback), pattern=r"^track:"))
    app.add_handler(CallbackQueryHandler(serialize_user(library_callback), pattern=r"^lib:"))
    app.add_handler(CallbackQueryHandler(serialize_user(upload_callback), pattern=r"^upload:(save|studio):-?[0-9]{1,19}$"))
    app.add_handler(CommandHandler("clearfavorites", serialize_user(clearfavorites_command)))
    app.add_handler(CommandHandler("panel", serialize_user(admin_panel)))
    app.add_handler(CommandHandler("admin", serialize_user(admin_panel)))
    app.add_handler(CallbackQueryHandler(serialize_user(owner_callback), pattern=r"^owner:"))
    app.add_handler(CommandHandler("users", serialize_user(show_users)))
    app.add_handler(CommandHandler("cleanup", serialize_user(cleanup_command)))
    app.add_handler(
        MessageHandler(
            filters.AUDIO | filters.Document.AUDIO | filters.VOICE,
            serialize_user(handle_user_audio)
        )
    )
    app.add_handler(
        MessageHandler(
            (filters.PHOTO | filters.VIDEO | filters.AUDIO),
            serialize_user(handle_admin_media)
        )
    )
    app.add_handler(CallbackQueryHandler(serialize_user(handle_callback)))
    app.add_handler(MessageHandler(filters.COMMAND, serialize_user(unknown_command)))

    return app


def main():
    build_application().run_polling()

if __name__ == "__main__":
    main()
