from i18n_ui import tr
"""Own audio files are saved and replayed exactly; never sent to catalog search."""
import asyncio
from contextlib import asynccontextmanager
from hashlib import sha256
from html import escape
import os
from pathlib import Path
import tempfile
from telegram import InputFile, InlineKeyboardButton as Button
from ui_layout import comfortable_keyboard as Markup
from media_store import MediaStore
from scratch import scratch_root
from operations import checkpoint


def library_store():
    active = Path(os.getenv("AUDIO_CACHE_DIR", "/app/data/audio"))
    return MediaStore(active.parent / "library")


def owned_path(value, uid, *, active=False):
    if not value:
        return None
    store = MediaStore(Path(os.getenv("AUDIO_CACHE_DIR", "/app/data/audio"))) if active else library_store()
    directory = store.user_directory(uid).resolve()
    path = Path(value)
    return path if not path.is_symlink() and path.is_file() and path.resolve().parent == directory else None


def register_upload(update, context, media, local_source=None):
    kind = "voice" if update.effective_message.voice else ("document" if update.effective_message.document else "audio")
    filename = getattr(media, "file_name", None) or (tr("Голосовое.ogg") if kind == "voice" else tr("Мой трек.mp3"))
    filename = filename.replace(chr(92), "/").rsplit("/", 1)[-1][:160]
    title = str(getattr(media, "title", None) or Path(filename).stem or "Мой трек")[:128]
    artist = str(getattr(media, "performer", None) or tr("Мои загрузки"))[:128]
    identity = f"{update.effective_user.id}:{media.file_unique_id}"
    identifier = -(10**16 + int.from_bytes(sha256(identity.encode()).digest()[:6], "big"))
    song = {"id": identifier, "title": title, "artist": artist, "kind": "upload",
            "media_kind": kind, "file_id": media.file_id, "original_filename": filename,
            "duration": getattr(media, "duration", None), "_local_source": local_source}
    if hasattr(song["duration"], "total_seconds"):
        song["duration"] = song["duration"].total_seconds()
    requests = context.user_data.setdefault("upload_requests", {})
    previous = requests.get(str(identifier), {})
    if previous.get("_library_audio"):
        song["_library_audio"] = previous["_library_audio"]
    requests[str(identifier)] = song
    while len(requests) > 20:
        requests.pop(next(iter(requests)))
    return song


@asynccontextmanager
async def source_path(update, context, song):
    uid = update.effective_user.id
    path = owned_path(song.get("_library_audio"), uid) or owned_path(song.get("_local_source"), uid, active=True)
    if path:
        yield path
        return
    if not song.get("file_id"):
        raise ValueError("Файл недоступен. Пришли его снова.")
    with tempfile.TemporaryDirectory(dir=scratch_root(), prefix="swidj_own_") as directory:
        file = await context.bot.get_file(song["file_id"])
        if getattr(file, "file_size", 0) and file.file_size > 20 * 1024 * 1024:
            raise ValueError("Для сохранения пришли файл до 20 МБ.")
        path = Path(directory) / "source.audio"
        await file.download_to_drive(path)
        if not 0 < path.stat().st_size <= 20 * 1024 * 1024:
            raise ValueError("Для сохранения пришли файл до 20 МБ.")
        checkpoint()
        yield path


async def retain_upload(update, context, song):
    song = dict(song)
    uid = update.effective_user.id
    if not owned_path(song.get("_library_audio"), uid):
        async with source_path(update, context, song) as path:
            song["_library_audio"] = await asyncio.to_thread(library_store().retain, uid, path)
    song.pop("_local_source", None)
    context.user_data.setdefault("upload_requests", {})[str(song["id"])] = song
    if context.user_data.get("downloaded_song", {}).get("id") == song["id"]:
        context.user_data["downloaded_song"] = dict(song)
    return song


async def send_upload(update, context, song):
    async with source_path(update, context, song) as path:
        checkpoint()
        caption = f"🎵 <b>{escape(song['title'])}</b>\n{escape(song['artist'])}"
        with open(path, "rb") as audio:
            item = InputFile(audio, filename=song.get("original_filename") or "Мой трек.mp3")
            kwargs = {"chat_id": update.effective_chat.id, "caption": caption, "parse_mode": "HTML"}
            from track_card import card_keyboard
            kwargs["reply_markup"] = card_keyboard(context, song, delivered=True)
            kind = song.get("media_kind", "audio")
            if kind == "voice":
                result = await context.bot.send_voice(voice=item, **kwargs)
            elif kind == "document":
                result = await context.bot.send_document(document=item, **kwargs)
            else:
                result = await context.bot.send_audio(audio=item, title=song["title"], performer=song["artist"], **kwargs)
            if update.callback_query and update.callback_query.data.startswith("track:listen:"):
                from track_card import retire_download_menus
                await retire_download_menus(update,context)
            return result


async def open_studio(update, context, song, retain, studio):
    async with source_path(update, context, song) as path:
        await retain(context, update.effective_user.id, path)
    context.user_data["downloaded_song"] = dict(song)
    context.user_data["pending_effects"] = []
    await studio(update, context)


async def show_card(update, song, context):
    from track_card import show_card as show_track_card
    return await show_track_card(update, context, song, saved=True,
        extra_rows=[[Button("← Моя музыка", callback_data="lib:home")]])
