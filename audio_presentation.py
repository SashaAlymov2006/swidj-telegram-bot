"""Music file names, embedded tags and optional provider cover art."""
import asyncio
from html import escape
import io
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse
import requests
from telegram import InputFile
from operations import checkpoint

IMAGE_HOSTS = ("ytimg.com", "ggpht.com", "genius.com", "rapgenius.com",
               "dzcdn.net", "sndcdn.com", "scdn.co", "spotifycdn.com", "mzstatic.com")


def clean_label(value, fallback, limit=128):
    value = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or ""))
    value = " ".join(value.split())
    return value[:limit].strip() or fallback


def music_labels(title, artist):
    from i18n_ui import tr
    title = clean_label(title, tr("Аудио"))
    artist = clean_label(artist, tr("Исполнитель не указан"))
    name = re.sub(r'[<>:"/\\|?*]', "", f"{artist} — {title}")[:150].strip(" .")
    return title, artist, (name or "SwiDJ") + ".mp3"


def jpeg_thumbnail(data):
    if not data or len(data) > 2 * 1024 * 1024:
        return None
    try:
        result = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
             "-i", "pipe:0", "-frames:v", "1", "-vf",
             "scale=320:320:force_original_aspect_ratio=decrease",
             "-q:v", "4", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"],
            input=data, capture_output=True, timeout=10, check=True)
        return result.stdout if 0 < len(result.stdout) < 200000 else None
    except (subprocess.SubprocessError, OSError):
        return None


def fetch_cover(url):
    if not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url or "")
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            return None
        if not any(host == suffix or host.endswith("." + suffix) for suffix in IMAGE_HOSTS):
            return None
        with requests.get(url, stream=True, allow_redirects=False, timeout=(4, 6)) as response:
            if response.status_code != 200 or not response.headers.get("Content-Type", "").lower().startswith("image/"):
                return None
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 2 * 1024 * 1024:
                    return None
        return jpeg_thumbnail(bytes(data))
    except (requests.RequestException, ValueError):
        return None


def prepare_music(path, title, artist, cover=None):
    title, artist, filename = music_labels(title, artist)
    thumbnail = fetch_cover(cover) if cover else None
    duration = None
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import TIT2, TPE1, APIC
        audio = MP3(path)
        duration = round(audio.info.length)
        if audio.tags is None:
            audio.add_tags()
        if thumbnail is None:
            pictures = audio.tags.getall("APIC")
            if pictures:
                thumbnail = jpeg_thumbnail(pictures[0].data)
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        if thumbnail:
            audio.tags.delall("APIC")
            audio.tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=thumbnail))
        audio.save(v2_version=3)
    except Exception:
        # Optional presentation must never prevent delivery of a valid provider file.
        pass
    return title, artist, filename, thumbnail, duration


async def send_music(bot, chat_id, path, title=None, artist=None, cover=None, *, reply_markup=None):
    title, artist, filename, thumbnail, duration = await asyncio.to_thread(
        prepare_music, path, title, artist, cover)
    kwargs = {
        "chat_id": chat_id, "title": title, "performer": artist,
        "caption": f"🎵 <b>{escape(title)}</b>\n{escape(artist)}\n\n♪ SwiDJ",
        "parse_mode": "HTML",
    }
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    if thumbnail:
        kwargs["thumbnail"] = InputFile(thumbnail, filename="cover.jpg")
    if duration:
        kwargs["duration"] = duration
    checkpoint()
    with open(path, "rb") as audio:
        return await bot.send_audio(audio=InputFile(audio, filename=filename), **kwargs)
