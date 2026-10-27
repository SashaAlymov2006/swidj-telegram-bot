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


async def send_cached_music(bot, chat_id, source_url, title=None, artist=None, *, reply_markup=None, allow_public=True):
    """Reuse only this bot's file sent to the same private chat; no provider request."""
    from download_cache import configured
    from telegram.error import BadRequest
    try:
        bot_id=bot.id
        if type(bot_id) is not int or type(chat_id) is not int or chat_id<=0:return None
        cache=configured()
        file_id=await asyncio.to_thread(cache.telegram_get,bot_id,chat_id,source_url,allow_public=allow_public) if cache else None
        cached_info=await asyncio.to_thread(cache.telegram_info,bot_id,chat_id,source_url) if file_id else None
    except Exception:return None
    if not file_id:return None
    credit=cached_info['metadata'] if cached_info and cached_info['file_id']==file_id else {}
    title=title or credit.get('title');artist=artist or credit.get('artist')
    kwargs={'chat_id':chat_id,'audio':file_id}
    if reply_markup is not None:kwargs['reply_markup']=reply_markup
    if title:
        label,performer,_=music_labels(title,artist)
        kwargs.update(title=label,performer=performer,caption=f'🎵 <b>{escape(label)}</b>\n{escape(performer)}\n\n♪ SwiDJ',parse_mode='HTML')
    from jamendo_source import identifier,license_url as checked_license
    if identifier(credit.get('source_url')) and checked_license(credit.get('license_url')):
        kwargs['caption']=kwargs.get('caption','♪ SwiDJ')+'\n<a href="'+escape(credit['source_url'],quote=True)+'">Jamendo</a> · <a href="'+escape(checked_license(credit['license_url']),quote=True)+'">Creative Commons</a>'
        kwargs['parse_mode']='HTML'
    from audius_source import canonical as aud_url
    if aud_url(credit.get('source_url')):
        kwargs['caption']=kwargs.get('caption','♪ SwiDJ')+'\n<a href="'+escape(aud_url(credit['source_url']),quote=True)+'">Audius</a>'
        kwargs['parse_mode']='HTML'
    checkpoint()
    try:return await bot.send_audio(**kwargs)
    except BadRequest as error:
        if not any(word in str(error).lower() for word in ('file identifier','file_id','wrong remote file','file reference')):raise
        await asyncio.to_thread(cache.telegram_set,bot_id,chat_id,source_url,None)
        return None


async def send_music(bot, chat_id, path, title=None, artist=None, cover=None, *, reply_markup=None, source_url=None, license_url=None):
    known_public=False;public_copy=False;credit_url=source_url;credit_license=license_url
    if source_url:
        try:
            from download_cache import configured
            cache=configured()
            if cache:
                known_public=await asyncio.to_thread(cache.public_file,source_url)
                if known_public:public_copy=await asyncio.to_thread(cache.public_file,source_url,path)
                if public_copy:
                    provenance=await asyncio.to_thread(cache.public_metadata,source_url)
                    if provenance.get('source') in ('SoundCloud','Jamendo','Audius'):
                        credit_url=provenance.get('source_url') or source_url;credit_license=provenance.get('license_url') or license_url
        except Exception:pass
    if source_url and (not known_public or public_copy):
        reused=await send_cached_music(bot,chat_id,source_url,title,artist,reply_markup=reply_markup,allow_public=public_copy)
        if reused:return reused
    title, artist, filename, thumbnail, duration = await asyncio.to_thread(
        prepare_music, path, title, artist, cover)
    kwargs = {
        "chat_id": chat_id, "title": title, "performer": artist,
        "caption": f"🎵 <b>{escape(title)}</b>\n{escape(artist)}\n\n♪ SwiDJ",
        "parse_mode": "HTML",
    }
    from jamendo_source import identifier,license_url as checked_license
    if identifier(credit_url) and checked_license(credit_license):
        kwargs['caption']+='\n<a href="'+escape(credit_url,quote=True)+'">Jamendo</a> · <a href="'+escape(checked_license(credit_license),quote=True)+'">Creative Commons</a>'
    from audius_source import canonical as aud_url
    if aud_url(credit_url):kwargs['caption']+='\n<a href="'+escape(aud_url(credit_url),quote=True)+'">Audius</a>'
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    if thumbnail:
        kwargs["thumbnail"] = InputFile(thumbnail, filename="cover.jpg")
    if duration:
        kwargs["duration"] = duration
    checkpoint()
    with open(path, "rb") as audio:
        message=await bot.send_audio(audio=InputFile(audio, filename=filename), **kwargs)
    if source_url and (not known_public or public_copy):
        try:
            from download_cache import configured
            cache=configured()
            if cache and type(bot.id) is int and getattr(message,'audio',None) and isinstance(message.audio.file_id,str):
                source='Audius' if aud_url(credit_url) else 'Jamendo' if identifier(credit_url) else 'SoundCloud' if str(credit_url).startswith('https://soundcloud.com/') else None
                await asyncio.to_thread(cache.telegram_set,bot.id,chat_id,source_url,message.audio.file_id,metadata={'title':title,'artist':artist,'duration':duration,'source':source,'source_url':credit_url,'license_url':credit_license},public=public_copy)
        except Exception:pass
    return message
